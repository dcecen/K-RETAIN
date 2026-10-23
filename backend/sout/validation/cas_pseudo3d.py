"""Cas élémentaires du pseudo-3D : « coupes 2D assemblées » (Ds = 0) contre vraie plaque, balayages
de la rigidité horizontale, de l'espacement des butons, de la longueur, du pas, des bords, des
liernes, et fouille fermée (double écran). Mêmes modèles que les tests unitaires, exposés au rapport."""
from __future__ import annotations

import numpy as np

from ..noyau.modele import DefAppui, Ecran, Modele, Phase
from ..noyau.phasage import calculer
from ..pseudo3d.calcul import MoteurPseudo3D
from ..sol.couches import Couche
from ..sol.terrain import SurchargePlan
from .cas_elementaires import Cas, Grandeur

SABLE = Couche("Sable", 0.0, 20, 10, 32, EM=12000, alpha=1 / 3)
RECT = [[0.0, 0.0], [20.0, 0.0], [20.0, 12.0], [0.0, 12.0]]
E_HEB400 = 210000e3 * 57680.5253806435e-8   # kN·m² (base DEMO)


def _modele(espacement=4.0, raideur=30000.0, precharge=20.0, EI_lierne=None, appuis=True, type_="buton"):
    infos = {"espacement": espacement, "symetrique": True, "type": type_}
    if EI_lierne is not None:
        infos["EI_lierne"] = EI_lierne
    app = {"B": DefAppui("B", -1.0, raideur, precharge=precharge, type=type_, infos=infos)} if appuis else {}
    phases = [Phase("Exc1", excaver=-2.0), Phase("Pose", poser=list(app)), Phase("Exc2", excaver=-6.0)]
    return Modele(ecran=Ecran(0.0, -12.0, 1e5), couches=[SABLE], appuis=app, pas=0.25, phases=phases)


def _bool(libelle: str, condition: bool, source: str) -> Grandeur:
    return Grandeur(libelle, 1.0, 1.0 if condition else 0.0, 0.0, source, echelle=1.0)


def rigidite_horizontale_bandes_2d_contre_plaque() -> Cas:
    """Paroi de 48 m, butons tous les 4 m : Ds/Dz de 0 (bandes 2D indépendantes) à 1 (plaque isotrope)."""
    cas = Cas("p3d_rigidite_horizontale", "pseudo3d",
              "Paroi droite 48 m, butons tous les 4 m, rapport Ds/Dz de 0 à 1 : des coupes 2D assemblées à la vraie plaque")
    m = _modele()
    r2 = calculer(m).phases[-1]
    r2s = calculer(_modele(appuis=False)).phases[-1]
    y_avec, y_sans, H2 = float(np.abs(r2.y).max()), float(np.abs(r2s.y).max()), r2.appuis[0]["effort"]
    lignes = []
    profils = {}
    for rap in (0.0, 1e-3, 1e-2, 0.1, 1.0):
        mo = MoteurPseudo3D(m, 48.0, 1.0, rapport_rigidite_horizontale=rap)
        ph = mo.calculer().phases[-1]
        prof = np.abs(ph.W).max(axis=1)
        inter = slice(8, -8)
        eff = float(np.mean([a["effort"] for a in ph.appuis[3:-3]]))
        lignes.append({"Ds/Dz": rap, "y_max_mm": float(prof.max() * 1e3), "y_min_interieur_mm": float(prof[inter].min() * 1e3),
                       "rapport_max_min": float(prof[inter].max() / prof[inter].min()), "Mz_max": float(ph.Mz.max()),
                       "Ms_absmax": float(np.abs(ph.Ms).max()), "effort_par_buton_kN": eff, "effort_sur_H2D_e": eff / (H2 * 4.0)})
        j = int(np.argmin(np.abs(mo.z + 1.0)))
        profils[rap] = (ph.W[:, j] * 1e3).tolist()
    l0, l1 = lignes[0], lignes[-1]
    cas.grandeurs = [
        Grandeur("Ds = 0 : ligne sans buton = écran 2D sans appui", y_sans, l0["y_max_mm"] / 1e3, 1e-6, "coupes 2D indépendantes", "m"),
        _bool("Ds = 0 : rapport max/min > 3 (chaque buton ne retient que sa ligne)", l0["rapport_max_min"] > 3.0, "bandes indépendantes"),
        _bool("Ds = Dz : rapport max/min < 1,3 (la plaque redistribue)", l1["rapport_max_min"] < 1.3, "plaque isotrope"),
        _bool("Ds = Dz : déplacement encadré par le 2D à appui réparti et la bande libre",
              0.9 * y_avec <= l1["y_min_interieur_mm"] / 1e3 and l1["y_max_mm"] / 1e3 <= y_sans, "encadrement physique"),
        Grandeur("Ds = Dz : effort par buton / (H_2D · e)", 1.0, l1["effort_sur_H2D_e"], 0.05, "paroi longue ≈ 2D", ""),
        _bool("le déplacement maximal décroît quand Ds/Dz croît", all(a["y_max_mm"] >= b["y_max_mm"] - 1e-9 for a, b in zip(lignes, lignes[1:])), "monotonie"),
    ]
    cas.courbes = {"tableau": lignes, "s": mo.s.tolist(), "profils_mm": {str(k): v for k, v in profils.items()},
                   "y_2d_appui_reparti_mm": y_avec * 1e3, "y_2d_sans_appui_mm": y_sans * 1e3}
    return cas


