from fastapi.testclient import TestClient

from sout.api import app


def test_sante():
    r = TestClient(app).get("/api/sante")
    assert r.status_code == 200
    assert r.json()["statut"] == "ok"
