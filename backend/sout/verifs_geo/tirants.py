"""Résistance du scellement des tirants.

R = π · Ds · Ls · qs (frottement latéral limite qs le long du scellement, donné
dans le script à partir des essais ou de l'abaque retenu par l'ingénieur).
Critère : gamma_effet · T ≤ R / gamma_a (docs/normes/nf_p94_282.yaml -> tirants).
"""
from __future__ import annotations

import math

from ..noyau.modele import Modele
from ..noyau.phasage import ResultatCalcul
from ..verifs import Lecteur, Verif, resultat

SOURCE = "NF P 94-282 — résistance du scellement R = π·Ds·Ls·qs"


def verifier(modele: Modele, res: ResultatCalcul, normes) -> list[Verif]:
    sorties = []
    for d in modele.appuis.values():
        if d.type != "tirant":
            continue
        inf = d.infos
        esp, ang = inf.get("espacement", 1.0), inf.get("angle", 0.0)
        T, phase = 0.0, None
        for ph in res.phases:
            for a in ph.appuis if ph.ok else []:
                if a["nom"] == d.nom:
                    N = a["effort"] * esp / math.cos(math.radians(ang))
                    if N > T:
                        T, phase = N, ph.nom
        Ds, Ls, qs = inf.get("diametre_forage"), inf.get("longueur_scellee"), inf.get("qs")
        if not (Ds and Ls and qs):
            sorties.append(resultat("Scellement du tirant", d.nom, phase, None, "", SOURCE,
                                    detail_non_verifiable=f"T = {T:.0f} kN — donnez diametre_forage, longueur_scellee et qs"))
            continue
        R = math.pi * Ds * Ls * qs
        lect = Lecteur(normes)
        ge = lect.v("nf_p94_282", "tirants.gamma_effet")
        ga = lect.v("nf_p94_282", "tirants.gamma_a")
        detail = f"T = {T:.0f} kN par tirant, R = π·{Ds}·{Ls}·{qs:.0f} = {R:.0f} kN (T/R = {T / R:.2f} caractéristique)"
        sorties.append(resultat("Scellement du tirant", d.nom, phase,
                                None if lect.manquants else ge * ga * T / R, detail, SOURCE, lect))
    return sorties