def espacement_des_butons() -> Cas:
    cas = Cas("p3d_espacement", "pseudo3d", "Paroi isotrope 48 m : espacement des butons 2, 4, 6, 8 m (même raideur par buton)")
    lignes = []
    for e in (2.0, 4.0, 6.0, 8.0):
        m = _modele(espacement=e)
        ph = MoteurPseudo3D(m, 48.0, 1.0).calculer().phases[-1]
        H2 = calculer(m).phases[-1].appuis[0]["effort"]
        prof = np.abs(ph.W).max(axis=1)[8:-8]
        eff = float(np.mean([a["effort"] for a in ph.appuis[1:-1]])) if len(ph.appuis) > 2 else float(ph.appuis[0]["effort"])
        lignes.append({"espacement_m": e, "y_max_mm": float(prof.max() * 1e3), "rapport_max_min": float(prof.max() / prof.min()),
                       "Ms_absmax": float(np.abs(ph.Ms).max()), "effort_par_buton_kN": eff, "effort_sur_H2D_e": eff / (H2 * e)})
    cas.grandeurs = [
        _bool("le déplacement entre butons croît avec l'espacement", all(a["y_max_mm"] <= b["y_max_mm"] + 1e-9 for a, b in zip(lignes, lignes[1:])), "monotonie"),
        _bool("la variation le long de la paroi croît avec l'espacement", all(a["rapport_max_min"] <= b["rapport_max_min"] + 1e-9 for a, b in zip(lignes, lignes[1:])), "monotonie"),
        Grandeur("effort par buton / (H_2D · e) à 4 m", 1.0, lignes[1]["effort_sur_H2D_e"], 0.05, "paroi longue ≈ 2D", ""),
    ]
    cas.courbes = {"tableau": lignes}
    return cas


def longueur_de_paroi() -> Cas:
    cas = Cas("p3d_longueur", "pseudo3d", "Paroi isotrope à bords libres, butons tous les 4 m : longueur 12, 24, 48, 96 m")
    m = _modele()
    y2 = float(np.abs(calculer(m).phases[-1].y).max())
    lignes = []
    for L in (12.0, 24.0, 48.0, 96.0):
        mo = MoteurPseudo3D(m, L, 1.0)
        ph = mo.calculer().phases[-1]
        ic = len(mo.s) // 2
        lignes.append({"longueur_m": L, "y_centre_mm": float(np.abs(ph.W[ic - 2:ic + 3]).max() * 1e3), "y_max_mm": float(np.abs(ph.W).max() * 1e3),
                       "y_2d_mm": y2 * 1e3})
    cas.grandeurs = [Grandeur(f"déplacement au centre / 2D pour {l['longueur_m']:.0f} m", 1.0, l["y_centre_mm"] / (y2 * 1e3), 0.05,
                              "loin des bords la plaque retrouve le 2D", "") for l in lignes if l["longueur_m"] >= 24]
    cas.courbes = {"tableau": lignes}
    return cas


