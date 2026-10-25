"""Lecture tolérante : un bloc `projet:` (nom, affaire, client…) est accepté et un mot-clé inconnu est
ignoré avec un avertissement (ligne et chemin) au lieu de bloquer le calcul ; les vraies erreurs
(valeur hors bornes, mot-clé obligatoire manquant, cohérence) restent bloquantes."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sout.api import app
from sout.script.lecteur import ScriptInvalide, lire_script, valider

RACINE = Path(__file__).resolve().parents[3]
BASE = (RACINE / "exemples" / "elementaires" / "2d" / "E03_precharge_au_verin.yaml").read_text(encoding="utf-8")
CLIENT = TestClient(app)


def _avec_extras(texte: str) -> str:
    t = texte.replace("projet: E03 Précharge au vérin — effort après la pose = 50 kN/m",
                      "projet:\n  nom: Chantier Test\n  affaire: A-123\n  client: Ville")
    t = t.replace("phi: 32, kh: 20000 }", "phi: 32, kh: 20000, description: sable fin }")
    return t.replace("paroi: { type: palplanche,", "paroi: { remarque: rideau provisoire, type: palplanche,")


def test_projet_en_bloc_et_mots_cles_inconnus_non_bloquants():
    s = lire_script(_avec_extras(BASE))
    assert s.projet == "Chantier Test"
    assert s.projet_infos == {"nom": "Chantier Test", "affaire": "A-123", "client": "Ville"}
    av = [(a.ligne, a.chemin, a.niveau) for a in s.avertissements_lecture]
    assert ("paroi.remarque" in [c for _, c, _ in av]) and ("sol[1].description" in [c for _, c, _ in av])
    assert all(n == "avertissement" and l is not None for l, _, n in av)
    assert valider(_avec_extras(BASE)) == s.avertissements_lecture


def test_bloc_projet_sans_nom_et_projet_numerique():
    s = lire_script(BASE.replace("projet: E03 Précharge au vérin — effort après la pose = 50 kN/m", "projet:\n  affaire: A-123"))
    assert s.projet == "A-123"
    s = lire_script(BASE.replace("projet: E03 Précharge au vérin — effort après la pose = 50 kN/m", "projet:\n  lieu: Lyon"))
    assert s.projet == "Projet sans nom" and s.projet_infos == {"lieu": "Lyon"}
    assert lire_script(BASE.replace("projet: E03 Précharge au vérin — effort après la pose = 50 kN/m", "projet: 2026")).projet == "2026"


def test_les_vraies_erreurs_restent_bloquantes_et_les_avertissements_les_accompagnent():
    t = _avec_extras(BASE).replace("phi: 32,", "phi: -3,")
    with pytest.raises(ScriptInvalide) as e:
        lire_script(t)
    niveaux = [x.niveau for x in e.value.erreurs]
    assert niveaux[0] == "erreur" and "avertissement" in niveaux
    assert any(x.chemin == "sol[1].phi" and x.niveau == "erreur" for x in e.value.erreurs)
    # mot-clé obligatoire manquant : bloquant
    with pytest.raises(ScriptInvalide):
        lire_script(BASE.replace("gamma_dejauge: 10, ", ""))


def test_api_calcule_malgre_les_mots_cles_inconnus():
    t = _avec_extras(BASE)
    v = CLIENT.post("/api/valider", json={"texte": t}).json()
    assert v["ok"] and v["erreurs"] == [] and len(v["avertissements"]) == 2
    r = CLIENT.post("/api/calcul", json={"texte": t}).json()
    assert r["ok"], r["erreurs"]
    res = r["resultats"]
    assert res["projet"] == "Chantier Test"
    assert res["phases"][2]["appuis"][0]["effort_kN_m"] == pytest.approx(50.0, abs=1e-6)
    assert sum("mot-clé inconnu" in a for a in res["avertissements"]) == 2
    bloque = CLIENT.post("/api/valider", json={"texte": t.replace("phi: 32,", "phi: -3,")}).json()
    assert not bloque["ok"] and len(bloque["erreurs"]) == 1 and len(bloque["avertissements"]) == 2
    rc = CLIENT.post("/api/calcul", json={"texte": t.replace("phi: 32,", "phi: -3,")}).json()
    assert not rc["ok"] and rc["erreurs"][0]["niveau"] == "erreur"
