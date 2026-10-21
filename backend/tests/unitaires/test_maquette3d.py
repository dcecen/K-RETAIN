"""J8 — maquette 3D autonome."""
import json
import math
import re
from pathlib import Path

from fastapi.testclient import TestClient

from sout.api import app
from sout.maquette3d.generer import placer_appuis

RACINE = Path(__file__).resolve().parents[3]


def test_placement_automatique_des_butons_et_tirants():
    rect = [[0, 0], [20, 0], [20, 12], [0, 12]]
    p = placer_appuis(rect, {"B": {"type": "buton", "espacement": 5.0}})
    assert len(p) == 4
    for ap in p:   # butons en travers de la largeur (12 m), depuis le plus long côté
        assert math.dist(ap["de"], ap["a"]) == 12.0 or abs(math.dist(ap["de"], ap["a"]) - 12.0) < 1e-9
    t = placer_appuis(rect, {"T": {"type": "tirant", "espacement": 4.0, "longueur_libre": 8,
                                   "longueur_scellee": 6, "angle": 0}})
    assert t and all(not (0 < ap["a"][0] < 20 and 0 < ap["a"][1] < 12) for ap in t)  # vers l'extérieur


def test_api_maquette_fichier_autonome():
    texte = (RACINE / "exemples" / "berlinoise_tirants.yaml").read_text(encoding="utf-8")
    r = TestClient(app).post("/api/maquette", json={"texte": texte})
    assert r.status_code == 200
    html = r.text
    assert "var THREE=" in html and "cdn" not in html.lower()      # three.js intégré, aucune ressource externe
    assert not re.search(r'<script[^>]+src=', html)
    donnees = json.loads(re.search(r"const D = (\{.*?\});\nconst T", html, re.S).group(1))
    assert donnees["paroi"]["type"] == "berlinoise"
    assert len(donnees["phases"]) == 4 and donnees["phases"][-1]["fond"] == -6.0
    assert donnees["plan_appuis"]


def test_api_maquette_script_invalide():
    r = TestClient(app).post("/api/maquette", json={"texte": "projet: x"})
    assert r.status_code == 400
