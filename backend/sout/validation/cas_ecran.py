"""Cas élémentaires de l'écran 2D (poutre sur ressorts élasto-plastiques, principe RIDO / K-Réa) :
équilibre limite d'un écran rigide (autostable et ancré en butée simple), équilibre global à chaque
phase, balayages de grandeurs physiques (kh, EI, φ, γ, hauteur d'excavation, raideur et précharge
de l'appui, nappe) avec les monotonies attendues, convergence du maillage."""
from __future__ import annotations

import numpy as np
from scipy.optimize import fsolve

from ..noyau.modele import DefAppui, Ecran, Modele, Phase
from ..noyau.phasage import calculer
from ..sol.couches import Couche
from .cas_elementaires import Cas, Grandeur

GAMMA, PHI = 20.0, 30.0
KA, KP = 1.0 / 3.0, 3.0          # Rankine pour φ = 30° (δ = 0, c = 0) : Ka = tan²(45 − φ/2), Kp = 1/Ka


def _sable(kh=2e4, phi=PHI, gamma=GAMMA) -> Couche:
    return Couche("Sable", 0.0, gamma, gamma - 10.0, phi, c=0.0, kh=kh)


def _bool(libelle: str, condition: bool, source: str) -> Grandeur:
    return Grandeur(libelle, 1.0, 1.0 if condition else 0.0, 0.0, source, echelle=1.0)


# ---------------------------------------------------------------------------
# Équilibre limite d'un écran rigide
# ---------------------------------------------------------------------------
def h_critique_autostable_equilibre_limite(D: float, ka: float, kp: float, gamma: float) -> float:
    """Rupture d'un écran rigide autostable par rotation autour d'un point de profondeur t
    (poussée/butée limites de part et d'autre, inversées sous t) : équilibre des forces et des
    moments (inconnues h et t). Méthode classique de l'écran autostable en sol pulvérulent
    (Costet & Sanglerat, Cours pratique de mécanique des sols ; Craig, Soil Mechanics)."""
    a, b = ka * gamma, kp * gamma

    def eq(x):
        h, t = x
        F = (a * t ** 2 / 2 - b * (t - h) ** 2 / 2 + b * (D ** 2 - t ** 2) / 2 - a * ((D - h) ** 2 - (t - h) ** 2) / 2)

        def I(d1, d2, c):   # ∫ (d − c)·d dd
            return (d2 ** 3 - d1 ** 3) / 3 - c * (d2 ** 2 - d1 ** 2) / 2

        M = (a * t ** 3 / 3 - b * I(h, t, h) + b * (D ** 3 - t ** 3) / 3 - a * I(t, D, h))
        return [F, M]

    h, t = fsolve(eq, [0.5 * D, 0.8 * D])
    assert 0 < h < t < D
    return float(h)


def h_critique_ancre_butee_simple(D: float, ka: float, kp: float, gamma: float) -> tuple[float, float]:
    """Écran rigide ancré en tête, méthode de la butée simple (free earth support) : rotation autour
    de l'ancrage, poussée limite sur toute la hauteur derrière, butée limite sous le fond devant ;
    équilibre des moments autour de l'ancrage => hauteur d'excavation critique h, puis effort
    d'ancrage T = Pa − Pp (Costet & Sanglerat ; Craig, Soil Mechanics, chapitre des écrans ancrés)."""
    Ma = ka * gamma * D ** 3 / 3                         # moment de la poussée autour de la tête

    def Mp(h):                                           # moment de la butée autour de la tête
        return kp * gamma * ((D ** 3 - h ** 3) / 3 - h * (D ** 2 - h ** 2) / 2)

    bas, haut = 0.0, D
    for _ in range(80):
        h = 0.5 * (bas + haut)
        if Mp(h) > Ma:
            bas = h
        else:
            haut = h
    h = 0.5 * (bas + haut)
    T = ka * gamma * D ** 2 / 2 - kp * gamma * (D - h) ** 2 / 2
    return h, T


