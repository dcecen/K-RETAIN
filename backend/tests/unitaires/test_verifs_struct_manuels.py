"""Contrôles à la main des vérifications structurelles (critère de fin du jalon J6 : chaque
vérification correspond à un calcul manuel de référence) et branchement sur le pseudo-3D.

Coefficients : VALEURS DE TEST (NORMES_TEST / NORMES_TEST_EC2 de test_verifs_struct.py), base
matériaux DEMO. Chaque attendu est écrit en clair avec sa chaîne de calcul ; les grandeurs de la
base (A, I, W, masse, fy…) sont relues pour que la chaîne reste lisible, les résultats finaux sont
aussi comparés à des littéraux calculés à la main (garde contre une erreur d'unité).
"""
import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from sout.materiaux.base import catalogue_par_defaut
from sout.parois import construire_ecran
from sout.script.lecteur import lire_script
from sout.script.schema import Appui, Paroi
from sout.verifications import executer
from sout.verifs_struct import ec2
from sout.verifs_struct.elements import (_barre, _blindage, _dalle, _efforts_appuis_3d, _lierne, _tirant,
                                         section_element, verifier_appuis, verifier_paroi)
from test_verifs_struct import NORMES_TEST, NORMES_TEST_EC2

RACINE = Path(__file__).resolve().parents[3]
CAT = catalogue_par_defaut()
CLE = "ELU_fondamental"
G_EFF = 1.35


def test_buton_modulaire_flambement_temperature_et_poids_propre():
    """Tube 508 × 12,5 (A 194,6 cm², I 59 755 cm⁴, W 2 353 cm³, 153,3 kg/m, S355, E 210 GPa), L = 16 m,
    N_k = 1 000 kN, ΔT 10 °C bridé à 50 % :
    ΔN_T = 0,5·1,2e-5·10·E·A = 245,2 kN ; N_Ed = 1,35·1 245,2 = 1 681,0 kN ;
    N_cr = π²·E·I/L² = 4 837,9 kN ; N_pl = 6 908,3 kN ; λ̄ = 1,195 ; Φ = 1,3185 ; χ(a) = 0,5332 ;
    N_b,Rd = 3 683,4 kN ; q = 1,504 kN/m ; M_Ed = 1,35·q·L²/8·1/(1 − N_Ed/N_cr) = 99,6 kN·m ;
    M_c,Rd = W·fy/γM0 = 835,3 kN·m ; taux = 0,4564 + 0,1192 = 0,5756."""
    sec = section_element("modulaire_A", None, CAT)
    taux, detail, lect = _barre(sec, 1000.0, 16.0, 0.0, NORMES_TEST, CLE)
    assert not lect.manquants
    A, I, W, m_, fy, E = sec["A_cm2"], sec["I_cm4"], sec["W_cm3"], sec["masse_kg_m"], sec["fy"], sec["E"]
    dN = 0.5 * 1.2e-5 * 10 * E * 1e3 * A * 1e-4
    N_Ed = G_EFF * (1000 + dN)
    N_cr = math.pi ** 2 * E * 1e3 * I * 1e-8 / 16 ** 2
    N_pl = A * 1e-4 * fy * 1e3
    lam = math.sqrt(N_pl / N_cr)
    phi = 0.5 * (1 + 0.21 * (lam - 0.2) + lam ** 2)
    chi = 1 / (phi + math.sqrt(phi ** 2 - lam ** 2))
    q = m_ * 9.81 / 1000
    M_Ed = G_EFF * q * 16 ** 2 / 8 / (1 - N_Ed / N_cr)
    attendu = N_Ed / (chi * N_pl) + M_Ed / (W * 1e-6 * fy * 1e3)
    assert dN == pytest.approx(245.2, abs=0.1) and N_cr == pytest.approx(4837.9, abs=0.5)
    assert chi == pytest.approx(0.5332, abs=5e-4)
    assert taux == pytest.approx(attendu, rel=1e-9)
    assert taux == pytest.approx(0.5756, abs=5e-4)
    assert "N_Ed = 1681" in detail and "M poids propre = 99.6" in detail
    # température seule : N_Ed = 1,35·ΔN_T
    t0, d0, _ = _barre(sec, 0.0, 16.0, 0.0, NORMES_TEST, CLE)
    assert f"N_Ed = {G_EFF * dN:.0f}" in d0 and 0 < t0 < taux


