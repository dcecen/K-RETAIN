"""Résolution de l'écoulement permanent en 2D (loi de Darcy, conservation de la
masse) par différences finies sur une grille de cellules, perméabilités
anisotropes par cellule, charges imposées sur des cellules ou des faces.

Équation : div(k · grad h) = 0, discrétisée en volumes finis sur une grille
rectangulaire : la conductance entre deux cellules voisines est la moyenne
harmonique des perméabilités (couches en série) multipliée par la section de
la face et divisée par la distance entre centres. Référence : Bear J. (1972),
*Dynamics of Fluids in Porous Media* ; Harr M.E. (1962), *Groundwater and Seepage*.

Conventions : x horizontal (m), z vertical vers le haut (m), k en m/s,
charge h en m (altitude piézométrique), pression u = γw·(h − z).
Les cellules « inactives » (sol sec, hors domaine) sont ignorées ; une face
« imperméable » a une conductance nulle.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import spsolve


@dataclass
class Grille:
    x: np.ndarray   # faces verticales (nx + 1)
    z: np.ndarray   # faces horizontales (nz + 1)

    def __post_init__(self):
        self.xc = 0.5 * (self.x[1:] + self.x[:-1])
        self.zc = 0.5 * (self.z[1:] + self.z[:-1])
        self.dx = np.diff(self.x)
        self.dz = np.diff(self.z)

    @property
    def forme(self) -> tuple[int, int]:
        return len(self.xc), len(self.zc)

    def flux_face_sup(self, h: np.ndarray, kz: np.ndarray) -> np.ndarray:
        """Débit par mètre à travers la face supérieure de la colonne (m³/s/m, > 0 vers le haut),
        calculé sur la dernière cellule active de chaque colonne à partir de la charge imposée
        sur sa face supérieure (stockée dans `h_face_sup`)."""
        q = np.zeros(len(self.xc))
        for i in range(len(self.xc)):
            j = self._derniere_active[i]
            if j < 0 or np.isnan(self._face_sup[i]):
                continue
            q[i] = -kz[i, j] * (self._face_sup[i] - h[i, j]) / (0.5 * self.dz[j]) * self.dx[i]
        return q


def resoudre_grille(g: Grille, kx: np.ndarray, kz: np.ndarray, fixe: np.ndarray,
                    actif: np.ndarray | None = None, faces_etanches_x: np.ndarray | None = None,
                    face_sup: np.ndarray | None = None, resistance_x: np.ndarray | None = None,
                    charge_face_x: np.ndarray | None = None) -> np.ndarray:
    """Charge h aux centres des cellules.

    fixe[i, j]  : charge imposée dans la cellule (NaN = inconnue). Une charge
                  imposée sur la cellule du haut ou du bas d'une colonne vaut
                  condition de Dirichlet sur la face correspondante (demi-cellule).
    actif[i, j] : cellule participant à l'écoulement (défaut : toutes).
    faces_etanches_x[i, j] : face verticale entre les cellules (i−1, j) et (i, j) étanche
                  (tableau de forme (nx + 1, nz)).
    face_sup[i] : charge imposée sur la face supérieure de la dernière cellule active
                  de la colonne i (NaN = flux nul) ; remplace `fixe` sur cette cellule
                  par une condition sur la face (demi-distance).
    resistance_x[i, j] : résistance hydraulique supplémentaire R = e/k (s) de la face verticale i
                  (écran partiellement étanche), en série avec les demi-cellules voisines :
                  conductance = dz / (d/k_eq + R), loi de Darcy, résistances en série (0 ou NaN = aucune).
    charge_face_x[i, j] : charge imposée sur la face verticale i (NaN = aucune) pour la cellule
                  active qui la borde (demi-cellule, résistance de face en série) : face de
                  suintement d'un écran perméable vers la fouille (h = z, soit u = 0).
    """
    nx, nz = g.forme
    actif = np.ones((nx, nz), bool) if actif is None else actif
    fsup = np.full(nx, np.nan) if face_sup is None else face_sup
    # cellules du haut et du bas d'une colonne avec charge imposée : convertir en face
    fixe = fixe.copy()
    derniere = np.full(nx, -1, int)
    for i in range(nx):
        js = np.where(actif[i])[0]
        if len(js) == 0:
            continue
        derniere[i] = js[-1]
        if not np.isnan(fixe[i, js[-1]]) and np.isnan(fsup[i]):
            fsup[i] = fixe[i, js[-1]]
            fixe[i, js[-1]] = np.nan
    g._face_sup = fsup
    g._derniere_active = derniere
    finf = np.full(nx, np.nan)
    for i in range(nx):
        js = np.where(actif[i])[0]
        if len(js) and not np.isnan(fixe[i, js[0]]) and len(js) > 1:
            finf[i] = fixe[i, js[0]]
            fixe[i, js[0]] = np.nan

    num = -np.ones((nx, nz), int)
    libres = np.argwhere(actif & np.isnan(fixe))
    for n, (i, j) in enumerate(libres):
        num[i, j] = n
    N = len(libres)
    lig, col, val = [], [], []
    b = np.zeros(N)
    diag = np.zeros(N)

    def lien(n, i2, j2, c):
        """Conductance c entre la cellule n et la cellule (i2, j2)."""
        if not actif[i2, j2]:
            return
        m = num[i2, j2]
        if m >= 0:
            lig.append(n); col.append(m); val.append(-c)
        else:
            b[n] += c * fixe[i2, j2]
        diag[n] += c

    for n, (i, j) in enumerate(libres):
        # voisins horizontaux
        for i2 in (i - 1, i + 1):
            face = i if i2 < i else i + 1      # face verticale entre (i2, j) et (i, j) ; 0 et nx : bords du domaine
            if faces_etanches_x is not None and faces_etanches_x[face, j]:
                continue
            R = 0.0 if resistance_x is None or np.isnan(resistance_x[face, j]) else float(resistance_x[face, j])
            if charge_face_x is not None and not np.isnan(charge_face_x[face, j]):
                # charge imposée sur la face (bord du domaine ou face de suintement) : demi-cellule et résistance en série
                c = g.dz[j] / (0.5 * g.dx[i] / kx[i, j] + R)
                diag[n] += c; b[n] += c * charge_face_x[face, j]
                continue
            if not (0 <= i2 < nx) or not actif[i2, j]:
                continue
            d = 0.5 * (g.dx[i] + g.dx[i2])
            k = 2 * kx[i, j] * kx[i2, j] / (kx[i, j] + kx[i2, j])
            lien(n, i2, j, k * g.dz[j] / d if R <= 0 else g.dz[j] / (d / k + R))
        # voisins verticaux
        for j2 in (j - 1, j + 1):
            if 0 <= j2 < nz and actif[i, j2]:
                d = 0.5 * (g.dz[j] + g.dz[j2])
                k = 2 * kz[i, j] * kz[i, j2] / (kz[i, j] + kz[i, j2])
                lien(n, i, j2, k * g.dx[i] / d)
        # faces supérieure / inférieure à charge imposée
        if j == derniere[i] and not np.isnan(fsup[i]):
            c = kz[i, j] * g.dx[i] / (0.5 * g.dz[j])
            diag[n] += c; b[n] += c * fsup[i]
        js = np.where(actif[i])[0]
        if len(js) and j == js[0] and not np.isnan(finf[i]):
            c = kz[i, j] * g.dx[i] / (0.5 * g.dz[j])
            diag[n] += c; b[n] += c * finf[i]
    for n in range(N):
        lig.append(n); col.append(n); val.append(diag[n])
    A = sparse.csc_matrix((val, (lig, col)), shape=(N, N))
    sol = spsolve(A, b) if N else np.zeros(0)
    h = fixe.copy()
    for n, (i, j) in enumerate(libres):
        h[i, j] = sol[n]
    # cellules du bas à charge imposée sur la face : valeur de la face reportée dans fixe pour l'affichage
    for i in range(nx):
        js = np.where(actif[i])[0]
        if len(js) and not np.isnan(finf[i]) and np.isnan(fixe[i, js[0]]):
            pass
    h[~actif] = np.nan
    return h


def isolignes(xc: np.ndarray, zc: np.ndarray, h: np.ndarray, niveaux: list[float]) -> list[dict]:
    """Segments des équipotentielles (marching squares) : [{"niveau", "segments": [[x0,z0,x1,z1], ...]}]."""
    sorties = []
    nx, nz = h.shape
    for niv in niveaux:
        segs = []
        for i in range(nx - 1):
            for j in range(nz - 1):
                c = [h[i, j], h[i + 1, j], h[i + 1, j + 1], h[i, j + 1]]
                if any(np.isnan(v) for v in c):
                    continue
                pts = []
                coins = [(xc[i], zc[j]), (xc[i + 1], zc[j]), (xc[i + 1], zc[j + 1]), (xc[i], zc[j + 1])]
                for k in range(4):
                    a, b2 = c[k], c[(k + 1) % 4]
                    if (a - niv) * (b2 - niv) < 0:
                        t = (niv - a) / (b2 - a)
                        (xa, za), (xb, zb) = coins[k], coins[(k + 1) % 4]
                        pts.append((xa + t * (xb - xa), za + t * (zb - za)))
                if len(pts) >= 2:
                    segs.append([round(pts[0][0], 3), round(pts[0][1], 3), round(pts[1][0], 3), round(pts[1][1], 3)])
                    if len(pts) == 4:
                        segs.append([round(pts[2][0], 3), round(pts[2][1], 3), round(pts[3][0], 3), round(pts[3][1], 3)])
        if segs:
            sorties.append({"niveau": niv, "segments": segs})
    return sorties
