"""Scripts de vérification élémentaire du menu Fichier (exemples/elementaires) : chaque script est
calculé par l'API, comme depuis l'interface, et le résultat annoncé dans son en-tête est contrôlé
contre sa référence (équilibre limite, convention K-Réa, pseudo-3D, EC2, EC3)."""
import math
import re
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from sout.api import app
from sout.noyau.phasage import calculer
from sout.script.conversion import vers_modele
from sout.script.lecteur import lire_script
from sout.materiaux.base import catalogue_par_defaut
from sout.validation.cas_ecran import h_critique_ancre_butee_simple, h_critique_autostable_equilibre_limite

RACINE = Path(__file__).resolve().parents[3]
DOSSIER = RACINE / "exemples" / "elementaires"
CLIENT = TestClient(app)


def _texte(nom: str) -> str:
    return (DOSSIER / f"{nom}.yaml").read_text(encoding="utf-8")


def _calcul(nom: str) -> dict:
    r = CLIENT.post("/api/calcul", json={"texte": _texte(nom)}).json()
    assert r["ok"], r.get("erreurs")
    return r["resultats"]


def test_les_scripts_elementaires_sont_proposes_dans_le_menu():
    ex = CLIENT.get("/api/exemples").json()
    elem = [e for e in ex if e.get("groupe") == "Vérifications élémentaires"]
    assert [e["nom"] for e in elem] == sorted(p.stem for p in DOSSIER.glob("*.yaml"))
    assert len(elem) == 8 and all(e["texte"].startswith("# VÉRIFICATION ÉLÉMENTAIRE") for e in elem)
    assert any(e.get("groupe") == "Exemples" for e in ex)


def test_E01_autostable_equilibre_limite():
    h = h_critique_autostable_equilibre_limite(10.0, 1 / 3, 3.0, 20.0)
    assert h == pytest.approx(5.05, abs=0.01)
    ph = _calcul("E01_autostable_equilibre_limite")["phases"]
    assert ph[1]["ok"] and 4.90 / h == pytest.approx(0.97, abs=0.005)
    assert not ph[2]["ok"] and "upture" in ph[2]["message"] and 5.20 / h == pytest.approx(1.03, abs=0.005)


def test_E02_ancre_butee_simple():
    h, T = h_critique_ancre_butee_simple(12.0, 1 / 3, 3.0, 20.0)
    assert h == pytest.approx(8.57, abs=0.01) and T == pytest.approx(126.3, abs=0.1)
    ph = _calcul("E02_ancre_butee_simple")["phases"]
    assert ph[2]["ok"] and ph[2]["appuis"][0]["effort_kN_m"] == pytest.approx(T, rel=0.05)
    assert not ph[3]["ok"]


def test_E03_precharge_au_verin_et_equilibre():
    ph = _calcul("E03_precharge_au_verin")["phases"]
    assert ph[2]["appuis"][0]["effort_kN_m"] == pytest.approx(300 / 6, abs=1e-6)
    assert ph[3]["appuis"][0]["effort_kN_m"] > 50.0
    s = lire_script(_texte("E03_precharge_au_verin"))
    res = calculer(vers_modele(s, catalogue_par_defaut()))
    for p in res.phases[1:]:
        am, av = p.pressions["amont"], p.pressions["aval"]
        L = np.repeat(np.diff(p.z) / 2, 2)
        F = (np.sum(am["L"] * am["p"]) - np.sum(av["L"] * av["p"]) + np.sum((p.eau["u_amont"] - p.eau["u_aval"]) * L)
             - sum(a["effort"] for a in p.appuis))
        assert abs(F) < 1e-6


def test_E04_E05_coupes_2d_assemblees_contre_plaque():
    r4, r5 = _calcul("E04_pseudo3d_coupes_2d_assemblees"), _calcul("E05_pseudo3d_plaque_isotrope")
    # E04 : |y| max = écran 2D sans appui
    s = lire_script(_texte("E04_pseudo3d_coupes_2d_assemblees").replace("poser: B", "poser: []"))
    y_sans = float(np.abs(calculer(vers_modele(s, catalogue_par_defaut())).phases[-1].y).max() * 1e3)
    q4, q5 = r4["pseudo3d"]["phases"][-1], r5["pseudo3d"]["phases"][-1]
    assert q4["y_max_mm"] == pytest.approx(y_sans, rel=1e-5)
    # E05 : effort d'un buton intérieur = effort 2D × espacement, déplacement bien plus faible
    H2 = r5["phases"][-1]["appuis"][0]["effort_kN_m"]
    interieurs = [a["effort"] for a in q5["appuis"][3:-3]]
    assert np.mean(interieurs) == pytest.approx(H2 * 4.0, rel=0.05)
    assert q5["y_max_mm"] < 0.1 * q4["y_max_mm"]
    for q in (q4, q5):
        assert abs(q["bilan"]["residu"]) <= 1e-6 * q["bilan"]["echelle"]


def test_E06_double_ecran():
    avec = _calcul("E06_fouille_fermee_double_ecran")["pseudo3d"]["phases"][-1]
    texte = _texte("E06_fouille_fermee_double_ecran")
    texte = texte[:texte.index("surcharges:")] + texte[texte.index("phases:"):]
    sans = CLIENT.post("/api/calcul", json={"texte": texte}).json()["resultats"]["pseudo3d"]["phases"][-1]
    ea = {round(a["s"], 3): a for a in avec["appuis"]}
    es = {round(a["s"], 3): a for a in sans["appuis"]}
    assert ea[10.0]["s2"] == pytest.approx(42.0)
    assert ea[10.0]["effort"] / es[10.0]["effort"] == pytest.approx(1.13, abs=0.05)
    assert abs(avec["bilan"]["residu"]) <= 1e-6 * avec["bilan"]["echelle"]


def test_E07_section_beton_arme():
    vs = {v["nom"]: v for v in _calcul("E07_str_paroi_moulee")["verifications"]}
    v = vs["Paroi moulée — flexion (face fouille)"]
    fcd, fyd = 30 / 1.5, 500 / 1.15
    lx = 20e-4 * fyd / fcd
    MR = fcd * 1e3 * lx * (0.53 - lx / 2)
    assert MR == pytest.approx(442, abs=0.5)
    assert f"M_Rd = {MR:.0f} kN·m/m" in v["detail"]


def test_E08_flambement_buton():
    vs = {v["nom"]: v for v in _calcul("E08_str_buton_flambement")["verifications"]}
    v = vs["Buton — flambement et flexion"]
    E, A, I, fy, L = 210000e3, 194.6e-4, 59755e-8, 355e3, 16.0
    Ncr, Npl = math.pi ** 2 * E * I / L ** 2, A * fy
    lam = math.sqrt(Npl / Ncr)
    phi = 0.5 * (1 + 0.21 * (lam - 0.2) + lam ** 2)
    chi = 1 / (phi + math.sqrt(phi ** 2 - lam ** 2))
    assert chi * Npl == pytest.approx(3683, abs=1)
    assert f"χ = {chi:.2f}" in v["detail"] and f"N_b,Rd = {chi * Npl:.0f} kN" in v["detail"]
    assert float(re.search(r"λ̄ = ([\d.]+)", v["detail"]).group(1)) == pytest.approx(lam, abs=0.01)


def test_rapport_de_validation_servi():
    r = CLIENT.get("/api/validation/rapport")
    assert r.status_code == 200 and "Rafale d'exemples élémentaires" in r.text and "<svg" in r.text
