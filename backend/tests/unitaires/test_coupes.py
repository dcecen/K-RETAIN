"""Coupes de calcul (projet 2D à plusieurs coupes) : héritage, calcul indépendant, cache,
non-régression du script sans coupes, tronçons orphelins, synthèse projet."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sout import api
from sout.script.coupes import fusionner, phasage_projet, preparer, synthese_projet
from sout.script.lecteur import ScriptInvalide, lire_script

RACINE = Path(__file__).resolve().parents[3]
BASE = (RACINE / "exemples" / "fouille_exemple.yaml").read_text(encoding="utf-8")
BLOC_PLAN = """
plan:
  contour: [[0, 0], [20, 0], [20, 12], [0, 12]]
  cotes: { long_sud: 0, court_est: 1, long_nord: 2, court_ouest: 3 }
"""
BLOC_COUPES = """
coupes:
  - nom: C1 — long côté sud
    zone: { paroi: long_sud }
  - nom: C2 — long côté nord, sol plus faible
    zone: { paroi: long_nord }
    trace: { de: [10, 20], a: [10, 6] }
    script:
      sol:
        - { nom: Remblai, toit: 0.0, gamma: 18, gamma_dejauge: 9, phi: 24, c: 0, EM: 3000, alpha: 0.5 }
        - { nom: Sable, toit: -3.0, gamma: 20, gamma_dejauge: 11, phi: 30, c: 0, EM: 9000, alpha: 0.33 }
  - nom: C3 — petit côté est
    zone: { paroi: court_est }
    script:
      phases:
        - { nom: "Terrassement à -2,0", excaver: -2.0 }
        - { nom: Pose du buton B1, poser: B1 }
        - { nom: Terrassement final sans pompage, excaver: -5.0 }
