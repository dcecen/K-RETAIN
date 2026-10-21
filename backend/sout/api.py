"""Serveur FastAPI : relie le calcul à l'interface web.

Les fonctions de calcul restent pures ; ce module ne fait que la traduction
requêtes HTTP <-> objets Python.
"""
from fastapi import FastAPI

from sout import __version__

app = FastAPI(title="RetainWall", version=__version__)


@app.get("/api/sante")
def sante() -> dict:
    """Point de contrôle : le serveur répond."""
    return {"statut": "ok", "version": __version__}
