"""Serveur FastAPI : relie le calcul à l'interface web.

Les fonctions de calcul restent pures ; ce module ne fait que la traduction
requêtes HTTP <-> objets Python.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel

from sout import __version__
from sout.noyau.phasage import ErreurModele, calculer
from sout.resultats import serialiser
from sout.script.conversion import ErreurConversion, vers_modele
from sout.script.lecteur import ScriptInvalide, lire_script
from sout.script.schema import Script

RACINE = Path(__file__).resolve().parents[2]
EXEMPLES = RACINE / "exemples"

app = FastAPI(title="RetainWall", version=__version__)


class Texte(BaseModel):
    texte: str


def _catalogue():
    """Base matériaux (None si indisponible)."""
    try:
        from sout.materiaux.base import catalogue_par_defaut
    except ImportError:
        return None
    return catalogue_par_defaut()


@app.get("/api/sante")
def sante() -> dict:
    """Point de contrôle : le serveur répond."""
    return {"statut": "ok", "version": __version__}


@app.get("/api/schema")
def schema() -> dict:
    """Schéma JSON du langage (auto-complétion et aide de l'éditeur)."""
    return Script.model_json_schema()


@app.get("/api/exemples")
def exemples() -> list[dict]:
    return [{"nom": p.stem, "texte": p.read_text(encoding="utf-8")} for p in sorted(EXEMPLES.glob("*.yaml"))]


@app.post("/api/valider")
def valider(t: Texte) -> dict:
    try:
        lire_script(t.texte)
    except ScriptInvalide as e:
        return {"ok": False, "erreurs": [x.vers_dict() for x in e.erreurs]}
    return {"ok": True, "erreurs": []}


def preparer(texte: str):
    """Script -> (script, modèle) ; lève ScriptInvalide ou ErreurConversion."""
    s = lire_script(texte)
    return s, vers_modele(s, _catalogue())


@app.post("/api/calcul")
def calcul(t: Texte) -> dict:
    try:
        s, m = preparer(t.texte)
        res = calculer(m)
    except ScriptInvalide as e:
        return {"ok": False, "erreurs": [x.vers_dict() for x in e.erreurs]}
    except (ErreurConversion, ErreurModele) as e:
        return {"ok": False, "erreurs": [{"ligne": None, "chemin": "", "message": str(e)}]}
    return {"ok": True, "erreurs": [], "resultats": serialiser(res, m, s.projet)}
