"""Équilibre vertical de l'écran (NF P 94-282).

Efforts verticaux sur l'écran, par mètre linéaire (positif vers le bas) :
- poids propre W, déjaugé sous la nappe ;
- frottement sol-écran Σ L·p·tan δ, vers le bas là où le sol se décomprime (poussée), vers le
  haut là où il est comprimé (butée, contre-butée) ;
- composante verticale des tirants : H·tan i (vers le bas) ; des bracons : −H·tan a.

Si la résultante est descendante, elle doit être reprise par la pointe et le
frottement : gamma_effet · F ≤ Qb/gamma_b + Qs/gamma_s (÷ gamma_R_d), avec
Qb = k_p · pl(pointe) · A_pointe et Qs = coefficient_qs · pl · périmètre · fiche.
MÉTHODE SIMPLIFIÉE (pl de la couche du pied, frottement sur la fiche seule, 2 faces
par mètre pour les écrans continus) : à confronter à la NF P 94-282.

Si la résultante est montante, l'obliquité δp admise en butée n'est pas
mobilisable : la vérification échoue (réduire δp ou alourdir l'écran).
"""
from __future__ import annotations

import math

import numpy as np

from ..noyau.modele import Modele
from ..noyau.phasage import ResultatCalcul
from ..sol.couches import indice_couche, trier
from ..verifs import Lecteur, Verif, resultat

G = 9.81  # m/s², accélération de la pesanteur
SOURCE = "NF P 94-282 — équilibre vertical (méthode simplifiée RetainWall, à confronter à la norme)"


def _geometrie(modele: Modele, lect: Lecteur) -> tuple[float | None, float, float]:
    """(poids par m de hauteur [kN/m²], aire de pointe [m²/m], périmètre [m/m])."""
    inf = modele.ecran.infos
    t = inf.get("type")
    sec = inf.get("section") or {}
    if t == "palplanche":
        w = (sec.get("masse_kg_m2") or 0) * G / 1000
        return w, (sec.get("A_cm2_m") or 0) * 1e-4, 2.0
    if t == "berlinoise":
        e = inf.get("entraxe", 1.0)
        w = (sec.get("masse_kg_m") or 0) * G / 1000 / e
        perim = 2 * ((sec.get("h_mm") or 0) + (sec.get("b_mm") or 0)) / 1000 / e
        return w, (sec.get("A_cm2") or 0) * 1e-4 / e, perim
    if t not in ("paroi_moulee", "pieux_secants", "pieux_disjoints"):
        return 0.0, 0.0, 2.0
    gb = lect.v("ec2", "poids_volumique_beton_arme")
    if t == "paroi_moulee":
        e = inf.get("epaisseur", 0.0)
        return (gb * e if gb is not None else None), e, 2.0
    if t in ("pieux_secants", "pieux_disjoints"):
        D, e = inf.get("diametre", 0.0), inf.get("entraxe", 1.0)
        a = math.pi * D**2 / 4 / e
        perim = 2.0 if t == "pieux_secants" else math.pi * D / e
        return (gb * a if gb is not None else None), a, perim
    return 0.0, 0.0, 2.0


def _efforts_verticaux(modele: Modele, ph, W: float, A_b: float) -> tuple[float, float]:
    """(efforts descendants, efforts montants) sur l'écran pour la phase, en kN/m.

    Sens du frottement sol-écran : le sol qui se décomprime (pression ≤ pression
    au repos) tasse le long de l'écran et l'entraîne vers le bas ; le sol comprimé
    (pression > pression au repos : butée, contre-butée) remonte et le soulève.
    Poids déjaugé sous la nappe la plus haute (poussée d'Archimède = pression
    d'eau sous la pointe).
    """
    descend, monte = 0.0, 0.0
    for cote in ("amont", "aval"):
        c = ph.pressions[cote]
        v = c["L"] * c["p"] * c["tan_delta"]
        comprime = c["p"] > c["p0"] + 1e-9
        monte += float(np.sum(v[comprime]))
        descend += float(np.sum(v[~comprime]))
    for a in ph.appuis:
        d = modele.appuis[a["nom"]]
        ang = math.radians(d.infos.get("angle", 0.0))
        if d.type == "tirant":
            descend += a["effort"] * math.tan(ang)
        elif d.type == "bracon":
            monte += a["effort"] * math.tan(ang)
    niveaux = [h for h in (ph.eau_amont, ph.eau_aval) if h is not None]
    L_noye = 0.0
    if niveaux:
        L_noye = min(max(min(max(niveaux), modele.ecran.tete) - modele.ecran.pied, 0.0),
                     modele.ecran.tete - modele.ecran.pied)
    descend += W - modele.gamma_w * A_b * L_noye
    return descend, monte


