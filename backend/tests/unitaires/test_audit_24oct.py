"""Audit du 24 octobre 2026 — lot 1 : plus d'erreur 500 muette sur les cas limites."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sout import api
from sout.assemblages.service import REGISTRE, completer, type_de
from sout.script.lecteur import ScriptInvalide, lire_script
from sout.verifs import Verif, pire

RACINE = Path(__file__).resolve().parents[3]
EXEMPLE = (RACINE / "exemples" / "fouille_exemple_EI.yaml").read_text(encoding="utf-8")
CLIENT = TestClient(api.app, raise_server_exceptions=False)


def _v(etat, taux):
    return Verif("Pieux — flexion", "structure", "pieux", "P1", etat, taux, "", "")


def test_pire_garde_un_non_ok_sans_taux_devant_un_taux_chiffre():
    """Section de pieu insuffisante : « non_ok » sans taux ; levait KeyError('non_ok')."""
    res = pire([_v("ok", 0.4), _v("non_ok", None), _v("attention", 0.95)])
    assert len(res) == 1 and res[0].etat == "non_ok" and res[0].taux is None
    res = pire([_v("non_verifiable", None), _v("ok", 0.2)])
    assert res[0].taux == 0.2
    assert pire([_v("non_verifiable", None)])[0].etat == "non_verifiable"


def test_kerisel_absi_sans_table_donne_un_message_et_pas_un_500():
    texte = EXEMPLE.replace("calcul:\n", "calcul:\n  coefficients: kerisel_absi\n", 1)
    assert "kerisel_absi" in texte
    r = CLIENT.post("/api/calcul", json={"texte": texte})
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is False and "TODO-NORME" in d["erreurs"][0]["message"]


def test_exception_imprevue_renvoie_un_message_en_francais(monkeypatch):
    def boum(texte):
        raise RuntimeError("division impossible")
    monkeypatch.setattr(api, "executer_texte", boum)
    api.vider_cache_coupes()
    r = CLIENT.post("/api/calcul", json={"texte": EXEMPLE})
    assert r.status_code == 500
    d = r.json()
    assert d["ok"] is False
    assert "Erreur interne du serveur de calcul (RuntimeError)" in d["erreurs"][0]["message"]
    assert "division impossible" in d["erreurs"][0]["message"]


def test_requete_mal_formee_en_francais():
    r = CLIENT.post("/api/calcul", json={"script": "x"})
    assert r.status_code == 422
    d = r.json()
    assert d["ok"] is False and d["erreurs"][0]["message"].startswith("Requête invalide")


def test_contour_ferme_et_sommets_confondus():
    plan = "\nplan:\n  contour: [[0, 0], [20, 0], [20, 12], [0, 12], [0, 0]]\n"
    s = lire_script(EXEMPLE + plan)
    assert s.plan.contour == [[0, 0], [20, 0], [20, 12], [0, 12]]
    with pytest.raises(ScriptInvalide) as ex:
        lire_script(EXEMPLE + "\nplan:\n  contour: [[0, 0], [20, 0], [20, 0], [0, 12]]\n")
    assert "confondus" in str(ex.value.erreurs[0].message)


def test_caractere_interdit_dans_le_yaml_est_une_erreur_de_script():
    with pytest.raises(ScriptInvalide) as ex:
        lire_script(EXEMPLE + "\nprojet_infos: {note: a\x01b}\n")
    assert "YAML" in ex.value.erreurs[0].message


def test_parametre_d_assemblage_non_numerique():
    t = type_de(next(iter(REGISTRE)))
    p_num = next(p for p in t.parametres if p.genre in ("nombre", "entier"))
    v = completer(t, {p_num.cle: "12,5"})[p_num.cle]
    attendu = 12.5
    if p_num.mini is not None:
        attendu = max(attendu, p_num.mini)
    if p_num.maxi is not None:
        attendu = min(attendu, p_num.maxi)
    assert isinstance(v, (int, float)) and v == pytest.approx(attendu, abs=0.5)   # bornes du paramètre respectées
    with pytest.raises(ValueError) as ex:
        completer(t, {p_num.cle: "douze"})
    assert "nombre attendu" in str(ex.value)
    r = CLIENT.post("/api/assemblages/schema", json={"type": t.cle, "parametres": {p_num.cle: "douze"}})
    assert r.status_code == 400 and "nombre attendu" in r.json()["detail"]


def test_base_materiaux_absente_donne_503(monkeypatch):
    monkeypatch.setattr(api, "_catalogue", lambda: None)
    assert CLIENT.get("/api/materiaux").status_code == 503
    assert CLIENT.get("/api/materiaux/references").status_code == 503