def _autostable(h: float, D: float = 10.0, EI: float = 1e5, pas: float = 0.1):
    m = Modele(ecran=Ecran(0.0, -D, EI), couches=[_sable()], phases=[Phase("Excavation", excaver=-h)], pas=pas)
    return calculer(m)


def _ancre(h: float, D: float = 12.0, EI: float = 1e9, pas: float = 0.1):
    app = {"A": DefAppui("A", 0.0, 1e6, unilateral=False, infos={"espacement": 1.0})}
    m = Modele(ecran=Ecran(0.0, -D, EI), couches=[_sable()], appuis=app, pas=pas,
               phases=[Phase("Ancrage", poser=["A"]), Phase("Excavation", excaver=-h)])
    return calculer(m)


def _bissection(fonction, bas: float, haut: float, n: int = 18) -> float:
    """Plus grande hauteur d'excavation pour laquelle le calcul trouve un équilibre."""
    for _ in range(n):
        h = 0.5 * (bas + haut)
        if fonction(h).complet:
            bas = h
        else:
            haut = h
    return bas


def autostable_rigide() -> Cas:
    cas = Cas("ecran_autostable_rigide", "ecran", "Écran autostable très raide (EI 1e9) dans un sable φ = 30° : hauteur critique d'excavation")
    D = 10.0
    h_ref = h_critique_autostable_equilibre_limite(D, KA, KP, GAMMA)
    h = _bissection(lambda x: _autostable(x, D=D, EI=1e9, pas=0.1), 1.0, 9.0)
    cas.grandeurs = [Grandeur("hauteur critique", h_ref, h, 2e-2, "équilibre limite rigide-plastique (Ka = 1/3, Kp = 3)", "m")]
    cas.courbes = {"h_ref": h_ref, "h": h}
    return cas


def ecran_ancre_butee_simple() -> Cas:
    cas = Cas("ecran_ancre_butee_simple", "ecran",
              "Écran rigide de 12 m ancré en tête (ancrage très raide) dans un sable φ = 30° : hauteur critique et effort d'ancrage de la butée simple")
    D = 12.0
    h_ref, T_ref = h_critique_ancre_butee_simple(D, KA, KP, GAMMA)
    h = _bissection(lambda x: _ancre(x, D=D), 2.0, 11.5)
    res = _ancre(h, D=D)
    T = res.phases[-1].appuis[0]["effort"]
    cas.grandeurs = [
        Grandeur("hauteur critique d'excavation", h_ref, h, 2e-2, "butée simple (free earth support), Ka = 1/3, Kp = 3", "m"),
        Grandeur("effort d'ancrage à la limite", T_ref, T, 5e-2, "T = Pa − Pp = Ka·γ·D²/2 − Kp·γ·(D − h)²/2", "kN/m"),
    ]
    cas.courbes = {"h_ref": h_ref, "h": h, "T_ref": T_ref, "T": T}
    return cas


# ---------------------------------------------------------------------------
# Écran butonné : équilibre, balayages, convergence
# ---------------------------------------------------------------------------
def _base(kh=2e4, EI=1e5, phi=PHI, gamma=GAMMA, H=6.0, k_app=30000.0, F0=0.0, eau_amont=None, pas=0.1) -> Modele:
    app = {"B": DefAppui("B", -1.0, k_app, precharge=F0, infos={"espacement": 4.0})}
    eau = {"amont": eau_amont, "aval": -H} if eau_amont is not None else {}
    phases = [Phase("Exc1", excaver=-2.0), Phase("Pose", poser=["B"]), Phase("Exc2", excaver=-H, eau=eau)]
    return Modele(ecran=Ecran(0.0, -12.0, EI), couches=[_sable(kh, phi, gamma)], appuis=app, pas=pas, phases=phases)


