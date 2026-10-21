"""Stabilité générale par cercles de glissement — méthode de Bishop simplifiée.

Bishop A.W. (1955), « The use of the slip circle in the stability analysis of
slopes », Géotechnique 5(1), p. 7-17.

    F = Σ [ c'·b + (W − u·b)·tan φ' ] / m_α  /  Σ W·sin α
    m_α = cos α + sin α · tan φ' / F           (résolution itérative)

Repère : écran en x = 0, amont x < 0, fouille 0 < x < largeur, z vers le haut.
Seuls les cercles passant sous le pied de l'écran sont étudiés (stabilité
d'ensemble de l'écran et du massif). Glissement vers la fouille.
Hypothèses : pressions interstitielles hydrostatiques (nappe amont pour x < 0,
nappe aval pour x > 0) ; tirants et écran négligés (du côté de la sécurité) ;
surcharges amont (répartie, bande) comptées en poids sur les tranches.
Paramètres de calcul : tan φ'/gamma_phi, c'/gamma_c, surcharges × gamma_Q ;
critère F ≥ gamma_R_d (docs/normes/nf_p94_282.yaml → stabilite_generale).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from ..noyau.modele import Modele
from ..noyau.phasage import ResultatCalcul
from ..sol.couches import indice_couche, trier
from ..verifs import Lecteur, Verif, resultat

SOURCE = "Bishop (1955), méthode simplifiée — NF P 94-282 stabilité générale"


@dataclass
class Profil:
    """Géométrie et sol pour la recherche de cercles."""
    couches: list
    z_amont: float
    z_aval: float
    largeur: float           # largeur de la fouille (m)
    h_amont: float | None    # nappes
    h_aval: float | None
    gamma_w: float
    charges: list            # [(x0, x1, q)] surcharges verticales en surface (kPa)

    def terrain(self, x: np.ndarray) -> np.ndarray:
        return np.where((x > 0) & (x < self.largeur), self.z_aval, self.z_amont)

    def nappe(self, x: float) -> float | None:
        return self.h_aval if 0 < x < self.largeur else self.h_amont


def _colonne(p: Profil, x: float, z_bas: float, z_haut: float, n: int = 12) -> float:
    """Poids d'une colonne de sol de largeur unité (kPa·m → kN/m²), totaux sous la nappe."""
    if z_haut <= z_bas:
        return 0.0
    hw = p.nappe(x)
    zs = np.linspace(z_bas, z_haut, n + 1)
    w = 0.0
    for z0, z1 in zip(zs[:-1], zs[1:]):
        zm = 0.5 * (z0 + z1)
        c = p.couches[indice_couche(p.couches, zm)]
        w += (c.gamma_dejauge + p.gamma_w if hw is not None and zm < hw else c.gamma) * (z1 - z0)
    if hw is not None and hw > z_haut:  # eau libre au-dessus (fouille noyée)
        w += p.gamma_w * (hw - z_haut)
    return w


def facteur(p: Profil, xc: float, zc: float, R: float, gphi: float = 1.0, gc: float = 1.0,
            gQ: float = 1.0, n_tranches: int = 60) -> float | None:
    """Coefficient de sécurité de Bishop d'un cercle (None si cercle non pertinent)."""
    xs = np.linspace(xc - R + 1e-6, xc + R - 1e-6, 800)
    zarc = zc - np.sqrt(np.maximum(R**2 - (xs - xc) ** 2, 0.0))
    dans = zarc < p.terrain(xs)
    if not dans.any():
        return None
    # segment contenant x = 0
    i0 = int(np.argmin(np.abs(xs)))
    if not dans[i0]:
        return None
    a = i0
    while a > 0 and dans[a - 1]:
        a -= 1
    b = i0
    while b < len(xs) - 1 and dans[b + 1]:
        b += 1
    x1, x2 = xs[a], xs[b]
    if x2 >= p.largeur:  # le cercle doit ressortir dans la fouille
        return None
    bords = np.unique(np.concatenate([np.linspace(x1, x2, n_tranches + 1), [0.0]]))
    bords = bords[(bords >= x1) & (bords <= x2)]
    num_items = []
    W_list, sin_list, cos_list, tphi_list, cb_list, ub_list = [], [], [], [], [], []
    for xa, xb in zip(bords[:-1], bords[1:]):
        bw = xb - xa
        if bw <= 1e-9:
            continue
        xm = 0.5 * (xa + xb)
        zb = zc - math.sqrt(max(R**2 - (xm - xc) ** 2, 0.0))
        zt = float(p.terrain(np.array([xm]))[0])
        W = _colonne(p, xm, zb, zt) * bw
        for x0, x1_, q in p.charges:
            recouv = max(0.0, min(xb, x1_) - max(xa, x0))
            W += gQ * q * recouv
        sin_a = (xc - xm) / R
        cos_a = math.sqrt(max(1 - sin_a**2, 0.0))
        c = p.couches[indice_couche(p.couches, zb)]
        hw = p.nappe(xm)
        u = p.gamma_w * max(hw - zb, 0.0) if hw is not None else 0.0
        W_list.append(W); sin_list.append(sin_a); cos_list.append(cos_a)
        tphi_list.append(math.tan(math.radians(c.phi)) / gphi)
        cb_list.append(c.c / gc * bw); ub_list.append(u * bw)
        num_items.append(1)
    W_, s_, c_, t_ = map(np.array, (W_list, sin_list, cos_list, tphi_list))
    cb, ub = np.array(cb_list), np.array(ub_list)
    moteur = float(np.sum(W_ * s_))
    if moteur <= 1e-9:
        return None
    F = 1.0
    for _ in range(100):
        m = c_ + s_ * t_ / F
        if np.any(m <= 0.05):  # tranches à très forte pente inverse : cercle écarté
            return None
        F_new = float(np.sum((cb + np.maximum(W_ - ub, 0.0) * t_) / m)) / moteur
        if abs(F_new - F) < 1e-6:
            return F_new
        F = F_new
    return F


