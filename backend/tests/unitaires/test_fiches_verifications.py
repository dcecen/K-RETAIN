"""Fiches détaillées des vérifications (lot 3 du 25/10/2026) : famille, principe, données, étapes et schéma
exposés par chaque vérification, cohérents avec le texte du détail et sérialisables en JSON."""
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sout import api
from sout.verifs import Lecteur, donnee, famille_de, resultat

RACINE = Path(__file__).resolve().parents[3]
BASE = (RACINE / "exemples" / "fouille_exemple.yaml").read_text(encoding="utf-8")
# même exemple avec une lierne sur le buton (l'exemple n'en a que dans les assemblages)
BASE_LIERNE = BASE.replace("precharge: 50 }", "precharge: 50, lierne: HEB 400, acier: S355 }")
assert BASE_LIERNE != BASE
CLIENT = TestClient(api.app)
FAMILLES = {"butee", "equilibre_vertical", "massif_ancrage", "fond_de_fouille", "stabilite_generale", "deplacements",
            "hydraulique", "ecran", "appuis", "liernes", "assemblages", "anneau", "calcul"}


def _calcul(texte: str) -> dict:
    api.vider_cache_coupes()
    r = CLIENT.post("/api/calcul", json={"texte": texte}).json()
    assert r["ok"], r.get("erreurs")
    return r["resultats"]


