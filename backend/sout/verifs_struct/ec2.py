"""Formules de béton armé (EN 1992-1-1). Coefficients lus dans docs/normes/ec2.yaml.

- Flexion simple, section rectangulaire, diagramme rectangulaire (§ 3.1.7) :
  bloc comprimé de hauteur λ·x et de contrainte η·fcd ; fcd = αcc·fck/γc ;
  fyd = fyk/γs ; pivot de rupture béton εcu3. Équilibre : η·fcd·b·λx = As·fyd,
  bras de levier z = d − λx/2.
- Section circulaire à armatures réparties : intégration numérique de
  l'équilibre (mêmes lois), effort normal nul.
- Effort tranchant sans armatures transversales (§ 6.2.2) :
  VRd,c = [C_Rd,c·k·(100·ρl·fck)^(1/3)]·bw·d ≥ v_min·bw·d, k = 1 + √(200/d[mm]).
Unités : M en kN·m, dimensions en m, contraintes en MPa, As en cm².
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class Materiaux:
    fck: float        # MPa
    fyk: float        # MPa
    gamma_c: float
    gamma_s: float
    alpha_cc: float
    lam: float        # λ
    eta: float        # η
    eps_cu3: float    # ‰
    Es: float         # MPa

    @property
    def fcd(self) -> float:
        return self.alpha_cc * self.fck / self.gamma_c

    @property
    def fyd(self) -> float:
        return self.fyk / self.gamma_s

    @property
    def x_lim_sur_d(self) -> float:
        """Axe neutre limite pour que l'acier atteigne fyd (pivot béton) : εcu3/(εcu3 + εyd)."""
        eps_yd = self.fyd / self.Es * 1000
        return self.eps_cu3 / (self.eps_cu3 + eps_yd)


def flexion_rectangulaire(M_kNm: float, b: float, d: float, mat: Materiaux) -> dict:
    """Section d'acier tendu requise (cm²) et taux d'utilisation du béton comprimé."""
    M = abs(M_kNm) * 1e-3  # MN·m
    fcd = mat.fcd
    mu = M / (b * d**2 * fcd)
    mu_lim = mat.eta * mat.lam * mat.x_lim_sur_d * (1 - mat.lam * mat.x_lim_sur_d / 2)
    disc = 1 - 2 * mu / mat.eta
    if disc < 0:
        return {"mu": mu, "mu_lim": mu_lim, "As_cm2": math.inf, "x_sur_d": math.inf}
    lx = d * (1 - math.sqrt(disc))
    if mu > mu_lim:
        # acier non plastifié : pas de section d'acier tendu seule qui convienne
        return {"mu": mu, "mu_lim": mu_lim, "As_cm2": math.inf, "x_sur_d": lx / mat.lam / d}
    As = mat.eta * fcd * b * lx / mat.fyd * 1e4
    return {"mu": mu, "mu_lim": mu_lim, "As_cm2": As, "x_sur_d": lx / mat.lam / d}


def m_rd_rectangulaire(As_cm2: float, b: float, d: float, mat: Materiaux) -> float:
    """Moment résistant (kN·m) d'une section rectangulaire d'armatures tendues As.
    Si l'axe neutre dépasse la limite de plastification de l'acier, il est plafonné
    à x_lim (moment du béton seul à cet axe : valeur du côté de la sécurité)."""
    As = As_cm2 * 1e-4
    lx = As * mat.fyd / (mat.eta * mat.fcd * b)
    lx = min(lx, mat.lam * mat.x_lim_sur_d * d)
    return mat.eta * mat.fcd * b * lx * (d - lx / 2) * 1e3


def m_rd_circulaire(D: float, As_cm2: float, r_s: float, mat: Materiaux, n_barres: int = 24) -> float:
    """Moment résistant (kN·m) d'une section circulaire de diamètre D, armatures As
    réparties sur un cercle de rayon r_s (effort normal nul)."""
    R = D / 2
    a_barre = As_cm2 * 1e-4 / n_barres
    angles = [2 * math.pi * k / n_barres for k in range(n_barres)]
    ys = [r_s * math.cos(t) for t in angles]  # ordonnée depuis le centre, positive vers la fibre comprimée
    fcd, fyd, Es = mat.fcd, mat.fyd, mat.Es
    ecu = mat.eps_cu3 / 1000

    def efforts(x: float) -> tuple[float, float]:
        # béton : segment circulaire de hauteur λx depuis la fibre supérieure
        h = min(mat.lam * x, D)
        th = 2 * math.acos(max(-1.0, min(1.0, (R - h) / R)))
        Ac = R**2 / 2 * (th - math.sin(th))
        yc = 4 * R * math.sin(th / 2) ** 3 / (3 * (th - math.sin(th))) if th > 1e-9 else R
        Nc = mat.eta * fcd * Ac
        Mc = Nc * yc
        Ns, Ms = 0.0, 0.0
        for y in ys:
            eps = ecu * (x - (R - y)) / x
            sig = max(-fyd, min(fyd, Es * eps))
            Ns += sig * a_barre
            Ms += sig * a_barre * y
        return Nc + Ns, Mc + Ms

    bas, haut = 1e-4 * D, 3 * D
    for _ in range(80):
        x = 0.5 * (bas + haut)
        N, _ = efforts(x)
        if N > 0:
            haut = x
        else:
            bas = x
    return efforts(0.5 * (bas + haut))[1] * 1e3


def as_circulaire(M_kNm: float, D: float, r_s: float, mat: Materiaux) -> float:
    """Section d'armatures (cm²) requise pour M dans une section circulaire (∞ si impossible)."""
    M = abs(M_kNm)
    haut = math.pi * D**2 / 4 * 1e4 * 0.08  # borne de recherche numérique (8 % de la section), pas une valeur normative
    if m_rd_circulaire(D, haut, r_s, mat) < M:
        return math.inf
    bas = 0.0
    for _ in range(60):
        a = 0.5 * (bas + haut)
        if m_rd_circulaire(D, a, r_s, mat) >= M:
            haut = a
        else:
            bas = a
    return haut


def v_rd_c(bw: float, d: float, As_cm2: float, fck: float, gamma_c: float, C_Rd_c: float,
           coef_v_min: float, k_max: float, rho_l_max: float) -> float:
    """VRd,c (kN) — EN 1992-1-1 § 6.2.2 (1), sans effort normal."""
    d_mm = d * 1000
    k = min(1 + math.sqrt(200 / d_mm), k_max)
    rho = min(As_cm2 * 1e-4 / (bw * d), rho_l_max)
    v = C_Rd_c * k * (100 * rho * fck) ** (1 / 3)
    v_min = coef_v_min * k**1.5 * fck**0.5
    return max(v, v_min) * bw * d * 1e3