def _synthese(res) -> dict:
    ph = res.phases[-1]
    return {"y_max_mm": float(np.abs(ph.y).max() * 1e3), "y_vers_fouille_mm": float(ph.y.max() * 1e3),
            "M_max": float(ph.M.max()), "M_min": float(ph.M.min()),
            "V_absmax": float(np.abs(ph.V).max()), "effort_appui": float(ph.appuis[0]["effort"]) if ph.appuis else 0.0}


def _residu_equilibre(ph) -> float:
    """Somme des forces horizontales sur l'écran (sol + eau + appuis), rapportée aux forces brutes."""
    am, av = ph.pressions["amont"], ph.pressions["aval"]
    F = np.sum(am["L"] * am["p"]) - np.sum(av["L"] * av["p"])
    e = ph.eau
    L = np.repeat(np.diff(ph.z) / 2, 2)
    F += np.sum((e["u_amont"] - e["u_aval"]) * L)
    F -= sum(a["effort"] for a in ph.appuis)
    brut = np.sum(am["L"] * np.abs(am["p"])) + np.sum(av["L"] * np.abs(av["p"])) + np.sum(np.abs(e["u_amont"] - e["u_aval"]) * L) \
        + sum(abs(a["effort"]) for a in ph.appuis)
    return float(F / max(brut, 1e-12))


def equilibre_global_par_phase() -> Cas:
    cas = Cas("ecran_equilibre_phases", "ecran", "Écran butonné avec nappe : somme des forces (sol, eau, appui) nulle à chaque phase")
    res = calculer(_base(eau_amont=-3.0))
    for ph in res.phases:
        if ph.ok:
            cas.grandeurs.append(Grandeur(f"résidu relatif des forces — {ph.nom}", 0.0, _residu_equilibre(ph), 1e-6, "statique", "", echelle=1.0))
    cas.grandeurs.append(_bool("pressions toujours entre poussée et butée limites",
                               all(np.all(c["p"] >= c["pa"] - 1e-9) and np.all(c["p"] <= c["pp"] + 1e-9)
                                   for ph in res.phases if ph.ok for c in ph.pressions.values()), "loi des ressorts"))
    cas.courbes = {"phases": [ph.nom for ph in res.phases], "y_max_mm": [float(np.abs(ph.y).max() * 1e3) for ph in res.phases]}
    return cas


def _balayage(nom, titre, parametre, valeurs, constructeur, monotonies, source="physique de l'écran") -> Cas:
    """monotonies : liste de (grandeur, 'croit' | 'decroit')."""
    cas = Cas(nom, "ecran_balayage", titre)
    lignes = []
    for v in valeurs:
        d = {parametre: v}
        d.update(_synthese(calculer(constructeur(v))))
        lignes.append(d)
    for g, sens in monotonies:
        serie = [l[g] for l in lignes]
        ok = all(a <= b + 1e-9 for a, b in zip(serie, serie[1:])) if sens == "croit" else all(a >= b - 1e-9 for a, b in zip(serie, serie[1:]))
        cas.grandeurs.append(_bool(f"{g} {'croît' if sens == 'croit' else 'décroît'} quand {parametre} croît", ok, source))
    cas.courbes = {"parametre": parametre, "tableau": lignes}
    return cas


def balayage_kh() -> Cas:
    return _balayage("balayage_kh", "Coefficient de réaction kh de 10 000 à 80 000 kN/m³", "kh (kN/m³)", [1e4, 2e4, 4e4, 8e4],
                     lambda v: _base(kh=v), [("y_max_mm", "decroit")])


def balayage_EI() -> Cas:
    return _balayage("balayage_EI", "Rigidité de l'écran de 1e4 (palplanches légères) à 1e6 kN·m²/m (paroi moulée)", "EI (kN·m²/m)",
                     [1e4, 1e5, 1e6], lambda v: _base(EI=v), [("y_max_mm", "decroit")])


