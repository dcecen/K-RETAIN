"""Bouchons de fond de fouille : injecté, jet-grouting, radier lesté, substratum
imperméable (bouchon naturel). Chacun est actif à partir d'une phase donnée.

Épaisseur minimale (soulèvement, EN 1997-1 § 10.2, UPL) : à la base du bouchon,
γ_dst · u ≤ γ_stb · (poids du bouchon + poids sus-jacent) avec, du côté de la
sécurité, u = γw · (h_amont − z_base) (pleine charge amont sous le bouchon) :
    e_min = [γ_dst·γw·(h_amont − z_toit) − γ_stb·W_sus] / (γ_stb·γ_b − γ_dst·γw)
"""
from __future__ import annotations

from dataclasses import dataclass

TYPES = ("injecte", "jet_grouting", "radier_leste", "substratum")


@dataclass(frozen=True)
class Bouchon:
    type: str
    toit: float              # m, cote du toit
    base: float              # m, cote de la base
    k: float | None = None   # m/s, perméabilité (None : imperméable)
    gamma: float = 20.0      # kN/m3, poids volumique du bouchon
    phase: int | str | None = None   # actif à partir de cette phase (indice 1 = première phase, ou nom)
    lest: float = 0.0        # kPa, charge permanente sus-jacente (radier lesté)

    @property
    def epaisseur(self) -> float:
        return self.toit - self.base

    def actif(self, indice_phase: int, nom_phase: str) -> bool:
        """indice_phase : 0 = état initial, 1 = première phase du script."""
        if self.phase is None:
            return True
        if isinstance(self.phase, str):
            return nom_phase == self.phase or indice_phase >= 10**9
        return indice_phase >= int(self.phase)


def epaisseur_minimale(h_amont: float, z_toit: float, gamma_bouchon: float, gamma_w: float,
                       gamma_dst: float, gamma_stb: float, poids_sus: float = 0.0) -> float:
    """Épaisseur minimale e (m) pour le soulèvement du bouchon (voir module)."""
    den = gamma_stb * gamma_bouchon - gamma_dst * gamma_w
    if den <= 0:
        return float("inf")
    e = (gamma_dst * gamma_w * (h_amont - z_toit) - gamma_stb * poids_sus) / den
    return max(e, 0.0)


def correction_contrainte_totale(z, b: Bouchon, couches, z_fond: float, z_nappe_aval, gamma_w: float):
    """Δσv (kPa) à ajouter à la contrainte totale calculée avec le sol seul, côté fouille :
    le poids du bouchon remplace celui du sol dans la zone du bouchon, et le lest s'ajoute
    sous son toit. γ du sol : γ'+γw sous la nappe aval, γ au-dessus."""
    import numpy as np
    from ..sol.couches import indice_couche, trier
    z = np.asarray(z, float)
    tri = trier(couches)
    haut = min(b.toit, z_fond)
    out = np.where(z < haut, b.lest, 0.0)
    if b.type == "substratum":
        return out   # couche naturelle : son poids est déjà celui du sol
    n = 40
    for k, zk in enumerate(z):
        if zk >= haut:
            continue
        bas = max(zk, b.base)
        if bas >= haut:
            continue
        zs = np.linspace(bas, haut, n + 1)
        for z0, z1 in zip(zs[:-1], zs[1:]):
            zm = 0.5 * (z0 + z1)
            c = tri[indice_couche(tri, zm)]
            g_sol = (c.gamma_dejauge + gamma_w) if (z_nappe_aval is not None and zm < z_nappe_aval) else c.gamma
            out[k] += (b.gamma - g_sol) * (z1 - z0)
    return out
