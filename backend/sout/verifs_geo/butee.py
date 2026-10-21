"""Mobilisation de la butée (NF P 94-282, vérification à l'ELU).

Bm = butée mobilisée : intégrale des pressions côté aval sous le fond de fouille.
Bt = butée limite : intégrale des pressions passives limites sur la même hauteur.
Critère (forme des coefficients : docs/normes/nf_p94_282.yaml → butee) :
    gamma_effet · Bm ≤ Bt / (gamma_R_e · gamma_R_d)
Taux = gamma_effet · gamma_R_e · gamma_R_d · Bm / Bt.
"""
from __future__ import annotations

import numpy as np

from ..noyau.phasage import ResultatCalcul
from ..verifs import Lecteur, Verif, resultat

SOURCE = "NF P 94-282 — mobilisation de la butée (coefficients : docs/normes/nf_p94_282.yaml)"


def butee_par_phase(res: ResultatCalcul) -> list[tuple[str, float, float]]:
    """[(phase, Bm, Bt)] en kN/m pour les phases excavées."""
    sortie = []
    for ph in res.phases[1:]:
        if not ph.ok:
            continue
        av = ph.pressions["aval"]
        if len(av["z"]) == 0:
            continue
        Bm = float(np.sum(av["L"] * av["p"]))
        Bt = float(np.sum(av["L"] * av["pp"]))
        if Bt > 0:
            sortie.append((ph.nom, Bm, Bt))
    return sortie


def verifier(res: ResultatCalcul, normes) -> list[Verif]:
    lect = Lecteur(normes)
    ge = lect.v("nf_p94_282", "butee.gamma_effet")
    gre = lect.v("nf_p94_282", "butee.gamma_R_e")
    grd = lect.v("nf_p94_282", "butee.gamma_R_d")
    phases = butee_par_phase(res)
    if not phases:
        return []
    nom, Bm, Bt = max(phases, key=lambda t: t[1] / t[2])
    detail_k = f"Bm = {Bm:.0f} kN/m, Bt = {Bt:.0f} kN/m, Bm/Bt = {Bm / Bt:.2f} (valeurs caractéristiques)"
    taux = None if lect.manquants else ge * gre * grd * Bm / Bt
    return [resultat("Mobilisation de la butée", "fiche", nom, taux, detail_k, SOURCE, lect,
                     detail_non_verifiable=detail_k + " — coefficients partiels manquants")]
