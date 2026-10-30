"""Lecture et conversion des fichiers RIDO (sout/script/rido.py), outils sans Excel et fichiers de démonstration.

Le fichier de référence est le fichier réel fourni par l'utilisateur (docs/rido/berlinoise_IPE400_excel.rid) ;
ses valeurs viennent d'une feuille Excel non fournie : les tests la remplacent par une feuille de démonstration
(outils.rido_exemples.CELLULES_DEMO), ce qui vérifie la lecture, pas des résultats RIDO."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from outils.rido_exemples import CAS, CELLULES_DEMO, texte_r00, texte_rido
from outils.rido_sans_excel import lire_texte, sans_excel
from sout.api import app
from sout.script.lecteur import lire_script
from sout.script.rido import Classeur, ErreurExpression, ValeurIndisponible, charger_table, convertir, evaluer

RACINE = Path(__file__).resolve().parents[3]
FOURNI = RACINE / "docs" / "rido" / "berlinoise_IPE400_excel.rid"
EXEMPLES = RACINE / "exemples" / "rido"
CLIENT = TestClient(app)


def _fourni() -> str:
    return FOURNI.read_text(encoding="utf-8")


def _calcul(texte: str) -> dict:
    r = CLIENT.post("/api/calcul", json={"texte": texte}).json()
    assert r["ok"], r.get("erreurs")
    return r["resultats"]


def test_expressions_rido():
    v = {"b": 0.18, "h": 0.4, "esp": 2.1, "B": 9.0}
    assert evaluer("min(1;(b+2*h)/esp)", v) == pytest.approx(0.98 / 2.1)
    assert evaluer("2^3", v) == 8.0
    assert evaluer("(b>=0.6)*5", v) == 0.0 and evaluer("(b<0.6)*5", v) == 5.0
    assert evaluer("1/1.35/1.1", v) == pytest.approx(1 / 1.485)
    assert evaluer("max(1;2;3)", v) == 3.0 and evaluer(".05", v) == 0.05
    assert evaluer("B", v) == 9.0 and evaluer("b", v) == 0.18      # casse distinguée
    with pytest.raises(ErreurExpression):
        evaluer("x+1", v)
    with pytest.raises(ErreurExpression):
        evaluer("__import__('os')", v)
    with pytest.raises(ValeurIndisponible):
        evaluer("xlc(1,4,6)", v)
    cl = Classeur({(1, 1, 3): "Cote", (1, 2, 1): "TN", (1, 2, 3): 136.6, (1, 4, 6): 23130})
    assert evaluer("xlc(1,4,6)", v, cl) == 23130 and evaluer("xlc(1,l_TN,c_Cote)", v, cl) == 136.6


def test_fichier_fourni_sans_feuille_excel():
    """Sans la feuille, chaque valeur liée à Excel est signalée ; les blocs du fichier sont reconnus."""
    conv = convertir(_fourni(), FOURNI.name)
    assert not conv.complet
    assert any("xlc(1, 12, 4)" in e for e in conv.erreurs) and any("l_TN" in e for e in conv.erreurs)
    assert len(conv.script["sol"]) == 5
    assert [p["nom"] for p in conv.script["phases"]] == ["Phase 1 - Excavation à FF"]
    assert len(conv.calculs_non_repris) == 2
    assert any("directive Excel" in n for n in conv.non_repris)


def test_fichier_fourni_avec_feuille_de_demonstration():
    conv = convertir(_fourni(), FOURNI.name, classeur=Classeur(CELLULES_DEMO))
    assert conv.complet, conv.erreurs
    s = conv.script
    p = s["paroi"]
    assert (p["tete"], p["pied"], p["EI"]) == (136.6, 128.6, pytest.approx(2.1 * 23130 / 2.1))
    assert p["type"] == "berlinoise" and p["coefficients_largeur"] == [{"haut": 136.6, "bas": 128.6, "rapport": round(0.98 / 2.1, 6)}]
    # kh de la couche 1 : formule du fichier, Re = min(C ; max(P ; P')) avec b = 0,18 < 0,6 (P = 0)
    EM, a, EI, esp = 4.0, 0.5, 23130.0, 2.1
    C = 2 * (EM * 1000 / a) ** (4 / 3) / EI ** (1 / 3)
    Pbis = 6 * EM * 1000 / (4 / 3 * 2.65**a + a) / esp
    assert s["sol"][0]["kh"] == pytest.approx(min(C, Pbis), abs=0.01)
    assert [c["toit"] for c in s["sol"]] == [136.6, 135.6, 134.0, 132.0, 130.0]
    assert (s["sol"][1]["gamma"], s["sol"][1]["gamma_dejauge"], s["sol"][1]["phi"], s["sol"][1]["c"]) == (19, 9, 27, 5)
    assert s["eau"] == {"rido": {"amont": 125.0, "aval": 125.0}}
    assert s["surcharges"] == [{"nom": "sub1", "type": "bande", "q": 5.0, "distance": 0.5, "largeur": 10.0, "cote": 136.6,
                                "cote_ecran": "amont", "phase": 1}]
    assert s["phases"] == [{"nom": "Phase 1 - Excavation à FF", "excaver": 133.6}]
    assert any("rrc" in n for n in conv.non_repris)
    assert any("MEL" in c for c in conv.calculs_non_repris) and any("ELU" in c for c in conv.calculs_non_repris)
    lire_script(conv.texte)
    res = _calcul(conv.texte)
    assert all(ph["ok"] for ph in res["phases"])


def test_ordre_des_colonnes_relu_dans_la_table():
    """Corriger l'ordre dans docs/rido/correspondance.yaml suffit : φ et c permutés dans la table -> lus permutés."""
    table = charger_table()
    table["couches"]["colonnes"] = ["base", "gamma", "gamma_dejauge", "ka", "k0", "kp", "c", "phi", "delta_a", "delta_p", "kh"]
    s = convertir(_fourni(), classeur=Classeur(CELLULES_DEMO), table=table).script
    assert (s["sol"][1]["phi"], s["sol"][1]["c"]) == (5, 27)