def convergence_du_pas_horizontal() -> Cas:
    cas = Cas("p3d_convergence", "pseudo3d",
              "Paroi 24 m, butons tous les 4 m : pas horizontal 1, 0,5 et 0,25 m, sans et avec largeur_appui = 2 m")
    m = _modele()
    lignes = []
    for larg in (None, 2.0):
        for pas in (1.0, 0.5, 0.25):
            mo = MoteurPseudo3D(m, 24.0, pas, largeur_appui=larg)
            ph = mo.calculer().phases[-1]
            j = int(np.argmin(np.abs(mo.z + 1.0)))
            a = ph.appuis[2]
            i = int(np.argmin(np.abs(mo.s - a["s"])))
            lignes.append({"largeur_appui_m": larg or 0.0, "pas_m": pas, "y_max_mm": float(np.abs(ph.W).max() * 1e3),
                           "Mz_max": float(ph.Mz.max()), "Ms_au_buton": float(ph.Ms[i, j]), "V_absmax": float(np.abs(ph.V_diag).max())})
    p, l = lignes[:3], lignes[3:]
    cas.grandeurs = [
        Grandeur("y_max : pas 0,5 contre 0,25 (ponctuel)", p[1]["y_max_mm"], p[2]["y_max_mm"], 1e-2, "convergence", "mm"),
        Grandeur("Mz max : pas 0,5 contre 0,25 (ponctuel)", p[1]["Mz_max"], p[2]["Mz_max"], 1e-2, "convergence", "kN·m/m"),
        _bool("sans largeur d'appui, V au droit du buton croît sans limite (singularité)", p[2]["V_absmax"] > 1.6 * p[1]["V_absmax"], "charge concentrée sur une plaque"),
        Grandeur("avec largeur_appui 2 m : Ms au buton, pas 0,5 contre 0,25", l[1]["Ms_au_buton"], l[2]["Ms_au_buton"], 0.05, "convergence", "kN·m/m"),
        Grandeur("avec largeur_appui 2 m : V max, pas 0,5 contre 0,25", l[1]["V_absmax"], l[2]["V_absmax"], 0.02, "convergence", "kN/m"),
    ]
    cas.courbes = {"tableau": lignes}
    return cas


def conditions_aux_bords() -> Cas:
    cas = Cas("p3d_bords", "pseudo3d", "Paroi isotrope de 20 m : bords libres, appuyés, encastrés")
    m = _modele()
    lignes = []
    for bords in ("libres", "appuyes", "encastres"):
        ph = MoteurPseudo3D(m, 20.0, 1.0, bords=bords).calculer().phases[-1]
        lignes.append({"bords": bords, "y_max_mm": float(np.abs(ph.W).max() * 1e3), "Mz_max": float(ph.Mz.max()),
                       "Ms_absmax": float(np.abs(ph.Ms).max()), "reactions_bords_kN": float(ph.bilan["reactions"])})
    y = [l["y_max_mm"] for l in lignes]
    cas.grandeurs = [_bool("y_max : libres > appuyés > encastrés", y[0] > y[1] > y[2], "plus le bord retient, moins la paroi bouge"),
                     _bool("réactions de bords nulles à bords libres", lignes[0]["reactions_bords_kN"] == 0.0, "statique")]
    cas.courbes = {"tableau": lignes}
    return cas


def liernes_sur_palplanches() -> Cas:
    cas = Cas("p3d_liernes", "pseudo3d", "Palplanches (Ds = 0), butons tous les 6 m : sans lierne, lierne HEB 400, lierne très raide")
    lignes = []
    for nom, EI in (("sans", None), ("HEB 400", E_HEB400), ("très raide (1e9)", 1e9)):
        m = _modele(espacement=6.0, EI_lierne=EI)
        ph = MoteurPseudo3D(m, 48.0, 1.0, rapport_rigidite_horizontale=0.0).calculer().phases[-1]
        prof = np.abs(ph.W).max(axis=1)[6:-6]
        li = ph.liernes.get("B")
        lignes.append({"lierne": nom, "y_max_mm": float(prof.max() * 1e3), "rapport_max_min": float(prof.max() / prof.min()),
                       "M_lierne_max": float(np.abs(li["M"]).max()) if li else 0.0,
                       "effort_buton_kN": float(np.mean([a["effort"] for a in ph.appuis[2:-2]]))})
    y2 = float(np.abs(calculer(_modele(espacement=6.0)).phases[-1].y).max())
    cas.grandeurs = [
        _bool("sans lierne : les butons ne retiennent que leur ligne (max/min > 3)", lignes[0]["rapport_max_min"] > 3.0, "Ds = 0"),
        _bool("HEB 400 : la lierne redistribue (max/min < 1,5)", lignes[1]["rapport_max_min"] < 1.5, "poutre horizontale continue"),
        Grandeur("lierne très raide : déplacement = 2D à appui réparti", y2 * 1e3, lignes[2]["y_max_mm"], 1e-3, "n·e = L", "mm"),
    ]
    cas.courbes = {"tableau": lignes}
    return cas


