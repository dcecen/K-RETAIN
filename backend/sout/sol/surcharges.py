"""Surcharges en surface : augmentation de contrainte verticale Δσv(z) au droit
de l'écran, appliquée ensuite aux coefficients Ka, K0, Kp.

Sources (solutions élastiques, déformation plane) :
- Surcharge répartie illimitée : Δσv = q.
- Surcharge en bande (largeur b, à la distance d de l'écran) : solution de
  Boussinesq intégrée, Δσz = q/π · [α + sin α · cos(α + 2β)], avec α l'angle
  sous lequel la bande est vue depuis le point et β l'angle entre la verticale
  et le bord le plus proche. Poulos H.G. & Davis E.H. (1974), *Elastic
  Solutions for Soil and Rock Mechanics*, Wiley, § 3.2 (strip load).
- Charge linéique parallèle à l'écran (Q en kN/m, à la distance d) : solution
  de Flamant, Δσz = 2·Q·z³ / (π·r⁴), r² = d² + z². Poulos & Davis (1974), § 3.1.

Hypothèse de modélisation : la contrainte verticale calculée dans le massif
semi-infini est transmise aux ressorts sans effet miroir de l'écran.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Surcharge:
    nom: str
    type: str                 # "repartie", "bande", "lineique"
    q: float                  # kPa (répartie, bande) ou kN/m (linéique)
    distance: float = 0.0     # m, distance au parement de l'écran
    largeur: float = 0.0      # m, largeur de la bande
    cote: float | None = None  # m, cote d'application (défaut : terrain du côté considéré)
    cote_ecran: str = "amont"  # "amont" ou "aval"


def delta_sigma_v(s: Surcharge, z: np.ndarray, z_terrain: float) -> np.ndarray:
    """Δσv (kPa) aux cotes z dues à la surcharge s."""
    z = np.asarray(z, dtype=float)
    z_app = z_terrain if s.cote is None else s.cote
    prof = z_app - z
    out = np.zeros_like(z)
    sous = prof > 1e-9
    if s.type == "repartie":
        out[sous] = s.q
    elif s.type == "bande":
        if s.largeur <= 0:
            raise ValueError(f"surcharge {s.nom} : largeur de bande nulle")
        h = prof[sous]
        b1 = np.arctan(s.distance / h)
        b2 = np.arctan((s.distance + s.largeur) / h)
        alpha = b2 - b1
        out[sous] = s.q / math.pi * (alpha + np.sin(alpha) * np.cos(alpha + 2.0 * b1))
    elif s.type == "lineique":
        h = prof[sous]
        r2 = s.distance**2 + h**2
        out[sous] = 2.0 * s.q * h**3 / (math.pi * r2**2)
    else:
        raise ValueError(f"surcharge {s.nom} : type inconnu « {s.type} »")
    return out
