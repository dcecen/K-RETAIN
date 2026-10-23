"""Calcul pseudo-3D phasé : paroi en plaque (grillage) sur ressorts élasto-plastiques.

Le sol reste en ressorts, avec exactement la même loi et le même phasage que le
calcul 2D (sout.noyau.phasage) : chaque ligne verticale du grillage porte les
ressorts de la section 2D, multipliés par sa largeur tributaire, avec sa propre
mémoire d'état. Les appuis deviennent ponctuels, répartis à leur espacement le
long de la paroi (raideur et précharge 2D × espacement).

Conditions aux extrémités : libres, appuyées (w = 0 et rotation le long du bord
nulle) ou encastrées (w = 0, les deux rotations nulles).
Angle de fouille au milieu de la paroi : les deux parois se tiennent mutuellement
dans leur plan, d'où w = 0 sur la ligne d'angle (parois supposées indéformables
dans leur plan). Seule la présence d'un angle compte : sa valeur n'intervient pas,
et la continuité du ferraillage d'angle (encastrement partiel) est négligée.

Efforts restitués par phase : déplacement W, moments Mz (vertical) et Ms (horizontal)
du grillage, torsion Mzs, effort tranchant V par la statique de chaque ligne verticale
(charges du sol, de l'eau, des appuis et forces de transfert de la plaque, voir
plaque.efforts_lignes), réactions des lignes pénalisées (bords, angle) et bilan
d'équilibre global.
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
    appuis: list = field(default_factory=list)  # [{"nom", "s", "effort", "actif", "espacement", "angle"}] kN par appui
    V: np.ndarray = field(default_factory=lambda: np.zeros((0, 0)))    # kN/m aux nœuds (ns, nz)
    V_diag: np.ndarray = field(default_factory=lambda: np.zeros((0, 0)))   # kN/m, 2 points par élément
    M_stat: np.ndarray = field(default_factory=lambda: np.zeros((0, 0)))   # kN·m/m par la statique, 2 points par élément
    z_diag: np.ndarray = field(default_factory=lambda: np.zeros(0))
    Mzs: np.ndarray = field(default_factory=lambda: np.zeros((0, 0)))  # kN·m/m, torsion
    p: np.ndarray = field(default_factory=lambda: np.zeros(0))         # kPa, pression de chaque ressort
    reactions: np.ndarray = field(default_factory=lambda: np.zeros((0, 0)))  # kN par nœud pénalisé (bords, angle), positif = retient
    forces: dict = field(default_factory=dict)   # {"sol", "eau", "appuis", "reactions"} : kN par nœud (ns, nz), positifs vers la fouille
    bilan: dict = field(default_factory=dict)    # sommes (kN) et moments résiduels (kN·m)


@dataclass
class ResultatPseudo3D:
    s: np.ndarray
    z: np.ndarray
    phases: list[PhasePseudo3D]
    avertissements: list[str]


class MoteurPseudo3D:
    def __init__(self, modele: Modele, longueur: float, pas_horizontal: float = 0.5, bords: str = "libres",
                 angle: float | None = None, rigidite_horizontale: float | None = None,
                 largeur_appui: float | None = None, rapport_rigidite_horizontale: float | None = None,
                 torsion: float | None = None, longueur_panneau: float | None = None,
                 origine_panneaux: float = 0.0):
        self.m = modele
        self.largeur_appui = largeur_appui
        self.m2 = MoteurPhases(modele)
        self.z = self.m2.z
        nz = len(self.z)
        ns = max(3, int(round(longueur / pas_horizontal)) + 1)
        self.s = np.linspace(0.0, longueur, ns)
        self.ns, self.nz = ns, nz
        self.avertissements = list(self.m2.avertissements)
        self.Dz = self.m2.EI_elem
        # Rigidité horizontale : valeur du script > rapport du script > défaut du type de paroi
        # (sout.parois.construction.rigidite_horizontale) > isotropie avec avertissement.
        defaut = modele.ecran.infos.get("rigidite_horizontale") or {}
        if rigidite_horizontale is not None:
            self.Ds = np.full_like(self.Dz, float(rigidite_horizontale))
            source = f"Ds = {rigidite_horizontale:g} kN·m²/m imposé par le script"
        elif rapport_rigidite_horizontale is not None:
            self.Ds = float(rapport_rigidite_horizontale) * self.Dz
            source = f"Ds = {rapport_rigidite_horizontale:g}·Dz imposé par le script"
        elif defaut.get("rapport") is not None:
            self.Ds = float(defaut["rapport"]) * self.Dz
            source = f"Ds = {defaut['rapport']:g}·Dz, {defaut['source']}"
            if defaut.get("avertissement"):
                self.avertissements.append(defaut["avertissement"])
        else:
            self.Ds = self.Dz.copy()
            source = "Ds = Dz, plaque isotrope par défaut"
            self.avertissements.append(
                "Pseudo-3D : rigidité horizontale non donnée, plaque isotrope (Ds = Dz). Pour des palplanches, "
                "des pieux disjoints ou une paroi moulée à joints, donnez pseudo3d.rigidite_horizontale.")
        if 0.0 < float(self.Ds.max()) < 1e-6 * float(self.Dz.max()):
            self.avertissements.append(
                "Pseudo-3D : rigidité horizontale inférieure à 1e-6·Dz, arrondie à 0 (conditionnement numérique).")
            self.Ds = np.zeros_like(self.Dz)
        self.Ds_nulle = bool(float(self.Ds.max()) <= 0.0)
        self.GJ = np.sqrt(self.Ds * self.Dz) if torsion is None else np.full_like(self.Dz, float(torsion))
        self.avertissements.append(
            f"Pseudo-3D : rigidité horizontale {source} ; torsion GJ = "
            + ("√(Ds·Dz) (plaque de Huber, ν = 0)" if torsion is None else f"{torsion:g} kN·m²/m imposée") + ".")
        # Joints de panneaux : aucun moment ni torsion horizontaux à travers l'élément qui porte le joint
        self.coef_h = None
        self.joints: list[float] = []
        if longueur_panneau is not None and longueur_panneau < longueur - 1e-9:
            if longueur_panneau < 2 * pas_horizontal:
                raise ErreurModele(f"pseudo3d : longueur_panneau ({longueur_panneau} m) doit valoir au moins deux fois "
                                   f"pas_horizontal ({pas_horizontal} m)")
            x = float(origine_panneaux)
            while x < longueur - 1e-9:
                if x > 1e-9:
                    self.joints.append(x)
                x += longueur_panneau
            self.coef_h = np.ones((ns - 1, nz))
            for x in self.joints:
                i = min(int(np.searchsorted(self.s, x + 1e-9) - 1), ns - 2)
                self.coef_h[max(i, 0), :] = 0.0
            self.avertissements.append(
                f"Pseudo-3D : joints de panneaux en s = {', '.join(f'{x:g}' for x in self.joints)} m : "
                "aucun moment horizontal ni torsion transmis (panneaux indépendants en flexion horizontale).")
        K = plaque.assembler(self.s, self.z, self.Dz, self.Ds, coef_h=self.coef_h, GJ_elem=self.GJ)
        # Grillage réduit à la flexion verticale (forces de transfert, voir plaque.forces_transfert)
        self.K_v = plaque.assembler(self.s, self.z, self.Dz, np.zeros_like(self.Ds), GJ_elem=np.zeros_like(self.Dz))
        # Conditions aux limites par pénalité
        self.pen = 1e4 * float(K.diagonal().max())
        diag = np.zeros(K.shape[0])
        if self.Ds_nulle:
            # Sans flexion horizontale, θs n'est tenu que par la torsion des poutres verticales, qui
            # laisse libre la rotation d'ensemble de chaque ligne : θs est bloqué (bandes indépendantes).
            diag[2::3] = self.pen
        if bords in ("appuyes", "encastres"):
            for i in (0, ns - 1):
                for j in range(nz):
                    k = i * nz + j
                    diag[3 * k] = self.pen          # w = 0
                    diag[3 * k + 1] = self.pen      # θz = 0 : w nul tout le long du bord ⇒ pente tangente nulle
                    if bords == "encastres":
                        diag[3 * k + 2] = self.pen  # θs = 0 : rotation normale au bord bloquée
        self.i_angle = None
        if angle is not None and abs(angle - 180.0) > 1e-6:
            self.i_angle = int(np.argmin(np.abs(self.s - longueur / 2)))
            for j in range(nz):
                diag[3 * (self.i_angle * nz + j)] = self.pen
        self.ddl_pen_w = np.flatnonzero(diag[0::3] > 0)   # nœuds dont w est pénalisé (réactions)
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
        if largeur_appui is None and modele.appuis:
            self.avertissements.append(
                "Pseudo-3D : chaque appui ponctuel agit sur un seul nœud ; le moment horizontal Ms et l'effort "
                "tranchant V à son droit dépendent du maillage (singularité d'une charge concentrée sur une plaque). "
                "Donnez pseudo3d.largeur_appui (plaque d'appui, semelle de lierne) pour le répartir.")

    def _noeuds_appui(self, sp: float) -> list[tuple[int, float]]:
        """Nœuds (indice i, part) portant un appui placé en s = sp : le plus proche, ou, avec
        largeur_appui, chaque nœud au prorata du recouvrement de sa bande tributaire
        [milieu avec le voisin de gauche, milieu avec le voisin de droite] par l'intervalle
        [sp − largeur/2, sp + largeur/2] (répartition uniforme exacte sur la largeur)."""
        if self.largeur_appui is not None:
            bords = np.concatenate([[self.s[0]], 0.5 * (self.s[1:] + self.s[:-1]), [self.s[-1]]])
            lo, hi = sp - self.largeur_appui / 2, sp + self.largeur_appui / 2
            rec = np.clip(np.minimum(bords[1:], hi) - np.maximum(bords[:-1], lo), 0.0, None)
            if rec.sum() > 1e-12:
                sel = np.flatnonzero(rec > 1e-12)
                return [(int(i), float(rec[i] / rec.sum())) for i in sel]
        return [(int(np.argmin(np.abs(self.s - sp))), 1.0)]

    def _positions_appui(self, espacement: float) -> np.ndarray:
        """Appuis réels à leur espacement exact, centrés sur la longueur modélisée."""
        L = self.s[-1]
        nb = max(1, int(np.floor(L / espacement + 1e-9)))
        debut = (L - (nb - 1) * espacement) / 2
        return debut + espacement * np.arange(nb)

    # ------------------------------------------------------------------
    def _efforts_phase(self, u: np.ndarray, r: Ressorts, appuis: Appuis, f_ext: np.ndarray,
                       u_am: np.ndarray, u_av: np.ndarray) -> dict:
        """Champs d'efforts d'une phase résolue : moments du grillage, torsion, V par la statique
        de chaque ligne (plaque.efforts_lignes), réactions, forces nodales et bilan d'équilibre."""
        m2, ns, nz = self.m2, self.ns, self.nz
        W = u[0::3]
        Mz, Ms = plaque.moments(self.s, self.z, self.Dz, self.Ds, u, coef_h=self.coef_h)
        Mzs = plaque.torsion(self.s, self.z, self.Dz, self.Ds, u, GJ_elem=self.GJ)
        p, _ = r.pressions(W)
        nd, m2n = m2.nd, self.m2_taille
        A, P = r.A.reshape(ns, m2n), p.reshape(ns, m2n)
        # charge nette sol + eau de chaque demi-maille, par mètre de paroi (comme en 2D)
        q_lignes = (A[:, :nd] * P[:, :nd] - A[:, nd:] * P[:, nd:]) / (m2.d_L[None, :] * self.ds[:, None]) \
            + (u_am - u_av)[None, :]
        eff, _ = appuis.efforts(W)
        f_app = -np.bincount(appuis.noeud, weights=eff, minlength=ns * nz) if len(appuis) else np.zeros(ns * nz)
        t_w, t_th = plaque.forces_transfert(self.K, self.K_v, u, ns, nz)
        z_diag, M_stat, V_diag = plaque.efforts_lignes(self.z, m2.d_zb, m2.d_zh, m2.d_noeud, q_lignes,
                                                       f_app.reshape(ns, nz), t_w, t_th, self.ds)
        V = np.empty((ns, nz))
        V[:, 0], V[:, -1] = V_diag[:, 0], V_diag[:, -1]
        V[:, 1:-1] = 0.5 * (V_diag[:, 1:-2:2] + V_diag[:, 2:-1:2])
        reactions = np.zeros(ns * nz)
        reactions[self.ddl_pen_w] = self.pen * W[self.ddl_pen_w]
        f_sol = np.bincount(r.noeud, weights=-r.s * r.A * p, minlength=ns * nz)
        f_eau = f_ext[0::3]
        forces = {"sol": f_sol.reshape(ns, nz), "eau": f_eau.reshape(ns, nz), "appuis": f_app.reshape(ns, nz),
                  "reactions": (-reactions).reshape(ns, nz)}
        total = f_sol + f_eau + f_app - reactions
        Z = np.tile(self.z - self.z[0], ns)
        S = np.repeat(self.s, nz)
        bilan = {"sol": float(f_sol.sum()), "eau": float(f_eau.sum()), "appuis": float(f_app.sum()),
                 "reactions": float(-reactions.sum()), "residu": float(total.sum()),
                 "moment_residu_z": float((total * Z).sum()), "moment_residu_s": float((total * S).sum()),
                 "echelle": float(np.abs(f_sol).sum() + np.abs(f_eau).sum() + np.abs(f_app).sum() + np.abs(reactions).sum())}
        return {"W": W.reshape(ns, nz), "Mz": Mz, "Ms": Ms, "Mzs": Mzs, "V": V, "V_diag": V_diag, "M_stat": M_stat,
                "z_diag": z_diag, "p": p, "reactions": reactions.reshape(ns, nz), "forces": forces, "bilan": bilan}

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
        signales: set[str] = set()

        def _points(nom: str, W: np.ndarray, raideur: float, F0: float) -> list:
            d = m.appuis[nom]
            e = d.infos.get("espacement", 1.0) or 1.0
            j = int(np.argmin(np.abs(self.z - d.cote)))
            pts = []
            for sp in self._positions_appui(e):
                for i, part in self._noeuds_appui(sp):
                    if self.i_angle is not None and i == self.i_angle and nom not in signales:
                        signales.add(nom)
                        self.avertissements.append(
                            f"Pseudo-3D : un point de l'appui {nom} tombe sur la ligne d'angle (s = {self.s[i]:.1f} m), "
                            "où le déplacement est nul : il ne porte rien.")
                    k = i * nz + j
                    pts.append((k, float(sp), float(W[k]), raideur * e * part, F0 * e * part))
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
            champs = self._efforts_phase(u, r, appuis, f_ext, u_am, u_av)
            r.memoriser(W)
            sv_prec, present_prec = sol3["sv"], sol3["present"]
            f_ext_prec = f_ext
            eff, actif = appuis.efforts(W)
            groupes: dict[tuple[str, float], list] = {}   # un appui réel = ses nœuds porteurs
            for nm, sp, ef, ac in zip(noms, ss, eff, actif):
                g = groupes.setdefault((nm, sp), [0.0, False])
                g[0] += float(ef); g[1] = g[1] or bool(ac)
            sorties.append(PhasePseudo3D(
                ph.nom, True, "",
                appuis=[{"nom": nm, "s": sp, "effort": g[0], "actif": g[1],
                         "espacement": float(m.appuis[nm].infos.get("espacement", 1.0) or 1.0),
                         "angle": float(m.appuis[nm].infos.get("angle", 0.0) or 0.0)}
                        for (nm, sp), g in groupes.items()],
                **champs))
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
    paroi = ex.script.paroi
    return MoteurPseudo3D(ex.modele, p.longueur, p.pas_horizontal, p.bords, p.angle, p.rigidite_horizontale,
                          p.largeur_appui, p.rapport_rigidite_horizontale, p.torsion,
                          paroi.longueur_panneau, paroi.origine_panneaux).calculer()


