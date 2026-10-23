"""Cas élémentaires de la plaque (grillage pseudo-3D sans sol) : solutions de Timoshenko &
Woinowsky-Krieger, isotropie du grillage, équilibre, convergence. Mêmes calculs que
tests/unitaires/test_plaque_reference.py, exposés au rapport."""
from __future__ import annotations

import numpy as np

from .cas_elementaires import Cas, Grandeur
from .plaque_reference import fleche_milieu_charges_nodales, navier_ponctuelle, navier_uniforme, resoudre_plaque

TWK = "Timoshenko & Woinowsky-Krieger (1959), Theory of Plates and Shells, 2e éd."
A, B, D, Q = 4.0, 4.0, 1000.0, 10.0


def plaque_carree_appuyee() -> Cas:
    n = 20
    cas = Cas("plaque_carree_appuyee", "plaque", "Plaque carrée 4 × 4 m appuyée sur quatre côtés, charge uniforme (ν = 0), maillage 20 × 20")
    r = resoudre_plaque(A, B, n, n, D, D, q=Q)
    w_ref, Mx_ref, My_ref = navier_uniforme(A, B, Q, A / 2, B / 2, D, D)
    ic = n // 2
    cas.grandeurs = [
        Grandeur("w au centre", w_ref, float(r["W"][ic, ic]), 1e-2, "série de Navier, " + TWK + " § 30 (0,00406·q·a⁴/D)", "m"),
        Grandeur("Ms (= Mx) au centre", Mx_ref, float(r["Ms"][ic, ic]), 2e-2, "série de Navier dérivée, ν = 0", "kN·m/m"),
        Grandeur("Mz (= My) au centre", My_ref, float(r["Mz"][ic, ic]), 2e-2, "série de Navier dérivée, ν = 0", "kN·m/m"),
        Grandeur("Σ réactions = charge totale", r["charge_totale"], float(-r["reactions"].sum()), 1e-10, "statique", "kN"),
    ]
    cas.courbes = {"s": r["s"].tolist(), "w_grillage": r["W"][:, ic].tolist(),
                   "w_navier": [navier_uniforme(A, B, Q, x, B / 2, D, D)[0] for x in r["s"]]}
    return cas


