"""Raideurs et forces initiales des appuis, ramenées au mètre linéaire d'écran.

Mécanique élémentaire (barre élastique de raideur axiale EA/L) :
- raideur horizontale d'une barre inclinée de θ sur l'horizontale :
  k = E·A·cos²θ / L_élastique, divisée par l'espacement e des appuis ;
- effort horizontal par mètre : H = N·cos θ / e, et réciproquement N = H·e / cos θ.

Choix de modélisation documentés (à confirmer selon votre pratique et la
NF P 94-282 fournie dans docs/normes) :
- buton entre deux parois symétriques : longueur élastique L/2 (les deux
  parois se rapprochent), sinon L ;
- tirant : longueur élastique = longueur libre, sauf valeur imposée
  (`longueur_elastique`), par ex. longueur libre + une part du scellement ;
- dalle : bande de 1 m de large, épaisseur ep, même règle de symétrie que les butons.
Unités : E en MPa, A en cm², longueurs en m, angles en degrés, efforts en kN.
"""
from __future__ import annotations

import math


def _kN_par_m(E_MPa: float, A_cm2: float) -> float:
    """E·A en kN : MPa × cm² = 1e3 kN/m² × 1e-4 m² ... soit E(MPa)·A(cm²)·0,1 kN."""
    return E_MPa * 1e3 * A_cm2 * 1e-4


def raideur_barre(E_MPa: float, A_cm2: float, L_elastique: float, espacement: float, angle: float = 0.0) -> float:
    """Raideur horizontale (kN/m par m d'écran) d'une barre inclinée de `angle`."""
    if L_elastique <= 0 or espacement <= 0:
        raise ValueError("raideur d'appui : longueur élastique et espacement doivent être > 0")
    c = math.cos(math.radians(angle))
    return _kN_par_m(E_MPa, A_cm2) * c * c / (L_elastique * espacement)


def raideur_buton(E_MPa: float, A_cm2: float, longueur: float, espacement: float,
                  angle: float = 0.0, symetrique: bool = True) -> float:
    L = longueur / 2.0 if symetrique else longueur
    return raideur_barre(E_MPa, A_cm2, L, espacement, angle)


def raideur_tirant(E_MPa: float, A_cm2: float, longueur_libre: float, espacement: float,
                   inclinaison: float, longueur_elastique: float | None = None) -> float:
    L = longueur_elastique if longueur_elastique is not None else longueur_libre
    return raideur_barre(E_MPa, A_cm2, L, espacement, inclinaison)


def raideur_dalle(E_MPa: float, epaisseur: float, portee: float, symetrique: bool = True) -> float:
    """Dalle : bande de 1 m (A = ep × 1 m = ep·1e4 cm²), espacement 1 m."""
    L = portee / 2.0 if symetrique else portee
    return raideur_barre(E_MPa, epaisseur * 1e4, L, 1.0, 0.0)


def force_horizontale(N: float, espacement: float, angle: float = 0.0) -> float:
    """Effort horizontal par mètre d'écran (kN/m) d'un effort axial N (kN)."""
    return N * math.cos(math.radians(angle)) / espacement


def effort_axial(H: float, espacement: float, angle: float = 0.0) -> float:
    """Effort axial N (kN) d'un appui à partir de l'effort horizontal H (kN/m)."""
    return H * espacement / math.cos(math.radians(angle))
