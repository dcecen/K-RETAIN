"""Équilibre vertical de l'écran (NF P 94-282).

Efforts verticaux sur l'écran, par mètre linéaire (positif vers le bas) :
- poids propre W ;
- composante verticale de la poussée amont : Σ L·p·tan δa (le sol tassé tire l'écran vers le bas) ;
- composante verticale des tirants : H·tan i (vers le bas) ; des bracons : −H·tan a ;
- composante verticale de la butée aval : −Σ L·p·tan δp (la butée qui remonte soulève l'écran).

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


def verifier(modele: Modele, res: ResultatCalcul, normes) -> list[Verif]:
    sorties = []
    lect = Lecteur(normes)
    w_m, A_b, perim = _geometrie(modele, lect)
    H = modele.ecran.tete - modele.ecran.pied
    W = w_m * H if w_m is not None else None
    pire_cas = None
    for ph in res.phases[1:]:
        if not ph.ok:
            continue
        am, av = ph.pressions["amont"], ph.pressions["aval"]
        Pv_am = float(np.sum(am["L"] * am["p"] * am["tan_delta"]))
        Pv_av = float(np.sum(av["L"] * av["p"] * av["tan_delta"]))
        Tv = 0.0
        for a in ph.appuis:
            d = modele.appuis[a["nom"]]
            ang = math.radians(d.infos.get("angle", 0.0))
            if d.type == "tirant":
                Tv += a["effort"] * math.tan(ang)
            elif d.type == "bracon":
                Tv -= a["effort"] * math.tan(ang)
        descend = (W or 0.0) + Pv_am + max(Tv, 0.0)
        monte = Pv_av + max(-Tv, 0.0)
        F = descend - monte
        if pire_cas is None or F > pire_cas[1] or (monte > descend and monte / max(descend, 1e-9) > pire_cas[2]):
            pire_cas = (ph, F, monte / max(descend, 1e-9), descend, monte)
    if pire_cas is None:
        return []
    ph, F, rapport, descend, monte = pire_cas
    if F < 0:
        # δp non mobilisable : critère purement d'équilibre (pas de coefficient partiel en jeu)
        detail = (f"résultante montante : butée verticale {monte:.0f} kN/m > efforts descendants "
                  f"{descend:.0f} kN/m ; réduire δp/φ' ou justifier la reprise")
        sorties.append(resultat("Équilibre vertical (mobilisation de δp)", "écran", ph.nom, rapport, detail, SOURCE,
                                Lecteur(normes) if W is not None else lect))
        return sorties
    ge = lect.v("nf_p94_282", "equilibre_vertical.gamma_effet")
    gb = lect.v("nf_p94_282", "equilibre_vertical.gamma_b")
    gs = lect.v("nf_p94_282", "equilibre_vertical.gamma_s")
    grd = lect.v("nf_p94_282", "equilibre_vertical.gamma_R_d")
    kp = lect.v("nf_p94_282", "equilibre_vertical.k_p")
    cqs = lect.v("nf_p94_282", "equilibre_vertical.coefficient_qs")
    couches = trier(modele.couches)
    pl = couches[indice_couche(couches, modele.ecran.pied + 1e-6)].pl
    if pl is None:
        lect.manquants.append(f"script : pl de la couche au pied de l'écran")
    fiche = max(ph.terrain_aval - modele.ecran.pied, 0.0)
    detail_k = f"effort descendant {F:.0f} kN/m (poids {W or 0:.0f}, poussée verticale {descend - (W or 0):.0f}, butée verticale −{monte:.0f})"
    taux = None
    if not lect.manquants:
        Qb = kp * pl * A_b
        Qs = cqs * pl * perim * fiche
        R = (Qb / gb + Qs / gs) / grd
        taux = ge * F / R if R > 0 else float("inf")
        detail_k += f" ; Qb = {Qb:.0f}, Qs = {Qs:.0f} kN/m"
    sorties.append(resultat("Équilibre vertical (portance)", "écran", ph.nom, taux, detail_k, SOURCE, lect))
    return sorties
