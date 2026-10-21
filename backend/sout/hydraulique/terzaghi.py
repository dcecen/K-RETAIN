"""Renard / boulance par la méthode de Terzaghi (1943), *Theoretical Soil Mechanics*, § 97.

Le prisme de sol contre l'écran côté fouille, de hauteur D (fiche sous le fond) et
de largeur D/2, est soulevé par l'excès de pression d'eau à sa base :
    F = W' / U = (γ' · D · D/2) / (γw · h_a · D/2) = γ' · D / (γw · h_a)
où h_a est l'excès de charge moyen (par rapport au niveau d'eau aval) à la base du
prisme, lu dans le réseau d'écoulement.
"""
from __future__ import annotations


def facteur_securite(D: float, gamma_prime: float, gamma_w: float, h_a: float) -> float:
    if h_a <= 0:
        return float("inf")
    return gamma_prime * D / (gamma_w * h_a)
