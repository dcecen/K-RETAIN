"""Tests de référence de la plaque (grillage de Hambly) **sans sol**.

Sources des solutions analytiques (toutes les séries sont calculées ici, aucun
coefficient de table n'est recopié comme référence ; les valeurs de table ne servent
qu'à contrôler l'ordre de grandeur) :
- Timoshenko S. & Woinowsky-Krieger S. (1959), *Theory of Plates and Shells*, 2e éd. :
  § 30 (solution de Navier, plaque appuyée sur quatre côtés sous charge uniforme,
  éq. 131-133), § 33 (charge concentrée), § 44 (plaque encastrée, table 35),
  § 91 (plaque orthotrope, équation de Huber) ;
- RDM : poutre sur deux appuis sous charge uniforme (flexion cylindrique).

Repère : s (longueur a, « x » des ouvrages), z (longueur b, « y »), w positif dans le
sens de la charge. Moments par mètre : Ms = −Ds·∂²w/∂s² (« Mx »), Mz = −Dz·∂²w/∂z²
(« My »). Le grillage est la plaque orthotrope de Huber à ν = 0 (sout.pseudo3d.plaque) :
à ν = 0, Mx = −D·∂²w/∂x² sans terme de Poisson.

Conditions aux limites par élimination des degrés de liberté (pas par pénalité) : un
bord appuyé bloque w et la rotation **le long** du bord (w = 0 sur tout le bord
implique une pente tangente nulle) ; un bord encastré bloque aussi la rotation normale.
"""
from __future__ import annotations

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Solutions analytiques
# ---------------------------------------------------------------------------
from sout.validation.plaque_reference import (fleche_milieu_charges_nodales, navier_ponctuelle,  # noqa: E402
                                              navier_uniforme, resoudre_plaque)


A, B, D, Q = 4.0, 4.0, 1000.0, 10.0


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_navier_plaque_carree_appuyee():
    """Carrée appuyée sur quatre côtés, charge uniforme : w, Ms (= Mx) et Mz (= My) au centre
    contre la série de Navier (T&WK § 30). Contrôle d'ordre de grandeur : w_c = 0,00406·q·a⁴/D (table 8)."""
    n = 20
    r = resoudre_plaque(A, B, n, n, D, D, q=Q)
    w_ref, Mx_ref, My_ref = navier_uniforme(A, B, Q, A / 2, B / 2, D, D)
    assert w_ref == pytest.approx(0.00406 * Q * A ** 4 / D, rel=2e-3)
    ic = n // 2
    assert r["W"][ic, ic] == pytest.approx(w_ref, rel=1e-2)
    assert r["Ms"][ic, ic] == pytest.approx(Mx_ref, rel=2e-2)
    assert r["Mz"][ic, ic] == pytest.approx(My_ref, rel=2e-2)
    assert Mx_ref == pytest.approx(My_ref, rel=1e-9)   # symétrie de la plaque carrée