def _nombres(texte: str) -> list[float]:
    return [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", texte)]


def test_socle_resultat_fiche_et_coefficients_lus():
    class N:
        def valeur(self, f, c):
            return {"x.a": 1.5, "x.b": 2.0}[c]

        def source(self, f, c):
            return f"source {c}"

    lect = Lecteur(N())
    a, b = lect.v("fichier", "x.a"), lect.v("fichier", "x.b")
    v = resultat("Test", "e", "P1", a * b / 10, "détail", "méthode", lect, famille="butee", principe="p",
                 donnees=[donnee("X", "une valeur", 3.0, "kN")], etapes=["étape 1"], schema={"type": "profil"})
    assert v.famille == "butee" and v.principe == "p" and v.etapes == ["étape 1"] and v.schema == {"type": "profil"}
    symboles = [d["symbole"] for d in v.donnees]
    assert symboles == ["X", "a", "b"]                      # données du module puis valeurs normatives lues
    assert v.donnees[1]["origine"] == "norme:fichier:x.a" and v.donnees[1]["valeur"] == 1.5
    assert donnee("t", "texte", "abc")["valeur"] == "abc" and donnee("n", "nul", None)["valeur"] is None
    json.dumps(v.vers_dict())
    assert famille_de("Mobilisation de la butée", "geotechnique") == "butee"
    assert famille_de("Lierne — raidisseurs", "structure") == "liernes"
    assert famille_de("Inconnue", "structure") == "structure"
    v2 = resultat("Buton — flambement et flexion", "B1", None, 0.5, "d", "s")
    assert v2.famille == "appuis" and v2.donnees == [] and v2.schema is None


def test_toutes_les_verifications_ont_une_famille_et_sont_serialisables():
    texte = BASE_LIERNE.replace("verifications: [butee, equilibre_vertical, fond_de_fouille, stabilite_generale, structure]",
                                "verifications: [butee, equilibre_vertical, kranz, fond_de_fouille, stabilite_generale, deplacements, structure]")
    texte = texte.replace("eau:\n", "criteres: { deplacement_max_mm: 30, deplacement_tete_mm: 20 }\neau:\n")
    res = _calcul(texte)
    vs = res["verifications"]
    assert len(vs) >= 10
    for v in vs:
        assert v["famille"] in FAMILLES, (v["nom"], v["famille"])
        assert isinstance(v["donnees"], list) and isinstance(v["etapes"], list)
    assert {v["famille"] for v in vs} >= {"butee", "equilibre_vertical", "fond_de_fouille", "stabilite_generale", "deplacements", "ecran", "appuis", "liernes", "assemblages"}
    # chaque vérification à fiche porte un principe, des données avec les coefficients lus et des étapes
    avec_fiche = [v for v in vs if v["famille"] in ("butee", "fond_de_fouille", "stabilite_generale", "deplacements")]
    for v in avec_fiche:
        assert v["principe"] and v["etapes"], v["nom"]
        assert any(d["origine"].startswith("norme:") for d in v["donnees"]) or v["famille"] == "deplacements", v["nom"]
    json.dumps(vs)


def test_fiche_butee_coherente_avec_le_detail():
    v = {x["nom"]: x for x in _calcul(BASE)["verifications"]}["Mobilisation de la butée"]
    d = {x["symbole"]: x["valeur"] for x in v["donnees"]}
    Bm, Bt = _nombres(v["detail"])[:2]
    assert round(d["Bm"]) == Bm and round(d["Bt"]) == Bt and d["Bm/Bt"] == pytest.approx(d["Bm"] / d["Bt"])
    assert d["gamma_effet"] and d["gamma_R_e"] and d["gamma_R_d"]
    assert v["taux"] == pytest.approx(d["gamma_effet"] * d["gamma_R_e"] * d["gamma_R_d"] * d["Bm"] / d["Bt"], rel=1e-9)
    s = v["schema"]
    assert s["type"] == "butee" and s["phase"] == v["phase"] and len(s["z"]) == len(s["p"]) == len(s["pp"]) > 10
    assert max(s["z"]) <= s["fond"] + 1e-6 and all(pp >= p - 1e-9 for p, pp in zip(s["p"], s["pp"]))
    assert "Bm = Σ L_i·p_i" in v["etapes"][0] and "taux" in v["etapes"][-1]


def test_fiche_bishop_expose_le_cercle_exact():
    v = {x["nom"]: x for x in _calcul(BASE)["verifications"]}["Stabilité générale (Bishop)"]
    d = {x["symbole"]: x["valeur"] for x in v["donnees"]}
    m = re.search(r"centre x = ([-\d.]+), z = ([-\d.]+), R = ([\d.]+) m", v["detail"])
    assert abs(d["x_c"] - float(m.group(1))) <= 0.051 and abs(d["z_c"] - float(m.group(2))) <= 0.051 and abs(d["R"] - float(m.group(3))) <= 0.051
    s = v["schema"]
    assert s["type"] == "cercle" and s["R"] == d["R"] and s["largeur"] == d["largeur"]
    assert s["zc"] - s["R"] < s["pied"]                   # le cercle passe sous le pied de l'écran
    if v["taux"] is not None:
        assert d["F_d"] and v["taux"] == pytest.approx(d["gamma_R_d"] / d["F_d"], rel=1e-9) and s["cercle_calcul"]


def test_fiche_fond_de_fouille_et_equilibre_vertical():
    vs = {x["nom"]: x for x in _calcul(BASE)["verifications"]}
    upl = vs["Fond de fouille — soulèvement (UPL)"]
    d = {x["symbole"]: x["valeur"] for x in upl["donnees"]}
    assert upl["schema"]["type"] == "fond_de_fouille" and d["u_pied"] == pytest.approx(d["γw"] * (upl["schema"]["nappe_amont"] - upl["schema"]["pied"]))
    assert d["Δh_aval"] == pytest.approx(d["Δh"] * d["L_aval"] / (d["L_amont"] + d["L_aval"]))
    assert d["i"] == pytest.approx(d["Δh_aval"] / d["L_aval"])
    ev = vs["Équilibre vertical (mobilisation de δp)"]
    d2 = {x["symbole"]: x["valeur"] for x in ev["donnees"]}
    assert ev["schema"]["type"] == "forces_verticales" and ev["schema"]["montants"] == d2["F_montants"]
    assert ev["taux"] == pytest.approx(d2["F_montants"] / d2["F_descendants"], rel=1e-9)


def test_fiche_buton_et_lierne():
    vs = {x["nom"]: x for x in _calcul(BASE_LIERNE)["verifications"]}
    b = vs["Buton — flambement et flexion"]
    d = {x["symbole"]: x["valeur"] for x in b["donnees"]}
    assert b["famille"] == "appuis" and b["schema"]["type"] == "barre" and b["schema"]["chi"] == d["χ"]
    assert f"χ = {d['χ']:.2f}" in b["detail"] and f"N_b,Rd = {d['N_b,Rd']:.0f} kN" in b["detail"]
    assert d["λ̄"] == pytest.approx((d["N_pl"] / d["N_cr"]) ** 0.5, rel=1e-9)
    assert b["taux"] == pytest.approx(d["N_Ed"] / d["N_b,Rd"] + d["M_Ed"] / d["M_c,Rd"], rel=1e-9)
    li = next(v for n, v in vs.items() if n.startswith("Lierne — flexion"))
    d3 = {x["symbole"]: x["valeur"] for x in li["donnees"]}
    assert li["famille"] == "liernes" and li["schema"]["type"] == "poutre_continue" and li["schema"]["e"] == d3["e"]
    assert d3["My"] == pytest.approx(d3["gamma_effets"] * d3["q"] * d3["e"] ** 2 / 8, rel=1e-9)
    assert d3["V"] == pytest.approx(d3["gamma_effets"] * 0.625 * d3["q"] * d3["e"], rel=1e-9)
    assert all(v["famille"] == "assemblages" for n, v in vs.items() if v["element"].startswith("A1 (") or v["element"].startswith("A2 ("))