def fouille_fermee_double_ecran() -> Cas:
    cas = Cas("p3d_fouille_fermee", "pseudo3d",
              "Fouille fermée 20 × 12 m : liens ≡ ressorts L/2 si tout est symétrique ; grue de 3 000 kN derrière la paroi sud")
    m = _modele()
    liens = MoteurPseudo3D(m, None, 1.0, contour=RECT, liens=True).calculer().phases[-1]
    sol = MoteurPseudo3D(m, None, 1.0, contour=RECT, liens=False).calculer().phases[-1]
    Q = SurchargePlan(nom="grue", type="ponctuelle", q=3000.0, position=(10.0, -3.0), cote_ecran="amont")
    mq = Modele(ecran=Ecran(0.0, -12.0, 1e5), couches=[SABLE], appuis=m.appuis, pas=0.25, surcharges=[Q], phases=m.phases)
    charge = MoteurPseudo3D(mq, None, 1.0, contour=RECT).calculer().phases[-1]
    charge_sol = MoteurPseudo3D(mq, None, 1.0, contour=RECT, liens=False).calculer().phases[-1]
    e_l = {a["s"]: a["effort"] for a in liens.appuis}
    e_q = {a["s"]: a["effort"] for a in charge.appuis}
    nord = slice(32, 53)
    d_liens = float(np.abs(charge.W[nord] - liens.W[nord]).max())
    d_sol = float(np.abs(charge_sol.W[nord] - sol.W[nord]).max())
    cas.grandeurs = [
        Grandeur("symétrique : écart liens / ressorts L/2 (relatif)", 0.0, float(np.abs(liens.W - sol.W).max() / np.abs(sol.W).max()), 1e-6, "équivalence", "", echelle=1.0),
        _bool("angles : quatre lignes de réaction", len(np.flatnonzero(np.abs(liens.reactions).sum(axis=1) > 0)) == 4, "w = 0 aux sommets"),
        Grandeur("grue : effort du buton au droit de la charge / sans charge", 1.13, e_q[10.0] / e_l[10.0], 0.05, "transmission par le buton (+13 % sur ce cas)", ""),
        _bool("grue : la paroi nord recule vers sa terre au droit du buton", np.abs(charge.W[42]).max() < np.abs(liens.W[42]).max(), "double écran"),
        _bool("grue : effet sur la paroi nord par les butons ≥ 5 × la diffusion directe de Boussinesq", d_liens > 5 * d_sol, "double écran"),
        Grandeur("équilibre global (résidu relatif)", 0.0, abs(charge.bilan["residu"]) / charge.bilan["echelle"], 1e-6, "statique", "", echelle=1.0),
    ]
    cas.courbes = {"s": list(range(64)), "W_sud_mm": (np.abs(charge.W[0:21]).max(axis=1) * 1e3).tolist(),
                   "W_sud_sans_mm": (np.abs(liens.W[0:21]).max(axis=1) * 1e3).tolist(),
                   "W_nord_mm": (charge.W[32:53, int(np.argmin(np.abs(np.linspace(0, -12, charge.W.shape[1]) + 1.0)))] * 1e3).tolist(),
                   "W_nord_sans_mm": (liens.W[32:53, int(np.argmin(np.abs(np.linspace(0, -12, liens.W.shape[1]) + 1.0)))] * 1e3).tolist(),
                   "efforts_avec": e_q, "efforts_sans": e_l}
    return cas


CAS_PSEUDO3D_RAPIDES = [rigidite_horizontale_bandes_2d_contre_plaque, fouille_fermee_double_ecran]
CAS_PSEUDO3D = [rigidite_horizontale_bandes_2d_contre_plaque, espacement_des_butons, longueur_de_paroi,
                convergence_du_pas_horizontal, conditions_aux_bords, liernes_sur_palplanches, fouille_fermee_double_ecran]


def cas_pseudo3d(rapide: bool = False) -> list[Cas]:
    return [f() for f in (CAS_PSEUDO3D_RAPIDES if rapide else CAS_PSEUDO3D)]
