"""Audit du 24 octobre 2026 — lot 4 : API et exploitation (cache sensible aux normes et à la base, fichiers de
coupe confinés, limites de taille, authentification allégée, import de catalogue sûr, routes sans test)."""
import base64
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from sout import api, utilisateurs
from sout.materiaux import base, importer
from sout.script.coupes import ErreurCoupe, chemin_script_coupe

RACINE = Path(__file__).resolve().parents[3]
EXEMPLE = (RACINE / "exemples" / "fouille_exemple_EI.yaml").read_text(encoding="utf-8")
CLIENT = TestClient(api.app, raise_server_exceptions=False)
PLAN = "\nplan:\n  contour: [[0, 0], [20, 0], [20, 12], [0, 12]]\n  cotes: { sud: 0, est: 1 }\n"


# ---------------------------------------------------------------- 1. cache
def test_le_cache_depend_des_normes_et_de_la_base(monkeypatch):
    api.vider_cache_coupes()
    monkeypatch.setattr(api, "_empreinte_environnement", lambda: "env-A")
    assert CLIENT.post("/api/calcul", json={"texte": EXEMPLE}).json()["ok"]
    assert CLIENT.post("/api/calcul", json={"texte": EXEMPLE}).json()["ok"]
    s = api.statistiques_cache()
    assert (s["calculs"], s["cache"]) == (1, 1)
    monkeypatch.setattr(api, "_empreinte_environnement", lambda: "env-B")   # une norme ou un catalogue a changé
    assert CLIENT.post("/api/calcul", json={"texte": EXEMPLE}).json()["ok"]
    assert api.statistiques_cache()["calculs"] == 2
    api.vider_cache_coupes()


def test_empreinte_environnement_change_avec_un_fichier_de_norme(tmp_path, monkeypatch):
    from sout import normes
    d = tmp_path / "normes"
    d.mkdir()
    f = d / "ec3.yaml"
    f.write_text("gamma_M0: 1.0\n", encoding="utf-8")
    monkeypatch.setattr(normes, "DOSSIER", d)
    e1 = api._empreinte_environnement()
    f.write_text("gamma_M0: 1.1\n# modifié\n", encoding="utf-8")
    assert api._empreinte_environnement() != e1


# ---------------------------------------------------------------- 2. fichiers de coupe confinés
def test_script_de_coupe_hors_du_dossier_exemples_refuse():
    for mauvais in ("../backend/pyproject.toml", "C:/Windows/win.ini", "/etc/passwd", "//serveur/partage/x.yaml", "elementaires/../../CLAUDE.md"):
        with pytest.raises(ErreurCoupe) as ex:
            chemin_script_coupe(mauvais, "C1")
        assert "exemples" in str(ex.value), mauvais
    bon = chemin_script_coupe("elementaires/E01_autostable_equilibre_limite.yaml", "C1")
    assert bon.is_file() and bon.parent.name == "elementaires"
    with pytest.raises(ErreurCoupe) as ex:
        chemin_script_coupe("inexistant.yaml", "C1")
    assert "introuvable" in str(ex.value)
    texte = EXEMPLE + PLAN + "coupes:\n  - nom: C1\n    zone: { paroi: sud }\n    script: ../backend/pyproject.toml\n"
    r = CLIENT.post("/api/coupes/preparer", json={"texte": texte}).json()
    assert r["ok"] is False and "exemples" in r["erreurs"][0]["message"]


# ---------------------------------------------------------------- 3. limites
def test_script_trop_long_refuse_en_francais():
    r = CLIENT.post("/api/valider", json={"texte": "a" * (api.TAILLE_MAX_SCRIPT + 1)})
    assert r.status_code == 422 and "trop long" in r.json()["erreurs"][0]["message"]


def test_bornes_de_calculabilite_du_schema():
    from sout.script.lecteur import ScriptInvalide, lire_script
    with pytest.raises(ScriptInvalide):
        lire_script(EXEMPLE + "\nhydraulique: { regime: hydrostatique, largeur_amont: 5000 }\n")
    with pytest.raises(ScriptInvalide):
        lire_script(EXEMPLE + "\npseudo3d: { longueur: 5000 }\n")


# ---------------------------------------------------------------- 4. authentification
def _entete(nom, mdp):
    return {"Authorization": "Basic " + base64.b64encode(f"{nom}:{mdp}".encode()).decode()}


def test_identification_verifiee_une_fois_puis_mise_en_cache(tmp_path, monkeypatch):
    f = tmp_path / "utilisateurs.json"
    monkeypatch.setattr(utilisateurs, "FICHIER", f)
    monkeypatch.setattr(utilisateurs, "ITERATIONS", 1000)
    utilisateurs.ajouter("cache_test", "mot-de-passe-solide")
    appels = []
    original = utilisateurs.verifier

    def compte(nom, mdp, fichier=None):
        appels.append(nom)
        return original(nom, mdp, fichier)
    monkeypatch.setattr(utilisateurs, "verifier", compte)
    monkeypatch.setenv("RETAINWALL_AUTH", "1")
    api.vider_cache_authentification()
    c = TestClient(api.app)
    assert c.get("/api/schema", headers=_entete("cache_test", "mot-de-passe-solide")).status_code == 200
    assert c.get("/api/schema", headers=_entete("cache_test", "mot-de-passe-solide")).status_code == 200
    assert c.get("/api/schema", headers=_entete("cache_test", "faux")).status_code == 401
    assert appels == ["cache_test", "cache_test"]   # 1 succès mis en cache + 1 échec (jamais mis en cache)
    api.vider_cache_authentification()