def plaque_rectangulaire_appuyee() -> Cas:
    a, b, n_s, n_z = 8.0, 4.0, 40, 20
    cas = Cas("plaque_rectangulaire_appuyee", "plaque", "Plaque 8 × 4 m appuyée, charge uniforme : centre et point (a/4, b/4)")
    r = resoudre_plaque(a, b, n_s, n_z, D, D, q=Q)
    for (i, j), lib in (((n_s // 2, n_z // 2), "centre"), ((n_s // 4, n_z // 4), "point (a/4, b/4)")):
        w_ref, Mx_ref, My_ref = navier_uniforme(a, b, Q, r["s"][i], r["z"][j], D, D)
        cas.grandeurs += [
            Grandeur(f"w au {lib}", w_ref, float(r["W"][i, j]), 1e-2, TWK + " § 30", "m"),
            Grandeur(f"Ms au {lib}", Mx_ref, float(r["Ms"][i, j]), 2e-2, TWK + " § 30", "kN·m/m"),
            Grandeur(f"Mz au {lib}", My_ref, float(r["Mz"][i, j]), 2e-2, TWK + " § 30", "kN·m/m"),
        ]
    return cas


def plaque_charge_ponctuelle() -> Cas:
    n, P = 20, 100.0
    cas = Cas("plaque_charge_ponctuelle", "plaque", "Plaque carrée appuyée, force de 100 kN au centre")
    r = resoudre_plaque(A, B, n, n, D, D, P=(P, n // 2, n // 2))
    ic = n // 2
    cas.grandeurs = [
        Grandeur("w au centre", navier_ponctuelle(A, B, P, A / 2, B / 2, A / 2, B / 2, D), float(r["W"][ic, ic]), 1e-2, TWK + " § 33", "m"),
        Grandeur("w en (a/4, b/2)", navier_ponctuelle(A, B, P, A / 2, B / 2, A / 4, B / 2, D), float(r["W"][n // 4, ic]), 1e-2, TWK + " § 33", "m"),
        Grandeur("Σ réactions = P", P, float(-r["reactions"].sum()), 1e-10, "statique", "kN"),
    ]
    return cas


def plaque_orthotrope_huber() -> Cas:
    n, Ds = 20, D / 10
    cas = Cas("plaque_orthotrope", "plaque", "Plaque carrée appuyée, Ds = Dz/10 (orthotrope de Huber, torsion √(Ds·Dz))")
    r = resoudre_plaque(A, B, n, n, D, Ds, q=Q)
    w_ref, Mx_ref, My_ref = navier_uniforme(A, B, Q, A / 2, B / 2, Ds, D)
    ic = n // 2
    cas.grandeurs = [
        Grandeur("w au centre", w_ref, float(r["W"][ic, ic]), 1e-2, TWK + " § 91 (H = √(Dx·Dy))", "m"),
        Grandeur("Ms au centre", Mx_ref, float(r["Ms"][ic, ic]), 3e-2, TWK + " § 91", "kN·m/m"),
        Grandeur("Mz au centre", My_ref, float(r["Mz"][ic, ic]), 3e-2, TWK + " § 91", "kN·m/m"),
    ]
    return cas


def plaque_encastree() -> Cas:
    n = 24
    cas = Cas("plaque_encastree", "plaque", "Plaque carrée encastrée sur quatre côtés, charge uniforme")
    r = resoudre_plaque(A, B, n, n, D, D, q=Q, bords_s="encastres", bords_z="encastres")
    ic = n // 2
    cas.grandeurs = [Grandeur("w au centre", 0.00126 * Q * A ** 4 / D, float(r["W"][ic, ic]), 3e-2, TWK + " § 44, table 35 (0,00126·q·a⁴/D)", "m")]
    return cas


def plaque_flexion_cylindrique() -> Cas:
    n = 20
    cas = Cas("plaque_flexion_cylindrique", "plaque", "Bande appuyée sur deux bords opposés, libre sur les autres : poutre dans chaque direction")
    r = resoudre_plaque(6.0, B, 12, n, D, D, q=Q, bords_s="libres", bords_z="appuyes")
    jc = n // 2
    w_nodal = fleche_milieu_charges_nodales(B, D, Q, n)
    cas.grandeurs = [
        Grandeur("w milieu (appuis en z)", w_nodal, float(r["W"][3, jc]), 1e-9, "poutre à charges nodales : 5qL⁴/384D·(1 − 4/5n²)", "m"),
        Grandeur("Mz milieu (appuis en z)", Q * B ** 2 / 8, float(r["Mz"][3, jc]), 1e-6, "qL²/8", "kN·m/m"),
        Grandeur("Ms ≡ 0 (appuis en z)", 0.0, float(np.abs(r["Ms"]).max()), 1e-9, "flexion cylindrique", "kN·m/m", echelle=Q * B ** 2 / 8),
    ]
    Ds = 400.0
    r2 = resoudre_plaque(A, 6.0, n, 12, D, Ds, q=Q, bords_s="appuyes", bords_z="libres")
    cas.grandeurs += [
        Grandeur("w milieu (appuis en s, Ds = 400)", fleche_milieu_charges_nodales(A, Ds, Q, n), float(r2["W"][n // 2, 3]), 1e-9, "poutres horizontales seules", "m"),
        Grandeur("Ms milieu (appuis en s)", Q * A ** 2 / 8, float(r2["Ms"][n // 2, 3]), 1e-6, "qa²/8", "kN·m/m"),
        Grandeur("Mz ≡ 0 (appuis en s)", 0.0, float(np.abs(r2["Mz"]).max()), 1e-9, "flexion cylindrique", "kN·m/m", echelle=Q * A ** 2 / 8),
    ]
    return cas


def plaque_isotropie_du_grillage() -> Cas:
    cas = Cas("plaque_isotropie", "plaque", "Plaque 6 × 4 m (Dz 1000, Ds 300) et la même tournée de 90° : champ transposé")
    r1 = resoudre_plaque(6.0, 4.0, 18, 12, 1000.0, 300.0, q=Q)
    r2 = resoudre_plaque(4.0, 6.0, 12, 18, 300.0, 1000.0, q=Q)
    ref = float(np.abs(r1["W"]).max())
    cas.grandeurs = [
        Grandeur("écart max de w après rotation", 0.0, float(np.abs(r2["W"] - r1["W"].T).max()), 1e-8, "symétrie du grillage", "m", echelle=ref),
        Grandeur("écart max Mz ↔ Ms après rotation", 0.0, float(np.abs(r2["Ms"] - r1["Mz"].T).max()), 1e-8, "symétrie du grillage", "kN·m/m",
                 echelle=float(np.abs(r1["Mz"]).max())),
    ]
    return cas


def plaque_convergence() -> Cas:
    cas = Cas("plaque_convergence", "plaque", "Plaque carrée appuyée : erreur sur w au centre pour 10, 20, 40 éléments par côté")
    w_ref = navier_uniforme(A, B, Q, A / 2, B / 2, D, D)[0]
    err = []
    for n in (10, 20, 40):
        r = resoudre_plaque(A, B, n, n, D, D, q=Q)
        err.append(abs(float(r["W"][n // 2, n // 2]) - w_ref) / w_ref)
    cas.grandeurs = [
        Grandeur("erreur relative à 40 éléments", 0.0, err[2], 2e-3, "O(h²)", "", echelle=1.0),
        Grandeur("rapport des erreurs 10/20 (≈ 4 en O(h²))", 4.0, err[0] / err[1], 0.05, "ordre 2 du grillage", ""),
        Grandeur("rapport des erreurs 20/40 (≈ 4 en O(h²))", 4.0, err[1] / err[2], 0.05, "ordre 2 du grillage", ""),
    ]
    cas.courbes = {"n": [10, 20, 40], "erreur": err}
    return cas


CAS_PLAQUE = [plaque_carree_appuyee, plaque_rectangulaire_appuyee, plaque_charge_ponctuelle, plaque_orthotrope_huber,
              plaque_encastree, plaque_flexion_cylindrique, plaque_isotropie_du_grillage, plaque_convergence]


def cas_plaque() -> list[Cas]:
    return [f() for f in CAS_PLAQUE]
