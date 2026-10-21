"""Coefficients de pression des terres (composantes horizontales, écran vertical,
terre-plein horizontal).

Sources :
- Coulomb (1776), formule générale pour un écran vertical et un terre-plein
  horizontal, telle que reproduite par ex. dans Das, *Principles of Geotechnical
  Engineering*, chapitre « Lateral earth pressure ».
- Rankine (1857) : cas δ = 0, Ka = tan²(π/4 − φ/2), Kp = tan²(π/4 + φ/2).
- Jaky (1944) : K0 = 1 − sin φ' (sol normalement consolidé).
- Caquot & Kérisel, *Traité de mécanique des sols* : théorème des états
  correspondants pour la cohésion, H = c'·cot φ'.

Avertissement : pour la butée avec δ > φ/3, la formule de Coulomb (surface
plane) surestime Kp et n'est pas du côté de la sécurité. Les tables de
Kérisel-Absi (surfaces courbes) doivent alors être préférées dès qu'elles sont
fournies dans docs/normes/kerisel_absi (voir sout.sol.kerisel_absi).
"""
from __future__ import annotations

import math


def _verifier(phi: float, delta: float) -> tuple[float, float]:
    if not 0.0 <= phi < 90.0:
        raise ValueError(f"angle de frottement φ' hors bornes : {phi}°")
    if abs(delta) > phi + 1e-9:
        raise ValueError(f"obliquité |δ| = {abs(delta)}° supérieure à φ' = {phi}°")
    return math.radians(phi), math.radians(abs(delta))


def ka_coulomb(phi: float, delta: float = 0.0) -> float:
    """Coefficient de poussée de Coulomb Ka (poussée inclinée de δ sur la normale).

    Ka = cos²φ / ( cos δ · [1 + √( sin(φ+δ)·sin φ / cos δ )]² )
    (écran vertical, terre-plein horizontal). Source : Coulomb (1776).
    """
    p, d = _verifier(phi, delta)
    racine = math.sqrt(math.sin(p + d) * math.sin(p) / math.cos(d))
    return math.cos(p) ** 2 / (math.cos(d) * (1.0 + racine) ** 2)


def kp_coulomb(phi: float, delta: float = 0.0) -> float:
    """Coefficient de butée de Coulomb Kp (|δ| pris en valeur absolue).

    Kp = cos²φ / ( cos δ · [1 − √( sin(φ+δ)·sin φ / cos δ )]² )
    Source : Coulomb (1776). Non conservatif si δ > φ/3 (voir module).
    """
    p, d = _verifier(phi, delta)
    racine = math.sqrt(math.sin(p + d) * math.sin(p) / math.cos(d))
    return math.cos(p) ** 2 / (math.cos(d) * (1.0 - racine) ** 2)


def kah(phi: float, delta: float = 0.0) -> float:
    """Composante horizontale de la poussée : Kah = Ka · cos δ."""
    return ka_coulomb(phi, delta) * math.cos(math.radians(delta))


def kph(phi: float, delta: float = 0.0) -> float:
    """Composante horizontale de la butée : Kph = Kp · cos δ."""
    return kp_coulomb(phi, delta) * math.cos(math.radians(delta))


def k0_jaky(phi: float) -> float:
    """K0 = 1 − sin φ'. Source : Jaky (1944), sol normalement consolidé."""
    return 1.0 - math.sin(math.radians(phi))


def terme_cohesion_poussee(phi: float, c: float, k_ah: float) -> float:
    """Réduction de la pression active due à la cohésion (kPa).

    États correspondants (Caquot) : pa = Kah·(σ'v + H) − H avec H = c'·cot φ',
    soit pa = Kah·σ'v − H·(1 − Kah). Pour φ' = 0 : limite de Rankine, 2c.
    """
    if c == 0.0:
        return 0.0
    if phi < 1e-6:
        return 2.0 * c
    return c / math.tan(math.radians(phi)) * (1.0 - k_ah)


def terme_cohesion_butee(phi: float, c: float, k_ph: float) -> float:
    """Augmentation de la pression passive due à la cohésion (kPa).

    États correspondants : pp = Kph·(σ'v + H) − H = Kph·σ'v + H·(Kph − 1).
    Pour φ' = 0 : limite de Rankine, 2c.
    """
    if c == 0.0:
        return 0.0
    if phi < 1e-6:
        return 2.0 * c
    return c / math.tan(math.radians(phi)) * (k_ph - 1.0)
