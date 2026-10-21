"""J10 — accès par identifiant (HTTP Basic, mots de passe hachés)."""
import base64
import json

import pytest
from fastapi.testclient import TestClient

from sout import utilisateurs
from sout.api import app


@pytest.fixture
def comptes(tmp_path, monkeypatch):
    f = tmp_path / "utilisateurs.json"
    monkeypatch.setattr(utilisateurs, "FICHIER", f)
    monkeypatch.setattr(utilisateurs, "ITERATIONS", 1000)  # rapide pour les tests
    utilisateurs.ajouter("ingenieur", "mot-de-passe-solide")
    return f


def _entete(nom, mdp):
    return {"Authorization": "Basic " + base64.b64encode(f"{nom}:{mdp}".encode()).decode()}


def test_mot_de_passe_hache(comptes):
    d = json.loads(comptes.read_text(encoding="utf-8"))
    assert "mot-de-passe-solide" not in comptes.read_text(encoding="utf-8")
    assert set(d["ingenieur"]) == {"sel", "iterations", "empreinte"}
    assert utilisateurs.verifier("ingenieur", "mot-de-passe-solide")
    assert not utilisateurs.verifier("ingenieur", "mauvais")
    assert not utilisateurs.verifier("inconnu", "mot-de-passe-solide")
    with pytest.raises(ValueError):
        utilisateurs.ajouter("x", "court")


def test_acces_protege_en_deploiement(comptes, monkeypatch):
    monkeypatch.setenv("RETAINWALL_AUTH", "1")
    c = TestClient(app)
    assert c.get("/api/sante").status_code == 200          # sonde libre
    r = c.get("/api/schema")
    assert r.status_code == 401 and "Basic" in r.headers["www-authenticate"]
    assert c.get("/api/schema", headers=_entete("ingenieur", "faux")).status_code == 401
    assert c.get("/api/schema", headers=_entete("ingenieur", "mot-de-passe-solide")).status_code == 200


def test_acces_libre_en_developpement(monkeypatch):
    monkeypatch.delenv("RETAINWALL_AUTH", raising=False)
    assert TestClient(app).get("/api/schema").status_code == 200


def test_guide_a_jour_avec_le_schema():
    from sout.script.documentation import GUIDE, reference

    assert reference() in GUIDE.read_text(encoding="utf-8"), \
        "référence du guide périmée : lancez python -m sout.script.documentation"


def test_toutes_les_routes_api_restent_accessibles():
    """Le montage de l'interface sur « / » doit rester déclaré en dernier (sinon il masque les routes)."""
    c = TestClient(app)
    assert c.get("/api/assemblages/types").status_code == 200
    assert len(c.get("/api/assemblages/types").json()) == 14
