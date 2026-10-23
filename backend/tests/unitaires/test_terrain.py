"""Surcharges étendues rapportées à la coupe (sol/terrain.py) : solutions élastiques contrôlées à la
main, monotonie en distance, phases d'application, convoi refusé, non-régression."""
import math
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from sout import api
from sout.noyau.phasage import ErreurModele
from sout.script.conversion import vers_modele
from sout.script.lecteur import ScriptInvalide, lire_script
from sout.sol.terrain import (CoupeCalcul, ErreurTerrain, SurchargePlan, boussinesq_ponctuelle, delta_sigma_v_plan,
                              delta_sigma_v_surcharges, ligne_quelconque, newmark_coin, rectangle_quelconque)
from sout.sol.surcharges import Surcharge, delta_sigma_v

RACINE = Path(__file__).resolve().parents[3]
BASE = (RACINE / "exemples" / "fouille_exemple.yaml").read_text(encoding="utf-8")
COUPE = CoupeCalcul(x=10.0, y=0.0, ni=(0.0, 1.0), t=(1.0, 0.0), k=0, s=10.0, cote="long_sud")   # côté y = 0, terre en y < 0


def _bande_main(q, d, b, h):
    """Boussinesq intégré pour une bande (Poulos & Davis § 3.2) : q/π·[α + sin α·cos(α + 2β)]."""
    b1 = math.atan(d / h)
    b2 = math.atan((d + b) / h)
    a = b2 - b1
    return q / math.pi * (a + math.sin(a) * math.cos(a + 2 * b1))


def test_bande_60_kPa_a_1_m_retrouve_boussinesq_a_la_main():
    """Bande de 60 kPa, 4 m de large, à 1 m de la paroi : trois cotes sous un terrain à 0."""
    s = SurchargePlan("S", "bande", 60.0, distance=1.0, largeur=4.0)
    for h, attendu in ((1.0, _bande_main(60, 1, 4, 1.0)), (3.0, _bande_main(60, 1, 4, 3.0)), (8.0, _bande_main(60, 1, 4, 8.0))):
        v = delta_sigma_v_plan(s, np.array([-h]), 0.0, COUPE)[0]
        assert v == pytest.approx(attendu, rel=1e-9)
    # valeurs chiffrées (calcul manuel : β1 = atan(d/h), β2 = atan((d+b)/h), α = β2 − β1) :
    # h = 1 m : α = 0,588, sin α·cos(α + 2β1) = −0,308 → 60/π·0,280 = 5,35 kPa
    # h = 3 m : α = 0,709, +0,141 → 16,2 kPa ; h = 8 m : α = 0,434, +0,326 → 14,5 kPa
    assert delta_sigma_v_plan(s, np.array([-1.0]), 0.0, COUPE)[0] == pytest.approx(5.35, abs=0.05)
    assert delta_sigma_v_plan(s, np.array([-3.0]), 0.0, COUPE)[0] == pytest.approx(16.2, abs=0.2)
    assert delta_sigma_v_plan(s, np.array([-8.0]), 0.0, COUPE)[0] == pytest.approx(14.5, abs=0.2)
    # même résultat que la forme historique du moteur
    hist = delta_sigma_v(Surcharge("S", "bande", 60.0, 1.0, 4.0), np.array([-1.0, -3.0, -8.0]), 0.0)
    assert np.allclose(delta_sigma_v_plan(s, np.array([-1.0, -3.0, -8.0]), 0.0, COUPE), hist)


def test_newmark_coin_et_rectangle_quelconque():
    """Sous le coin d'un carré 2 × 2 chargé de 100 kPa à 2 m : I = 0,1752 (abaque de Newmark, m = n = 1)."""
    v = newmark_coin(100.0, 2.0, 2.0, np.array([2.0]))[0]
    assert v == pytest.approx(17.52, abs=0.05)
    # sous le centre d'un carré 4 × 4 : 4 coins de 2 × 2 → 4 × 17,52 = 70,1 kPa à 2 m
    c = rectangle_quelconque(100.0, -2, 2, -2, 2, 0.0, 0.0, np.array([2.0]))[0]
    assert c == pytest.approx(4 * v, rel=1e-9)
    # très grand rectangle : tend vers q
    assert rectangle_quelconque(100.0, -500, 500, -500, 500, 0.0, 0.0, np.array([1.0]))[0] == pytest.approx(100.0, rel=1e-3)
    # point extérieur : superposition avec signes, toujours ≥ 0 et plus faible que sous la charge
    ext = rectangle_quelconque(100.0, 0, 4, 0, 4, 6.0, 2.0, np.array([2.0]))[0]
    assert 0 < ext < c


