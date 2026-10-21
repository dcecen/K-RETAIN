"""Ressorts élasto-plastiques sol-écran (loi d'interaction de la méthode aux
coefficients de réaction, principe de RIDO et K-Réa).

Référence générale : Delattre L. (2001), « Un siècle de méthodes de calcul
d'écrans de soutènement. II. Les méthodes aux coefficients de réaction »,
Bulletin des laboratoires des Ponts et Chaussées n° 234.

Pour chaque ressort (une demi-maille de sol d'un côté de l'écran) :

    p = borne( p_ref + s·kh·(y − y_ref) ,  pa , pp )

- s = −1 côté amont (terre soutenue) : la pression baisse quand l'écran
  s'éloigne du sol (y > 0, vers la fouille) ;
- s = +1 côté aval (fouille) : la pression augmente quand l'écran pousse le sol.
- (y_ref, p_ref) est un point de la droite élastique ; il est mis à jour en fin
  de phase (mémoire de l'état, décharge et rechargement élastiques avec la
  pente kh, palier plastique sur pa ou pp).

Force exercée sur l'écran (kN par mètre linéaire d'écran, positive vers la
fouille) : f = −s · A · p, où A = longueur tributaire × largeur de réaction.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

AMONT = -1
AVAL = +1


@dataclass
class Ressorts:
    noeud: np.ndarray   # indice du nœud porteur
    s: np.ndarray       # −1 amont, +1 aval
    A: np.ndarray       # m (longueur tributaire × largeur relative)
    kh: np.ndarray      # kN/m3
    p_ref: np.ndarray   # kPa
    y_ref: np.ndarray   # m
    pa: np.ndarray      # kPa, pression limite de poussée
    pp: np.ndarray      # kPa, pression limite de butée

    @classmethod
    def vide(cls) -> "Ressorts":
        z = np.zeros(0)
        return cls(np.zeros(0, dtype=int), z, z, z, z, z, z, z)

    def __len__(self) -> int:
        return len(self.noeud)

    def pressions(self, y_noeuds: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Pression p (kPa) et statut (−1 sur pa, 0 élastique, +1 sur pp)."""
        y = y_noeuds[self.noeud]
        p_el = self.p_ref + self.s * self.kh * (y - self.y_ref)
        p = np.clip(p_el, self.pa, self.pp)
        statut = np.where(p_el <= self.pa, -1, np.where(p_el >= self.pp, 1, 0))
        return p, statut

    def forces_et_raideurs(self, y_noeuds: np.ndarray, n: int) -> tuple[np.ndarray, np.ndarray]:
        """Force nodale sur l'écran et raideur tangente (par nœud)."""
        p, statut = self.pressions(y_noeuds)
        f = np.bincount(self.noeud, weights=-self.s * self.A * p, minlength=n)
        k = np.bincount(self.noeud, weights=np.where(statut == 0, self.A * self.kh, 0.0), minlength=n)
        return f, k

    def memoriser(self, y_noeuds: np.ndarray) -> None:
        """Fin de phase : la droite élastique passe par l'état atteint."""
        p, _ = self.pressions(y_noeuds)
        self.p_ref = p
        self.y_ref = y_noeuds[self.noeud].copy()
