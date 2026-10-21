"""Serveur FastAPI : relie le calcul à l'interface web.

Les fonctions de calcul restent pures ; ce module ne fait que la traduction
requêtes HTTP <-> objets Python.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from pydantic import BaseModel

from sout import __version__, normes
from sout.noyau.phasage import ErreurModele
from sout.resultats import serialiser
from sout.script.conversion import ErreurConversion, vers_modele
from sout.script.lecteur import ScriptInvalide, lire_script
from sout.script.schema import Script

RACINE = Path(__file__).resolve().parents[2]
EXEMPLES = RACINE / "exemples"

app = FastAPI(title="RetainWall", version=__version__)


@app.middleware("http")
async def controle_acces(request, call_next):
    """Authentification HTTP Basic en déploiement (RETAINWALL_AUTH=1) ; /api/sante reste libre."""
    import base64

    from fastapi.responses import PlainTextResponse

    from sout import utilisateurs

    if not utilisateurs.authentification_active() or request.url.path == "/api/sante":
        return await call_next(request)
    entete = request.headers.get("authorization", "")
    if entete.lower().startswith("basic "):
        try:
            nom, _, mdp = base64.b64decode(entete[6:]).decode("utf-8").partition(":")
        except (ValueError, UnicodeDecodeError):
            nom, mdp = "", ""
        if nom and utilisateurs.verifier(nom, mdp):
            return await call_next(request)
    return PlainTextResponse("Identification requise", status_code=401,
                             headers={"WWW-Authenticate": 'Basic realm="RetainWall", charset="UTF-8"'})


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
    return s, vers_modele(s, _catalogue(), normes.charger())


def executer_texte(texte: str):
    """Script -> exécution complète (calculs par jeu d'eau + vérifications)."""
    from sout.verifications import executer

    return executer(lire_script(texte), _catalogue(), normes.charger())


@app.post("/api/calcul")
def calcul(t: Texte) -> dict:
    try:
        ex = executer_texte(t.texte)
    except ScriptInvalide as e:
        return {"ok": False, "erreurs": [x.vers_dict() for x in e.erreurs]}
    except (ErreurConversion, ErreurModele) as e:
        return {"ok": False, "erreurs": [{"ligne": None, "chemin": "", "message": str(e)}]}
    r = serialiser(ex.resultat, ex.modele, ex.script.projet)
    r["verifications"] = [v.vers_dict() for v in ex.verifications]
    r["suggestions"] = ex.suggestions
    r["jeux_eau"] = {j: {"complet": res.complet} for j, (_, res) in ex.jeux.items() if j is not None}
    from sout.maquette3d.generer import geometrie

    r["maquette"] = geometrie(ex)   # géométrie de la vue 3D (contour, paroi, appuis en plan)
    if ex.script.calcul.mode == "pseudo3d":
        from sout.pseudo3d.calcul import depuis_script, serialiser as serialiser_p3d

        try:
            r["pseudo3d"] = serialiser_p3d(depuis_script(ex), ex.resultat)
        except ErreurModele as e:
            r["avertissements"].append(f"Pseudo-3D non calculé : {e}")
    return {"ok": True, "erreurs": [], "resultats": r}


@app.get("/api/materiaux")
def materiaux() -> dict:
    """Contenu de la base matériaux, table par table."""
    from sout.materiaux.base import TABLES

    cat = _catalogue()
    return {t: cat.lister(t) for t in TABLES}


@app.get("/api/materiaux/references")
def references() -> dict:
    return _catalogue().references()


@app.post("/api/materiaux/import")
async def importer_catalogue(fichier: UploadFile) -> dict:
    """Importe un catalogue CSV/XLSX (copié dans docs/catalogues) puis reconstruit la base."""
    import tempfile

    from sout.materiaux.importer import importer

    nom = Path(fichier.filename or "catalogue.csv").name
    if Path(nom).suffix.lower() not in (".csv", ".xlsx"):
        raise HTTPException(400, "format attendu : .csv ou .xlsx")
    with tempfile.TemporaryDirectory() as d:
        chemin = Path(d) / nom
        chemin.write_bytes(await fichier.read())
        try:
            compte = importer([chemin])
        except ValueError as e:
            raise HTTPException(400, str(e)) from None
    return {"ok": True, "lignes": compte}


class FichierRido(BaseModel):
    texte: str
    nom: str = "import RIDO"


@app.post("/api/rido")
def import_rido(f: FichierRido) -> dict:
    """Convertit un fichier RIDO en script, avec le rapport des données non reprises."""
    from sout.script.rido import convertir

    conv = convertir(f.texte, f.nom)
    return {"texte": conv.texte, "rapport": conv.rapport}


@app.post("/api/maquette")
def maquette(t: Texte):
    """Maquette 3D autonome (fichier HTML unique)."""
    from fastapi.responses import HTMLResponse

    from sout.maquette3d.generer import generer_html

    try:
        ex = executer_texte(t.texte)
    except ScriptInvalide as e:
        raise HTTPException(400, "script invalide : " + "; ".join(str(x) for x in e.erreurs[:3])) from None
    except (ErreurConversion, ErreurModele) as e:
        raise HTTPException(400, str(e)) from None
    p3d = None
    if ex.script.calcul.mode == "pseudo3d" and ex.script.pseudo3d is not None:
        try:
            from sout.pseudo3d.calcul import champ_pour_maquette
            p3d = champ_pour_maquette(ex)
        except ImportError:
            p3d = None
    return HTMLResponse(generer_html(ex, p3d))


class DemandeAssemblage(BaseModel):
    type: str
    parametres: dict = {}
    efforts: dict = {}
    fck: float | None = None


@app.get("/api/assemblages/types")
def assemblages_types() -> list[dict]:
    from sout.assemblages.service import liste_types

    return liste_types()


@app.post("/api/assemblages/schema")
def assemblage_schema(d: DemandeAssemblage) -> dict:
    from sout.assemblages.service import schema as schema_assemblage

    try:
        return schema_assemblage(d.type, d.parametres, d.efforts, _catalogue(), normes.charger(), d.fck)
    except KeyError as e:
        raise HTTPException(400, str(e)) from None


@app.post("/api/assemblages/verifier")
def assemblage_verifier(d: DemandeAssemblage) -> list[dict]:
    from sout.assemblages.service import verifier as verifier_assemblage

    try:
        return [v.vers_dict() for v in verifier_assemblage(d.type, d.parametres, d.efforts, _catalogue(), normes.charger(), d.fck)]
    except KeyError as e:
        raise HTTPException(400, str(e)) from None


# Interface compilée — à garder en DERNIER : un montage sur « / » masque les routes déclarées après lui.
# Interface compilée (npm run build) servie par le même serveur en déploiement.
_DIST = RACINE / "frontend" / "dist"
if _DIST.exists():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=_DIST, html=True), name="interface")
