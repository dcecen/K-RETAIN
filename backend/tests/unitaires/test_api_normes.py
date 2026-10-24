"""Point d'API /api/normes (référentiel en lecture seule) et compléments de traçabilité des résultats
(Bm, Bt, méthodes des coefficients par couche). Aucune valeur de norme n'est écrite ici : le test lit
le fichier YAML et vérifie que l'API le restitue tel quel."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from ruamel.yaml import YAML

from sout import normes
from sout.api import app

RACINE = Path(__file__).resolve().parents[3]
CLIENT = TestClient(app)


def test_api_normes_restitue_les_fichiers_yaml():
    r = CLIENT.get("/api/normes")
    assert r.status_code == 200
    d = r.json()
    assert Path(d["dossier"]) == normes.DOSSIER
    fichiers = d["fichiers"]
    assert "nf_p94_282" in fichiers
    arbre = YAML(typ="safe").load((normes.DOSSIER / "nf_p94_282.yaml").read_text(encoding="utf-8"))
    par_cle = {e["cle"]: e for e in fichiers["nf_p94_282"]}
    assert par_cle["approche_de_calcul"]["valeur"] == arbre["approche_de_calcul"]["valeur"]
    assert par_cle["butee.gamma_R_e"]["valeur"] == arbre["butee"]["gamma_R_e"]["valeur"]
    assert par_cle["butee.gamma_R_e"]["source"] == arbre["butee"]["gamma_R_e"]["source"]
    # une valeur TODO-NORME reste None, avec sa source explicative
    assert par_cle["surcharges_et_terrain.methode_surcharges"]["valeur"] is None
    assert "TODO-NORME" in par_cle["surcharges_et_terrain.methode_surcharges"]["source"]


def test_synthese_expose_Bm_Bt_et_methodes_des_couches():
    texte = (RACINE / "exemples" / "berlinoise_tirants.yaml").read_text(encoding="utf-8")
    r = CLIENT.post("/api/calcul", json={"texte": texte}).json()
    assert r["ok"]
    res = r["resultats"]
    ph = res["phases"][-1]
    s = ph["synthese"]
    assert s["Bt_kN_m"] > 0 and s["Bm_kN_m"] > 0
    assert s["Bm_kN_m"] / s["Bt_kN_m"] == pytest.approx(s["butee_mobilisee"], rel=1e-9)
    assert ph["iterations"] >= 1
    for c in res["couches"]:
        assert c["methode_k"].startswith("Coulomb")
        assert c["methode_kh"] in ("kh imposé", "Schmitt (EM, α, EI)", "Schmitt, EM par corrélation CPT (EM = qc × EM/qc)")
        assert c["k0_source"] in ("saisi", "Jaky (1 − sin φ')")
        assert "phi" in c and "delta_p_sur_phi" in c
