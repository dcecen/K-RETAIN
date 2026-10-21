"""Propriétés géométriques des sections, calculées à partir des dimensions.

Géométrie pure (pas de valeur normative) :
- tube circulaire creux (D, t) ;
- profilé en I laminé (h, b, tw, tf, r) avec congés de raccordement, formules
  usuelles des catalogues de profilés (aire, inertie et modules élastique et
  plastique selon l'axe fort et l'axe faible).
Unités d'entrée : mm ; sorties : cm², cm⁴, cm³, cm, kg/m (acier 7850 kg/m³).
"""
from __future__ import annotations

import math

# kg/m3 : masse volumique de l'acier de construction, utilisée seulement pour estimer la
# masse linéique d'un profilé dont le catalogue ne la donne pas (la valeur du catalogue prime).
MASSE_VOLUMIQUE_ACIER = 7850.0


def tube(D: float, t: float) -> dict:
    if not 0 < t < D / 2:
        raise ValueError("tube : épaisseur incohérente")
    d = D - 2 * t
    A = math.pi / 4 * (D**2 - d**2)
    I = math.pi / 64 * (D**4 - d**4)
    W = I / (D / 2)
    Wpl = (D**3 - d**3) / 6
    return {
        "A_cm2": A / 1e2, "Iy_cm4": I / 1e4, "Iz_cm4": I / 1e4,
        "Wel_y_cm3": W / 1e3, "Wel_z_cm3": W / 1e3, "Wpl_y_cm3": Wpl / 1e3, "Wpl_z_cm3": Wpl / 1e3,
        "iy_cm": math.sqrt(I / A) / 10, "iz_cm": math.sqrt(I / A) / 10,
        "Avz_cm2": 2 * A / math.pi / 1e2,
        "masse_kg_m": A * 1e-6 * MASSE_VOLUMIQUE_ACIER,
    }


def profil_i(h: float, b: float, tw: float, tf: float, r: float = 0.0) -> dict:
    """Profilé en I doublement symétrique avec congés de rayon r."""
    hw = h - 2 * tf
    # Congés : 4 aires (1 − π/4)·r² de centre de gravité à 0,2234·r du bord de l'âme / de l'aile
    a_c = (1 - math.pi / 4) * r**2
    A = 2 * b * tf + hw * tw + 4 * a_c
    # Axe fort y
    Iy = b * h**3 / 12 - (b - tw) * hw**3 / 12
    yc = hw / 2 - (10 - 3 * math.pi) / (12 - 3 * math.pi) * r  # position du centre de gravité du congé
    Ic = (1 / 3 - math.pi / 16 - 1 / (36 * (1 - math.pi / 4))) * r**4
    Iy += 4 * (Ic + a_c * yc**2)
    # Axe faible z
    Iz = 2 * tf * b**3 / 12 + hw * tw**3 / 12
    zc = tw / 2 + (10 - 3 * math.pi) / (12 - 3 * math.pi) * r
    Iz += 4 * (Ic + a_c * zc**2)
    # Modules plastiques
    Wpl_y = b * tf * (h - tf) + tw * hw**2 / 4 + 4 * a_c * yc
    Wpl_z = b**2 * tf / 2 + hw * tw**2 / 4 + 4 * a_c * zc
    # Aire de cisaillement (EN 1993-1-1 6.2.6(3)a, expression géométrique) :
    Avz = A - 2 * b * tf + (tw + 2 * r) * tf
    return {
        "A_cm2": A / 1e2, "Iy_cm4": Iy / 1e4, "Iz_cm4": Iz / 1e4,
        "Wel_y_cm3": Iy / (h / 2) / 1e3, "Wel_z_cm3": Iz / (b / 2) / 1e3,
        "Wpl_y_cm3": Wpl_y / 1e3, "Wpl_z_cm3": Wpl_z / 1e3,
        "iy_cm": math.sqrt(Iy / A) / 10, "iz_cm": math.sqrt(Iz / A) / 10,
        "Avz_cm2": Avz / 1e2,
        "masse_kg_m": A * 1e-6 * MASSE_VOLUMIQUE_ACIER,
    }
