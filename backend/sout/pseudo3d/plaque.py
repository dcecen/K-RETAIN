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

Vérifié contre les solutions analytiques de Timoshenko & Woinowsky-Krieger (plaque
appuyée, encastrée, orthotrope de Huber) : tests/unitaires/test_plaque_reference.py.
Limites : ν = 0 (pas de terme de couplage de Poisson), plaque mince (pas de
déformation d'effort tranchant), pas de comportement dans le plan de la paroi.

Nœud k = i·nz + j (i selon s, j selon z) ; degrés de liberté 3k (w), 3k+1 (θz), 3k+2 (θs).
"""
from __future__ import annotations

import numpy as np
from scipy import sparse

from ..noyau.poutre import efforts_par_statique, rigidite_element

__all__ = ["largeurs_tributaires", "assembler", "moments", "torsion", "forces_transfert", "efforts_lignes",
           "rigidite_element"]


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


def _blocs_flexion(EI: np.ndarray, L: np.ndarray) -> np.ndarray:
    """Matrices (n, 4, 4) de n éléments d'Hermite sur (w₁, θ₁, w₂, θ₂) : même formule que
    sout.noyau.poutre.rigidite_element, vectorisée."""
    c = EI / L ** 3
    L2 = L ** 2
    k = np.array([[12 * c, 6 * c * L, -12 * c, 6 * c * L],
                  [6 * c * L, 4 * c * L2, -6 * c * L, 2 * c * L2],
                  [-12 * c, -6 * c * L, 12 * c, -6 * c * L],
                  [6 * c * L, 2 * c * L2, -6 * c * L, 4 * c * L2]])
    return np.moveaxis(k, -1, 0)


def _entrees(ddl: np.ndarray, k: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(lignes, colonnes, valeurs) des matrices élémentaires k (n, m, m) aux degrés de liberté ddl (n, m)."""
    m = ddl.shape[1]
    return np.repeat(ddl, m, axis=1).ravel(), np.tile(ddl, (1, m)).ravel(), k.reshape(len(ddl), m * m).ravel()


def assembler(s: np.ndarray, z: np.ndarray, Dz_elem: np.ndarray, Ds_elem: np.ndarray,
              EI_h_sup: np.ndarray | None = None, coef_h: np.ndarray | None = None) -> sparse.csc_matrix:
    """Rigidité du grillage (assemblage vectorisé).

    Dz_elem, Ds_elem : rigidités par mètre pour chaque élément vertical (selon z).
    EI_h_sup (ns−1, nz) : rigidité de flexion absolue (kN·m²) ajoutée à chaque élément
    horizontal (i, j) — poutre réelle sur une rangée, par ex. une lierne.
    coef_h (ns−1, nz) : facteur appliqué à la flexion et à la torsion des éléments
    horizontaux (0 sur un joint qui ne transmet pas de moment horizontal).
    """
    ns, nz = len(s), len(z)
    ds = largeurs_tributaires(s)
    dz = largeurs_tributaires(z)
    Dz_noeud = _moyenne_noeuds(Dz_elem, nz)
    Ds_noeud = _moyenne_noeuds(Ds_elem, nz)
    # --- poutres verticales : élément (i, j) entre les nœuds i·nz+j et i·nz+j+1
    a = (np.arange(ns)[:, None] * nz + np.arange(nz - 1)[None, :]).ravel()
    b = a + 1
    Lv = np.tile(np.diff(z), ns)
    EIv = (Dz_elem[None, :] * ds[:, None]).ravel()
    GJv = (np.sqrt(Ds_elem * Dz_elem)[None, :] * ds[:, None]).ravel()
    ddl_v = np.stack([3 * a, 3 * a + 1, 3 * b, 3 * b + 1], axis=1)
    ddl_tv = np.stack([3 * a + 2, 3 * b + 2], axis=1)
    kt = np.array([[1.0, -1.0], [-1.0, 1.0]])
    l1, c1, v1 = _entrees(ddl_v, _blocs_flexion(EIv, Lv))
    l2, c2, v2 = _entrees(ddl_tv, (GJv / Lv)[:, None, None] * kt[None])
    # --- poutres horizontales : élément (i, j) entre les nœuds i·nz+j et (i+1)·nz+j
    a = (np.arange(ns - 1)[:, None] * nz + np.arange(nz)[None, :]).ravel()
    b = a + nz
    Lh = np.repeat(np.diff(s), nz)
    EIh = np.tile(Ds_noeud * dz, ns - 1)
    GJh = np.tile(np.sqrt(Ds_noeud * Dz_noeud) * dz, ns - 1)
    if coef_h is not None:
        EIh = EIh * np.asarray(coef_h, float).ravel()
        GJh = GJh * np.asarray(coef_h, float).ravel()
    if EI_h_sup is not None:
        EIh = EIh + np.asarray(EI_h_sup, float).ravel()
    ddl_h = np.stack([3 * a, 3 * a + 2, 3 * b, 3 * b + 2], axis=1)
    ddl_th = np.stack([3 * a + 1, 3 * b + 1], axis=1)
    l3, c3, v3 = _entrees(ddl_h, _blocs_flexion(EIh, Lh))
    l4, c4, v4 = _entrees(ddl_th, (GJh / Lh)[:, None, None] * kt[None])
    N = 3 * ns * nz
    return sparse.coo_matrix((np.concatenate([v1, v2, v3, v4]),
                              (np.concatenate([l1, l2, l3, l4]), np.concatenate([c1, c2, c3, c4]))),
                             shape=(N, N)).tocsc()


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


def torsion(s: np.ndarray, z: np.ndarray, Dz_elem: np.ndarray, Ds_elem: np.ndarray, u: np.ndarray) -> np.ndarray:
    """Moment de torsion par mètre Mzs = √(Ds·Dz)·∂²w/∂s∂z (torque des poutres verticales
    par mètre de largeur ; dans le grillage chaque famille de poutres porte le moment de
    torsion de la plaque, Hambly § 3). Valeur aux nœuds par moyenne des éléments adjacents."""
    ns, nz = len(s), len(z)
    Ts = u[2::3].reshape(ns, nz)
    GJ = np.sqrt(Ds_elem * Dz_elem)
    T_elem = GJ[None, :] * np.diff(Ts, axis=1) / np.diff(z)[None, :]
    out = np.zeros((ns, nz))
    out[:, :-1] += T_elem
    out[:, 1:] += T_elem
    out[:, 1:-1] /= 2.0
    return out


def forces_transfert(K: sparse.spmatrix, K_v: sparse.spmatrix, u: np.ndarray, ns: int, nz: int
                     ) -> tuple[np.ndarray, np.ndarray]:
    """Forces (kN) et couples (kN·m, conjugués de θz) que le reste de la plaque — flexion
    horizontale, torsion, conditions aux limites pénalisées — exerce sur chaque ligne
    verticale : t = (K − K_v)·u, K_v étant le grillage réduit à la flexion verticale.
    À l'équilibre K·u = f, donc chaque ligne verticale est en équilibre sous f − t :
    c'est ce qui permet la statique ligne par ligne (efforts_lignes). En flexion
    cylindrique t ≡ 0."""
    r = (K - K_v) @ u
    return r[0::3].reshape(ns, nz), r[1::3].reshape(ns, nz)


def efforts_lignes(z: np.ndarray, zb: np.ndarray, zh: np.ndarray, d_noeud: np.ndarray, q_lignes: np.ndarray,
                   F_noeuds: np.ndarray, t_w: np.ndarray, t_th: np.ndarray, ds: np.ndarray
                   ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Effort tranchant et moment par la statique de chaque ligne verticale (par mètre de paroi).

    q_lignes (ns, nd) : charge sol + eau de chaque demi-maille (kN/m par mètre de paroi) ;
    F_noeuds (ns, nz) : forces ponctuelles aux nœuds (kN par ligne, positives vers la fouille :
    −efforts des appuis) ; t_w, t_th : forces et couples de transfert (forces_transfert), dont
    l'opposé charge la ligne ; les forces de transfert sont réparties sur les demi-mailles du
    nœud (comme le sol), les couples restent concentrés. ds : largeur tributaire des lignes.
    Renvoie (z_diag, M_stat, V) à deux points par élément, tableaux (ns, 2·(nz−1)) ; V est
    nul aux extrémités libres et saute au droit des appuis ponctuels."""
    ns, nz = t_w.shape
    Ltot = np.bincount(d_noeud, weights=zh - zb, minlength=nz)
    V = np.empty((ns, 2 * (nz - 1)))
    M = np.empty_like(V)
    tous = np.arange(nz)
    zp = None
    for i in range(ns):
        q = q_lignes[i] - t_w[i, d_noeud] / (ds[i] * Ltot[d_noeud])
        zp, M[i], V[i] = efforts_par_statique(z, zb, zh, q, tous, F_noeuds[i] / ds[i], tous, -t_th[i] / ds[i])
    return zp, M, V
