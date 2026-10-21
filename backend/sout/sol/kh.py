"""Coefficient de réaction horizontal kh.

Formule de Schmitt (1995), « Méthode empirique d'évaluation du coefficient de
réaction du sol vis-à-vis des ouvrages de soutènement souples », Revue française
de géotechnique n° 71 ; reprise dans le cahier des charges (docs/specs.md) :

    kh = 2,1 · (EM/α)^(4/3) / (EI)^(1/3)

avec EM en kPa, EI en kN·m²/m, kh en kN/m³.
"""
from __future__ import annotations


def kh_schmitt(EM: float, alpha: float, EI: float) -> float:
    """kh (kN/m³) selon Schmitt ; EM (kPa), α (-), EI (kN·m²/m)."""
    if EM <= 0 or alpha <= 0 or EI <= 0:
        raise ValueError("Schmitt : EM, α et EI doivent être strictement positifs")
    return 2.1 * (EM / alpha) ** (4.0 / 3.0) / EI ** (1.0 / 3.0)


def em_depuis_cpt(qc: float, EM_sur_qc: float | None) -> float:
    """EM = (EM/qc) · qc.

    Il n'existe pas de corrélation universelle qc -> EM (voir docs/specs.md) :
    le rapport EM/qc est choisi et documenté par l'utilisateur, couche par couche.
    """
    if EM_sur_qc is None or EM_sur_qc <= 0:
        raise ValueError("corrélation CPT : le rapport EM_sur_qc doit être fourni (> 0)")
    return EM_sur_qc * qc
