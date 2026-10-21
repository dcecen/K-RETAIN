"""Calcul phasé d'un écran sur ressorts élasto-plastiques.

Chaque phase part de l'état de la précédente : déplacements, état des
ressorts (droite élastique mémorisée), appuis posés avec le déplacement
atteint à leur pose.

Hypothèses de modélisation (principe de RIDO et K-Réa, à valider sur les cas
de référence, voir Delattre 2001, BLPC 234) :
- état initial : pression au repos p0 = K0·σ'v des deux côtés, y = 0 ;
- une variation Δσ'v (excavation, remblai, nappe, surcharge) décale la
  pression de référence de Kd·Δσ'v, Kd = coefficient de décharge de la couche
  (par défaut K0), puis la pression est ramenée entre pa et pp ;
- un sol mis en place (remblai) démarre au repos contre l'écran déplacé ;
- un appui ne reprend que les déplacements postérieurs à sa pose, plus sa
  précharge (ou précontrainte) F0 ;
- eau : pressions hydrostatiques amont et aval appliquées sur toute la
  largeur de l'écran.

Chaque ressort représente une demi-maille de sol d'un côté de l'écran ; sa
pression est évaluée au milieu de la demi-maille (intégration exacte d'une
pression linéaire) et reportée au nœud.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..sol import coefficients as coef
from ..sol import kerisel_absi
from ..sol.couches import Couche, contraintes_verticales, indice_couche, trier
from ..sol.kh import em_depuis_cpt, kh_schmitt
from ..sol.surcharges import Surcharge, delta_sigma_v
from .modele import Modele, Phase
from .poutre import maillage
from .ressorts import AMONT, AVAL, Ressorts
from .solveur import Appuis, RuptureEquilibre, resoudre


class ErreurModele(Exception):
    """Donnée incohérente ou manquante dans le modèle."""


@dataclass
class ResultatPhase:
    nom: str
    ok: bool
    message: str
    terrain_amont: float
    terrain_aval: float
    eau_amont: float | None
    eau_aval: float | None
    z: np.ndarray = field(default_factory=lambda: np.zeros(0))
    y: np.ndarray = field(default_factory=lambda: np.zeros(0))          # m
    z_diag: np.ndarray = field(default_factory=lambda: np.zeros(0))
    M: np.ndarray = field(default_factory=lambda: np.zeros(0))          # kN·m/m
    V: np.ndarray = field(default_factory=lambda: np.zeros(0))          # kN/m
    pressions: dict = field(default_factory=dict)   # {"amont": {...}, "aval": {...}}
    eau: dict = field(default_factory=dict)         # {"z", "u_amont", "u_aval"}
    appuis: list = field(default_factory=list)      # [{"nom", "cote", "effort", "actif"}]
    iterations: int = 0


@dataclass
class ResultatCalcul:
    phases: list[ResultatPhase]
    z: np.ndarray
    avertissements: list[str] = field(default_factory=list)

    @property
    def complet(self) -> bool:
        return all(p.ok for p in self.phases)


def _coefficients_couche(c: Couche, methode: str) -> tuple[float, float, float, float, float, float]:
    """(Kah, Kph, K0, terme cohésion poussée, terme cohésion butée, Kd)."""
    da = c.delta_a_sur_phi * c.phi
    dp = c.delta_p_sur_phi * c.phi
    if methode == "coulomb":
        k_ah, k_ph = coef.kah(c.phi, da), coef.kph(c.phi, dp)
    elif methode == "kerisel_absi":
        k_ah, k_ph = kerisel_absi.kah(c.phi, c.delta_a_sur_phi), kerisel_absi.kph(c.phi, c.delta_p_sur_phi)
    else:
        raise ErreurModele(f"méthode de coefficients inconnue : {methode}")
    k0 = c.K0 if c.K0 is not None else coef.k0_jaky(c.phi)
    kd = c.coef_decharge if c.coef_decharge is not None else k0
    return (k_ah, k_ph, k0, coef.terme_cohesion_poussee(c.phi, c.c, k_ah),
            coef.terme_cohesion_butee(c.phi, c.c, k_ph), kd)


def _kh_couche(c: Couche, EI: float) -> float:
    if c.kh is not None:
        return c.kh
    EM = c.EM
    if EM is None and c.qc is not None:
        EM = em_depuis_cpt(c.qc, c.EM_sur_qc)
    if EM is None or c.alpha is None:
        raise ErreurModele(
            f"couche « {c.nom} » : EM (ou qc avec EM_sur_qc) et α sont nécessaires pour kh de Schmitt, "
            "ou bien imposez kh"
        )
    return kh_schmitt(EM, c.alpha, EI)


class MoteurPhases:
    """Prépare le maillage et les ressorts, puis enchaîne les phases."""

    def __init__(self, modele: Modele):
        self.m = modele
        ec = modele.ecran
        if not modele.couches:
            raise ErreurModele("aucune couche de sol définie")
        self.couches = trier(modele.couches)
        self.terrain_amont = modele.terrain_amont if modele.terrain_amont is not None else self.couches[0].toit
        self.terrain_aval = modele.terrain_aval if modele.terrain_aval is not None else self.terrain_amont

        cotes = [ec.tete, ec.pied, self.terrain_amont, self.terrain_aval]
        cotes += [c.toit for c in self.couches]
        cotes += [a.cote for a in modele.appuis.values()]
        cotes += [z for z in (modele.eau_amont, modele.eau_aval) if z is not None]
        for ph in modele.phases:
            cotes += [z for z in (ph.excaver, ph.remblayer_amont, ph.remblayer_aval) if z is not None]
            cotes += [z for z in ph.eau.values() if z is not None]
        for a in modele.appuis.values():
            if not ec.pied <= a.cote <= ec.tete:
                raise ErreurModele(f"appui {a.nom} : cote {a.cote} hors de l'écran [{ec.pied} ; {ec.tete}]")
        self.z = maillage(cotes, ec.pied, ec.tete, modele.pas)
        z = self.z
        n = len(z)
        self.EI_elem = ec.EI_en(0.5 * (z[1:] + z[:-1]))

        # Demi-mailles : (nœud, z bas, z haut)
        noeud, zb, zh = [], [], []
        for i in range(n):
            if i > 0:
                noeud.append(i); zb.append(0.5 * (z[i - 1] + z[i])); zh.append(z[i])
            if i < n - 1:
                noeud.append(i); zb.append(z[i]); zh.append(0.5 * (z[i] + z[i + 1]))
        self.d_noeud = np.array(noeud)
        self.d_zb, self.d_zh = np.array(zb), np.array(zh)
        self.d_zm = 0.5 * (self.d_zb + self.d_zh)
        self.d_L = self.d_zh - self.d_zb
        nd = len(noeud)

        # Propriétés par demi-maille
        props = [_coefficients_couche(c, modele.coefficients) for c in self.couches]
        idx = np.array([indice_couche(self.couches, zm) for zm in self.d_zm])
        tab = np.array(props)[idx]
        self.d_kah, self.d_kph, self.d_k0, self.d_ca, self.d_cp, self.d_kd = tab.T
        EI_noeud = ec.EI_en(z)
        self.d_kh = np.array([_kh_couche(self.couches[i], EI_noeud[noeud[j]]) for j, i in enumerate(idx)])
        self.d_couche = idx
        self.d_tan_delta_a = np.array([np.tan(np.radians(self.couches[i].delta_a_sur_phi * self.couches[i].phi)) for i in idx])
        self.d_tan_delta_p = np.array([np.tan(np.radians(self.couches[i].delta_p_sur_phi * self.couches[i].phi)) for i in idx])

        # Ressorts : demi-mailles côté amont puis côté aval
        self.ressorts = Ressorts(
            noeud=np.concatenate([self.d_noeud, self.d_noeud]),
            s=np.concatenate([np.full(nd, AMONT, float), np.full(nd, AVAL, float)]),
            A=np.zeros(2 * nd), kh=np.zeros(2 * nd), p_ref=np.zeros(2 * nd),
            y_ref=np.zeros(2 * nd), pa=np.zeros(2 * nd), pp=np.zeros(2 * nd),
        )
        self.nd = nd
        self.avertissements: list[str] = []
        if modele.coefficients == "coulomb" and any(c.delta_p_sur_phi > 1.0 / 3.0 for c in self.couches):
            self.avertissements.append(
                "Butée de Coulomb avec |δp| > φ/3 : Kp surestimé, non conservatif. "
                "Fournissez les tables de Kérisel-Absi (docs/normes/kerisel_absi)."
            )

    # ------------------------------------------------------------------
    def _sigma_v(self, cote: int, terrain: float, eau: float | None, surcharges: list[Surcharge]) -> tuple[np.ndarray, np.ndarray]:
        nom = "amont" if cote == AMONT else "aval"
        dsv = np.zeros(self.nd)
        for s in surcharges:
            if s.cote_ecran == nom:
                dsv += delta_sigma_v(s, self.d_zm, terrain)
        return contraintes_verticales(self.d_zm, terrain, eau, self.couches, self.m.gamma_w, dsv)

    def calculer(self) -> ResultatCalcul:
        m = self.m
        n = len(self.z)
        terrain = {AMONT: self.terrain_amont, AVAL: self.terrain_aval}
        eau = {AMONT: m.eau_amont, AVAL: m.eau_aval}
        surcharges: dict[str, Surcharge] = {s.nom: s for s in m.surcharges}
        poses: dict[str, tuple[float, float]] = {}   # nom -> (y_pose, F0)
        u = np.zeros(2 * n)
        sv_prec = np.zeros(2 * self.nd)
        present_prec = np.zeros(2 * self.nd, dtype=bool)
        r = self.ressorts
        resultats: list[ResultatPhase] = []

        phases = [Phase(nom="État initial")] + list(m.phases)
        for k, ph in enumerate(phases):
            # --- actions de la phase ---------------------------------
            try:
                if ph.excaver is not None:
                    if ph.excaver > terrain[AVAL] + 1e-9:
                        raise ErreurModele(f"excavation à {ph.excaver} au-dessus du terrain aval actuel ({terrain[AVAL]})")
                    if ph.excaver <= m.ecran.pied:
                        raise ErreurModele(f"excavation à {ph.excaver} sous le pied de l'écran")
                    terrain[AVAL] = ph.excaver
                if ph.remblayer_aval is not None:
                    if ph.remblayer_aval < terrain[AVAL] - 1e-9:
                        raise ErreurModele("remblai aval sous le terrain aval actuel")
                    terrain[AVAL] = ph.remblayer_aval
                if ph.remblayer_amont is not None:
                    if ph.remblayer_amont < terrain[AMONT] - 1e-9:
                        raise ErreurModele("remblai amont sous le terrain amont actuel")
                    terrain[AMONT] = ph.remblayer_amont
                if "amont" in ph.eau:
                    eau[AMONT] = ph.eau["amont"]
                if "aval" in ph.eau:
                    eau[AVAL] = ph.eau["aval"]
                for nom in ph.retirer_surcharges:
                    if nom not in surcharges:
                        raise ErreurModele(f"surcharge « {nom} » à retirer inconnue")
                    del surcharges[nom]
                for s in ph.ajouter_surcharges:
                    surcharges[s.nom] = s
                for nom in ph.deposer:
                    if nom not in poses:
                        raise ErreurModele(f"appui « {nom} » à déposer non posé")
                    del poses[nom]
                y_noeuds = u[0::2]
                for nom in ph.poser:
                    if nom not in m.appuis:
                        raise ErreurModele(f"appui « {nom} » inconnu")
                    a = m.appuis[nom]
                    i = int(np.argmin(np.abs(self.z - a.cote)))
                    poses[nom] = (float(y_noeuds[i]), a.precharge)
            except ErreurModele as e:
                resultats.append(ResultatPhase(ph.nom, False, f"Erreur de données : {e}",
                                               terrain[AMONT], terrain[AVAL], eau[AMONT], eau[AVAL]))
                break

            # --- état du sol -----------------------------------------
            liste_s = list(surcharges.values())
            sv_am, _ = self._sigma_v(AMONT, terrain[AMONT], eau[AMONT], liste_s)
            sv_av, _ = self._sigma_v(AVAL, terrain[AVAL], eau[AVAL], liste_s)
            sv = np.concatenate([sv_am, sv_av])
            present = np.concatenate([self.d_zh <= terrain[AMONT] + 1e-9, self.d_zh <= terrain[AVAL] + 1e-9])
            kah2 = np.tile(self.d_kah, 2); kph2 = np.tile(self.d_kph, 2)
            pa = np.maximum(kah2 * sv - np.tile(self.d_ca, 2), 0.0)
            pp = kph2 * sv + np.tile(self.d_cp, 2)
            p0 = np.clip(np.tile(self.d_k0, 2) * sv, pa, pp)

            fl = np.ones(2 * self.nd)
            fr = np.ones(2 * self.nd)
            if m.ecran.largeur_reaction is not None:
                for cote, sl in ((AMONT, slice(0, self.nd)), (AVAL, slice(self.nd, 2 * self.nd))):
                    a_, b_ = m.ecran.largeur_reaction(self.d_zm, cote, terrain[AVAL])
                    fl[sl], fr[sl] = a_, b_

            y_ress = u[0::2][r.noeud]
            nouveau = present & ~present_prec
            existant = present & present_prec
            p_ref = r.p_ref.copy()
            y_ref = r.y_ref.copy()
            p_ref[nouveau] = p0[nouveau]
            y_ref[nouveau] = y_ress[nouveau]
            p_ref[existant] += np.tile(self.d_kd, 2)[existant] * (sv[existant] - sv_prec[existant])
            p_ref = np.clip(p_ref, pa, pp)
            r.p_ref, r.y_ref, r.pa, r.pp = p_ref, y_ref, pa, pp
            r.A = np.where(present, np.tile(self.d_L, 2) * fl, 0.0)
            r.kh = np.tile(self.d_kh, 2) * np.where(fl > 0, fr / np.where(fl > 0, fl, 1.0), 0.0)

            # --- eau -------------------------------------------------
            gw = m.gamma_w
            u_am = np.where(self.d_zm < eau[AMONT], gw * (eau[AMONT] - self.d_zm), 0.0) if eau[AMONT] is not None else np.zeros(self.nd)
            u_av = np.where(self.d_zm < eau[AVAL], gw * (eau[AVAL] - self.d_zm), 0.0) if eau[AVAL] is not None else np.zeros(self.nd)
            f_ext = np.zeros(2 * n)
            f_ext[0::2] = np.bincount(self.d_noeud, weights=(u_am - u_av) * self.d_L, minlength=n)

            # --- appuis ----------------------------------------------
            noms = list(poses)
            defs = [m.appuis[nm] for nm in noms]
            appuis = Appuis(
                nom=noms,
                noeud=np.array([int(np.argmin(np.abs(self.z - d.cote))) for d in defs], dtype=int),
                k=np.array([d.raideur for d in defs], dtype=float),
                F0=np.array([poses[nm][1] for nm in noms], dtype=float),
                y_pose=np.array([poses[nm][0] for nm in noms], dtype=float),
                unilateral=np.array([d.unilateral for d in defs], dtype=bool),
            )

            # --- résolution ------------------------------------------
            base = dict(terrain_amont=terrain[AMONT], terrain_aval=terrain[AVAL],
                        eau_amont=eau[AMONT], eau_aval=eau[AVAL])
            try:
                sol = resoudre(self.z, self.EI_elem, r, appuis, f_ext, u0=u, y_rupture=m.y_rupture)
            except RuptureEquilibre as e:
                resultats.append(ResultatPhase(ph.nom, False, f"Rupture : {e}", **base))
                break

            u = sol.u
            r.memoriser(sol.y)
            sv_prec, present_prec = sv, present

            pressions = {}
            for nom_cote, sl in (("amont", slice(0, self.nd)), ("aval", slice(self.nd, 2 * self.nd))):
                msk = present[sl]
                ordre = np.argsort(self.d_zm[msk])
                f = fl[sl][msk][ordre]
                pressions[nom_cote] = {
                    "z": self.d_zm[msk][ordre],
                    "p": sol.p[sl][msk][ordre] * f,
                    "pa": pa[sl][msk][ordre] * f,
                    "pp": pp[sl][msk][ordre] * f,
                    "p0": (np.tile(self.d_k0, 2) * sv)[sl][msk][ordre] * f,
                    "statut": sol.statut[sl][msk][ordre],
                    # force du ressort = L × p (p est déjà rapportée au mètre linéaire d'écran)
                    "L": np.tile(self.d_L, 2)[sl][msk][ordre],
                    "z_noeud": self.z[r.noeud[sl][msk][ordre]],
                    "tan_delta": self.d_tan_delta_a[msk][ordre] if nom_cote == "amont" else self.d_tan_delta_p[msk][ordre],
                    "couche": self.d_couche[msk][ordre],
                }
            ordre = np.argsort(self.d_zm)
            resultats.append(ResultatPhase(
                nom=ph.nom, ok=True, message="", **base,
                z=self.z, y=sol.y, z_diag=sol.z_diag, M=sol.M, V=sol.V,
                pressions=pressions,
                eau={"z": self.d_zm[ordre], "u_amont": u_am[ordre], "u_aval": u_av[ordre]},
                appuis=[{"nom": nm, "cote": d.cote, "type": d.type, "effort": float(e_), "actif": bool(a_)}
                        for nm, d, e_, a_ in zip(noms, defs, sol.efforts_appuis, sol.appuis_actifs)],
                iterations=sol.iterations,
            ))
        return ResultatCalcul(phases=resultats, z=self.z, avertissements=self.avertissements)


def calculer(modele: Modele) -> ResultatCalcul:
    """Point d'entrée : calcule toutes les phases du modèle."""
    return MoteurPhases(modele).calculer()
