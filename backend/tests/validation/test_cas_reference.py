"""Cas de validation contre K-Réa ou RIDO (tolérance 5 %, CLAUDE.md règle 3).

Pour chaque dossier casXX contenant `entree.yaml` et `reference.json`, on
compare par phase : déplacement maximal, moment maximal (en valeur absolue)
et efforts d'appui. Les cas sans fichiers sont ignorés (skip) et signalés.
"""
import json
from pathlib import Path

import numpy as np
import pytest

from sout.api import _catalogue
from sout.noyau.phasage import calculer
from sout.script.conversion import vers_modele
from sout.script.lecteur import lire_script

TOLERANCE = 0.05
DOSSIER = Path(__file__).resolve().parent
CAS = sorted(p.name for p in DOSSIER.iterdir() if p.is_dir() and p.name.startswith("cas"))


def _ecart(calc, ref):
    return abs(calc - ref) / max(abs(ref), 1e-9)


@pytest.mark.validation
@pytest.mark.parametrize("cas", CAS)
def test_cas_reference(cas):
    d = DOSSIER / cas
    if not ((d / "entree.yaml").exists() and (d / "reference.json").exists()):
        pytest.skip(f"{cas} : entree.yaml ou reference.json absent (voir {cas}/README.md)")
    ref = json.loads((d / "reference.json").read_text(encoding="utf-8"))
    s = lire_script((d / "entree.yaml").read_text(encoding="utf-8"))
    res = calculer(vers_modele(s, _catalogue()))
    assert res.complet, [p.message for p in res.phases]
    phases = {p.nom: p for p in res.phases}
    ecarts = []
    for rp in ref["phases"]:
        p = phases[rp["nom"]]
        if "deplacement_max_mm" in rp:
            e = _ecart(np.abs(p.y).max() * 1e3, rp["deplacement_max_mm"])
            ecarts.append((rp["nom"], "déplacement max", e))
        if "moment_max_kNm" in rp:
            e = _ecart(np.abs(p.M).max(), rp["moment_max_kNm"])
            ecarts.append((rp["nom"], "moment max", e))
        for nom, val in rp.get("efforts_appuis_kN", {}).items():
            calc = next(a["effort"] for a in p.appuis if a["nom"] == nom)
            ecarts.append((rp["nom"], f"effort {nom}", _ecart(calc, val)))
    hors = [f"{ph} / {g} : écart {e:.1%}" for ph, g, e in ecarts if e > TOLERANCE]
    assert not hors, f"{cas} ({ref.get('logiciel', '?')}) hors tolérance :\n" + "\n".join(hors)
