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


class DemandeCalcul(BaseModel):
    texte: str
    coupe: str | None = None     # nom d'une coupe de calcul : calcule cette coupe seule


# Cache des calculs par coupe : empreinte du script fusionné -> résultats sérialisés.
# Une coupe dont le script n'a pas changé n'est pas recalculée.
_CACHE_COUPES: dict[str, dict] = {}
_CACHE_MAX = 48
_STATS = {"calculs": 0, "cache": 0}


def statistiques_cache() -> dict:
    return dict(_STATS)


def vider_cache_coupes() -> None:
    _CACHE_COUPES.clear()
    _STATS["calculs"] = _STATS["cache"] = 0


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


def _resultats_script(texte: str) -> dict:
    """Résultats sérialisés d'un script complet (une coupe), avec cache par empreinte."""
    from sout.script.coupes import empreinte

    cle = empreinte(texte)
    if cle in _CACHE_COUPES:
        _STATS["cache"] += 1
        return _CACHE_COUPES[cle]
    ex = executer_texte(texte)
    _STATS["calculs"] += 1
    r = serialiser(ex.resultat, ex.modele, ex.script.projet, _catalogue(), normes.charger())
    r["verifications"] = [v.vers_dict() for v in ex.verifications]
    r["suggestions"] = ex.suggestions
    r["jeux_eau"] = {j: {"complet": res.complet} for j, (_, res) in ex.jeux.items() if j is not None}
    from sout.maquette3d.generer import geometrie

    r["maquette"] = geometrie(ex)   # géométrie de la vue 3D (contour, paroi, appuis en plan)
    if ex.script.calcul.mode == "pseudo3d":
        from sout.pseudo3d.calcul import serialiser as serialiser_p3d

        if ex.pseudo3d is not None:          # calculé une seule fois, dans verifications.executer
            r["pseudo3d"] = serialiser_p3d(ex.pseudo3d, ex.resultat)
        r["avertissements"].extend(ex.avertissements)
    if len(_CACHE_COUPES) >= _CACHE_MAX:
        del _CACHE_COUPES[next(iter(_CACHE_COUPES))]
    _CACHE_COUPES[cle] = r
    return r


def _erreur(e) -> dict:
    if isinstance(e, ScriptInvalide):
        return {"ok": False, "erreurs": [x.vers_dict() for x in e.erreurs]}
    return {"ok": False, "erreurs": [{"ligne": None, "chemin": "", "message": str(e)}]}


def _projet(texte: str):
    from sout.script.coupes import ErreurCoupe, preparer

    s = lire_script(texte)
    try:
        return s, preparer(texte, s)
    except ErreurCoupe as e:
        raise ErreurConversion(str(e)) from None


@app.post("/api/coupes/preparer")
def coupes_preparer(t: Texte) -> dict:
    """Coupes du projet (textes fusionnés non renvoyés) : nom, tronçon, trace, héritage, cache."""
    try:
        _, p = _projet(t.texte)
    except (ScriptInvalide, ErreurConversion) as e:
        return _erreur(e)
    return {"ok": True, "erreurs": [], "unique": p.unique, "contour": p.contour, "orphelins": p.orphelins,
            "avertissements": p.avertissements,
            "coupes": [{**c.vers_dict(), "en_cache": c.empreinte in _CACHE_COUPES} for c in p.coupes]}


def _assembler(p, resultats: dict[str, dict]) -> dict:
    from sout.script.coupes import chiffres_cles, phasage_projet, synthese_projet

    noms = [c.nom for c in p.coupes]
    projet, corr = phasage_projet([[ph["nom"] for ph in resultats[n]["phases"]] for n in noms])
    return {
        "unique": p.unique, "contour": p.contour, "orphelins": p.orphelins, "avertissements": p.avertissements,
        "coupes": [{**c.vers_dict(), "correspondance": corr[i], **({} if i == 0 else {"resultats": resultats[c.nom]})}
                   for i, c in enumerate(p.coupes)],
        "phasage_projet": projet,
        "synthese": {"verifications": synthese_projet({n: resultats[n].get("verifications", []) for n in noms}),
                     "chiffres": chiffres_cles({n: resultats[n] for n in noms})},
    }


@app.post("/api/coupes/synthese")
def coupes_synthese(t: Texte) -> dict:
    """Phasage projet, correspondance des phases et synthèse (pire coupe par vérification) ; calcule les coupes manquantes."""
    try:
        _, p = _projet(t.texte)
        resultats = {c.nom: _resultats_script(c.texte) for c in p.coupes}
    except (ScriptInvalide, ErreurConversion, ErreurModele) as e:
        return _erreur(e)
    a = _assembler(p, resultats)
    a["coupes"] = [{k: v for k, v in c.items() if k != "resultats"} for c in a["coupes"]]
    return {"ok": True, "erreurs": [], "projet": a}


@app.post("/api/calcul")
def calcul(t: DemandeCalcul) -> dict:
    """Calcul complet. Avec `coupe`, calcule cette coupe seule ; sinon toutes les coupes du projet
    (cache par coupe) et la synthèse. `resultats` = première coupe (compatibilité)."""
    try:
        s, p = _projet(t.texte)
        if t.coupe is not None:
            c = next((x for x in p.coupes if x.nom == t.coupe), None)
            if c is None:
                return {"ok": False, "erreurs": [{"ligne": None, "chemin": "coupes", "message": f"coupe « {t.coupe} » inconnue"}]}
            return {"ok": True, "erreurs": [], "resultats": _resultats_script(c.texte), "coupe": c.vers_dict()}
        resultats = {c.nom: _resultats_script(c.texte) for c in p.coupes}
    except (ScriptInvalide, ErreurConversion, ErreurModele) as e:
        return _erreur(e)
    premiere = resultats[p.coupes[0].nom]
    return {"ok": True, "erreurs": [], "resultats": premiere, "projet": _assembler(p, resultats)}


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
