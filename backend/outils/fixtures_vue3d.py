"""Génère les jeux de résultats figés utilisés par les tests de la vue 3D (frontend).

    cd backend
    .venv/Scripts/python.exe -m outils.fixtures_vue3d

Écrit frontend/src/vue3d/__tests__/donnees/<exemple>.json : la réponse de /api/calcul
(resultats + projet) pour chaque exemple listé. Le test
tests/unitaires/test_vue3d_donnees.py vérifie que ces fichiers restent à jour.
"""
from __future__ import annotations

import json
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
SORTIE = RACINE / "frontend" / "src" / "vue3d" / "__tests__" / "donnees"
EXEMPLES = ["fouille_exemple", "fouille_ecoulement", "pseudo3d_angle", "berlinoise_tirants", "fouille_coupes", "pseudo3d_fouille_fermee"]


def resultats(nom: str) -> dict:
    from fastapi.testclient import TestClient

    from sout.api import app

    texte = (RACINE / "exemples" / f"{nom}.yaml").read_text(encoding="utf-8")
    r = TestClient(app).post("/api/calcul", json={"texte": texte}).json()
    if not r["ok"]:
        raise RuntimeError(f"{nom} : {r['erreurs']}")
    return {"resultats": r["resultats"], "projet": r["projet"]}


def _arrondi(v):
    """Six chiffres significatifs : fichiers plus légers, précision très supérieure aux tolérances des tests."""
    if isinstance(v, float):
        return float(f"{v:.6g}")
    if isinstance(v, list):
        return [_arrondi(x) for x in v]
    if isinstance(v, dict):
        return {k: _arrondi(x) for k, x in v.items()}
    return v


def ecrire() -> list[Path]:
    SORTIE.mkdir(parents=True, exist_ok=True)
    chemins = []
    for nom in EXEMPLES:
        p = SORTIE / f"{nom}.json"
        p.write_text(json.dumps(_arrondi(resultats(nom)), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        chemins.append(p)
    return chemins


if __name__ == "__main__":
    for p in ecrire():
        print(p, p.stat().st_size // 1024, "ko")