def test_tirant_dalle_calculs_manuels():
    """Tirant 6 × T15.7 (A 1,5 cm², fp0,1k 1 640 MPa), γ_armature de test 1,1, T_k = 600 kN :
    R = 6·1,5e-4·1 640e3/1,1 = 1 341,8 kN ; taux = 1,35·600/1 341,8 = 0,6037.
    Dalle 0,30 m en C30/37, H = 200 kN/m : σ = 1,35·200/0,30 = 0,90 MPa ; fcd = 30/1,5 = 20 MPa ; taux 0,045."""
    a = Appui(type="tirant", element="TORON-DEMO-T15.7", nombre=6, cote=-1.0, longueur_libre=8.0, angle=20.0)
    v = _tirant("T1", a, 600.0, "ph", CAT, NORMES_TEST, CLE)[0]
    assert v.taux == pytest.approx(G_EFF * 600 / (6 * 1.5e-4 * 1640e3 / 1.1), rel=1e-9)
    assert v.taux == pytest.approx(0.6037, abs=5e-4) and "1342 kN" in v.detail
    d = Appui(type="dalle", epaisseur=0.30, beton="C30/37", cote=-1.0, longueur=20.0)
    v = _dalle("D1", d, 200.0, "ph", CAT, NORMES_TEST_EC2, CLE)[0]
    assert v.taux == pytest.approx(0.045, rel=1e-9) and "0.90 MPa" in v.detail and "20.0 MPa" in v.detail


def test_lierne_heb300_deux_travees_et_efforts_pseudo3d():
    """HEB 300 S355 (Wpl,y 1 868,7 cm³, Wpl,z 870,1 cm³, Avz 47,43 cm², 117,0 kg/m), H = 150 kN/m, e = 5 m :
    My = 1,35·q·e²/8 = 632,8 kN·m ; Mz (poids propre 1,148 kN/m) = 4,84 kN·m ; V = 1,35·0,625·q·e = 632,8 kN ;
    My,Rd = 663,4, Mz,Rd = 308,9 kN·m, Vpl,Rd = 972,1 kN ; taux = max(0,9539 + 0,0157 ; 0,651) = 0,9696.
    Avec les efforts de la lierne modélisée en pseudo-3D (|M| 400 kN·m, |V| 300 kN) : taux = 0,8297."""
    a = Appui(type="buton", element="modulaire_A", cote=-1.0, espacement=5.0, longueur=16.0, lierne="HEB 300", acier="S355")
    p = CAT.profil("HEB 300")
    fy = 355.0
    MyR, MzR = p["Wpl_y_cm3"] * 1e-6 * fy * 1e3, p["Wpl_z_cm3"] * 1e-6 * fy * 1e3
    VR = p["Avz_cm2"] * 1e-4 * fy * 1e3 / math.sqrt(3)
    qv = p["masse_kg_m"] * 9.81 / 1000
    My, Mz, V = G_EFF * 0.125 * 150 * 25, G_EFF * 0.125 * qv * 25, G_EFF * 0.625 * 150 * 5
    v = _lierne("B1", a, 150.0, "ph", CAT, NORMES_TEST, CLE)[0]
    assert v.taux == pytest.approx(max(My / MyR + Mz / MzR, V / VR), rel=1e-9)
    assert v.taux == pytest.approx(0.9696, abs=5e-4) and MyR == pytest.approx(663.4, abs=0.1) and VR == pytest.approx(972.1, abs=0.1)
    v3 = _lierne("B1", a, 150.0, "ph", CAT, NORMES_TEST, CLE, efforts_3d=(400.0, 300.0, "ph"))[0]
    assert v3.taux == pytest.approx(max(G_EFF * 400 / MyR + Mz / MzR, G_EFF * 300 / VR), rel=1e-9)
    assert v3.taux == pytest.approx(0.8297, abs=5e-4) and "pseudo-3D" in v3.source


def _paroi(**kw):
    p = Paroi(tete=0.0, pied=-12.0, **kw)
    ec = construire_ecran(p, CAT, None)
    return SimpleNamespace(paroi=p), SimpleNamespace(ecran=ec)


