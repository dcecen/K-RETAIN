"""Paroi en plaque orthotrope modélisée par un grillage de poutres.

Analogie du grillage (Hambly E.C., *Bridge Deck Behaviour*, 2e éd., 1991) :
- poutres verticales : rigidité de flexion Dz·Δs (Dz = EI de la paroi par mètre,
  comme en 2D), degrés de liberté (w, θz = ∂w/∂z) ;
- poutres horizontales : rigidité Ds·Δz (Ds = rigidité de flexion horizontale par
  mètre de hauteur), degrés de liberté (w, θs = ∂w/∂s) ;
- torsion : GJ = √(Ds·Dz) par mètre dans chaque direction (plaque orthotrope de
  Huber avec ν = 0 : 4·Dxy = 2·√(Dx·Dy)), portée par θs dans les poutres
  verticales et par θz dans les poutres horizontales.
En flexion cylindrique (rien ne varie selon s), seules les poutres verticales
travaillent : le grillage redonne exactement la poutre 2D.

Nœud k = i·nz + j (i selon s, j selon z) ; degrés de liberté 3k (w), 3k+1 (θz), 3k+2 (θs).
"""
from __future__ import annotations

import numpy as np
from scipy import sparse

from ..noyau.poutre import rigidite_element


def largeurs_tributaires(x: np.ndarray) -> np.ndarray:
    t = np.zeros(len(x))
    t[1:] += 0.5 * np.diff(x)
    t[:-1] += 0.5 * np.diff(x)
    return t


def _moyenne_noeuds(v_elem: np.ndarray, nz: int) -> np.ndarray:
    """Valeur aux nœuds : moyenne des éléments adjacents (même règle partout)."""
    s = np.zeros(nz)
    c = np.zeros(nz)
    s[:-1] += v_elem; c[:-1] += 1
    s[1:] += v_elem; c[1:] += 1
    return s / c


def assembler(s: np.ndarray, z: np.ndarray, Dz_elem: np.ndarray, Ds_elem: np.ndarray) -> sparse.csc_matrix:
    """Rigidité du grillage. Dz_elem, Ds_elem : rigidités par mètre pour chaque élément vertical (selon z)."""
    ns, nz = len(s), len(z)
    ds = largeurs_tributaires(s)
    dz = largeurs_tributaires(z)
    Dz_noeud = _moyenne_noeuds(Dz_elem, nz)
    Ds_noeud = _moyenne_noeuds(Ds_elem, nz)
    lig, col, val = [], [], []

    def ajouter(ddl, k):
        for a in range(len(ddl)):
            for b in range(len(ddl)):
                lig.append(ddl[a]); col.append(ddl[b]); val.append(k[a, b])

    for i in range(ns):
        for j in range(nz - 1):
            a, b = i * nz + j, i * nz + j + 1
            L = z[j + 1] - z[j]
            ajouter([3 * a, 3 * a + 1, 3 * b, 3 * b + 1], rigidite_element(Dz_elem[j] * ds[i], L))
            GJ = np.sqrt(Ds_elem[j] * Dz_elem[j]) * ds[i]
            ajouter([3 * a + 2, 3 * b + 2], GJ / L * np.array([[1.0, -1.0], [-1.0, 1.0]]))
    for j in range(nz):
        for i in range(ns - 1):
            a, b = i * nz + j, (i + 1) * nz + j
            L = s[i + 1] - s[i]
            ajouter([3 * a, 3 * a + 2, 3 * b, 3 * b + 2], rigidite_element(Ds_noeud[j] * dz[j], L))
            GJ = np.sqrt(Ds_noeud[j] * Dz_noeud[j]) * dz[j]
            ajouter([3 * a + 1, 3 * b + 1], GJ / L * np.array([[1.0, -1.0], [-1.0, 1.0]]))
    N = 3 * ns * nz
    return sparse.csc_matrix((val, (lig, col)), shape=(N, N))


def moments(s: np.ndarray, z: np.ndarray, Dz_elem: np.ndarray, Ds_elem: np.ndarray,
            u: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Moments par mètre aux nœuds : Mz (flexion verticale, convention du 2D :
    positif face fouille tendue) et Ms (flexion horizontale, même convention de signe).
    Moyenne des extrémités d'éléments adjacents."""
    ns, nz = len(s), len(z)
    W = u[0::3].reshape(ns, nz)
    Tz = u[1::3].reshape(ns, nz)
    Ts = u[2::3].reshape(ns, nz)
    Mz = np.zeros((ns, nz))
    cz = np.zeros(nz)
    for j in range(nz - 1):
        L = z[j + 1] - z[j]
        ke = rigidite_element(Dz_elem[j], L)
        ue = np.stack([W[:, j], Tz[:, j], W[:, j + 1], Tz[:, j + 1]], axis=1)
        fe = ue @ ke.T
        Mz[:, j] += fe[:, 1]
        Mz[:, j + 1] += -fe[:, 3]
        cz[j] += 1; cz[j + 1] += 1
    Mz /= cz
    Ms = np.zeros((ns, nz))
    if ns > 1:
        Ds_noeud = _moyenne_noeuds(Ds_elem, nz)
        cs = np.zeros(ns)
        for i in range(ns - 1):
            L = s[i + 1] - s[i]
            for j in range(nz):
                ke = rigidite_element(Ds_noeud[j], L)
                fe = ke @ np.array([W[i, j], Ts[i, j], W[i + 1, j], Ts[i + 1, j]])
                Ms[i, j] += fe[1]
                Ms[i + 1, j] += -fe[3]
            cs[i] += 1; cs[i + 1] += 1
        Ms /= cs[:, None]
    return Mz, Ms
