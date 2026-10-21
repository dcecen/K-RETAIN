"""J7 — convertisseur RIDO piloté par table (aucun mot-clé RIDO réel n'est supposé).

Les mots-clés ci-dessous sont FICTIFS : ils testent le mécanisme de conversion,
pas le format RIDO."""
from pathlib import Path

import pytest

from sout.script.lecteur import lire_script
from sout.script.rido import charger_table, convertir

RACINE = Path(__file__).resolve().parents[3]

TABLE_FICTIVE = {
    "commentaires": ["#"],
    "mots_cles": {
        "XPROJ": {"cible": "projet", "colonnes": ["projet"]},
        "XPAROI": {"cible": "paroi", "colonnes": ["tete", "pied", "EI"], "fixes": {"type": "palplanche"}},
        "XCOUCHE": {"cible": "sol[]", "colonnes": ["nom", "toit", "gamma", "gamma_dejauge", "phi", "c", "EM", "alpha"],
                    "facteurs": {"EM": 1000.0}},
        "XPHASES": {"cible": "phases[]", "colonnes": ["nom", "excaver"], "lignes_suivantes": 2},
    },
}

FICHIER_FICTIF = """# fichier fictif
XPROJ Essai
XPAROI 0.0 -12.0 90000
XCOUCHE Sable 0.0 20 10 32 0 12 0.33
XINCONNU 1 2 3
XPHASES
Exc1 -2.0
Exc2 -4.5
"""


def test_conversion_avec_table_fictive():
    conv = convertir(FICHIER_FICTIF, "essai.rido", TABLE_FICTIVE)
    s = conv.script
    assert s["projet"] == "Essai"
    assert s["paroi"] == {"type": "palplanche", "tete": 0.0, "pied": -12.0, "EI": 90000.0}
    assert s["sol"][0]["EM"] == 12000.0 and s["sol"][0]["toit"] == 0.0
    assert [p["excaver"] for p in s["phases"]] == [-2.0, -4.5]
    assert any("XINCONNU" in r for r in conv.non_repris)
    script = lire_script(conv.texte)  # le texte produit est un script valide
    assert script.paroi.EI == 90000


def test_table_livree_vide_rien_n_est_devine():
    assert charger_table().get("mots_cles") == {}
    conv = convertir(FICHIER_FICTIF, "essai")
    assert conv.repris == 0
    assert len(conv.non_repris) == 8  # toutes les lignes non vides (aucun préfixe de commentaire déclaré)


@pytest.mark.validation
def test_exemples_rido_fournis():
    exemples = sorted((RACINE / "docs" / "rido").glob("*.rid*"))
    if not exemples or not charger_table().get("mots_cles"):
        pytest.skip("exemples RIDO ou table de correspondance non fournis (docs/rido)")
    for f in exemples:
        conv = convertir(f.read_text(encoding="utf-8", errors="replace"), f.name)
        lire_script(conv.texte)
