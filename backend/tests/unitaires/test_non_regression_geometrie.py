"""Non-régression des lots « géométrie » (octobre 2026).

Les valeurs de référence (donnees/non_regression_geometrie.json) ont été relevées AVANT les lots 1 et 4
(profil par côté, bloc geometrie) pour deux exemples à géométrie en plan sans objet de terrain :
`pseudo3d_fouille_fermee` (champ pseudo-3D : |y| max et M max par ligne verticale, efforts des butons)
et `fouille_coupes` (trois coupes explicites : synthèse par phase, efforts d'appui, vérifications, synthèse
projet). Ces exemples ne doivent pas changer : tolérance 1e-6 relative.
Ne jamais régénérer ce fichier pour faire passer un test (CLAUDE.md, règle 4).
"""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sout.api import app

RACINE = Path(__file__).resolve().parents[3]
REFERENCE = json.loads((Path(__file__).parent / "donnees" / "non_regression_geometrie.json").read_text(encoding="utf-8"))
TOL = 1e-6
CLES = ("y_max_mm", "z_y_max", "M_max", "M_min", "V_absmax", "butee_mobilisee")


def _calcul(nom: str) -> dict:
    texte = (RACINE / "exemples" / f"{nom}.yaml").read_text(encoding="utf-8")
    r = TestClient(app).post("/api/calcul", json={"texte": texte}).json()
    assert r["ok"], r.get("erreurs")
    return r


def _coupes(r: dict) -> dict:
    liste = (r.get("projet") or {}).get("coupes", [])
    coupes = {(liste[0]["nom"] if liste else "Coupe unique"): r["resultats"]}
    for c in liste[1:]:
        coupes[c["nom"]] = c["resultats"]
    return coupes


def _comparer_coupe(nom: str, res: dict, ref: dict) -> None:
    assert [p["nom"] for p in res["phases"]] == [p["nom"] for p in ref["phases"]]
    for pr, pa in zip(ref["phases"], res["phases"]):
        assert pa["ok"] == pr["ok"], f"{nom} / {pr['nom']}"
        if not pr["ok"]:
            continue
        for cle in CLES:
            assert pa["synthese"][cle] == pytest.approx(pr[cle], rel=TOL, abs=1e-9), f"{nom} / {pr['nom']} / {cle}"
        appuis = {a["nom"]: a["effort_kN_m"] for a in pa["appuis"]}
        assert set(appuis) == set(pr["appuis"]), f"{nom} / {pr['nom']} : appuis"
        for a, v in pr["appuis"].items():
            assert appuis[a] == pytest.approx(v, rel=TOL, abs=1e-9), f"{nom} / {pr['nom']} / appui {a}"
    verifs = [(v["nom"], v["element"], v["taux"], v["etat"]) for v in res.get("verifications", [])]
    attendu = [(v["nom"], v["element"], v["taux"], v["etat"]) for v in ref["verifications"]]
    assert len(verifs) == len(attendu), nom
    for (n1, e1, t1, s1), (n2, e2, t2, s2) in zip(verifs, attendu):
        assert (n1, e1, s1) == (n2, e2, s2), nom
        if t2 is None:
            assert t1 is None
        else:
            assert t1 == pytest.approx(t2, rel=TOL, abs=1e-9), f"{nom} / {n2} ({e2})"
    if "pseudo3d" in ref:
        p3 = res["pseudo3d"]
        assert p3["s"] == pytest.approx(ref["pseudo3d"]["s"], rel=TOL, abs=1e-9)
        for pr, pa in zip(ref["pseudo3d"]["phases"], p3["phases"]):
            assert pa["nom"] == pr["nom"] and pa["ok"] == pr["ok"]
            if not pr["ok"]:
                continue
            import numpy as np

            y = np.abs(np.array(pa["y_mm"])).max(axis=1)
            M = np.array(pa["M"]).max(axis=1)
            assert y == pytest.approx(pr["y_absmax_par_ligne"], rel=TOL, abs=2e-4), f"{nom} / {pr['nom']} : |y| par ligne"
            assert M == pytest.approx(pr["M_max_par_ligne"], rel=TOL, abs=2e-3), f"{nom} / {pr['nom']} : M par ligne"
            for cle in ("y_max_mm", "Mz_max", "Mz_min"):
                assert pa[cle] == pytest.approx(pr[cle], rel=TOL, abs=1e-9), f"{nom} / {pr['nom']} / {cle}"
            efforts = [(a["nom"], a["s"], a["effort"]) for a in pa["appuis"]]
            assert len(efforts) == len(pr["appuis"])
            for (n1, s1, e1), a in zip(efforts, pr["appuis"]):
                assert n1 == a["nom"] and s1 == pytest.approx(a["s"], abs=1e-9)
                assert e1 == pytest.approx(a["effort"], rel=TOL, abs=1e-9), f"{nom} / {pr['nom']} / buton {n1} à s = {s1}"


@pytest.mark.parametrize("nom", sorted(REFERENCE))
def test_resultats_identiques_a_la_reference(nom):
    ref = REFERENCE[nom]
    r = _calcul(nom)
    coupes = _coupes(r)
    assert set(coupes) == set(ref["coupes"]), f"{nom} : coupes"
    for c, res in coupes.items():
        _comparer_coupe(f"{nom} / {c}", res, ref["coupes"][c])
    if "synthese" in ref:
        syn = [(v["nom"], v["element"], v["coupe"], v["taux"], v["etat"]) for v in r["projet"]["synthese"]["verifications"]]
        attendu = [(v["nom"], v["element"], v["coupe"], v["taux"], v["etat"]) for v in ref["synthese"]]
        assert len(syn) == len(attendu)
        for (n1, e1, c1, t1, s1), (n2, e2, c2, t2, s2) in zip(syn, attendu):
            assert (n1, e1, c1, s1) == (n2, e2, c2, s2), nom
            if t2 is not None:
                assert t1 == pytest.approx(t2, rel=TOL, abs=1e-9), f"{nom} / synthèse {n2} ({e2})"