def _sous_echantillon(n: int, max_n: int) -> np.ndarray:
    return np.unique(np.linspace(0, n - 1, min(n, max_n)).round().astype(int))


def serialiser(res: ResultatPseudo3D, res2d=None) -> dict:
    js = _sous_echantillon(len(res.z), 90)
    phases2d = {p.nom: p for p in res2d.phases} if res2d is not None else {}
    phases = []
    for ph in res.phases:
        d = {"nom": ph.nom, "ok": ph.ok, "message": ph.message}
        if ph.ok:
            lignes = np.flatnonzero(np.abs(ph.reactions).sum(axis=1) > 0)
            d.update({
                "y_mm": (ph.W[:, js] * 1e3).round(3).tolist(),
                "M": ph.Mz[:, js].round(2).tolist(),
                "Ms": ph.Ms[:, js].round(2).tolist(),
                "V": ph.V[:, js].round(2).tolist(),
                "y_max_mm": float(np.abs(ph.W).max() * 1e3),
                "Mz_max": float(ph.Mz.max()), "Mz_min": float(ph.Mz.min()),
                "Ms_absmax": float(np.abs(ph.Ms).max()),
                "V_absmax": float(np.abs(ph.V_diag).max()),
                "Mzs_absmax": float(np.abs(ph.Mzs).max()),
                "appuis": ph.appuis,
                "reactions": {"s": res.s[lignes].round(3).tolist(),
                              "total_kN": ph.reactions[lignes].sum(axis=1).round(2).tolist()},
                "bilan": {k: round(v, 4) for k, v in ph.bilan.items()},
            })
            p2 = phases2d.get(ph.nom)
            if p2 is not None and p2.ok:
                d["y_max_2d_mm"] = float(np.abs(p2.y).max() * 1e3)
        phases.append(d)
    return {"s": res.s.round(4).tolist(), "z": res.z[js].round(4).tolist(), "phases": phases,
            "avertissements": res.avertissements}


def champ_pour_maquette(ex) -> dict:
    """Champ pseudo-3D au format attendu par la maquette (abscisse s le long du contour)."""
    return serialiser(depuis_script(ex))
