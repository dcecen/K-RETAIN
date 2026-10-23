"""Vue 3D persistante : données renvoyées par le calcul, non-régression du cas exemple,
jeux de résultats figés des tests de l'interface."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sout.api import app

RACINE = Path(__file__).resolve().parents[3]
DONNEES = RACINE / "frontend" / "src" / "vue3d" / "__tests__" / "donnees"


def _calcul(nom: str) -> dict:
    texte = (RACINE / "exemples" / f"{nom}.yaml").read_text(encoding="utf-8")
    r = TestClient(app).post("/api/calcul", json={"texte": texte}).json()
    assert r["ok"], r["erreurs"]
    return r["resultats"]


@pytest.fixture(scope="module")
def exemple() -> dict:
    return _calcul("fouille_exemple")


def test_non_regression_cas_exemple(exemple):
    """Valeurs du cas exemple figées avant la refonte de la vue 3D : la vue ne modifie rien.
    Mises à jour le 23/10/2026 : mise en charge au vérin de la précharge de B1 (50 kN/m) et
    diagrammes M/V par la statique (voir docs/ETAT.md, « Revue du moteur de calcul »)."""
    ph = next(p for p in exemple["phases"] if p["nom"] == "Terrassement final et pompage")
    s = ph["synthese"]
    assert s["y_max_mm"] == pytest.approx(17.6472, rel=1e-3)
    assert s["z_y_max"] == pytest.approx(-5.5, abs=1e-6)
    assert s["M_max"] == pytest.approx(254.71, rel=1e-3)
    assert s["M_min"] == pytest.approx(-153.372, rel=1e-3)
    b1 = next(a for a in ph["appuis"] if a["nom"] == "B1")
    assert b1["effort_kN_m"] == pytest.approx(142.192, rel=1e-3)
    assert b1["effort_axial_kN"] == pytest.approx(853.151, rel=1e-3)


def test_complement_appuis_fleches_et_elu(exemple):
    """Chaque appui porte, par phase, son effort ELU et ses flèches issues du module de vérification."""
    ph = next(p for p in exemple["phases"] if p["nom"] == "Terrassement final et pompage")
    b1 = next(a for a in ph["appuis"] if a["nom"] == "B1")
    assert b1["effort_elu_kN"] == pytest.approx(1.35 * 853.151, rel=1e-3)
    assert b1["fleche_mm"] is not None and 0 < b1["fleche_mm"] < 200
    assert b1["fleche_mm"] > b1["fleche_poids_propre_mm"]
    assert b1["N_cr_kN"] > b1["effort_axial_kN"]
    assert b1["raccourcissement_mm"] > 0
    assert b1["fleche_lierne_mm"] is None          # B1 n'a pas de lierne dans l'exemple


def test_couches_avec_coefficients_du_calcul(exemple):
    c = exemple["couches"]
    assert [x["nom"] for x in c] == ["Remblai", "Sable dense"]
    assert 0.3 < c[0]["kah"] < 0.4 and c[0]["kph"] > 2 and 0.4 < c[0]["k0"] < 0.6
    assert c[0]["kh"] > 0 and c[1]["kh"] > c[0]["kh"]


def test_geometrie_maquette_renvoyee_avec_le_calcul(exemple):
    g = exemple["maquette"]
    assert g["contour"] and g["plan_defaut"] is True
    assert g["paroi"]["type"] == "palplanche" and g["paroi"]["pied"] == -14.0
    assert {a["appui"] for a in g["plan_appuis"]} == {"B1"}
    assert len(g["i_critique"]) == len(exemple["phases"])
    assert g["assemblages"]["A1"]["appui"] == "B1"


@pytest.mark.parametrize("nom", ["fouille_exemple", "fouille_ecoulement", "pseudo3d_angle", "berlinoise_tirants", "fouille_coupes"])
def test_jeux_figes_de_la_vue3d_a_jour(nom):
    """Les jeux figés des tests de l'interface reflètent le calcul actuel
    (sinon : `python -m outils.fixtures_vue3d` dans backend)."""
    chemin = DONNEES / f"{nom}.json"
    assert chemin.exists(), f"{chemin} absent : lancer python -m outils.fixtures_vue3d"
    fige = json.loads(chemin.read_text(encoding="utf-8"))["resultats"]
    actuel = _calcul(nom)
    assert [p["nom"] for p in fige["phases"]] == [p["nom"] for p in actuel["phases"]]
    for pf, pa in zip(fige["phases"], actuel["phases"]):
        if pa["ok"]:
            assert pf["synthese"]["y_max_mm"] == pytest.approx(pa["synthese"]["y_max_mm"], rel=1e-4, abs=1e-6)
            assert pf["synthese"]["M_max"] == pytest.approx(pa["synthese"]["M_max"], rel=1e-4, abs=1e-6)
    assert fige["maquette"]["contour"] == actuel["maquette"]["contour"]
    assert set(fige) == set(actuel), "clés des résultats modifiées : régénérer les jeux figés"