def test_fichier_des_comptes_relu_seulement_s_il_change(tmp_path):
    f = tmp_path / "u.json"
    f.write_text(json.dumps({"a": {"sel": "00", "iterations": 1, "empreinte": "x"}}), encoding="utf-8")
    assert set(utilisateurs._lire(f)) == {"a"}
    f.write_text(json.dumps({"a": {"sel": "00", "iterations": 1, "empreinte": "x"},
                             "b": {"sel": "00", "iterations": 1, "empreinte": "y"}}), encoding="utf-8")
    assert set(utilisateurs._lire(f)) == {"a", "b"}
    utilisateurs._lire(f)["c"] = 1          # la copie renvoyée n'altère pas le cache
    assert set(utilisateurs._lire(f)) == {"a", "b"}


# ---------------------------------------------------------------- 5. import de catalogue
@pytest.fixture
def base_temporaire(tmp_path, monkeypatch):
    chemin = tmp_path / "materiaux.sqlite"
    catalogues = tmp_path / "catalogues"
    monkeypatch.setattr(base, "CHEMIN_BASE", chemin)
    monkeypatch.setattr(base, "CATALOGUES", catalogues)
    monkeypatch.setattr(importer, "CATALOGUES", catalogues)
    base.catalogue_par_defaut.cache_clear()
    base.reconstruire(chemin, catalogues)
    yield chemin, catalogues
    base.catalogue_par_defaut.cache_clear()


def test_import_d_un_catalogue_fautif_laisse_la_base_intacte(base_temporaire):
    chemin, catalogues = base_temporaire
    n0 = len(base.catalogue_par_defaut().lister("aciers"))
    mauvais = ("nuance;fy_MPa;fu_MPa;E_MPa\nS999;abc;490;210000\n").encode("utf-8")
    r = CLIENT.post("/api/materiaux/import", files={"fichier": ("aciers_test.csv", mauvais, "text/csv")})
    assert r.status_code == 400
    assert "nombre attendu" in r.json()["detail"] and "fy_MPa" in r.json()["detail"] and "S999" in r.json()["detail"]
    assert not list(catalogues.glob("*.csv"))                       # rien copié
    assert len(base.catalogue_par_defaut().lister("aciers")) == n0  # base inchangée
    r = CLIENT.post("/api/materiaux/import", files={"fichier": ("modele_aciers.csv", mauvais, "text/csv")})
    assert r.status_code == 400 and "modele_" in r.json()["detail"]
    bon = ("nuance;fy_MPa;fu_MPa;E_MPa\nS999;355;490;210000\n").encode("utf-8")
    r = CLIENT.post("/api/materiaux/import", files={"fichier": ("aciers_test.csv", bon, "text/csv")})
    assert r.status_code == 200 and r.json()["ok"]
    assert len(base.catalogue_par_defaut().lister("aciers")) == n0 + 1
    assert (catalogues / "aciers_test.csv").exists()
    assert not chemin.with_name(chemin.name + ".tmp").exists()


def test_reconstruction_echouee_garde_l_ancienne_base(base_temporaire):
    chemin, catalogues = base_temporaire
    n0 = len(base.catalogue_par_defaut().lister("aciers"))
    catalogues.mkdir(exist_ok=True)
    (catalogues / "aciers_casse.csv").write_text("nuance;fy_MPa;fu_MPa;E_MPa\nS1;x;y;z\n", encoding="utf-8")
    with pytest.raises(ValueError):
        base.reconstruire(chemin, catalogues)
    assert chemin.exists() and len(base.catalogue_par_defaut().lister("aciers")) == n0


# ---------------------------------------------------------------- 6. routes sans test
def test_routes_materiaux_rido_assemblages():
    r = CLIENT.get("/api/materiaux")
    assert r.status_code == 200 and set(r.json()) == set(base.TABLES)
    r = CLIENT.get("/api/materiaux/references")
    assert r.status_code == 200 and "HEB 300" in r.json()["profiles"]
    r = CLIENT.post("/api/rido", json={"texte": "# rien\n", "nom": "essai.rid"})
    assert r.status_code == 200 and set(r.json()) == {"texte", "rapport"}
    r = CLIENT.post("/api/assemblages/schema", json={"type": "platine_about", "parametres": {"lierne": "HEB 300", "buton": "modulaire_A"}, "efforts": {"N": 800}})
    assert r.status_code == 200 and r.json()["solides"]
    r = CLIENT.post("/api/assemblages/verifier", json={"type": "platine_about", "parametres": {"lierne": "HEB 300", "buton": "modulaire_A"}, "efforts": {"N": 800}})
    assert r.status_code == 200 and r.json() and all("etat" in v for v in r.json())
    assert CLIENT.post("/api/assemblages/verifier", json={"type": "inconnu"}).status_code == 400