"""
SCRIPT_3 = BASE + BLOC_PLAN + BLOC_COUPES


@pytest.fixture(autouse=True)
def _cache_vide():
    api.vider_cache_coupes()
    yield
    api.vider_cache_coupes()


def test_fusion_herite_et_remplace():
    fusion, herite, local = fusionner({"projet": "P", "sol": [1], "paroi": {"a": 1}, "plan": {}, "coupes": []},
                                      {"sol": [2], "x": 1})
    assert fusion["sol"] == [2] and fusion["paroi"] == {"a": 1} and fusion["projet"] == "P"
    assert fusion["plan"] == {} and "coupes" not in fusion                 # le plan reste celui du principal
    assert herite == ["paroi", "plan", "projet"] and local == ["sol", "x"]


def test_preparation_des_coupes():
    s = lire_script(SCRIPT_3)
    p = preparer(SCRIPT_3, s)
    assert [c.nom[:2] for c in p.coupes] == ["C1", "C2", "C3"]
    assert p.coupes[0].k == 0 and p.coupes[0].de == 0 and p.coupes[0].a == 20
    assert p.coupes[1].trace == [[10, 20], [10, 6]]
    assert p.coupes[0].trace and p.coupes[0].trace[0] != p.coupes[0].trace[1]   # trace par défaut
    assert "sol" in p.coupes[1].local and "paroi" in p.coupes[1].herite
    assert len({c.empreinte for c in p.coupes}) == 3
    assert [o["k"] for o in p.orphelins] == [3]                                  # petit côté ouest sans coupe
    assert any("sans coupe" in a for a in p.avertissements)
    assert any("angle" in a for a in p.avertissements)
    assert all("coupes:" not in c.texte and "contour:" in c.texte for c in p.coupes)


def test_trois_coupes_calculees_independamment():
    r = TestClient(api.app).post("/api/calcul", json={"texte": SCRIPT_3}).json()
    assert r["ok"], r["erreurs"]
    pr = r["projet"]
    assert [c["nom"][:2] for c in pr["coupes"]] == ["C1", "C2", "C3"]
    y1 = r["resultats"]["dimensionnant"]["deplacement"]["valeur_mm"]
    y2 = pr["coupes"][1]["resultats"]["dimensionnant"]["deplacement"]["valeur_mm"]
    y3 = pr["coupes"][2]["resultats"]["dimensionnant"]["deplacement"]["valeur_mm"]
    assert y1 == pytest.approx(17.7606, rel=1e-3)        # C1 = script principal = cas exemple
    assert y2 > 1.2 * y1                                 # sol plus faible : paroi plus souple
    assert y3 < y1                                       # excavation moins profonde
    assert api.statistiques_cache()["calculs"] == 3
    # phasage projet : réunion des phases par nom, C3 a une phase à elle
    assert "Terrassement final sans pompage" in pr["phasage_projet"]
    assert pr["coupes"][2]["correspondance"][-1] == pr["phasage_projet"].index("Terrassement final sans pompage")
    assert pr["coupes"][0]["correspondance"] == list(range(5))
    assert any("sans coupe" in a for a in pr["avertissements"])


def test_cache_par_coupe_modifier_C2_ne_recalcule_ni_C1_ni_C3():
    client = TestClient(api.app)
    client.post("/api/calcul", json={"texte": SCRIPT_3})
    assert api.statistiques_cache()["calculs"] == 3
    modifie = SCRIPT_3.replace("phi: 24", "phi: 26")
    r = client.post("/api/calcul", json={"texte": modifie}).json()
    assert r["ok"]
    assert api.statistiques_cache() == {"calculs": 4, "cache": 2}
    # calcul d'une coupe seule, déjà en cache
    r1 = client.post("/api/calcul", json={"texte": modifie, "coupe": "C1 — long côté sud"}).json()
    assert r1["ok"] and r1["coupe"]["nom"].startswith("C1")
    assert api.statistiques_cache()["calculs"] == 4
    p = client.post("/api/coupes/preparer", json={"texte": modifie}).json()
    assert all(c["en_cache"] for c in p["coupes"])
    s = client.post("/api/coupes/synthese", json={"texte": modifie}).json()
    assert s["ok"] and s["projet"]["synthese"]["verifications"]


def test_script_sans_coupes_identique_au_comportement_actuel():
    r = TestClient(api.app).post("/api/calcul", json={"texte": BASE}).json()
    assert r["ok"]
    assert r["projet"]["unique"] is True and len(r["projet"]["coupes"]) == 1
    assert r["projet"]["coupes"][0]["nom"] == "Coupe unique"
    assert r["resultats"]["dimensionnant"]["deplacement"]["valeur_mm"] == pytest.approx(17.7606, rel=1e-3)
    assert r["projet"]["phasage_projet"] == [p["nom"] for p in r["resultats"]["phases"]]
    assert r["projet"]["orphelins"] == []


def test_synthese_retient_la_pire_coupe_avec_son_nom():
    r = TestClient(api.app).post("/api/calcul", json={"texte": SCRIPT_3}).json()
    syn = r["projet"]["synthese"]
    butee = next(v for v in syn["verifications"] if v["nom"].startswith("Mobilisation de la butée"))
    taux = {c["nom"]: next(v["taux"] for v in (c.get("resultats") or r["resultats"])["verifications"] if v["nom"].startswith("Mobilisation"))
            for c in r["projet"]["coupes"]}
    pire = max(taux, key=lambda n: taux[n])
    assert butee["coupe"] == pire and butee["taux"] == pytest.approx(taux[pire])
    assert syn["chiffres"]["deplacement"]["coupe"].startswith("C2")
    # logique pure : taux prime sur l'état, état grave prime quand aucun taux
    lignes = synthese_projet({"A": [{"nom": "x", "element": "e", "etat": "ok", "taux": 0.5}],
                              "B": [{"nom": "x", "element": "e", "etat": "non_ok", "taux": 1.2}],
                              "C": [{"nom": "y", "element": "e", "etat": "non_verifiable", "taux": None}],
                              "D": [{"nom": "y", "element": "e", "etat": "non_ok", "taux": None}]})
    assert {l["nom"]: l["coupe"] for l in lignes} == {"x": "B", "y": "D"}


def test_phasage_projet_insere_les_phases_propres():
    projet, corr = phasage_projet([["a", "b", "c"], ["a", "b2", "c"], ["a", "c", "d"]])
    assert projet == ["a", "b", "b2", "c", "d"]
    assert corr[1] == [0, 2, 3] and corr[2] == [0, 3, 4]


def test_controles_des_coupes():
    with pytest.raises(ScriptInvalide) as e:
        lire_script(BASE + BLOC_PLAN + "coupes:\n  - { nom: X, zone: { paroi: inconnu } }\n")
    assert "inconnu" in str(e.value.erreurs[0])
    with pytest.raises(ScriptInvalide) as e:
        lire_script(BASE + BLOC_PLAN + "coupes:\n  - { nom: X, zone: { paroi: 0 } }\n  - { nom: X, zone: { paroi: 1 } }\n")
    assert "double" in str(e.value.erreurs[0])
    with pytest.raises(ScriptInvalide):
        lire_script(BASE + BLOC_PLAN + "coupes:\n  - { nom: X, zone: { paroi: 0 }, script: { plan: { contour: [] } } }\n")


def test_entree_yaml_d_une_coupe_epinglee_est_valide():
    """Même forme que l'entrée créée par « Épingler » dans la vue 3D (entreeYamlCoupe) : zone par nom de côté, trace."""
    texte = (RACINE / "exemples" / "fouille_coupes.yaml").read_text(encoding="utf-8")
    texte += "  - { nom: C4 — milieu du côté sud, zone: { paroi: long_sud }, trace: { de: [12.5, -8], a: [12.5, 8] } }" + chr(10)
    texte += "  - { nom: C5, zone: { paroi: 3 }, trace: { de: [-5.4, 9], a: [5.4, 9] } }" + chr(10)
    s = lire_script(texte)
    assert [c.nom for c in s.coupes][-2:] == ["C4 — milieu du côté sud", "C5"]
    p = preparer(texte, s)
    assert p.coupes[-1].k == 3 and p.coupes[-2].trace == [[12.5, -8], [12.5, 8]]
    assert p.orphelins == []            # C5 couvre désormais le côté ouest
