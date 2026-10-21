"""Couches de sol horizontales et contraintes verticales.

Repère : cote z en mètres, axe vertical vers le haut.
Unités : kN/m3, kPa, degrés.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Couche:
    """Couche de sol horizontale, définie par la cote de son toit.

    La couche s'étend du toit jusqu'au toit de la couche suivante
    (la dernière couche est supposée se prolonger indéfiniment).
    """

    nom: str
    toit: float                 # m (cote du toit)
    gamma: float                # kN/m3, poids volumique hors nappe
    gamma_dejauge: float        # kN/m3, poids volumique déjaugé (sous nappe)
    phi: float                  # degrés, angle de frottement effectif φ'
    c: float = 0.0              # kPa, cohésion effective c'
    EM: float | None = None     # kPa, module pressiométrique
    alpha: float | None = None  # -, coefficient rhéologique de Ménard
    pl: float | None = None     # kPa, pression limite
    qc: float | None = None     # kPa, résistance de pointe CPT
    EM_sur_qc: float | None = None  # -, corrélation qc -> EM choisie par l'utilisateur
    kh: float | None = None     # kN/m3, coefficient de réaction imposé (sinon Schmitt)
    K0: float | None = None     # -, coefficient des terres au repos imposé (sinon Jaky)
    delta_a_sur_phi: float = 0.0  # -, obliquité côté poussée δa/φ'
    delta_p_sur_phi: float = 0.0  # -, obliquité côté butée |δp|/φ'
    coef_decharge: float | None = None  # -, coefficient appliqué aux variations de σ'v (défaut K0)
    k_h: float | None = None    # m/s, perméabilité horizontale (écoulement)
    k_v: float | None = None    # m/s, perméabilité verticale (défaut k_h)
    cu: float | None = None     # kPa, cohésion non drainée (stabilité du fond en argile)
    sol_lane: str | None = None # type de sol pour le coefficient de Lane (clé de docs/normes/hydraulique.yaml)


def trier(couches: list[Couche]) -> list[Couche]:
    """Couches triées du haut vers le bas (toit décroissant)."""
    return sorted(couches, key=lambda c: -c.toit)


def indice_couche(couches_triees: list[Couche], z: float) -> int:
    """Indice (dans la liste triée) de la couche qui contient la cote z.

    Au-dessus du toit de la première couche, renvoie 0 (la première couche).
    """
    for i in range(len(couches_triees) - 1, -1, -1):
        if z <= couches_triees[i].toit + 1e-12:
            return i
    return 0


def contraintes_verticales(
    z: np.ndarray,
    z_terrain: float,
    z_nappe: float | None,
    couches: list[Couche],
    gamma_w: float,
    surcharge: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Contrainte verticale effective σ'v(z) et pression d'eau u(z), régime hydrostatique.

    σ'v = Σ γ·dz au-dessus de la nappe + Σ γ'·dz sous la nappe (contrainte
    effective de Terzaghi, γ' = poids volumique déjaugé).
    u = γw · (z_nappe − z) sous la nappe, 0 au-dessus (hydrostatique).
    Au-dessus du terrain, σ'v = 0. La surcharge Δσv (kPa) éventuelle s'ajoute
    à σ'v sous le terrain.

    Renvoie (sigma_v_eff, u) en kPa.
    """
    z = np.asarray(z, dtype=float)
    triees = trier(couches)
    zn = -np.inf if z_nappe is None else z_nappe
    ruptures = sorted(
        {c.toit for c in triees if c.toit < z_terrain} | ({zn} if zn < z_terrain else set()),
        reverse=True,
    )
    sv = np.zeros_like(z)
    for k, zk in enumerate(z):
        if zk >= z_terrain:
            continue
        haut = z_terrain
        total = 0.0
        for r in ruptures + [zk]:
            bas = max(r, zk)
            if bas >= haut:
                continue
            milieu = 0.5 * (haut + bas)
            couche = triees[indice_couche(triees, milieu)]
            g = couche.gamma_dejauge if milieu < zn else couche.gamma
            total += g * (haut - bas)
            haut = bas
            if bas <= zk:
                break
        sv[k] = total
    if z_nappe is None:
        u = np.zeros_like(z)
    else:
        u = np.where(z < zn, gamma_w * (zn - z), 0.0)
    if surcharge is not None:
        sv = sv + np.where(z < z_terrain, surcharge, 0.0)
    return sv, u


def contraintes_totales(z, z_terrain, z_nappe, couches, gamma_w, surcharge=None):
    """Contrainte verticale totale σv(z) = σ'v hydrostatique + u hydrostatique (kPa)."""
    sv, u = contraintes_verticales(z, z_terrain, z_nappe, couches, gamma_w, surcharge)
    return sv + u
