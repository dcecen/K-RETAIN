"""J3 — langage de script : validation, erreurs en français avec ligne, calcul via l'API."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sout.api import app
from sout.noyau.phasage import calculer
from sout.script.conversion import vers_modele
from sout.script.lecteur import ScriptInvalide, lire_script

EXEMPLE = (Path(__file__).resolve().parents[3] / "exemples" / "fouille_exemple_EI.yaml").read_text(encoding="utf-8")


def _erreurs(texte):
    with pytest.raises(ScriptInvalide) as ex:
        lire_script(texte)
    return ex.value.erreurs


def _ligne(texte, motif):
    return next(i + 1 for i, l in enumerate(texte.splitlines()) if motif in l)


def test_exemple_valide_et_calcule():
    s = lire_script(EXEMPLE)
    assert s.projet.startswith("Fouille exemple")
    m = vers_modele(s)
    assert m.eau_amont == -2.0 and m.phases[2].eau == {"aval": -7.0}
    assert m.appuis["B1"].precharge == pytest.approx(50 / 6)
    res = calculer(m)
    assert res.complet, [p.message for p in res.phases]
    assert len(res.phases) == 4


def test_mot_cle_inconnu_avec_ligne():
    texte = EXEMPLE.replace("    phi: 35", "    phii: 35")
    err = _erreurs(texte)
    inconnu = [e for e in err if "inconnu" in e.message]
    assert inconnu and inconnu[0].ligne == _ligne(texte, "phii")
    assert any("manquant" in e.message for e in err)  # phi manquant


def test_valeur_hors_bornes_message_francais():
    texte = EXEMPLE.replace("    gamma: 20", "    gamma: -20")
    err = _erreurs(texte)
    assert err[0].ligne == _ligne(texte, "gamma: -20")
    assert "strictement supérieur à 0" in err[0].message
    assert err[0].chemin == "sol[2].gamma"


def test_type_inconnu_liste_les_valeurs():
    texte = EXEMPLE.replace("type: palplanche", "type: palplanches")
    err = _erreurs(texte)
    assert "valeurs possibles" in err[0].message and "paroi_moulee" in err[0].message


def test_appui_inconnu_dans_une_phase():
    texte = EXEMPLE.replace("poser: B1", "poser: B2")
    err = _erreurs(texte)
    assert "B2" in err[0].message and err[0].ligne == _ligne(texte, "poser: B2")


def test_syntaxe_yaml():
    err = _erreurs("projet: x\nparoi: [1, 2\n")
    assert "syntaxe YAML" in err[0].message and err[0].ligne is not None


def test_schmitt_sans_EM():
    texte = EXEMPLE.replace("    EM: 4000\n", "")
    err = _erreurs(texte)
    assert "Schmitt" in err[0].message


def test_api_calcul_et_valider():
    c = TestClient(app)
    r = c.post("/api/calcul", json={"texte": EXEMPLE}).json()
    assert r["ok"], r["erreurs"]
    res = r["resultats"]
    assert res["complet"] and len(res["phases"]) == 4
    assert res["dimensionnant"]["appuis"]["B1"]["effort_kN_m"] > 0
    assert len(res["enveloppes"]["M_max"]) == len(res["phases"][-1]["M"])
    r = c.post("/api/valider", json={"texte": EXEMPLE.replace("tete: 0.0", "tete: -20")}).json()
    assert not r["ok"] and "pied" in r["erreurs"][0]["message"]
    assert "properties" in c.get("/api/schema").json()
