"""Mobilisation de la butée (NF P 94-282, vérification à l'ELU).

Bm = butée mobilisée : intégrale des pressions côté aval sous le fond de fouille.
Bt = butée limite : intégrale des pressions passives limites sur la même hauteur.
Critère (forme des coefficients : docs/normes/nf_p94_282.yaml -> butee) :
    gamma_effet · Bm ≤ Bt / (gamma_R_e · gamma_R_d)
Taux = gamma_effet · gamma_R_e · gamma_R_d · Bm / Bt.
"""
from __future__ import annotations

import numpy as np

from ..noyau.phasage import ResultatCalcul
from ..verifs import Lecteur, Verif, donnee, resultat

SOURCE = "NF P 94-282 — mobilisation de la butée (coefficients : docs/normes/nf_p94_282.yaml)"
PRINCIPE = ("La butée mobilisée Bm est la résultante des pressions calculées sur la face côté fouille, sous le fond de "
            "fouille ; la butée limite Bt est la résultante des pressions passives limites sur la même hauteur (même "
            "coefficient Kp et même cohésion que le calcul). La NF P 94-282 impose γ_effet·Bm ≤ Bt/(γ_R,e·γ_R,d) : le taux "
            "de travail vaut γ_effet·γ_R,e·γ_R,d·Bm/Bt. La phase retenue est celle du rapport Bm/Bt le plus élevé ; le "
            "schéma montre, sur la fiche, les pressions mobilisées (plein) et les pressions limites (contour).")


def _schema(ph, res: ResultatCalcul) -> dict:
    """Pressions côté fouille sous le fond (mobilisées et limites), sous-échantillonnées pour le dessin ; tête de
    l'écran, terrain côté terre et nappes de la phase pour le fond de coupe."""
    av = ph.pressions["aval"]
    z, p, pp = (np.asarray(av[k], float) for k in ("z", "p", "pp"))
    sous = z <= ph.terrain_aval + 1e-9
    n = int(sous.sum())
    idx = np.unique(np.linspace(0, n - 1, min(n, 60)).round().astype(int)) if n else np.array([], int)
    return {"type": "butee", "phase": ph.nom, "fond": float(ph.terrain_aval), "pied": float(res.z.min()), "tete": float(res.z.max()),
            "terrain_amont": float(ph.terrain_amont), "nappe_amont": ph.eau_amont, "nappe_aval": ph.eau_aval,
            "z": [round(float(x), 3) for x in z[sous][idx]], "p": [round(float(x), 2) for x in p[sous][idx]],
            "pp": [round(float(x), 2) for x in pp[sous][idx]]}


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
    ph = next(p for p in res.phases if p.nom == nom)
    detail_k = f"Bm = {Bm:.0f} kN/m, Bt = {Bt:.0f} kN/m, Bm/Bt = {Bm / Bt:.2f} (valeurs caractéristiques)"
    taux = None if lect.manquants else ge * gre * grd * Bm / Bt
    donnees = [donnee("Bm", "butée mobilisée côté fouille (phase retenue)", Bm, "kN/m"),
               donnee("Bt", "butée limite sur la même hauteur", Bt, "kN/m"),
               donnee("Bm/Bt", "mobilisation caractéristique (phase retenue)", Bm / Bt),
               donnee("phase", "phase du rapport Bm/Bt le plus élevé", nom)]
    donnees += [donnee(f"Bm/Bt ({n})", "mobilisation caractéristique de la phase", bm / bt) for n, bm, bt in phases if n != nom]
    etapes = [f"Bm = Σ L_i·p_i : pressions mobilisées sous le fond de fouille, phase « {nom} » : {Bm:.1f} kN/m",
              f"Bt = Σ L_i·pp_i : pressions limites de butée sur la même hauteur : {Bt:.1f} kN/m",
              f"Bm/Bt = {Bm / Bt:.3f} (valeur caractéristique)"]
    if taux is None:
        etapes.append("coefficients partiels manquants dans docs/normes : taux non calculable")
    else:
        etapes.append(f"taux = γ_effet·γ_R,e·γ_R,d·Bm/Bt = {ge:g} × {gre:g} × {grd:g} × {Bm / Bt:.3f} = {taux:.3f}")
    return [resultat("Mobilisation de la butée", "fiche", nom, taux, detail_k, SOURCE, lect,
                     detail_non_verifiable=detail_k + " — coefficients partiels manquants", famille="butee",
                     principe=PRINCIPE, donnees=donnees, etapes=etapes, schema=_schema(ph, res))]