def test_navier_plaque_rectangulaire_appuyee():
    """Rectangle 2a × a appuyé : w, Mx, My au centre et en un point hors centre."""
    a, b, n_s, n_z = 8.0, 4.0, 40, 20
    r = resoudre_plaque(a, b, n_s, n_z, D, D, q=Q)
    for (i, j) in ((n_s // 2, n_z // 2), (n_s // 4, n_z // 4)):
        w_ref, Mx_ref, My_ref = navier_uniforme(a, b, Q, r["s"][i], r["z"][j], D, D)
        assert r["W"][i, j] == pytest.approx(w_ref, rel=1e-2)
        assert r["Ms"][i, j] == pytest.approx(Mx_ref, rel=2e-2)
        assert r["Mz"][i, j] == pytest.approx(My_ref, rel=2e-2)


def test_navier_charge_ponctuelle_au_centre():
    """Force P au centre d'une plaque carrée appuyée : w au centre et en (a/4, b/2) (T&WK § 33)."""
    n = 20
    P = 100.0
    r = resoudre_plaque(A, B, n, n, D, D, P=(P, n // 2, n // 2))
    ic = n // 2
    assert r["W"][ic, ic] == pytest.approx(navier_ponctuelle(A, B, P, A / 2, B / 2, A / 2, B / 2, D), rel=1e-2)
    assert r["W"][n // 4, ic] == pytest.approx(navier_ponctuelle(A, B, P, A / 2, B / 2, A / 4, B / 2, D), rel=1e-2)
    assert -r["reactions"].sum() == pytest.approx(P, rel=1e-10)


def test_plaque_orthotrope_de_huber():
    """Ds = Dz/10, appuyée sur quatre côtés : w, Ms, Mz au centre contre la série orthotrope
    (T&WK § 91) avec H = √(Ds·Dz), ce qui est exactement la torsion du grillage."""
    n = 20
    Ds = D / 10
    r = resoudre_plaque(A, B, n, n, D, Ds, q=Q)
    w_ref, Mx_ref, My_ref = navier_uniforme(A, B, Q, A / 2, B / 2, Ds, D)   # Dx = Ds (selon s), Dy = Dz
    ic = n // 2
    assert r["W"][ic, ic] == pytest.approx(w_ref, rel=1e-2)
    assert r["Ms"][ic, ic] == pytest.approx(Mx_ref, rel=3e-2)
    assert r["Mz"][ic, ic] == pytest.approx(My_ref, rel=3e-2)
    # la plaque orthotrope fléchit nettement plus que l'isotrope de rigidité Dz
    assert w_ref > 1.5 * navier_uniforme(A, B, Q, A / 2, B / 2, D, D)[0]


def test_plaque_carree_encastree():
    """Carrée encastrée sur quatre côtés : w_c = 0,00126·q·a⁴/D (T&WK § 44, table 35 ; indépendant de ν)."""
    n = 24
    r = resoudre_plaque(A, B, n, n, D, D, q=Q, bords_s="encastres", bords_z="encastres")
    ic = n // 2
    assert r["W"][ic, ic] == pytest.approx(0.00126 * Q * A ** 4 / D, rel=3e-2)
    assert np.abs(r["W"][0]).max() == 0.0 and np.abs(r["W"][:, 0]).max() == 0.0


def test_flexion_cylindrique_bande_appuyee_en_z():
    """Bande appuyée sur z = 0 et z = L, libre en s : poutre sur deux appuis. Avec les charges
    concentrées aux nœuds, le grillage redonne exactement la poutre à charges nodales
    (w = 5qL⁴/(384·Dz)·(1 − 4/(5n²)), Mz = qL²/8 au milieu pour n pair) ; Ms ≡ 0."""
    n = 20
    r = resoudre_plaque(6.0, B, 12, n, D, D, q=Q, bords_s="libres", bords_z="appuyes")
    jc = n // 2
    w_nodal = fleche_milieu_charges_nodales(B, D, Q, n)
    assert w_nodal == pytest.approx(5 * Q * B ** 4 / (384 * D) * (1 - 4 / (5 * n ** 2)), rel=1e-12)
    assert w_nodal == pytest.approx(5 * Q * B ** 4 / (384 * D), rel=2.5e-3)   # erreur des charges nodales
    for i in range(r["W"].shape[0]):
        assert r["W"][i, jc] == pytest.approx(w_nodal, rel=1e-9)
        assert r["Mz"][i, jc] == pytest.approx(Q * B ** 2 / 8, rel=1e-6)
    assert np.abs(r["Ms"]).max() < 1e-9 * np.abs(r["Mz"]).max()
    # rien ne varie selon s : toutes les lignes verticales sont identiques
    assert np.allclose(r["W"], r["W"][[0]], rtol=1e-10, atol=1e-14)


def test_flexion_cylindrique_bande_appuyee_en_s():
    """Même bande tournée : appuyée sur s = 0 et s = a, libre en z. Ce sont les poutres
    horizontales (Ds) qui travaillent : w = 5qa⁴/(384·Ds), Ms = qa²/8, Mz ≡ 0."""
    n = 20
    Ds = 400.0
    r = resoudre_plaque(A, 6.0, n, 12, D, Ds, q=Q, bords_s="appuyes", bords_z="libres")
    ic = n // 2
    w_nodal = fleche_milieu_charges_nodales(A, Ds, Q, n)
    for j in range(r["W"].shape[1]):
        assert r["W"][ic, j] == pytest.approx(w_nodal, rel=1e-9)
        assert r["Ms"][ic, j] == pytest.approx(Q * A ** 2 / 8, rel=1e-6)
    assert np.abs(r["Mz"]).max() < 1e-9 * np.abs(r["Ms"]).max()


def test_isotropie_du_grillage_plaque_tournee():
    """La plaque a × b (Dz, Ds) tournée de 90° — b × a avec (Ds, Dz) — donne le champ transposé
    et les moments échangés : le grillage ne privilégie aucune direction."""
    r1 = resoudre_plaque(6.0, 4.0, 18, 12, 1000.0, 300.0, q=Q)
    r2 = resoudre_plaque(4.0, 6.0, 12, 18, 300.0, 1000.0, q=Q)
    np.testing.assert_allclose(r2["W"], r1["W"].T, rtol=1e-8, atol=1e-14)
    np.testing.assert_allclose(r2["Ms"], r1["Mz"].T, rtol=1e-8, atol=1e-10)
    np.testing.assert_allclose(r2["Mz"], r1["Ms"].T, rtol=1e-8, atol=1e-10)


def test_equilibre_et_symetrie():
    """Somme des réactions d'appui = charge totale ; champ symétrique par rapport aux deux axes."""
    n = 16
    r = resoudre_plaque(A, B, n, n, D, D / 3, q=Q)
    assert -r["reactions"].sum() == pytest.approx(r["charge_totale"], rel=1e-10)
    assert r["charge_totale"] == pytest.approx(Q * A * B, rel=1e-12)
    np.testing.assert_allclose(r["W"], r["W"][::-1, :], rtol=1e-10, atol=1e-16)
    np.testing.assert_allclose(r["W"], r["W"][:, ::-1], rtol=1e-10, atol=1e-16)
    # une plaque isotrope carrée est symétrique par la diagonale
    r = resoudre_plaque(A, B, n, n, D, D, q=Q)
    np.testing.assert_allclose(r["W"], r["W"].T, rtol=1e-10, atol=1e-16)


def test_convergence_en_h_carre():
    """L'erreur sur w au centre décroît en O(h²) : rapport des erreurs ≈ 4 d'un maillage au double."""
    w_ref = navier_uniforme(A, B, Q, A / 2, B / 2, D, D)[0]
    err = []
    for n in (10, 20, 40):
        r = resoudre_plaque(A, B, n, n, D, D, q=Q)
        err.append(abs(r["W"][n // 2, n // 2] - w_ref) / w_ref)
    assert err[0] > err[1] > err[2]
    assert 3.0 < err[0] / err[1] < 5.0
    assert 3.0 < err[1] / err[2] < 5.0
    assert err[2] < 2e-3
