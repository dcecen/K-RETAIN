"""J8 — maquette 3D autonome."""
import json
import math
import re
from pathlib import Path

import pytest
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


def test_sans_trace_en_plan_coupe_infinie_ou_paroi_droite_ouverte():
    """Sans tracé en plan, la maquette n'invente aucune fouille : étude 2D = tronçon droit d'écran ouvert aux deux bouts
    (coupe infinie, deux hauteurs d'écran, au moins 16 m) ; paroi droite pseudo-3D = polyligne ouverte de la longueur
    modélisée, droite ou en deux côtés de part et d'autre de l'angle (E04, P06) ; buton sans paroi en face dessiné sur
    sa longueur."""
    from sout.maquette3d.generer import contour_paroi_droite, coupe_infinie

    def cotes(c):
        return [math.hypot(c[i + 1][0] - c[i][0], c[i + 1][1] - c[i][1]) for i in range(len(c) - 1)]

    c, note = coupe_infinie(12.0)
    assert c == [[0.0, 0.0], [24.0, 0.0]] and "infinie" in note
    assert coupe_infinie(5.0)[0][1][0] == 16.0
    c, note = contour_paroi_droite(48.0, None)
    assert c == [[0.0, 0.0], [48.0, 0.0]] and "droite" in note
    for angle in (90.0, 120.0):
        c, note = contour_paroi_droite(80.0, angle)
        L = cotes(c)
        assert len(c) == 3 and L == pytest.approx([40.0, 40.0]) and "angle" in note
        ab = (c[0][0] - c[1][0], c[0][1] - c[1][1]); cb = (c[2][0] - c[1][0], c[2][1] - c[1][1])
        assert math.degrees(math.acos((ab[0] * cb[0] + ab[1] * cb[1]) / (L[0] * L[1]))) == pytest.approx(angle)
    client = TestClient(app)
    for nom, attendu in (("2d/E09_etat_initial_repos", [[0.0, 0.0], [24.0, 0.0]]), ("2d/E04_pseudo3d_coupes_2d_assemblees", [[0.0, 0.0], [48.0, 0.0]])):
        texte = (RACINE / "exemples" / "elementaires" / f"{nom}.yaml").read_text(encoding="utf-8")
        mq = client.post("/api/calcul", json={"texte": texte}).json()["resultats"]["maquette"]
        assert mq["contour"] == attendu and mq["ferme"] is False and mq["plan_defaut"] and mq["note_plan"]
    pa = placer_appuis([[0.0, 0.0], [24.0, 0.0]], {"B": {"type": "buton", "espacement": 6.0, "longueur": 18.0}}, ferme=False)
    assert len(pa) == 4 and all(abs(math.dist(p["de"], p["a"]) - 18.0) < 1e-9 for p in pa)
    assert placer_appuis([[0.0, 0.0], [24.0, 0.0]], {"B": {"type": "buton", "espacement": 6.0}}, ferme=False)[0]["a"][1] == pytest.approx(-6.0)