def balayage_phi() -> Cas:
    return _balayage("balayage_phi", "Angle de frottement de 25 à 40°", "phi (°)", [25.0, 30.0, 35.0, 40.0],
                     lambda v: _base(phi=v), [("y_max_mm", "decroit"), ("effort_appui", "decroit")])


def balayage_gamma() -> Cas:
    return _balayage("balayage_gamma", "Poids volumique de 17 à 21 kN/m³", "gamma (kN/m³)", [17.0, 19.0, 21.0],
                     lambda v: _base(gamma=v), [("y_max_mm", "croit"), ("M_max", "croit"), ("effort_appui", "croit")])


def balayage_hauteur() -> Cas:
    return _balayage("balayage_H", "Hauteur d'excavation finale de 4 à 7 m (fiche de 12 m)", "H (m)", [4.0, 5.0, 6.0, 7.0],
                     lambda v: _base(H=v), [("y_max_mm", "croit"), ("M_max", "croit"), ("effort_appui", "croit")])


def balayage_raideur_appui() -> Cas:
    return _balayage("balayage_k_appui", "Raideur du buton de 3 000 à 3 000 000 kN/m par mètre", "k_appui (kN/m/m)",
                     [3e3, 3e4, 3e5, 3e6], lambda v: _base(k_app=v), [("effort_appui", "croit"), ("y_max_mm", "decroit")])


def balayage_precharge() -> Cas:
    cas = _balayage("balayage_precharge", "Précharge du buton de 0 à 150 kN/m (le déplacement vers la fouille diminue ; "
                    "|y| max peut croître quand l'écran est repoussé vers la terre au niveau du buton)", "precharge (kN/m)",
                    [0.0, 50.0, 100.0, 150.0], lambda v: _base(F0=v), [("y_vers_fouille_mm", "decroit")])
    for v in (50.0, 150.0):
        res = calculer(_base(F0=v))
        cas.grandeurs.append(Grandeur(f"effort après la pose seule = précharge ({v:.0f} kN/m)", v, res.phases[2].appuis[0]["effort"], 1e-6,
                                      "mise en charge au vérin (convention K-Réa)", "kN/m"))
    return cas


def balayage_nappe() -> Cas:
    return _balayage("balayage_nappe", "Nappe amont absente, à −4 m, à −2 m (fouille pompée à −6 m)", "eau amont (m)", [None, -4.0, -2.0],
                     lambda v: _base(eau_amont=v), [("y_max_mm", "croit"), ("effort_appui", "croit")])


def convergence_maillage_2d() -> Cas:
    cas = Cas("ecran_convergence_maillage", "ecran", "Écran butonné : pas du maillage 0,5, 0,2, 0,1, 0,05 m")
    lignes = []
    for pas in (0.5, 0.2, 0.1, 0.05):
        d = {"pas (m)": pas}
        d.update(_synthese(calculer(_base(pas=pas))))
        lignes.append(d)
    ref = lignes[-1]
    cas.grandeurs = [
        Grandeur("y_max au pas 0,1 contre 0,05", ref["y_max_mm"], lignes[2]["y_max_mm"], 1e-2, "convergence", "mm"),
        Grandeur("M_max au pas 0,1 contre 0,05", ref["M_max"], lignes[2]["M_max"], 1e-2, "convergence", "kN·m/m"),
        Grandeur("effort d'appui au pas 0,1 contre 0,05", ref["effort_appui"], lignes[2]["effort_appui"], 1e-2, "convergence", "kN/m"),
    ]
    cas.courbes = {"tableau": lignes}
    return cas


CAS_ECRAN = [autostable_rigide, ecran_ancre_butee_simple, equilibre_global_par_phase, balayage_kh, balayage_EI, balayage_phi,
             balayage_gamma, balayage_hauteur, balayage_raideur_appui, balayage_precharge, balayage_nappe, convergence_maillage_2d]


def cas_ecran() -> list[Cas]:
    return [f() for f in CAS_ECRAN]
