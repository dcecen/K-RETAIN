"""Calcul pseudo-3D phasé : paroi en plaque (grillage) sur ressorts élasto-plastiques.

Le sol reste en ressorts, avec exactement la même loi et le même phasage que le
calcul 2D (sout.noyau.phasage) : chaque ligne verticale du grillage porte les
ressorts de la section 2D, multipliés par sa largeur tributaire, avec sa propre
mémoire d'état. Les appuis deviennent ponctuels, répartis à leur espacement le
long de la paroi (raideur et précharge 2D × espacement).

Conditions aux extrémités : libres, appuyées (w = 0) ou encastrées (w = 0, θs = 0).
Angle de fouille au milieu de la paroi : les deux parois se tiennent mutuellement
dans leur plan, d'où w = 0 sur la ligne d'angle (parois supposées indéformables
dans leur plan).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import sparse

from ..noyau.modele import Modele, Phase
from ..noyau.phasage import ErreurModele, MoteurPhases
from ..noyau.ressorts import Ressorts
from ..noyau.solveur import Appuis, RuptureEquilibre, resoudre_general
from . import plaque


@dataclass
class PhasePseudo3D:
    nom: str
    ok: bool
    message: str
    W: np.ndarray = field(default_factory=lambda: np.zeros((0, 0)))    # m, (ns, nz)
    Mz: np.ndarray = field(default_factory=lambda: np.zeros((0, 0)))   # kN·m/m
    Ms: np.ndarray = field(default_factory=lambda: np.zeros((0, 0)))   # kN·m/m
    appuis: list = field(default_factory=list)  # [{"nom", "s", "effort"}] kN par appui


@dataclass
class ResultatPseudo3D:
    s: np.ndarray
    z: np.ndarray
    phases: list[PhasePseudo3D]
    avertissements: list[str]


class MoteurPseudo3D:
    def __init__(self, modele: Modele, longueur: float, pas_horizontal: float = 0.5, bords: str = "libres",
                 angle: float | None = None, rigidite_horizontale: float | None = None):
        self.m = modele
        self.m2 = MoteurPhases(modele)
        self.z = self.m2.z
        nz = len(self.z)
        ns = max(3, int(round(longueur / pas_horizontal)) + 1)
        self.s = np.linspace(0.0, longueur, ns)
        self.ns, self.nz = ns, nz
        self.avertissements = list(self.m2.avertissements)
        self.Dz = self.m2.EI_elem
        if rigidite_horizontale is None:
            self.Ds = self.Dz.copy()
            self.avertissements.append(
                "Pseudo-3D : rigidité horizontale non donnée, plaque isotrope (Ds = Dz). Pour des palplanches, "
                "des pieux disjoints ou une paroi moulée à joints, donnez pseudo3d.rigidite_horizontale.")
        else:
            self.Ds = np.full_like(self.Dz, rigidite_horizontale)
        K = plaque.assembler(self.s, self.z, self.Dz, self.Ds)
        # Conditions aux limites par pénalité
        pen = 1e4 * float(K.diagonal().max())
        diag = np.zeros(K.shape[0])
        lignes = []
        if bords in ("appuyes", "encastres"):
            lignes += [0, ns - 1]
        for i in (0, ns - 1) if bords in ("appuyes", "encastres") else ():
            for j in range(nz):
                k = i * nz + j
                diag[3 * k] = pen
                if bords == "encastres":
                    diag[3 * k + 2] = pen
        self.i_angle = None
        if angle is not None and abs(angle - 180.0) > 1e-6:
            self.i_angle = int(np.argmin(np.abs(self.s - longueur / 2)))
            for j in range(nz):
                diag[3 * (self.i_angle * nz + j)] = pen
        self.K = (K + sparse.diags(diag)).tocsc()
        self.ddl_w = np.arange(0, 3 * ns * nz, 3)
        # Ressorts : les demi-mailles 2D de chaque ligne verticale
        r2 = self.m2.ressorts
        m2 = len(r2)
        self.ds = plaque.largeurs_tributaires(self.s)
        self.ressorts = Ressorts(
            noeud=np.concatenate([i * nz + r2.noeud for i in range(ns)]),
            s=np.tile(r2.s, ns), A=np.zeros(ns * m2), kh=np.zeros(ns * m2),
            p_ref=np.zeros(ns * m2), y_ref=np.zeros(ns * m2), pa=np.zeros(ns * m2), pp=np.zeros(ns * m2),
        )
        self.largeur = np.repeat(self.ds, m2)
        self.m2_taille = m2

    def _positions_appui(self, espacement: float) -> np.ndarray:
        """Appuis réels à leur espacement exact, centrés sur la longueur modélisée."""
        L = self.s[-1]
        nb = max(1, int(np.floor(L / espacement + 1e-9)))
        debut = (L - (nb - 1) * espacement) / 2
        return debut + espacement * np.arange(nb)

    def calculer(self) -> ResultatPseudo3D:
        m, m2 = self.m, self.m2
        ns, nz = self.ns, self.nz
        etat = m2.etat_chantier_initial()
        r = self.ressorts
        u = np.zeros(3 * ns * nz)
        sv_prec = np.zeros(ns * self.m2_taille)
        present_prec = np.zeros(ns * self.m2_taille, dtype=bool)
        poses: dict[str, list] = {}   # nom -> [(nœud, s, y_pose, k, F0)]
        f_ext_prec = np.zeros_like(u)  # forces imposées (eau) de la dernière phase calculée
        sorties: list[PhasePseudo3D] = []

        def _points(nom: str, W: np.ndarray, raideur: float, F0: float) -> list:
            d = m.appuis[nom]
            e = d.infos.get("espacement", 1.0) or 1.0
            j = int(np.argmin(np.abs(self.z - d.cote)))
            pts = []
            for sp in self._positions_appui(e):
                i = int(np.argmin(np.abs(self.s - sp)))
                k = i * nz + j
                pts.append((k, float(self.s[i]), float(W[k]), raideur * e, F0 * e))
            return pts

        def _appuis(dico: dict[str, list]) -> tuple[Appuis, list]:
            noms, noeuds, ks, F0s, yps, unis, ss = [], [], [], [], [], [], []
            for nom, pts in dico.items():
                for (k, sp, yp, kk, F0) in pts:
                    noms.append(nom); noeuds.append(k); ks.append(kk); F0s.append(F0); yps.append(yp)
                    unis.append(m.appuis[nom].unilateral); ss.append(sp)
            return Appuis(nom=noms, noeud=np.array(noeuds, dtype=int), k=np.array(ks, float),
                          F0=np.array(F0s, float), y_pose=np.array(yps, float), unilateral=np.array(unis, bool)), ss

        for ph in [Phase(nom="État initial")] + chaine_principale(m.phases):
            try:
                poser, deposer = m2.appliquer_actions(etat, ph)
            except ErreurModele as e:
                sorties.append(PhasePseudo3D(ph.nom, False, f"Erreur de données : {e}"))
                break
            for nom in deposer:
                poses.pop(nom, None)
            # Mise en charge au vérin des appuis précontraints (même règle que le 2D, voir
            # sout.noyau.phasage) : force F0 seule sur l'état précédent, puis ressort bloqué.
            a_verin = [nm for nm in poser if m.appuis[nm].precharge != 0.0]
            if a_verin:
                W = u[0::3]
                dico = dict(poses)
                for nm in a_verin:
                    dico[nm] = _points(nm, W, 0.0, m.appuis[nm].precharge)
                appuis_v, _ = _appuis(dico)
                try:
                    u, _, _ = resoudre_general(self.K, self.ddl_w, r, appuis_v, f_ext_prec, u0=u, y_rupture=m.y_rupture)
                except RuptureEquilibre as e:
                    sorties.append(PhasePseudo3D(ph.nom, False, f"Rupture à la mise en charge des appuis : {e}"))
                    break
                r.memoriser(u[0::3])
            W = u[0::3]
            for nom in poser:
                d = m.appuis[nom]
                poses[nom] = _points(nom, W, d.raideur, d.precharge)
            sol = m2.etat_sol(etat)
            sol3 = {c: (np.tile(v, ns) if isinstance(v, np.ndarray) else v) for c, v in sol.items()}
            MoteurPhases.mettre_a_jour_ressorts(r, sol3, u[0::3][r.noeud], present_prec, sv_prec, self.largeur)
            u_am, u_av = m2.pressions_eau(etat)
            f_ligne = m2.force_eau_noeuds(u_am, u_av)
            f_ext = np.zeros_like(u)
            f_ext[0::3] = np.outer(self.ds, f_ligne).ravel()
            appuis, ss = _appuis(poses)
            noms = list(appuis.nom)
            try:
                u, it, nR = resoudre_general(self.K, self.ddl_w, r, appuis, f_ext, u0=u, y_rupture=m.y_rupture)
            except RuptureEquilibre as e:
                sorties.append(PhasePseudo3D(ph.nom, False, f"Rupture : {e}"))
                break
            W = u[0::3]
            r.memoriser(W)
            sv_prec, present_prec = sol3["sv"], sol3["present"]
            f_ext_prec = f_ext
            Mz, Ms = plaque.moments(self.s, self.z, self.Dz, self.Ds, u)
            eff, actif = appuis.efforts(W)
            sorties.append(PhasePseudo3D(
                ph.nom, True, "", W=W.reshape(ns, nz), Mz=Mz, Ms=Ms,
                appuis=[{"nom": nm, "s": sp, "effort": float(ef), "actif": bool(ac)}
                        for nm, sp, ef, ac in zip(noms, ss, eff, actif)]))
        return ResultatPseudo3D(self.s, self.z, sorties, self.avertissements)


def chaine_principale(phases: list) -> list:
    """Phases de la branche menant à la dernière phase de la liste (le pseudo-3D est linéaire)."""
    noms = [p.nom for p in phases]
    chaine = []
    k = len(phases) - 1
    while k >= 0:
        chaine.append(phases[k])
        p = phases[k]
        k = noms.index(p.depuis) if (p.depuis is not None and p.depuis in noms[:k]) else k - 1
    return chaine[::-1]


def depuis_script(ex) -> ResultatPseudo3D:
    p = ex.script.pseudo3d
    if p is None:
        raise ErreurModele("mode pseudo3d : bloc pseudo3d (longueur, pas_horizontal, bords) obligatoire")
    return MoteurPseudo3D(ex.modele, p.longueur, p.pas_horizontal, p.bords, p.angle, p.rigidite_horizontale).calculer()


def _sous_echantillon(n: int, max_n: int) -> np.ndarray:
    return np.unique(np.linspace(0, n - 1, min(n, max_n)).round().astype(int))


def serialiser(res: ResultatPseudo3D, res2d=None) -> dict:
    js = _sous_echantillon(len(res.z), 90)
    phases = []
    for k, ph in enumerate(res.phases):
        d = {"nom": ph.nom, "ok": ph.ok, "message": ph.message}
        if ph.ok:
            d.update({
                "y_mm": (ph.W[:, js] * 1e3).round(3).tolist(),
                "M": ph.Mz[:, js].round(2).tolist(),
                "Ms": ph.Ms[:, js].round(2).tolist(),
                "y_max_mm": float(np.abs(ph.W).max() * 1e3),
                "Mz_max": float(ph.Mz.max()), "Mz_min": float(ph.Mz.min()),
                "Ms_absmax": float(np.abs(ph.Ms).max()),
                "appuis": ph.appuis,
            })
            if res2d is not None and k < len(res2d.phases) and res2d.phases[k].ok:
                d["y_max_2d_mm"] = float(np.abs(res2d.phases[k].y).max() * 1e3)
        phases.append(d)
    return {"s": res.s.round(4).tolist(), "z": res.z[js].round(4).tolist(), "phases": phases,
            "avertissements": res.avertissements}


def champ_pour_maquette(ex) -> dict:
    """Champ pseudo-3D au format attendu par la maquette (abscisse s le long du contour)."""
    return serialiser(depuis_script(ex))