def test_ponctuelle_et_ligne():
    """Boussinesq ponctuelle : sous la charge, Δσz = 3Q/(2πz²) ; ligne très longue parallèle → Flamant."""
    Q = 1000.0
    assert boussinesq_ponctuelle(Q, np.array([0.0]), np.array([2.0]))[0] == pytest.approx(3 * Q / (2 * math.pi * 4.0), rel=1e-9)
    z = np.array([1.0, 3.0, 6.0])
    ligne = ligne_quelconque(25.0, (-400.0, -2.0), (400.0, -2.0), 0.0, 0.0, z)
    flamant = delta_sigma_v(Surcharge("L", "lineique", 25.0, 2.0), -z, 0.0)
    assert np.allclose(ligne, flamant, rtol=0.02)


def test_rectangle_loin_contribue_moins_qu_un_rectangle_proche():
    z = np.array([-1.0, -4.0, -8.0])
    proche = SurchargePlan("P", "rectangulaire", 40.0, position=(10.0, -6.0), emprise=(8.0, 6.0))
    loin = SurchargePlan("L", "rectangulaire", 40.0, position=(10.0, -20.0), emprise=(8.0, 6.0))
    vp = delta_sigma_v_plan(proche, z, 0.0, COUPE)
    vl = delta_sigma_v_plan(loin, z, 0.0, COUPE)
    assert np.all(vp > vl) and np.all(vl >= 0)
    # décalé le long de la paroi : encore moins
    decale = SurchargePlan("D", "rectangulaire", 40.0, position=(30.0, -6.0), emprise=(8.0, 6.0))
    assert np.all(delta_sigma_v_plan(decale, z, 0.0, COUPE) < vp)
    # un côté non concerné n'est pas chargé par une bande dédiée à un autre côté
    b = SurchargePlan("B", "bande", 30.0, distance=0.5, largeur=8.0, cotes_paroi=("long_nord",))
    assert np.all(delta_sigma_v_plan(b, z, 0.0, COUPE) == 0)
    # bande de longueur finie le long du côté : moins qu'une bande illimitée, nulle hors de l'emprise
    finie = SurchargePlan("F", "bande", 30.0, distance=0.5, largeur=8.0, emprise=(6.0, 14.0))
    infinie = SurchargePlan("I", "bande", 30.0, distance=0.5, largeur=8.0)
    assert np.all(delta_sigma_v_plan(finie, z, 0.0, COUPE) < delta_sigma_v_plan(infinie, z, 0.0, COUPE))
    assert np.all(delta_sigma_v_plan(finie, z, 0.0, COUPE) > 0)
    # ponctuelle avec emprise = rectangle de q/aire ; profondeur d'application
    g = SurchargePlan("G", "ponctuelle", 1200.0, position=(10.0, -6.0), emprise=(6.0, 6.0), profondeur=0.5)
    assert delta_sigma_v_plan(g, np.array([-0.3]), 0.0, COUPE)[0] == 0      # au-dessus de la cote d'application
    assert delta_sigma_v_plan(g, np.array([-3.0]), 0.0, COUPE)[0] > 0


def test_convoi_refuse_et_plan_necessaire():
    with pytest.raises(ErreurTerrain, match="TODO-NORME"):
        delta_sigma_v_plan(SurchargePlan("T", "convoi", 0.0, modele="Bc"), np.array([-2.0]), 0.0, COUPE)
    with pytest.raises(ErreurTerrain, match="plan"):
        delta_sigma_v_plan(SurchargePlan("R", "rectangulaire", 10.0, position=(0, 0), emprise=(1, 1)), np.array([-2.0]), 0.0, None)
    # l'interface du moteur additionne anciennes et nouvelles surcharges de la même face
    tot = delta_sigma_v_surcharges([Surcharge("A", "repartie", 10.0), SurchargePlan("U", "uniforme", 5.0), Surcharge("V", "repartie", 7.0, cote_ecran="aval")],
                                   "amont", np.array([-1.0]), 0.0, COUPE)
    assert tot[0] == pytest.approx(15.0)