def test_palplanche_corrosion_et_interaction_tranchant_moment():
    """AZ 26-700 S355 classe 2 (Wpl 3 059 cm³/m, h 427, t = s = 12,2 mm, largeur 0,70 m), perte 2 mm, β_B = 1 (test) :
    réduction (12,2 − 2)/12,2 = 0,8361 ; W = 2 557,5 cm³/m ; M_c,Rd = 907,9 kN·m/m ;
    Av = s·(h − t)/0,70·réduction = 60,44 cm²/m ; Vpl,Rd = 1 238,8 kN/m ;
    M_k = 400, V_k = 500 : V_Ed = 675 > 0,5·Vpl,Rd ⇒ ρ = (2·675/1 238,8 − 1)² = 0,00805, M_Rd = 900,6 ;
    taux = max(540/900,6 ; 675/1 238,8) = 0,5996."""
    s, m = _paroi(type="palplanche", profil="AZ 26-700", acier="S355", classe_section=2, perte_epaisseur=2.0)
    ef = {"M+": (400.0, "ph"), "M-": (-100.0, "ph"), "V": (500.0, "ph")}
    v = verifier_paroi(s, m, None, CAT, NORMES_TEST, CLE, "", efforts=ef)[0]
    reduc = 1 - 2 / 12.2
    W = 3059 * reduc
    MR = W * 1e-6 * 355e3
    Av = 12.2 * (427 - 12.2) / 100 / 0.7 * reduc
    VR = Av * 1e-4 * 355e3 / math.sqrt(3)
    rho = (2 * 675 / VR - 1) ** 2
    assert 675 > 0.5 * VR
    assert v.taux == pytest.approx(max(540 / (MR * (1 - rho)), 675 / VR), rel=1e-9)
    assert v.taux == pytest.approx(0.5996, abs=5e-4) and "W pl, corrosion" in v.detail
    # sans corrosion ni cisaillement élevé : taux = M_Ed/M_c,Rd simple
    s2, m2 = _paroi(type="palplanche", profil="AZ 26-700", acier="S355", classe_section=2)
    v2 = verifier_paroi(s2, m2, None, CAT, NORMES_TEST, CLE, "", efforts={"M+": (400.0, "ph"), "M-": (0.0, "ph"), "V": (100.0, "ph")})[0]
    assert v2.taux == pytest.approx(540 / (3059e-6 * 355e3), rel=1e-9)
    # classe 3 déclarée : W élastique
    s3, m3 = _paroi(type="palplanche", profil="AZ 26-700", acier="S355", classe_section=3)
    v3 = verifier_paroi(s3, m3, None, CAT, NORMES_TEST, CLE, "", efforts={"M+": (400.0, "ph"), "M-": (0.0, "ph"), "V": (100.0, "ph")})[0]
    assert v3.taux == pytest.approx(540 / (2600e-6 * 355e3), rel=1e-9) and "W él" in v3.detail


def test_berlinoise_et_blindage():
    """HEB 300 S355 tous les 2 m, M_k = 150 kN·m/m, V_k = 80 kN/m : par profilé M = 300, V = 160 ;
    M_Rd = 663,4 kN·m, Vpl,Rd = 972,1 kN ; taux = max(405/663,4 ; 216/972,1) = 0,6105.
    Blindage bois 0,08 m (résistance 10 MPa), portée 2,0 − 0,30 = 1,70 m, pression 30 kPa :
    M = 1,35·30·1,7²/8 = 14,63 kN·m/m ; σ = M/(t²/6) = 13,72 MPa ; taux 1,372."""
    s, m = _paroi(type="berlinoise", profil="HEB 300", acier="S355", entraxe=2.0, largeur_reaction_fiche=0.9,
                  blindage={"epaisseur": 0.08, "materiau": "bois", "resistance": 10.0})
    ef = {"M+": (150.0, "ph"), "M-": (-50.0, "ph"), "V": (80.0, "ph")}
    vs = verifier_paroi(s, m, None, CAT, NORMES_TEST, CLE, "", efforts=ef, modele=" [pseudo-3D]")
    v = vs[0]
    p = CAT.profil("HEB 300")
    MR = p["Wpl_y_cm3"] * 1e-6 * 355e3
    VR = p["Avz_cm2"] * 1e-4 * 355e3 / math.sqrt(3)
    assert v.nom.endswith(" [pseudo-3D]") and v.taux == pytest.approx(max(G_EFF * 300 / MR, G_EFF * 160 / VR), rel=1e-9)
    assert v.taux == pytest.approx(0.6105, abs=5e-4)
    assert not any("Blindage" in x.nom for x in vs)          # blindage : seulement en 2D (pressions du 2D)
    r = SimpleNamespace(phases=[SimpleNamespace(ok=True, nom="ph", terrain_aval=-3.0,
                                                pressions={"amont": {"z": np.array([-2.0, -1.0]), "p": np.array([30.0, 30.0])}},
                                                eau={"z": np.array([-12.0, 0.0]), "u_amont": np.array([0.0, 0.0])})])
    b = _blindage(s.paroi, r, m.ecran.infos, NORMES_TEST, CLE, "")[0]
    M = G_EFF * 30 * 1.7 ** 2 / 8
    assert b.taux == pytest.approx(M / (0.08 ** 2 / 6) / 1000 / 10, rel=1e-9)
    assert b.taux == pytest.approx(1.372, abs=1e-3) and b.etat == "non_ok"