def verifier(modele: Modele, res: ResultatCalcul, normes) -> list[Verif]:
    sorties = []
    lect_poids = Lecteur(normes)
    w_m, A_b, perim = _geometrie(modele, lect_poids)
    H = modele.ecran.tete - modele.ecran.pied
    W = w_m * H if w_m is not None else 0.0
    cas = [(ph, *_efforts_verticaux(modele, ph, W, A_b)) for ph in res.phases[1:] if ph.ok]
    if not cas:
        return []

    # 1. Mobilisation de δp : à vérifier pour CHAQUE phase (aucune phase ne doit être masquée)
    ph, descend, monte = max(cas, key=lambda t: t[2] / max(t[1], 1e-9))
    rapport = monte / max(descend, 1e-9)
    detail = (f"efforts montants (butée, contre-butée, bracons) {monte:.0f} kN/m pour des efforts descendants "
              f"(poids déjaugé, poussée, tirants) {descend:.0f} kN/m"
              + (" : résultante montante, réduire δp/φ' ou justifier la reprise" if rapport > 1 else ""))
    sorties.append(resultat("Équilibre vertical (mobilisation de δp)", "écran", ph.nom, rapport, detail, SOURCE,
                            lect_poids, detail_non_verifiable=detail + " — poids de l'écran incomplet"))

    # 2. Portance : phase de plus forte résultante descendante
    descendants = [(p, d - m) for p, d, m in cas if d - m > 0]
    if not descendants:
        return sorties
    ph, F = max(descendants, key=lambda t: t[1])
    lect = Lecteur(normes)
    lect.manquants += lect_poids.manquants
    ge = lect.v("nf_p94_282", "equilibre_vertical.gamma_effet")
    gb = lect.v("nf_p94_282", "equilibre_vertical.gamma_b")
    gs = lect.v("nf_p94_282", "equilibre_vertical.gamma_s")
    grd = lect.v("nf_p94_282", "equilibre_vertical.gamma_R_d")
    kp = lect.v("nf_p94_282", "equilibre_vertical.k_p")
    cqs = lect.v("nf_p94_282", "equilibre_vertical.coefficient_qs")
    couches = trier(modele.couches)
    pl = couches[indice_couche(couches, modele.ecran.pied - 1e-6)].pl   # couche sous la pointe
    if pl is None:
        lect.manquants.append("script : pl de la couche au pied de l'écran")
    fiche = max(ph.terrain_aval - modele.ecran.pied, 0.0)
    detail_k = (f"résultante descendante {F:.0f} kN/m. Méthode simplifiée : pl brut (et non ple*), "
                "qs proportionnel à pl, frottement Qs cumulé aux composantes p·tan δ (double comptage possible, "
                "à confirmer avec la NF P 94-282)")
    taux = None
    if not lect.manquants:
        Qb = kp * pl * A_b
        Qs = cqs * pl * perim * fiche
        R = (Qb / gb + Qs / gs) / grd
        taux = ge * F / R if R > 0 else float("inf")
        detail_k = f"Qb = {Qb:.0f}, Qs = {Qs:.0f} kN/m ; " + detail_k
    sorties.append(resultat("Équilibre vertical (portance)", "écran", ph.nom, taux, detail_k, SOURCE, lect))
    return sorties
