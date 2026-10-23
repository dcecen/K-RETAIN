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
from scipy.sparse.linalg import spsolve

from sout.pseudo3d import plaque


# ---------------------------------------------------------------------------
# Solutions analytiques
# ---------------------------------------------------------------------------
def navier_uniforme(a: float, b: float, q: float, x: float, y: float, Dx: float, Dy: float,
                    N: int = 199) -> tuple[float, float, float]:
    """(w, Mx, My) au point (x, y) d'une plaque a × b simplement appuyée sous charge uniforme q.

    Isotrope (Dx = Dy = D, ν = 0) : T&WK § 30, éq. (131) :
        w = 16q/(π⁶D) · Σ_{m,n impairs} sin(mπx/a)·sin(nπy/b) / [m·n·(m²/a² + n²/b²)²]
    Orthotrope (Huber, T&WK § 91) : même série avec le dénominateur
        m·n·(Dx·m⁴/a⁴ + 2H·m²n²/(a²b²) + Dy·n⁴/b⁴),  H = √(Dx·Dy),
    qui redonne la série isotrope quand Dx = Dy. Moments à ν = 0 : Mx = −Dx·w,xx, My = −Dy·w,yy.
    """
    H = np.sqrt(Dx * Dy)
    m = np.arange(1, N + 1, 2, dtype=float)[:, None]
    n = np.arange(1, N + 1, 2, dtype=float)[None, :]
    den = m * n * (Dx * (m / a) ** 4 + 2 * H * (m / a) ** 2 * (n / b) ** 2 + Dy * (n / b) ** 4)
    S = np.sin(m * np.pi * x / a) * np.sin(n * np.pi * y / b)
    c = 16 * q / np.pi ** 6
    w = c * float(np.sum(S / den))
    Mx = c * np.pi ** 2 * Dx * float(np.sum((m / a) ** 2 * S / den))
    My = c * np.pi ** 2 * Dy * float(np.sum((n / b) ** 2 * S / den))
    return w, Mx, My


def navier_ponctuelle(a: float, b: float, P: float, xi: float, eta: float, x: float, y: float,
                      D: float, N: int = 400) -> float:
    """w(x, y) d'une plaque isotrope a × b appuyée, charge concentrée P en (ξ, η) (T&WK § 33, éq. 133) :
    w = 4P/(π⁴·a·b·D) · Σ_{m,n} sin(mπξ/a)·sin(nπη/b)·sin(mπx/a)·sin(nπy/b) / (m²/a² + n²/b²)²."""
    m = np.arange(1, N + 1, dtype=float)[:, None]
    n = np.arange(1, N + 1, dtype=float)[None, :]
    S = (np.sin(m * np.pi * xi / a) * np.sin(n * np.pi * eta / b)
         * np.sin(m * np.pi * x / a) * np.sin(n * np.pi * y / b))
    return 4 * P / (np.pi ** 4 * a * b * D) * float(np.sum(S / ((m / a) ** 2 + (n / b) ** 2) ** 2))


# ---------------------------------------------------------------------------
# Résolution du grillage avec conditions aux limites par élimination
# ---------------------------------------------------------------------------
def resoudre_plaque(a: float, b: float, n_s: int, n_z: int, Dz: float, Ds: float, q: float = 0.0,
                    P: tuple[float, int, int] | None = None, bords_s: str = "appuyes",
                    bords_z: str = "appuyes") -> dict:
    """Plaque a (selon s) × b (selon z), n_s × n_z éléments, charge uniforme q et/ou force
    P = (valeur, i, j) au nœud (i, j). bords_s : état des bords s = 0 et s = a ("libres",
    "appuyes", "encastres") ; bords_z : idem pour z = 0 et z = b."""
    s = np.linspace(0.0, a, n_s + 1)
    z = np.linspace(0.0, b, n_z + 1)
    ns, nz = len(s), len(z)
    K = plaque.assembler(s, z, np.full(nz - 1, Dz), np.full(nz - 1, Ds)).tocsr()
    ds, dz = plaque.largeurs_tributaires(s), plaque.largeurs_tributaires(z)
    f = np.zeros(3 * ns * nz)
    f[0::3] = (q * np.outer(ds, dz)).ravel()
    if P is not None:
        f[3 * (P[1] * nz + P[2])] += P[0]
    bloque = np.zeros(3 * ns * nz, dtype=bool)
    if bords_s != "libres":
        for i in (0, ns - 1):
            k = i * nz + np.arange(nz)
            bloque[3 * k] = True          # w
            bloque[3 * k + 1] = True      # θz : rotation le long du bord s = cste
            if bords_s == "encastres":
                bloque[3 * k + 2] = True  # θs : rotation normale au bord
    if bords_z != "libres":
        for j in (0, nz - 1):
            k = np.arange(ns) * nz + j
            bloque[3 * k] = True
            bloque[3 * k + 2] = True      # θs : rotation le long du bord z = cste
            if bords_z == "encastres":
                bloque[3 * k + 1] = True
    libres = np.flatnonzero(~bloque)
    u = np.zeros(3 * ns * nz)
    u[libres] = spsolve(K[libres][:, libres].tocsc(), f[libres])
    reactions = (K @ u - f)[0::3].reshape(ns, nz)   # forces aux nœuds bloqués (0 ailleurs)
    Mz, Ms = plaque.moments(s, z, np.full(nz - 1, Dz), np.full(nz - 1, Ds), u)
    return {"s": s, "z": z, "W": u[0::3].reshape(ns, nz), "Mz": Mz, "Ms": Ms, "reactions": reactions,
            "charge_totale": float(f[0::3].sum())}


A, B, D, Q = 4.0, 4.0, 1000.0, 10.0


def fleche_milieu_charges_nodales(L: float, D: float, q: float, n: int) -> float:
    """Flèche au milieu d'une poutre sur deux appuis portant la charge uniforme q concentrée
    aux n + 1 nœuds d'un maillage régulier (q·h aux nœuds intérieurs) : superposition des
    charges ponctuelles, flèche au milieu sous une force P à la distance a ≤ L/2 d'un appui :
    δ = P·a·(3L² − 4a²)/(48·EI) (RDM, Timoshenko ; Roark tableau 8.1). Vaut
    5qL⁴/(384·D)·(1 − 4/(5n²)) : l'écart à la charge uniforme est l'erreur des charges nodales."""
    h = L / n
    tot = 0.0
    for k in range(1, n):
        a = min(k * h, L - k * h)
        tot += q * h * a * (3 * L ** 2 - 4 * a ** 2) / (48 * D)
    return tot


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
