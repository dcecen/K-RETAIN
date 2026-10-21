"""Formules de résistance de l'acier (EN 1993-1-1, EN 1993-5).

Les formules sont celles des articles cités ; toutes les valeurs de
coefficients (γM, facteurs d'imperfection, seuils) viennent de
docs/normes/ec3.yaml. Unités : kN, m, kPa (fy en MPa converti).
"""
from __future__ import annotations

import math


def n_cr(E_MPa: float, I_cm4: float, L_cr: float) -> float:
    """Charge critique d'Euler (kN) : π²·E·I / L². Théorie de l'élasticité (Euler, 1744)."""
    return math.pi**2 * E_MPa * 1e3 * I_cm4 * 1e-8 / L_cr**2


def chi(lambda_barre: float, alpha: float, lambda_0: float) -> float:
    """Coefficient de réduction pour le flambement — EN 1993-1-1 § 6.3.1.2 :
    Φ = 0,5·[1 + α·(λ̄ − λ0) + λ̄²],  χ = 1 / (Φ + √(Φ² − λ̄²)) ≤ 1.
    (λ0 : seuil du palier, lu dans docs/normes/ec3.yaml.)"""
    if lambda_barre <= lambda_0:
        return 1.0
    phi = 0.5 * (1 + alpha * (lambda_barre - lambda_0) + lambda_barre**2)
    return min(1.0, 1.0 / (phi + math.sqrt(max(phi**2 - lambda_barre**2, 0.0))))


def flambement(A_cm2: float, I_cm4: float, fy_MPa: float, E_MPa: float, L_cr: float,
               alpha: float, lambda_0: float, gamma_M1: float) -> dict:
    """Résistance au flambement N_b,Rd = χ·A·fy / γM1 — EN 1993-1-1 § 6.3.1.1 (sections de classe 1 à 3)."""
    N_pl = A_cm2 * 1e-4 * fy_MPa * 1e3
    Ncr = n_cr(E_MPa, I_cm4, L_cr)
    lam = math.sqrt(N_pl / Ncr)
    c = chi(lam, alpha, lambda_0)
    return {"N_pl": N_pl, "N_cr": Ncr, "lambda": lam, "chi": c, "N_b_Rd": c * N_pl / gamma_M1}


def m_rd(W_cm3: float, fy_MPa: float, gamma_M0: float) -> float:
    """Moment résistant M_c,Rd = W·fy / γM0 (kN·m) — EN 1993-1-1 § 6.2.5 (W plastique ou élastique selon la classe)."""
    return W_cm3 * 1e-6 * fy_MPa * 1e3 / gamma_M0


def v_pl_rd(Av_cm2: float, fy_MPa: float, gamma_M0: float) -> float:
    """Résistance plastique au cisaillement V_pl,Rd = Av·(fy/√3)/γM0 (kN) — EN 1993-1-1 § 6.2.6."""
    return Av_cm2 * 1e-4 * fy_MPa * 1e3 / math.sqrt(3) / gamma_M0


def amplification(N_Ed: float, N_cr_: float) -> float:
    """Amplification du second ordre des moments d'une barre comprimée : 1 / (1 − N/Ncr)
    (Timoshenko & Gere, *Theory of Elastic Stability*, 1961)."""
    if N_Ed >= N_cr_:
        return math.inf
    return 1.0 / (1.0 - N_Ed / N_cr_)
