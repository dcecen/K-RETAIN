"""Registre des cas élémentaires : chaque cas est une fonction pure qui construit le modèle,
le calcule et renvoie les grandeurs attendues (formule analytique citée) et calculées.
Les tests de validation (tests/validation) et le rapport (outils.rafale_elementaire) lisent
le même registre : aucune valeur n'est dupliquée.

Convention de signes (CLAUDE.md, sout.noyau.rdm) : axe z le long de la poutre, y positif
dans le sens « vers la fouille », M > 0 quand la face +y est tendue, V = dM/dz = somme des
charges au-dessus de la section. Une poutre « RDM7 » horizontale se lit avec z = x et +y =
sens des charges.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from ..noyau.rdm import PoutreRDM

RDM = "formulaire de RDM (Timoshenko, Résistance des matériaux ; Roark 7e éd., tableau 8.1)"
HETENYI = "Hetényi M. (1946), Beams on Elastic Foundation, chap. II"
EXACT = 1e-9      # cas exacts aux nœuds : seul l'arrondi machine subsiste


@dataclass
class Grandeur:
    libelle: str
    attendu: float
    calcule: float
    tolerance: float          # relative, sauf si echelle est donnée (alors absolue : |écart| ≤ tolerance·echelle)
    source: str = ""
    unite: str = ""
    echelle: float | None = None

    @property
    def ecart(self) -> float:
        if self.echelle is not None:
            return abs(self.calcule - self.attendu) / self.echelle
        return abs(self.calcule - self.attendu) / max(abs(self.attendu), 1e-300)

    @property
    def ok(self) -> bool:
        return self.ecart <= self.tolerance


@dataclass
class Cas:
    nom: str
    famille: str
    description: str
    grandeurs: list[Grandeur] = field(default_factory=list)
    courbes: dict = field(default_factory=dict)   # données pour les figures du rapport (z, y, M, V…)

    @property
    def ok(self) -> bool:
        return all(g.ok for g in self.grandeurs)

    @property
    def ecart_max(self) -> float:
        return max((g.ecart for g in self.grandeurs), default=0.0)


def _controles(cas: Cas, sol, libres: tuple[bool, bool] = (False, False)) -> None:
    """Contrôles de statique communs : équilibre des forces et des moments, V = dM/dz,
    q = dV/dz (élément par élément), V nul aux extrémités libres."""
    c = sol.controles
    cas.grandeurs += [
        Grandeur("équilibre des forces (résidu relatif)", 0.0, c["residu_forces"], 1e-9, "statique", echelle=1.0),
        Grandeur("équilibre des moments (résidu relatif)", 0.0, c["residu_moments"], 1e-9, "statique", echelle=1.0),
        Grandeur("V = dM/dz (écart relatif max)", 0.0, c["V_egale_dM_dz"], 1e-9, "RDM", echelle=1.0),
        Grandeur("q = dV/dz (écart relatif max)", 0.0, c["q_egale_dV_dz"], 1e-9, "RDM", echelle=1.0),
    ]
    vmax = max(float(np.abs(sol.V).max()), float(c["echelle_forces"]), 1e-12)
    if libres[0]:
        cas.grandeurs.append(Grandeur("V nul à l'extrémité libre z = 0", 0.0, float(sol.V[0]), 1e-8, "statique", "kN", echelle=vmax))
    if libres[1]:
        cas.grandeurs.append(Grandeur("V nul à l'extrémité libre z = L", 0.0, float(sol.V[-1]), 1e-8, "statique", "kN", echelle=vmax))
    cas.courbes = {"z": sol.z.tolist(), "y": sol.y.tolist(), "z_diag": sol.z_diag.tolist(), "M": sol.M.tolist(), "V": sol.V.tolist()}


def _val(sol, z: float, quoi: str, cote: str = "bas") -> float:
    """Valeur de M ou V au point du diagramme à la cote z (côté bas ou haut d'un nœud)."""
    tab = sol.M if quoi == "M" else sol.V
    idx = np.flatnonzero(np.abs(sol.z_diag - z) < 1e-9)
    if len(idx) == 0:
        idx = [int(np.argmin(np.abs(sol.z_diag - z)))]
    return float(tab[idx[0] if cote == "bas" else idx[-1]])


# ---------------------------------------------------------------------------
# Poutres sans sol (type RDM7)
# ---------------------------------------------------------------------------
L, EI, P, Q, C0 = 6.0, 2.0e5, 10.0, 5.0, 12.0


def console_force_en_bout() -> Cas:
    cas = Cas("console_force", "poutres", "Console encastrée en z = 0, force P en bout (z = L)")
    s = PoutreRDM(L, EI, 0.1).encastrement(0.0).force(L, P).resoudre()
    cas.grandeurs = [
        Grandeur("flèche en bout", P * L ** 3 / (3 * EI), float(s.y[-1]), EXACT, "PL³/3EI, " + RDM, "m"),
        Grandeur("rotation en bout", P * L ** 2 / (2 * EI), float(s.theta[-1]), EXACT, "PL²/2EI", "rad"),
        Grandeur("moment à l'encastrement", -P * L, _val(s, 0.0, "M"), EXACT, "−PL (face chargée comprimée)", "kN·m"),
        Grandeur("effort tranchant", P, _val(s, L / 2, "V"), EXACT, "V = P", "kN"),
        Grandeur("réaction à l'encastrement", P, s.reactions[0][0], EXACT, "ΣF = 0", "kN"),
        Grandeur("couple d'encastrement (valeur absolue)", P * L, abs(s.reactions[0][1]), EXACT, "ΣM = 0", "kN·m"),
        Grandeur("V juste sous la force en bout", P, _val(s, L, "V", "haut"), EXACT, "V = P jusqu'au point d'application", "kN"),
    ]
    _controles(cas, s)
    return cas


def console_charge_repartie() -> Cas:
    cas = Cas("console_repartie", "poutres", "Console encastrée en z = 0, charge uniforme q (charges nodales cohérentes)")
    s = PoutreRDM(L, EI, 0.1).encastrement(0.0).repartie(0.0, L, Q).resoudre()
    cas.grandeurs = [
        Grandeur("flèche en bout", Q * L ** 4 / (8 * EI), float(s.y[-1]), EXACT, "qL⁴/8EI, " + RDM, "m"),
        Grandeur("rotation en bout", Q * L ** 3 / (6 * EI), float(s.theta[-1]), EXACT, "qL³/6EI", "rad"),
        Grandeur("moment à l'encastrement", -Q * L ** 2 / 2, _val(s, 0.0, "M"), EXACT, "−qL²/2", "kN·m"),
        Grandeur("effort tranchant à l'encastrement", Q * L, _val(s, 0.0, "V"), EXACT, "qL", "kN"),
    ]
    _controles(cas, s, (False, True))
    return cas


def console_charges_nodales_concentrees() -> Cas:
    """Même console, mais avec la charge concentrée aux nœuds comme le fait le moteur de production
    pour le sol et l'eau : mesure de l'erreur de discrétisation (O(h²)) au pas 0,1 m."""
    cas = Cas("console_repartie_nodale", "poutres",
              "Console sous charge uniforme, charges concentrées aux nœuds (comme le moteur, pas 0,1 m) : erreur mesurée")
    s = PoutreRDM(L, EI, 0.1).encastrement(0.0).repartie(0.0, L, Q).resoudre(coherentes=False)
    cas.grandeurs = [
        Grandeur("flèche en bout", Q * L ** 4 / (8 * EI), float(s.y[-1]), 1e-3, "qL⁴/8EI (charges nodales : erreur O(h²))", "m"),
        Grandeur("moment à l'encastrement", -Q * L ** 2 / 2, _val(s, 0.0, "M"), EXACT, "−qL² /2 (statique exacte)", "kN·m"),
    ]
    _controles(cas, s, (False, True))
    return cas


def biappuyee_charge_repartie() -> Cas:
    cas = Cas("biappuyee_repartie", "poutres", "Poutre sur deux appuis simples, charge uniforme q")
    s = PoutreRDM(L, EI, 0.1).appui_simple(0.0).appui_simple(L).repartie(0.0, L, Q).resoudre()
    i = int(np.argmin(np.abs(s.z - L / 2)))
    cas.grandeurs = [
        Grandeur("flèche au milieu", 5 * Q * L ** 4 / (384 * EI), float(s.y[i]), EXACT, "5qL⁴/384EI, " + RDM, "m"),
        Grandeur("moment au milieu", Q * L ** 2 / 8, _val(s, L / 2, "M"), EXACT, "qL²/8", "kN·m"),
        Grandeur("réaction en z = 0", Q * L / 2, s.reactions[0][0], EXACT, "qL/2", "kN"),
        Grandeur("réaction en z = L", Q * L / 2, s.reactions[len(s.z) - 1][0], EXACT, "qL/2", "kN"),
        Grandeur("effort tranchant à l'appui z = 0", Q * L / 2, _val(s, 0.0, "V"), EXACT, "qL/2", "kN"),
        Grandeur("rotation à l'appui", Q * L ** 3 / (24 * EI), float(s.theta[0]), EXACT, "qL³/24EI", "rad"),
    ]
    _controles(cas, s)
    return cas


def biappuyee_force_au_milieu() -> Cas:
    cas = Cas("biappuyee_ponctuelle_centre", "poutres", "Poutre sur deux appuis, force P au milieu")
    s = PoutreRDM(L, EI, 0.1, cotes=[L / 2]).appui_simple(0.0).appui_simple(L).force(L / 2, P).resoudre()
    i = int(np.argmin(np.abs(s.z - L / 2)))
    cas.grandeurs = [
        Grandeur("flèche au milieu", P * L ** 3 / (48 * EI), float(s.y[i]), EXACT, "PL³/48EI, " + RDM, "m"),
        Grandeur("moment au milieu", P * L / 4, _val(s, L / 2, "M"), EXACT, "PL/4", "kN·m"),
        Grandeur("réactions", P / 2, s.reactions[0][0], EXACT, "P/2", "kN"),
        Grandeur("saut de V au droit de P", P, _val(s, L / 2, "V", "bas") - _val(s, L / 2, "V", "haut"), EXACT, "ΔV = P", "kN"),
    ]
    _controles(cas, s)
    return cas


def biappuyee_force_excentree() -> Cas:
    a = L / 3
    b = L - a
    cas = Cas("biappuyee_ponctuelle_excentree", "poutres", "Poutre sur deux appuis, force P en z = a = L/3")
    s = PoutreRDM(L, EI, 0.1, cotes=[a]).appui_simple(0.0).appui_simple(L).force(a, P).resoudre()
    i = int(np.argmin(np.abs(s.z - a)))
    cas.grandeurs = [
        Grandeur("moment sous la charge", P * a * b / L, _val(s, a, "M"), EXACT, "Pab/L, " + RDM, "kN·m"),
        Grandeur("réaction en z = 0", P * b / L, s.reactions[0][0], EXACT, "Pb/L", "kN"),
        Grandeur("réaction en z = L", P * a / L, s.reactions[len(s.z) - 1][0], EXACT, "Pa/L", "kN"),
        Grandeur("flèche sous la charge", P * a ** 2 * b ** 2 / (3 * EI * L), float(s.y[i]), EXACT, "Pa²b²/3EIL", "m"),
    ]
    _controles(cas, s)
    return cas


def biappuyee_charge_triangulaire() -> Cas:
    """Charge hydrostatique : q(z) = q0·z/L, nulle en z = 0, maximale en z = L."""
    cas = Cas("biappuyee_triangulaire", "poutres", "Poutre sur deux appuis, charge triangulaire (hydrostatique) de 0 à q0")
    q0 = Q
    s = PoutreRDM(L, EI, 0.02).appui_simple(0.0).appui_simple(L).repartie_lineaire(0.0, L, 0.0, q0).resoudre()
    zmax = L / math.sqrt(3)
    cas.grandeurs = [
        Grandeur("réaction côté charge nulle (z = 0)", q0 * L / 6, s.reactions[0][0], 1e-4, "q0·L/6, " + RDM, "kN"),
        Grandeur("réaction côté charge maximale (z = L)", q0 * L / 3, s.reactions[len(s.z) - 1][0], 1e-4, "q0·L/3", "kN"),
        Grandeur("moment maximal", q0 * L ** 2 / (9 * math.sqrt(3)), float(s.M.max()), 1e-4, "q0·L²/(9√3) en z = L/√3", "kN·m"),
        Grandeur("position du moment maximal", zmax, float(s.z_diag[int(np.argmax(s.M))]), 1e-2, "L/√3", "m"),
    ]
    _controles(cas, s)
    return cas


def biencastree_charge_repartie() -> Cas:
    cas = Cas("biencastree_repartie", "poutres", "Poutre encastrée aux deux extrémités, charge uniforme q")
    s = PoutreRDM(L, EI, 0.1).encastrement(0.0).encastrement(L).repartie(0.0, L, Q).resoudre()
    i = int(np.argmin(np.abs(s.z - L / 2)))
    cas.grandeurs = [
        Grandeur("moment aux encastrements", -Q * L ** 2 / 12, _val(s, 0.0, "M"), EXACT, "−qL²/12, " + RDM, "kN·m"),
        Grandeur("moment au milieu", Q * L ** 2 / 24, _val(s, L / 2, "M"), EXACT, "qL²/24", "kN·m"),
        Grandeur("flèche au milieu", Q * L ** 4 / (384 * EI), float(s.y[i]), EXACT, "qL⁴/384EI", "m"),
        Grandeur("réactions", Q * L / 2, s.reactions[0][0], EXACT, "qL/2", "kN"),
    ]
    _controles(cas, s)
    return cas


def encastree_appuyee_charge_repartie() -> Cas:
    cas = Cas("encastree_appuyee_repartie", "poutres", "Poutre encastrée en z = 0 et appuyée en z = L, charge uniforme q")
    s = PoutreRDM(L, EI, 0.1, cotes=[5 * L / 8]).encastrement(0.0).appui_simple(L).repartie(0.0, L, Q).resoudre()
    cas.grandeurs = [
        Grandeur("réaction à l'appui simple", 3 * Q * L / 8, s.reactions[len(s.z) - 1][0], EXACT, "3qL/8, " + RDM, "kN"),
        Grandeur("réaction à l'encastrement", 5 * Q * L / 8, s.reactions[0][0], EXACT, "5qL/8", "kN"),
        Grandeur("moment à l'encastrement", -Q * L ** 2 / 8, _val(s, 0.0, "M"), EXACT, "−qL²/8", "kN·m"),
        Grandeur("moment positif maximal", 9 * Q * L ** 2 / 128, float(s.M.max()), EXACT, "9qL²/128 en z = 5L/8", "kN·m"),
    ]
    _controles(cas, s)
    return cas


def continue_deux_travees() -> Cas:
    cas = Cas("continue_2_travees", "poutres", "Poutre continue sur trois appuis (deux travées égales L), charge uniforme q")
    s = (PoutreRDM(2 * L, EI, 0.1, cotes=[L, 3 * L / 8, 2 * L - 3 * L / 8]).appui_simple(0.0).appui_simple(L)
         .appui_simple(2 * L).repartie(0.0, 2 * L, Q).resoudre())
    n = len(s.z) - 1
    i_mid = int(np.argmin(np.abs(s.z - L)))
    cas.grandeurs = [
        Grandeur("réaction d'extrémité", 3 * Q * L / 8, s.reactions[0][0], EXACT, "3qL/8 (trois moments), " + RDM, "kN"),
        Grandeur("réaction centrale", 10 * Q * L / 8, s.reactions[i_mid][0], EXACT, "10qL/8", "kN"),
        Grandeur("réaction d'extrémité (z = 2L)", 3 * Q * L / 8, s.reactions[n][0], EXACT, "3qL/8", "kN"),
        Grandeur("moment sur l'appui central", -Q * L ** 2 / 8, _val(s, L, "M"), EXACT, "−qL²/8", "kN·m"),
        Grandeur("moment positif maximal en travée", 9 * Q * L ** 2 / 128, float(s.M.max()), EXACT, "9qL²/128 en 3L/8", "kN·m"),
    ]
    _controles(cas, s)
    return cas


def continue_trois_travees() -> Cas:
    cas = Cas("continue_3_travees", "poutres", "Poutre continue sur quatre appuis (trois travées égales L), charge uniforme q")
    s = (PoutreRDM(3 * L, EI, 0.1, cotes=[L, 2 * L]).appui_simple(0.0).appui_simple(L).appui_simple(2 * L)
         .appui_simple(3 * L).repartie(0.0, 3 * L, Q).resoudre())
    i1, i2 = int(np.argmin(np.abs(s.z - L))), int(np.argmin(np.abs(s.z - 2 * L)))
    cas.grandeurs = [
        Grandeur("réaction d'extrémité", 0.4 * Q * L, s.reactions[0][0], EXACT, "0,4·qL (trois moments), " + RDM, "kN"),
        Grandeur("réaction intermédiaire", 1.1 * Q * L, s.reactions[i1][0], EXACT, "1,1·qL", "kN"),
        Grandeur("moment sur appui intermédiaire", -Q * L ** 2 / 10, _val(s, L, "M"), EXACT, "−qL²/10", "kN·m"),
        Grandeur("moment sur le second appui intermédiaire", -Q * L ** 2 / 10, _val(s, 2 * L, "M"), EXACT, "−qL²/10", "kN·m"),
        Grandeur("moment positif maximal (travée de rive)", 0.08 * Q * L ** 2, float(s.M.max()), EXACT, "0,08·qL² en 0,4L", "kN·m"),
    ]
    assert i2 in s.reactions
    _controles(cas, s)
    return cas


def console_avec_ressort_en_bout() -> Cas:
    k = 3 * EI / L ** 3      # ressort de même raideur que la console : la force se partage par moitié
    cas = Cas("console_ressort_bout", "poutres", "Console encastrée en z = 0, ressort k en bout, force P en bout")
    s = PoutreRDM(L, EI, 0.1).encastrement(0.0).ressort(L, k_y=k).force(L, P).resoudre()
    y = P / (k + 3 * EI / L ** 3)
    cas.grandeurs = [
        Grandeur("flèche en bout", y, float(s.y[-1]), EXACT, "P/(k + 3EI/L³) : raideurs en parallèle", "m"),
        Grandeur("effort dans le ressort", k * y, float(-s.forces_ressorts[-1]), EXACT, "k·y = P/2", "kN"),
        Grandeur("moment à l'encastrement", -(P - k * y) * L, _val(s, 0.0, "M"), EXACT, "−(P − k·y)·L", "kN·m"),
    ]
    _controles(cas, s)
    return cas


def biappuyee_avec_ressort_central() -> Cas:
    a = L / 2
    k = 2.0e4
    cas = Cas("biappuyee_ressort_central", "poutres", "Poutre sur deux appuis (portée 2a), ressort k au milieu, charge uniforme q")
    s = PoutreRDM(L, EI, 0.1, cotes=[a]).appui_simple(0.0).appui_simple(L).ressort(a, k_y=k).repartie(0.0, L, Q).resoudre()
    d0 = 5 * Q * L ** 4 / (384 * EI)              # flèche sans ressort
    f = L ** 3 / (48 * EI)                        # souplesse au milieu sous une force unité
    Rc = d0 / (1 / k + f)                         # compatibilité : d0 − f·Rc = Rc/k
    i = int(np.argmin(np.abs(s.z - a)))
    s_inf = PoutreRDM(L, EI, 0.1, cotes=[a]).appui_simple(0.0).appui_simple(L).ressort(a, k_y=1e12).repartie(0.0, L, Q).resoudre()
    cas.grandeurs = [
        Grandeur("effort dans le ressort", Rc, float(-s.forces_ressorts[i]), 1e-7, "δ₀/(1/k + L³/48EI), δ₀ = 5qL⁴/384EI (compatibilité ; 1e-7 : conditionnement)", "kN"),
        Grandeur("flèche au milieu", Rc / k, float(s.y[i]), 1e-7, "R_c/k", "m"),
        Grandeur("limite ressort infiniment raide = appui central", 10 * Q * a / 8, float(-s_inf.forces_ressorts[i]), 1e-6,
                 "10·q·a/8 (poutre continue à deux travées a)", "kN"),
    ]
    _controles(cas, s)
    return cas


def couple_applique_au_milieu() -> Cas:
    cas = Cas("couple_milieu", "poutres", "Poutre sur deux appuis, couple C appliqué au milieu")
    s = PoutreRDM(L, EI, 0.1, cotes=[L / 2]).appui_simple(0.0).appui_simple(L).couple(L / 2, C0).resoudre()
    i = int(np.argmin(np.abs(s.z - L / 2)))
    cas.grandeurs = [
        Grandeur("saut de M au droit du couple", C0, abs(_val(s, L / 2, "M", "haut") - _val(s, L / 2, "M", "bas")), EXACT, "ΔM = C, " + RDM, "kN·m"),
        Grandeur("effort tranchant (constant)", C0 / L, abs(_val(s, L / 4, "V")), EXACT, "|V| = C/L", "kN"),
        Grandeur("réactions opposées", C0 / L, abs(s.reactions[0][0]), EXACT, "|R| = C/L", "kN"),
        Grandeur("flèche au milieu (antisymétrie)", 0.0, float(s.y[i]), EXACT, "0", "m", echelle=float(np.abs(s.y).max())),
        Grandeur("rotation aux appuis", C0 * L / (24 * EI), abs(float(s.theta[0])), EXACT, "C·L/24EI", "rad"),
        Grandeur("rotation sous le couple", C0 * L / (12 * EI), abs(float(s.theta[i])), EXACT, "C·L/12EI", "rad"),
        Grandeur("moment nul aux appuis", 0.0, abs(_val(s, 0.0, "M")) + abs(_val(s, L, "M", "haut")), EXACT, "appuis simples", "kN·m", echelle=C0),
    ]
    _controles(cas, s)
    return cas


# ---------------------------------------------------------------------------
# Poutres sur fondation de Winkler (Hetényi)
# ---------------------------------------------------------------------------
def _winkler(longueur: float = 60.0, EIw: float = 1.0e4, k: float = 2000.0, pas: float = 0.05) -> tuple[PoutreRDM, float]:
    lam = (k / (4 * EIw)) ** 0.25
    assert lam * longueur > 4 * math.pi
    return PoutreRDM(longueur, EIw, pas).ressorts_repartis(k), lam


def winkler_semi_infinie_force_en_bout() -> Cas:
    cas = Cas("winkler_semi_infinie_force", "poutres_winkler", "Poutre semi-infinie sur fondation de Winkler, force P à l'extrémité libre")
    p, lam = _winkler()
    k = 2000.0
    s = p.force(0.0, P).resoudre()
    zM = math.pi / (4 * lam)
    cas.grandeurs = [
        Grandeur("flèche sous la force", 2 * P * lam / k, float(s.y[0]), 1e-2, "y₀ = 2Pλ/k, λ = (k/4EI)^¼, " + HETENYI, "m"),
        Grandeur("moment maximal (en z = π/4λ)", -0.3224 * P / lam, _val(s, zM, "M"), 1e-2, "−0,3224·P/λ : M = −(P/λ)·e^(−λz)·sin λz", "kN·m"),
        Grandeur("moment nul à l'extrémité libre", 0.0, _val(s, 0.0, "M"), 1e-3, "extrémité libre (réaction du sol répartie sur la demi-bande d'extrémité : écart en (λh)²)", "kN·m", echelle=P / lam),
    ]
    _controles(cas, s, (False, True))
    return cas


def winkler_semi_infinie_couple_en_bout() -> Cas:
    cas = Cas("winkler_semi_infinie_couple", "poutres_winkler", "Poutre semi-infinie sur fondation de Winkler, couple C à l'extrémité libre")
    p, lam = _winkler()
    k = 2000.0
    s = p.couple(0.0, C0).resoudre()
    cas.grandeurs = [
        Grandeur("flèche à l'extrémité (valeur absolue)", 2 * C0 * lam ** 2 / k, abs(float(s.y[0])), 1e-2, "|y₀| = 2Cλ²/k, " + HETENYI, "m"),
        Grandeur("moment à l'extrémité (valeur absolue)", C0, abs(_val(s, 0.0, "M", "bas")), 1e-3, "|M(0)| = C (écart en (λh)², réaction répartie sur la demi-bande d'extrémité)", "kN·m"),
    ]
    _controles(cas, s, (False, True))
    return cas


def winkler_infinie_force() -> Cas:
    cas = Cas("winkler_infinie_force", "poutres_winkler", "Poutre infinie sur fondation de Winkler, force P au milieu")
    p, lam = _winkler(longueur=80.0)
    k = 2000.0
    s = p.force(40.0, P).resoudre()
    i = int(np.argmin(np.abs(s.z - 40.0)))
    cas.grandeurs = [
        Grandeur("flèche sous la force", P * lam / (2 * k), float(s.y[i]), 1e-2, "y₀ = Pλ/2k, " + HETENYI, "m"),
        Grandeur("moment sous la force", P / (4 * lam), _val(s, 40.0, "M"), 1e-2, "M₀ = +P/4λ (face chargée tendue sous la force)", "kN·m"),
    ]
    _controles(cas, s, (True, True))
    return cas


def winkler_charge_uniforme() -> Cas:
    cas = Cas("winkler_uniforme", "poutres_winkler",
              "Poutre sur fondation de Winkler, charge uniforme q : tassement uniforme sans flexion (charges nodales "
              "concentrées, comme le moteur : avec les charges cohérentes, le couple qL²/12 des éléments d'extrémité "
              "crée une couche limite de 1e-7 relatif)")
    p, _ = _winkler()
    k = 2000.0
    s = p.repartie(0.0, 60.0, Q).resoudre(coherentes=False)
    cas.grandeurs = [
        Grandeur("flèche uniforme", Q / k, float(s.y.mean()), 1e-9, "y = q/k", "m"),
        Grandeur("flèche uniforme (écart max)", 0.0, float(np.abs(s.y - Q / k).max()), 1e-9, "y = q/k partout", "m", echelle=Q / k),
        Grandeur("moment nul", 0.0, float(np.abs(s.M).max()), 1e-8, "M = 0 (arrondi sur 1 200 éléments)", "kN·m", echelle=Q * 60.0 ** 2 / 8),
    ]
    _controles(cas, s, (True, True))
    return cas


CAS_POUTRES = [
    console_force_en_bout, console_charge_repartie, console_charges_nodales_concentrees,
    biappuyee_charge_repartie, biappuyee_force_au_milieu, biappuyee_force_excentree, biappuyee_charge_triangulaire,
    biencastree_charge_repartie, encastree_appuyee_charge_repartie, continue_deux_travees, continue_trois_travees,
    console_avec_ressort_en_bout, biappuyee_avec_ressort_central, couple_applique_au_milieu,
    winkler_semi_infinie_force_en_bout, winkler_semi_infinie_couple_en_bout, winkler_infinie_force, winkler_charge_uniforme,
]


def cas_poutres() -> list[Cas]:
    return [f() for f in CAS_POUTRES]


REGISTRE = {"poutres": cas_poutres}