def test_script_surcharges_etendues_phases_et_non_regression():
    """Surcharges phasées converties en actions ; le cas exemple reste inchangé ; convoi refusé au calcul."""
    client = TestClient(api.app)
    api.vider_cache_coupes()
    texte = BASE.replace("""surcharges:
  - { type: bande, q: 20, distance: 1.0, largeur: 5.0 }""", """surcharges:
  - { type: bande, q: 20, distance: 1.0, largeur: 5.0 }
  - { nom: grue, type: ponctuelle, q: 1200, position: [10, -8], emprise: [6, 6], phases: [2, 3] }
  - { nom: stock, type: rectangulaire, q: 40, position: [30, -6], emprise: [10, 6], phase: Pose du buton B1 }
plan:
  contour: [[0, 0], [20, 0], [20, 12], [0, 12]]
  cotes: { long_sud: 0 }""")
    from sout import normes
    from sout.materiaux.base import catalogue_par_defaut
    cat, nrm = catalogue_par_defaut(), normes.charger()
    s = lire_script(texte)
    m = vers_modele(s, cat, nrm)
    assert [x.nom for x in m.surcharges] == ["S1"]
    assert [x.nom for x in m.phases[1].ajouter_surcharges] == ["grue", "stock"]
    assert m.phases[3].retirer_surcharges == ["grue"]                        # phases [2, 3] → retirée à la phase 4
    r = client.post("/api/calcul", json={"texte": texte}).json()
    assert r["ok"], r["erreurs"]
    assert any("milieu du côté" in a for a in r["projet"]["avertissements"])
    sm = r["resultats"]["maquette"]["surcharges"]
    assert [x["nom"] for x in sm] == ["S1", "grue", "stock"]
    grue = next(x for x in sm if x["nom"] == "grue")
    assert grue["phase_debut"] == 2 and grue["phase_fin"] == 3 and max(grue["profil"]["dsv"]) > 0
    # la grue charge la phase 3 et plus la phase 4 : déplacement en phase « Terrassement final » différent du cas exemple
    y_ref = TestClient(api.app).post("/api/calcul", json={"texte": BASE}).json()["resultats"]["phases"][3]["synthese"]["y_max_mm"]
    assert r["resultats"]["phases"][3]["synthese"]["y_max_mm"] != pytest.approx(y_ref, rel=1e-4)
    assert y_ref == pytest.approx(17.6472, rel=1e-3)
    # convoi : accepté par le schéma, refusé au calcul
    conv = BASE.replace("  - { type: bande, q: 20, distance: 1.0, largeur: 5.0 }", "  - { type: convoi, modele: Bc, q: 0 }")
    with pytest.raises(ErreurModele, match="TODO-NORME"):
        from sout.noyau.phasage import calculer
        calculer(vers_modele(lire_script(conv), cat, nrm))
    # contrôles du schéma
    with pytest.raises(ScriptInvalide):
        lire_script(BASE.replace("  - { type: bande, q: 20, distance: 1.0, largeur: 5.0 }", "  - { type: rectangulaire, q: 20 }"))


def test_entree_yaml_creee_depuis_la_3d_est_valide():
    """Même forme que l'entrée écrite par l'outil « Ajouter une surcharge » (entreeYamlSurcharge)."""
    texte = (RACINE / "exemples" / "fouille_coupes.yaml").read_text(encoding="utf-8")
    ligne_immeuble = next(l for l in texte.splitlines() if "nom: immeuble" in l)
    texte = texte.replace(ligne_immeuble, ligne_immeuble + chr(10) + "  - { nom: stock2, type: rectangulaire, q: 40, position: [25, -7], emprise: [10, 6], phase: 2 }")
    s = lire_script(texte)
    assert s.surcharges[-1].nom == "stock2" and s.surcharges[-1].phase == 2
    api.vider_cache_coupes()
    r = TestClient(api.app).post("/api/calcul", json={"texte": texte}).json()
    assert r["ok"], r["erreurs"]
    noms = [x["nom"] for x in r["resultats"]["maquette"]["surcharges"]]
    assert "stock2" in noms and "grue" in noms and "immeuble" in noms
