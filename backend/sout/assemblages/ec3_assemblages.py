"""Formules de résistance des assemblages acier (EN 1993-1-8, EN 1993-1-5) et de
compression localisée du béton (EN 1992-1-1 § 6.7).

Toutes les valeurs numériques normatives (γM, k2, αv, βw, fub, constantes des
formules d'interaction et d'axes) sont lues dans docs/normes/ec3_assemblages.yaml ;
les expressions ci-dessous sont celles des articles cités. Unités : kN, mm, MPa.
"""
from __future__ import annotations

import math

from ..verifs import Lecteur


def _cl(classe: str) -> str:
    """Clé YAML d'une classe de boulon : « 8.8 » -> « 8_8 » (le point sépare les niveaux du fichier)."""
    return str(classe).replace(".", "_")


def aire_boulon(d: float) -> float:
    """Aire brute de la tige A = π·d²/4 (mm²)."""
    return math.pi * d * d / 4


def aire_resistante(d: float, lect: Lecteur) -> float | None:
    """Section résistante As (mm²) du boulon, lue dans la table des diamètres (EN ISO 898-1)."""
    return lect.v("ec3_assemblages", f"boulons.As.M{int(d)}")


def diametre_trou(d: float, lect: Lecteur) -> float | None:
    """Diamètre du trou d0 = d + jeu nominal (EN 1090-2, jeu selon le diamètre)."""
    jeu = lect.v("ec3_assemblages", "boulons.jeu_trou_M16_M24" if d <= 24 else "boulons.jeu_trou_sup_M24")
    return None if jeu is None else d + jeu


def ft_rd(d: float, classe: str, lect: Lecteur) -> float | None:
    """Résistance en traction d'un boulon Ft,Rd = k2·fub·As/γM2 — EN 1993-1-8 tableau 3.4 (kN)."""
    k2 = lect.v("ec3_assemblages", "boulons.k2")
    fub = lect.v("ec3_assemblages", f"boulons.fub.{_cl(classe)}")
    gM2 = lect.v("ec3_assemblages", "gamma_M2")
    As = aire_resistante(d, lect)
    if None in (k2, fub, gM2, As):
        return None
    return k2 * fub * As / gM2 / 1000


def fv_rd(d: float, classe: str, lect: Lecteur, filetage_dans_plan: bool = True) -> float | None:
    """Résistance au cisaillement par plan Fv,Rd = αv·fub·A/γM2 — EN 1993-1-8 tableau 3.4 (kN)."""
    av = lect.v("ec3_assemblages", f"boulons.alpha_v.{_cl(classe)}")
    fub = lect.v("ec3_assemblages", f"boulons.fub.{_cl(classe)}")
    gM2 = lect.v("ec3_assemblages", "gamma_M2")
    A = aire_resistante(d, lect) if filetage_dans_plan else aire_boulon(d)
    if None in (av, fub, gM2, A):
        return None
    return av * fub * A / gM2 / 1000


def fb_rd(d: float, t: float, fu: float, classe: str, e1: float, e2: float, p1: float | None, lect: Lecteur) -> float | None:
    """Pression diamétrale Fb,Rd = k1·αb·fu·d·t/γM2 — EN 1993-1-8 tableau 3.4 (kN).
    αb = min(e1/3d0, p1/3d0 − 1/4, fub/fu, 1) ; k1 = min(2,8·e2/d0 − 1,7 ; 2,5) (boulons de rive)."""
    d0 = diametre_trou(d, lect)
    fub = lect.v("ec3_assemblages", f"boulons.fub.{_cl(classe)}")
    gM2 = lect.v("ec3_assemblages", "gamma_M2")
    if None in (d0, fub, gM2):
        return None
    ab = min(e1 / (3 * d0), fub / fu, 1.0)
    if p1 is not None:
        ab = min(ab, p1 / (3 * d0) - 0.25)
    k1 = min(2.8 * e2 / d0 - 1.7, 2.5)
    return max(k1, 0.0) * max(ab, 0.0) * fu * d * t / gM2 / 1000


def bp_rd(d: float, tp: float, fu: float, lect: Lecteur) -> float | None:
    """Poinçonnement Bp,Rd = c_p·π·dm·tp·fu/γM2 — EN 1993-1-8 tableau 3.4 (kN) ; dm = diamètre moyen de la tête."""
    cp = lect.v("ec3_assemblages", "boulons.coef_poinconnement")
    dm = lect.v("ec3_assemblages", f"boulons.dm.M{int(d)}")
    gM2 = lect.v("ec3_assemblages", "gamma_M2")
    if None in (cp, dm, gM2):
        return None
    return cp * math.pi * dm * tp * fu / gM2 / 1000


