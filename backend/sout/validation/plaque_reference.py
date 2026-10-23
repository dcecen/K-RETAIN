"""Solutions analytiques de plaques et résolution du grillage sans sol : partagées par les tests de
référence (tests/unitaires/test_plaque_reference.py) et par le rapport d'exemples élémentaires.

Sources : Timoshenko S. & Woinowsky-Krieger S. (1959), *Theory of Plates and Shells*, 2e éd. :
§ 30 (solution de Navier, plaque appuyée sur quatre côtés sous charge uniforme, éq. 131-133),
§ 33 (charge concentrée), § 44 (plaque encastrée, table 35), § 91 (plaque orthotrope, Huber).

Repère : s (longueur a, « x »), z (longueur b, « y »), w positif dans le sens de la charge.
Moments par mètre : Ms = −Ds·∂²w/∂s² (« Mx »), Mz = −Dz·∂²w/∂z² (« My »). Le grillage est la
plaque orthotrope de Huber à ν = 0. Conditions aux limites par élimination des degrés de
liberté : un bord appuyé bloque w et la rotation le long du bord, un bord encastré bloque aussi
la rotation normale.
"""
from __future__ import annotations

import numpy as np
from scipy.sparse.linalg import spsolve

from ..pseudo3d import plaque


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
