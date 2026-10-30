"""Coefficients de largeur par zone (paroi.coefficients_largeur, commande coe de RIDO)."""
import numpy as np
import pytest
from fastapi.testclient import TestClient

from sout.api import app
from sout.parois.construction import construire_ecran
from sout.script.lecteur import lire_script

CLIENT = TestClient(app)


def _script(EI: float, zones: str = "") -> str:
    return f"""projet: Essai coefficients de largeur
calcul: {{ kh: impose }}
paroi: {{ type: berlinoise, tete: 0.0, pied: -8.0, EI: {EI}{zones} }}
sol:
  - {{ nom: Sable, toit: 0.0, gamma: 19, gamma_dejauge: 10, phi: 32, kh: 12000 }}
surcharges:
  - {{ nom: q, type: bande, q: 10, distance: 0.5, largeur: 4, phase: 1 }}
phases:
  - {{ nom: Terrassement, excaver: -3.0 }}
"""


def test_fonction_par_zone():
    p = lire_script(_script(20000, ", coefficients_largeur: [{ haut: -3.0, bas: -8.0, rapport: 0.5 }]")).paroi
    e = construire_ecran(p)
    f, g = e.largeur_reaction(np.array([-1.0, -3.0, -5.0, -8.0]), 0, -3.0)
    assert list(f) == [1.0, 0.5, 0.5, 0.5] and list(g) == list(f)
    assert e.infos["coefficients_largeur"][0]["rapport"] == 0.5


def test_berlinoise_EI_impose_sans_largeur_refusee_sauf_avec_zones():
    with pytest.raises(Exception, match="fiche discontinue"):
        construire_ecran(lire_script(_script(20000)).paroi)


def test_similitude_sol_et_EI_multiplies_par_r():
    """Pressions, raideurs et limites du sol multipliées par r sur toute la hauteur, EI multiplié par r :
    l'équation EI·y'''' = p(y) est inchangée, donc y identique et M multiplié par r (vérification exacte)."""
    r = 0.4
    toute = ", coefficients_largeur: [{ haut: 0.0, bas: -8.0, rapport: %g }]"
    a = CLIENT.post("/api/calcul", json={"texte": _script(20000, toute % 1.0)}).json()["resultats"]["phases"][-1]
    b = CLIENT.post("/api/calcul", json={"texte": _script(20000 * r, toute % r)}).json()["resultats"]["phases"][-1]
    assert a["ok"] and b["ok"]
    assert np.allclose(b["y_mm"], a["y_mm"], rtol=1e-6, atol=1e-6)
    assert np.allclose(b["M"], r * np.array(a["M"]), rtol=1e-6, atol=1e-6)
    assert max(abs(x) for x in a["y_mm"]) > 1.0