def recherche(p: Profil, z_tete: float, z_pied: float, gphi=1.0, gc=1.0, gQ=1.0, n: int = 10) -> tuple[float, tuple]:
    """Cercle critique (F minimal) parmi les cercles passant sous le pied."""
    H = max(z_tete - z_pied, 1.0)
    meilleur = (math.inf, None)
    for xc in np.linspace(-1.5 * H, 0.6 * H, n):
        for zc in np.linspace(p.z_amont + 0.1 * H, p.z_amont + 2.0 * H, n):
            for zb in np.linspace(z_pied - 0.05 * H, z_pied - 1.2 * H, max(n // 2, 3)):
                R = zc - zb
                # le cercle doit passer sous le pied en x = 0
                if R <= abs(xc) or zc - math.sqrt(R**2 - xc**2) > z_pied:
                    continue
                F = facteur(p, xc, zc, R, gphi, gc, gQ)
                if F is not None and F < meilleur[0]:
                    meilleur = (F, (xc, zc, R))
    return meilleur


def profil_de(modele: Modele, ph, largeur: float | None) -> Profil:
    H = modele.ecran.tete - modele.ecran.pied
    charges = []
    for s in modele.surcharges:
        if s.cote_ecran != "amont":
            continue
        if s.type == "repartie":
            charges.append((-1e6, 0.0, s.q))
        elif s.type == "bande":
            charges.append((-(s.distance + s.largeur), -s.distance, s.q))
    return Profil(trier(modele.couches), ph.terrain_amont, ph.terrain_aval, largeur or 2.0 * H,
                  ph.eau_amont, ph.eau_aval, modele.gamma_w, charges)


def verifier(modele: Modele, res: ResultatCalcul, normes, largeur: float | None = None) -> list[Verif]:
    phases = [ph for ph in res.phases[1:] if ph.ok]
    if not phases:
        return []
    ph = min(phases, key=lambda p: p.terrain_aval)  # phase la plus profonde
    p = profil_de(modele, ph, largeur)
    lect = Lecteur(normes)
    gphi = lect.v("nf_p94_282", "stabilite_generale.gamma_phi")
    gc = lect.v("nf_p94_282", "stabilite_generale.gamma_c")
    gR = lect.v("nf_p94_282", "stabilite_generale.gamma_R_d")
    gQ = lect.v("nf_p94_282", "stabilite_generale.gamma_Q")
    Fk, cercle_k = recherche(p, modele.ecran.tete, modele.ecran.pied)
    if cercle_k is None:
        return [resultat("Stabilité générale (Bishop)", "massif", ph.nom, None, "aucun cercle pertinent trouvé",
                         SOURCE, detail_non_verifiable="aucun cercle passant sous le pied et ressortant dans la fouille")]
    detail_k = (f"F caractéristique = {Fk:.2f} (centre x = {cercle_k[0]:.1f}, z = {cercle_k[1]:.1f}, "
                f"R = {cercle_k[2]:.1f} m)")
    taux = None
    detail = detail_k
    if not lect.manquants:
        Fd, cercle_d = recherche(p, modele.ecran.tete, modele.ecran.pied, gphi, gc, gQ)
        taux = gR / Fd
        detail = f"F de calcul = {Fd:.2f} (paramètres pondérés) ; {detail_k}"
    return [resultat("Stabilité générale (Bishop)", "massif", ph.nom, taux, detail, SOURCE, lect,
                     detail_non_verifiable=detail_k)]
