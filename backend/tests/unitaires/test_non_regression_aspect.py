"""Non-régression de la refonte « aspect logiciel d'ingénierie » (octobre 2026).

Les valeurs de référence (donnees/non_regression_aspect.json) ont été relevées AVANT toute
modification, pour trois exemples : par phase, déplacement maximal et sa cote, moments extrêmes,
effort tranchant maximal, butée mobilisée, efforts d'appui ; puis taux et état de chaque vérification.
La refonte ne touche ni le moteur ni la sérialisation numérique : tolérance 1e-6 relative.
Ne jamais régénérer ce fichier pour faire passer un test (CLAUDE.md, règle 4).
"""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sout.api import app

RACINE = Path(__file__).resolve().parents[3]
REFERENCE = json.loads((Path(__file__).parent / "donnees" / "non_regression_aspect.json").read_text(encoding="utf-8"))
TOL = 1e-6


def _calcul(nom: str) -> dict:
    texte = (RACINE / "exemples" / f"{nom}.yaml").read_text(encoding="utf-8")
    r = TestClient(app).post("/api/calcul", json={"texte": texte}).json()
    assert r["ok"], r.get("erreurs")
    return r["resultats"]


@pytest.mark.parametrize("nom", sorted(REFERENCE))
def test_resultats_identiques_a_la_reference(nom):
    ref = REFERENCE[nom]
    res = _calcul(nom)
    assert [p["nom"] for p in res["phases"]] == [p["nom"] for p in ref["phases"]]
    for pr, pa in zip(ref["phases"], res["phases"]):
        assert pa["ok"] == pr["ok"], pr["nom"]
        if not pr["ok"]:
            continue
        s = pa["synthese"]
        for cle in ("y_max_mm", "z_y_max", "M_max", "M_min", "V_absmax", "butee_mobilisee"):
            assert s[cle] == pytest.approx(pr[cle], rel=TOL, abs=1e-9), f"{nom} / {pr['nom']} / {cle}"
        appuis = {a["nom"]: a["effort_kN_m"] for a in pa["appuis"]}
        assert set(appuis) == set(pr["appuis"]), f"{nom} / {pr['nom']} : appuis"
        for a, v in pr["appuis"].items():
            assert appuis[a] == pytest.approx(v, rel=TOL, abs=1e-9), f"{nom} / {pr['nom']} / appui {a}"
    verifs = [(v["nom"], v["element"], v["taux"], v["etat"]) for v in res.get("verifications", [])]
    attendu = [(v["nom"], v["element"], v["taux"], v["etat"]) for v in ref["verifications"]]
    assert len(verifs) == len(attendu)
    for (n1, e1, t1, s1), (n2, e2, t2, s2) in zip(verifs, attendu):
        assert (n1, e1, s1) == (n2, e2, s2)
        if t2 is None:
            assert t1 is None
        else:
            assert t1 == pytest.approx(t2, rel=TOL, abs=1e-9), f"{nom} / {n2} ({e2})"