def interaction_boulon(Fv_Ed: float, Fv_Rd: float, Ft_Ed: float, Ft_Rd: float, lect: Lecteur) -> float | None:
    """Fv,Ed/Fv,Rd + Ft,Ed/(c·Ft,Rd) ≤ 1 — EN 1993-1-8 tableau 3.4 (c lu dans la norme)."""
    c = lect.v("ec3_assemblages", "boulons.coef_interaction")
    if c is None or Fv_Rd <= 0 or Ft_Rd <= 0:
        return None
    return Fv_Ed / Fv_Rd + Ft_Ed / (c * Ft_Rd)


def fw_rd(a: float, fu: float, nuance: str, lect: Lecteur) -> float | None:
    """Résistance d'une soudure d'angle par unité de longueur, méthode simplifiée :
    Fw,Rd = a·fu/(√3·βw·γM2) — EN 1993-1-8 § 4.5.3.3 (kN/mm)."""
    bw = lect.v("ec3_assemblages", f"soudures.beta_w.{nuance}")
    gM2 = lect.v("ec3_assemblages", "gamma_M2")
    if None in (bw, gM2):
        return None
    return a * fu / (math.sqrt(3) * bw * gM2) / 1000


def m_pl_plaque(t: float, fy: float, lect: Lecteur) -> float | None:
    """Moment plastique d'une plaque par unité de largeur mpl = t²·fy/(4·γM0) (kN·mm/mm)."""
    gM0 = lect.v("ec3_assemblages", "gamma_M0")
    return None if gM0 is None else t * t * fy / (4 * gM0) / 1000


def n_pl(A_mm2: float, fy: float, lect: Lecteur) -> float | None:
    """Résistance plastique d'une section en traction/compression N = A·fy/γM0 (kN)."""
    gM0 = lect.v("ec3_assemblages", "gamma_M0")
    return None if gM0 is None else A_mm2 * fy / gM0 / 1000


def v_pl(Av_mm2: float, fy: float, lect: Lecteur) -> float | None:
    """Résistance plastique au cisaillement V = Av·fy/(√3·γM0) (kN) — EN 1993-1-1 § 6.2.6."""
    gM0 = lect.v("ec3_assemblages", "gamma_M0")
    return None if gM0 is None else Av_mm2 * fy / (math.sqrt(3) * gM0) / 1000


def axe(d: float, fyp: float, fup: float, t_oeil: float, fy_oeil: float, lect: Lecteur) -> dict | None:
    """Axe d'articulation — EN 1993-1-8 § 3.13.2, tableau 3.10 : cisaillement Fv,Rd = c_v·A·fup/γM2,
    pression diamétrale Fb,Rd = c_b·t·d·fy/γM0, flexion MRd = c_m·Wel·fyp/γM0 (kN, kN·mm)."""
    cv = lect.v("ec3_assemblages", "axes.coef_cisaillement")
    cb = lect.v("ec3_assemblages", "axes.coef_pression")
    cm = lect.v("ec3_assemblages", "axes.coef_flexion")
    gM0 = lect.v("ec3_assemblages", "gamma_M0")
    gM2 = lect.v("ec3_assemblages", "gamma_M2")
    if None in (cv, cb, cm, gM0, gM2):
        return None
    A = aire_boulon(d)
    Wel = math.pi * d**3 / 32
    return {"Fv_Rd": cv * A * fup / gM2 / 1000, "Fb_Rd": cb * t_oeil * d * fy_oeil / gM0 / 1000,
            "M_Rd": cm * Wel * fyp / gM0 / 1000}


def ame_charge_transversale(fyw: float, tw: float, ss: float, tf: float, r: float, lect: Lecteur) -> float | None:
    """Résistance de l'âme sous charge transversale, forme simplifiée : FRd = fyw·tw·(ss + c·(tf + r))/γM1
    — EN 1993-1-5 § 6 (longueur efficace ℓy approchée, χF = 1 : méthode simplifiée à confirmer)."""
    c = lect.v("ec3_assemblages", "ame.coef_diffusion")
    gM1 = lect.v("ec3_assemblages", "gamma_M1")
    if None in (c, gM1):
        return None
    return fyw * tw * (ss + c * (tf + r)) / gM1 / 1000


def compression_localisee_beton(fck: float, Ac0: float, Ac1: float, lect: Lecteur) -> float | None:
    """FRdu = Ac0·fcd·√(Ac1/Ac0) ≤ c·fcd·Ac0 — EN 1992-1-1 § 6.7 (kN), fcd = αcc·fck/γc (mm², MPa)."""
    gc = lect.v("ec2", "gamma_c")
    acc = lect.v("ec2", "alpha_cc")
    cmax = lect.v("ec3_assemblages", "beton.coef_max_compression_localisee")
    if None in (gc, acc, cmax):
        return None
    fcd = acc * fck / gc
    return min(Ac0 * fcd * math.sqrt(Ac1 / Ac0), cmax * fcd * Ac0) / 1000