def test_paroi_moulee_flexion_tranchant_et_flexion_horizontale():
    """Paroi moulée 0,60 m C30/37 (fcd 20 MPa, fyd 434,8 MPa), enrobage 0,07 (d = 0,53), armatures 20 / 10 cm²/m :
    face fouille M_k = 300 : μ = 405/(0,53²·20 000) = 0,0721 ; As requis = 18,26 cm²/m ;
    M_Rd(20 cm²) : λx = 20e-4·434,8e3/20e3 = 0,04348 m, M_Rd = 20e3·0,04348·(0,53 − 0,02174) = 441,97 ⇒ taux 0,9164.
    Tranchant V_k = 200 avec ρl de 10 cm²/m : k = 1,614, v = 0,345 < vmin = 0,393 MPa ⇒ VRd,c = 208,4 kN/m, taux 1,296 ;
    avec 25 / 25 cm²/m : v = 0,4686 > vmin ⇒ VRd,c = 248,3 kN/m, taux 1,088.
    Flexion horizontale Ms = 120 kN·m/m, enrobage horizontal 0,05 (d = 0,55), 8 cm²/m : M_Rd = 188,3 ⇒ taux 0,8604."""
    s, m = _paroi(type="paroi_moulee", epaisseur=0.6, beton="C30/37", enrobage=0.07, armatures_fouille=20.0,
                  armatures_terre=10.0, armatures_horizontales=8.0, enrobage_horizontal=0.05)
    ef = {"M+": (300.0, "ph"), "M-": (-150.0, "ph"), "V": (200.0, "ph"), "Ms": (120.0, "ph")}
    vs = {v.nom: v for v in verifier_paroi(s, m, None, CAT, NORMES_TEST_EC2, CLE, "", efforts=ef, modele=" [pseudo-3D]")}
    fcd, fyd = 30 / 1.5, 500 / 1.15
    lx = 20e-4 * fyd * 1e3 / (fcd * 1e3)
    MR = fcd * 1e3 * lx * (0.53 - lx / 2)
    vf = vs["Paroi moulée — flexion (face fouille) [pseudo-3D]"]
    assert vf.taux == pytest.approx(405 / MR, rel=1e-9) and vf.taux == pytest.approx(0.9164, abs=5e-4)
    assert "As requis = 18.3" in vf.detail
    vt = vs["Paroi moulée — effort tranchant sans armatures [pseudo-3D]"]
    k = 1 + math.sqrt(200 / 530)
    vmin = 0.035 * k ** 1.5 * math.sqrt(30)
    assert vt.taux == pytest.approx(270 / (vmin * 0.53 * 1e3), rel=1e-9) and vt.taux == pytest.approx(1.296, abs=1e-3)
    vh = vs["Flexion horizontale (moment Ms de la plaque) [pseudo-3D]"]
    lxh = 8e-4 * fyd * 1e3 / (fcd * 1e3)
    MRh = fcd * 1e3 * lxh * (0.55 - lxh / 2)
    assert vh.taux == pytest.approx(G_EFF * 120 / MRh, rel=1e-9) and vh.taux == pytest.approx(0.8604, abs=5e-4)
    # branche v > vmin du tranchant
    s2, m2 = _paroi(type="paroi_moulee", epaisseur=0.6, beton="C30/37", enrobage=0.07, armatures_fouille=25.0, armatures_terre=25.0)
    vt2 = {v.nom: v for v in verifier_paroi(s2, m2, None, CAT, NORMES_TEST_EC2, CLE, "", efforts=ef)}["Paroi moulée — effort tranchant sans armatures"]
    rho = 25e-4 / 0.53
    v_ = 0.12 * k * (100 * rho * 30) ** (1 / 3)
    assert v_ > vmin and vt2.taux == pytest.approx(270 / (v_ * 0.53 * 1e3), rel=1e-9) and vt2.taux == pytest.approx(1.088, abs=1e-3)
    assert ec2.v_rd_c(1.0, 0.53, 25.0, 30, 1.5, 0.12, 0.035, 2.0, 0.02) == pytest.approx(248.3, abs=0.1)
    # autres parois : Ms affiché, non vérifiable (TODO-NORME)
    s3, m3 = _paroi(type="palplanche", profil="AZ 26-700", acier="S355", classe_section=2)
    v3 = [v for v in verifier_paroi(s3, m3, None, CAT, NORMES_TEST, CLE, "", efforts=ef, modele=" [pseudo-3D]") if "horizontale" in v.nom][0]
    assert v3.etat == "non_verifiable" and "120 kN·m/m" in v3.detail and "TODO-NORME" in v3.source


