"""Poutre d'Euler-Bernoulli en éléments finis (2 degrés de liberté par nœud).

Degrés de liberté du nœud i : y_i (déplacement horizontal, positif vers la
fouille) et θ_i = dy/dz. Les nœuds sont rangés par cote z croissante.

Matrice de rigidité élémentaire classique (interpolation d'Hermite cubique),
voir par ex. Przemieniecki, *Theory of Matrix Structural Analysis* (1968),
ou tout cours d'éléments finis de poutre.
"""
from __future__ import annotations

import numpy as np
from scipy import sparse


def maillage(cotes_imposees: list[float], z_bas: float, z_haut: float, pas: float) -> np.ndarray:
    """Nœuds de z_bas à z_haut (croissants), passant par toutes les cotes imposées
    comprises dans l'intervalle, avec des éléments de longueur au plus `pas`.
    """
    if z_haut <= z_bas:
        raise ValueError("maillage : la tête doit être au-dessus du pied")
    points = sorted({round(z, 6) for z in cotes_imposees if z_bas <= z <= z_haut} | {z_bas, z_haut})
    noeuds = [points[0]]
    for a, b in zip(points[:-1], points[1:]):
        n = max(1, int(np.ceil((b - a) / pas - 1e-9)))
        noeuds.extend(np.linspace(a, b, n + 1)[1:].tolist())
    return np.array(noeuds)


def rigidite_element(EI: float, L: float) -> np.ndarray:
    """Matrice 4x4 de l'élément (y1, θ1, y2, θ2)."""
    c = EI / L**3
    return c * np.array(
        [
            [12.0, 6 * L, -12.0, 6 * L],
            [6 * L, 4 * L * L, -6 * L, 2 * L * L],
            [-12.0, -6 * L, 12.0, -6 * L],
            [6 * L, 2 * L * L, -6 * L, 4 * L * L],
        ]
    )


def assembler(z: np.ndarray, EI_elem: np.ndarray) -> sparse.csc_matrix:
    """Matrice de rigidité globale (2n x 2n) de la poutre libre."""
    n = len(z)
    lignes, colonnes, valeurs = [], [], []
    for e in range(n - 1):
        ke = rigidite_element(EI_elem[e], z[e + 1] - z[e])
        ddl = [2 * e, 2 * e + 1, 2 * e + 2, 2 * e + 3]
        for a in range(4):
            for b in range(4):
                lignes.append(ddl[a])
                colonnes.append(ddl[b])
                valeurs.append(ke[a, b])
    return sparse.csc_matrix((valeurs, (lignes, colonnes)), shape=(2 * n, 2 * n))


def efforts_internes(z: np.ndarray, EI_elem: np.ndarray, u: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Moment et effort tranchant aux deux extrémités de chaque élément.

    Convention (CLAUDE.md) : moment positif quand la face côté fouille est
    tendue, soit M = −EI·d²y/dz² avec y positif vers la fouille.
    Effort tranchant : V = dM/dz (constant par élément, les charges étant
    appliquées aux nœuds).

    Renvoie (z_points, M, V) avec deux points par élément (bas puis haut),
    pour tracer les sauts d'effort tranchant au droit des appuis.
    """
    n = len(z)
    zp = np.empty(2 * (n - 1))
    M = np.empty_like(zp)
    V = np.empty_like(zp)
    for e in range(n - 1):
        L = z[e + 1] - z[e]
        fe = rigidite_element(EI_elem[e], L) @ u[2 * e: 2 * e + 4]
        # fe[1] = −EI·y''(bas) ; fe[3] = EI·y''(haut)
        m_bas, m_haut = fe[1], -fe[3]
        zp[2 * e], zp[2 * e + 1] = z[e], z[e + 1]
        M[2 * e], M[2 * e + 1] = m_bas, m_haut
        V[2 * e] = V[2 * e + 1] = (m_haut - m_bas) / L
    return zp, M, V


def efforts_par_statique(
    z: np.ndarray, zb: np.ndarray, zh: np.ndarray, q: np.ndarray,
    noeud_app: np.ndarray | None = None, F_app: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Moment et effort tranchant par la statique : résultante des charges situées
    au-dessus de la section (définition de résistance des matériaux).

    Les charges du sol et de l'eau sont réparties uniformément sur leur tronçon
    [zb_j, zh_j] (demi-maille), et non concentrées au nœud comme dans le système
    résolu : l'effort tranchant est alors nul aux extrémités libres, ce que la
    concentration aux nœuds ne donne pas (la charge de la demi-maille
    d'extrémité apparaissait comme un saut de V au pied ou en tête).

    q : charge répartie de chaque tronçon (kN/m, positive vers la fouille) ;
    F_app : forces ponctuelles (kN, positives vers la fouille) aux nœuds noeud_app.
    Convention (CLAUDE.md) : V(z) = Σ charges au-dessus de z (positives vers la
    fouille) ; M(z) = −Σ charges × bras de levier, positif quand la face côté
    fouille est tendue (M = −EI·y'' avec y positif vers la fouille).

    Renvoie (z_points, M, V) avec deux points par élément (bas puis haut) ;
    V saute au droit des appuis, M est continu.
    """
    z = np.asarray(z, dtype=float)
    zb, zh, q = (np.asarray(v, dtype=float) for v in (zb, zh, q))
    n = len(z)
    bas = np.maximum(zb[None, :], z[:, None])                 # partie de chaque tronçon au-dessus de z_i
    longueur = np.clip(zh[None, :] - bas, 0.0, None)
    D = longueur @ q                                           # résultante répartie au-dessus de z_i
    bras = 0.5 * ((zh[None, :] - z[:, None]) ** 2 - (bas - z[:, None]) ** 2) * (longueur > 0)
    Mq = bras @ q
    Pa, Ma = np.zeros(n), np.zeros(n)                          # appuis strictement au-dessus du nœud i
    if noeud_app is not None and len(noeud_app):
        for j, F in zip(np.asarray(noeud_app, dtype=int), np.asarray(F_app, dtype=float)):
            Pa[:j] += F
            Ma[:j] += F * (z[j] - z[:j])
    M = -(Mq + Ma)
    zp = np.empty(2 * (n - 1))
    zp[0::2], zp[1::2] = z[:-1], z[1:]
    Mo = np.empty_like(zp)
    Mo[0::2], Mo[1::2] = M[:-1], M[1:]
    V = np.empty_like(zp)
    V[0::2] = D[:-1] + Pa[:-1]    # bas de l'élément e : charges au-dessus du nœud e, appuis aux nœuds > e
    V[1::2] = D[1:] + Pa[:-1]     # haut de l'élément e (sous le nœud e+1) : appuis aux nœuds ≥ e+1
    return zp, Mo, V
