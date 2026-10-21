"""Renard par la méthode de Lane (1935), *Security from under-seepage*, Trans. ASCE 100.

Longueur de cheminement pondérée : L_w = Σ (longueurs verticales) + 1/3 · Σ (longueurs
horizontales) — les parcours horizontaux comptent pour un tiers.
Critère : L_w / H ≥ C_lane, C_lane dépendant du sol (table de Lane, à fournir dans
docs/normes/hydraulique.yaml). Taux = C_lane · H / L_w.
"""
from __future__ import annotations


def longueur_ponderee(verticales: list[float], horizontales: list[float]) -> float:
    return float(sum(verticales) + sum(horizontales) / 3.0)


def taux(L_w: float, H: float, C_lane: float) -> float:
    if L_w <= 0:
        return float("inf")
    return C_lane * H / L_w