def test_efforts_des_appuis_pseudo3d_sans_multiplication_par_l_espacement():
    """Point de 600 kN, espacement 6 m, angle 20° : H = 100 kN/m, N = 600/cos 20° = 638,5 kN (et non 3 600)."""
    m = SimpleNamespace(appuis={"B": SimpleNamespace(type="buton", infos={"espacement": 6.0, "angle": 20.0})})
    res3d = SimpleNamespace(phases=[SimpleNamespace(ok=True, nom="p1", appuis=[{"nom": "B", "effort": 500.0}], liernes={}),
                                    SimpleNamespace(ok=True, nom="p2", appuis=[{"nom": "B", "effort": 600.0}, {"nom": "B", "effort": 550.0}], liernes={})])
    ef = _efforts_appuis_3d(m, res3d)
    assert ef["B"][0] == pytest.approx(100.0) and ef["B"][1] == pytest.approx(600 / math.cos(math.radians(20)), rel=1e-12)
    assert ef["B"][1] == pytest.approx(638.5, abs=0.1) and ef["B"][2] == "p2"


def test_execution_complete_pseudo3d_deux_series_de_verifications():
    """Exemple de fouille fermée : le pseudo-3D est calculé une seule fois, les STR produisent la série
    2D et la série [pseudo-3D] (paroi, flexion horizontale, buton avec N = effort du point, lierne
    avec ses moments 3D), et l'API renvoie le champ sans recalcul."""
    texte = (RACINE / "exemples" / "pseudo3d_fouille_fermee.yaml").read_text(encoding="utf-8")
    compteur = {"n": 0}
    from sout.pseudo3d import calcul as mod_calcul
    calc = mod_calcul.MoteurPseudo3D.calculer

    def compte(self):
        compteur["n"] += 1
        return calc(self)

    mod_calcul.MoteurPseudo3D.calculer = compte
    try:
        ex = executer(lire_script(texte), CAT, NORMES_TEST_EC2)
    finally:
        mod_calcul.MoteurPseudo3D.calculer = calc
    assert compteur["n"] == 1 and ex.pseudo3d is not None and ex.pseudo3d.complet
    noms = {v.nom for v in ex.verifications}
    assert "Paroi moulée — flexion (face fouille)" in noms and "Paroi moulée — flexion (face fouille) [pseudo-3D]" in noms
    assert "Flexion horizontale (moment Ms de la plaque) [pseudo-3D]" in noms
    assert "Buton — flambement et flexion [pseudo-3D]" in noms and "Lierne — flexion bi-axiale et cisaillement [pseudo-3D]" in noms
    vb = next(v for v in ex.verifications if v.nom == "Buton — flambement et flexion [pseudo-3D]")
    N3 = max(a["effort"] for ph in ex.pseudo3d.phases if ph.ok for a in ph.appuis)
    import re
    N_Ed = float(re.search(r"N_Ed = (\d+)", vb.detail).group(1))
    assert N_Ed == pytest.approx(G_EFF * (N3 + 245.2), abs=1.0)      # effort du point, non multiplié par l'espacement
    vl = next(v for v in ex.verifications if v.nom == "Lierne — flexion bi-axiale et cisaillement [pseudo-3D]")
    assert "pseudo-3D" in vl.source and vl.taux is not None
    vh = next(v for v in ex.verifications if v.nom.startswith("Flexion horizontale"))
    assert vh.taux is None and "As horizontal requis" in vh.detail       # armatures_horizontales absentes dans l'exemple
    assert all("largeur_appui" not in v.source for v in ex.verifications if v.nom.endswith("[pseudo-3D]"))   # largeur donnée