def _mini(couche: str, commandes: str) -> str:
    return ("Essai\n#EI = 50000\n10 0\n0 EI\n10\n" + couche + "\n5 .05\n" + commandes)


def test_toit_detecte_delta_en_degres_et_phases_multiples():
    t = _mini("10 20 10 0 0 0 30 0 20 10 8000",
              '*"P1\nber(2) 8\ncal(2)\n*"P2\nber(2) 6\ncal(2)\nfap 1 1.35\ncal(2)\nfap 1 1 1\n*"P3\nber(2) 5\ncal(2)\nxyz 3\nfin\nstop\n')
    conv = convertir(t)
    s = conv.script
    assert s["sol"][0]["toit"] == 10 and any("toit" in h for h in conv.hypotheses)
    assert s["sol"][0]["delta_a_sur_phi"] == pytest.approx(20 / 30) and s["sol"][0]["delta_p_sur_phi"] == pytest.approx(1 / 3)
    assert [p.get("excaver") for p in s["phases"]] == [8, 6, 5] and [p["nom"] for p in s["phases"]] == ["P1", "P2", "P3"]
    assert len(conv.calculs_non_repris) == 1
    assert any("xyz" in n for n in conv.non_repris) and any("stop" in n for n in conv.non_repris)
    assert s["paroi"]["type"] == "palplanche" and s["eau"]["rido"]["amont"] == 5


def test_butee_au_dela_de_coulomb_signalee():
    conv = convertir(_mini("0 20 10 0 0 0 30 0 0.66 0.66 8000", '*"P1\nber(2) 8\ncal(2)\nfin\n'))
    assert any("Kérisel-Absi" in h for h in conv.hypotheses)


def test_version_sans_excel():
    cl = Classeur(CELLULES_DEMO)
    texte, messages = sans_excel(_fourni(), cl, "demo")
    assert not messages and "xlc(" not in texte and "XLS=" not in texte and "CONST=" not in texte
    assert "#EI = 2.1*I/esp" in texte and "#Re1 = min(C1;max(P1;P1bis))" in texte
    assert convertir(texte).script == convertir(_fourni(), classeur=cl).script
    gabarit, _ = sans_excel(_fourni(), None)
    assert "#X12_4 = A_RENSEIGNER" in gabarit and "*X12_4 : cellule xlc(1,12,4)" in gabarit
    assert not any("xlc(" in l for l in gabarit.splitlines() if not l.startswith("*"))


def test_fichiers_de_demonstration_a_jour_et_calculables():
    assert lire_texte(EXEMPLES / "R00_fichier_fourni_sans_excel.rid").replace("\r\n", "\n") == texte_r00()
    for cas in CAS:
        f = EXEMPLES / cas.fichier
        assert lire_texte(f).replace("\r\n", "\n") == texte_rido(cas), f"{f.name} à régénérer : python -m outils.rido_exemples"
        conv = convertir(lire_texte(f), f.name)
        assert conv.complet, (f.name, conv.erreurs)
        assert (EXEMPLES / f"{cas.code}.yaml").read_text(encoding="utf-8") == conv.texte, f"{cas.code}.yaml à régénérer"
        res = _calcul(conv.texte)
        assert len(res["phases"]) == len(cas.fonds) + 1 and all(ph["ok"] for ph in res["phases"]), f.name


@pytest.mark.validation
def test_exemples_rido_fournis():
    """Fichiers RIDO réels de docs/rido : lecture sans erreur ; valeurs Excel manquantes signalées."""
    exemples = sorted((RACINE / "docs" / "rido").glob("*.rid*"))
    if not exemples:
        pytest.skip("aucun fichier RIDO dans docs/rido")
    for f in exemples:
        conv = convertir(lire_texte(f), f.name)
        assert conv.script["phases"], f.name
        assert conv.complet or any("feuille Excel" in e or "libellé" in e for e in conv.erreurs), f.name
