"""Serveur FastAPI : relie le calcul à l'interface web.

Les fonctions de calcul restent pures ; ce module ne fait que la traduction
requêtes HTTP <-> objets Python.
"""
from __future__ import annotations

import time

from pathlib import Path

import hashlib
import logging
import threading

from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from sout import __version__, normes
from sout.noyau.phasage import ErreurModele
from sout.resultats import serialiser
from sout.script.conversion import ErreurConversion, vers_modele
from sout.script.lecteur import ScriptInvalide, lire_script
from sout.script.schema import Script

RACINE = Path(__file__).resolve().parents[2]
EXEMPLES = RACINE / "exemples"

app = FastAPI(title="RetainWall", version=__version__)
_journal = logging.getLogger("retainwall")


@app.exception_handler(Exception)
async def _erreur_interne(request: Request, exc: Exception):
    """Toute exception non prévue : message en français lisible par l'interface (au lieu du
    « Internal Server Error » anonyme), détail complet dans le journal du serveur."""
    _journal.exception("erreur interne sur %s", request.url.path)
    message = (f"Erreur interne du serveur de calcul ({type(exc).__name__}) : {exc} — "
               "signalez ce message avec le script qui l'a provoqué.")
    return JSONResponse(status_code=500, content={"ok": False, "erreurs": [{"ligne": None, "chemin": "", "message": message}]})


_MESSAGES_422 = {
    "missing": "champ obligatoire manquant",
    "string_type": "texte attendu",
    "string_too_long": f"texte trop long (maximum {2_000_000:,} caractères)".replace(",", " "),
    "dict_type": "bloc de valeurs attendu",
    "float_parsing": "nombre attendu",
    "json_invalid": "JSON invalide",
}


@app.exception_handler(RequestValidationError)
async def _requete_invalide(request: Request, exc: RequestValidationError):
    """Requête mal formée (champ manquant, mauvais type, texte trop long) : message en français."""
    details = "; ".join(f"{'.'.join(str(x) for x in e['loc'] if x != 'body')} : {_MESSAGES_422.get(e['type'], e['msg'])}"
                        for e in exc.errors())
    return JSONResponse(status_code=422, content={"ok": False, "erreurs": [
        {"ligne": None, "chemin": "", "message": f"Requête invalide : {details}"}]})


# Identifications réussies (nom, empreinte du mot de passe) -> instant d'expiration. Sans ce cache,
# chaque requête (fichiers statiques compris) recalculait 600 000 itérations PBKDF2 dans la boucle
# d'événements. Un compte supprimé reste accepté au plus _AUTH_TTL secondes.
_AUTH_CACHE: dict[tuple[str, str], float] = {}
_AUTH_TTL = 600.0
_AUTH_MAX = 256


def vider_cache_authentification() -> None:
    _AUTH_CACHE.clear()


@app.middleware("http")
async def controle_acces(request, call_next):
    """Authentification HTTP Basic en déploiement (RETAINWALL_AUTH=1) ; /api/sante reste libre."""
    import base64

    from fastapi.responses import PlainTextResponse
    from starlette.concurrency import run_in_threadpool

    from sout import utilisateurs

    if not utilisateurs.authentification_active() or request.url.path == "/api/sante":
        return await call_next(request)
    entete = request.headers.get("authorization", "")
    if entete.lower().startswith("basic "):
        try:
            nom, _, mdp = base64.b64decode(entete[6:]).decode("utf-8").partition(":")
        except (ValueError, UnicodeDecodeError):
            nom, mdp = "", ""
        if nom:
            cle = (nom, hashlib.sha256(mdp.encode("utf-8")).hexdigest())
            maintenant = time.monotonic()
            if _AUTH_CACHE.get(cle, 0.0) > maintenant:
                return await call_next(request)
            if await run_in_threadpool(utilisateurs.verifier, nom, mdp):   # PBKDF2 hors de la boucle d'événements
                if len(_AUTH_CACHE) >= _AUTH_MAX:
                    _AUTH_CACHE.clear()
                _AUTH_CACHE[cle] = maintenant + _AUTH_TTL
                return await call_next(request)
    return PlainTextResponse("Identification requise", status_code=401,
                             headers={"WWW-Authenticate": 'Basic realm="RetainWall", charset="UTF-8"'})


TAILLE_MAX_SCRIPT = 2_000_000          # caractères ; un script de projet fait quelques milliers de lignes
TAILLE_MAX_IMPORT = 20 * 1024 * 1024    # octets, catalogue CSV / Excel


class Texte(BaseModel):
    texte: str = Field(max_length=TAILLE_MAX_SCRIPT)


class DemandeCalcul(BaseModel):
    texte: str = Field(max_length=TAILLE_MAX_SCRIPT)
    coupe: str | None = None     # nom d'une coupe de calcul : calcule cette coupe seule


# Cache des calculs par coupe : (empreinte du script fusionné | empreinte de l'environnement) -> résultats
# sérialisés. L'environnement = version du logiciel, fichiers docs/normes, base matériaux et catalogues :
# corriger un coefficient ou importer un catalogue invalide donc le cache sans redémarrage.
_CACHE_COUPES: dict[str, dict] = {}
_CACHE_MAX = 48
_STATS = {"calculs": 0, "cache": 0}
_VERROU_CACHE = threading.Lock()


def statistiques_cache() -> dict:
    return dict(_STATS)


def vider_cache_coupes() -> None:
    with _VERROU_CACHE:
        _CACHE_COUPES.clear()
        _STATS["calculs"] = _STATS["cache"] = 0


def _empreinte_environnement() -> str:
    """Empreinte (nom, date, taille) de tout ce qui influence un résultat en plus du texte du script."""
    from sout.materiaux.base import CATALOGUES, CHEMIN_BASE

    h = hashlib.sha256(__version__.encode("utf-8"))
    fichiers = sorted(normes.DOSSIER.rglob("*.yaml")) + sorted(normes.DOSSIER.rglob("*.csv")) + [CHEMIN_BASE]
    if CATALOGUES.exists():
        fichiers += sorted(p for p in CATALOGUES.iterdir() if p.is_file())
    for f in fichiers:
        try:
            st = f.stat()
        except OSError:
            continue
        h.update(f"{f.name}:{st.st_mtime_ns}:{st.st_size};".encode())
    return h.hexdigest()[:16]


def _cle_cache(empreinte_texte: str) -> str:
    return f"{empreinte_texte}|{_empreinte_environnement()}"


def _catalogue():
    """Base matériaux (None si indisponible)."""
    try:
        from sout.materiaux.base import catalogue_par_defaut
    except ImportError:
        return None
    return catalogue_par_defaut()


_DEMARRAGE = time.time()


@app.get("/api/sante")
def sante() -> dict:
    """Point de contrôle : le serveur répond. `demarrage` (secondes depuis 1970) permet au lanceur de
    savoir si le code a changé depuis le démarrage (il redémarre alors le serveur)."""
    return {"statut": "ok", "version": __version__, "demarrage": _DEMARRAGE}


@app.get("/api/schema")
def schema() -> dict:
    """Schéma JSON du langage (auto-complétion et aide de l'éditeur)."""
    return Script.model_json_schema()


def _aplatir_normes(noeud, prefixe: str = "") -> list[dict]:
    """Feuilles d'un fichier de normes : {cle pointée, valeur, source}. Une feuille est un bloc
    {valeur, source} ou un scalaire ; une valeur None reste None (TODO-NORME)."""
    out = []
    if isinstance(noeud, dict) and "valeur" in noeud:
        return [{"cle": prefixe, "valeur": noeud.get("valeur"), "source": str(noeud.get("source") or "")}]
    if isinstance(noeud, dict):
        for k, v in noeud.items():
            out.extend(_aplatir_normes(v, f"{prefixe}.{k}" if prefixe else str(k)))
        return out
    return [{"cle": prefixe, "valeur": noeud, "source": ""}]


@app.get("/api/normes")
def valeurs_normatives() -> dict:
    """Référentiel tel que lu par le calcul (docs/normes/*.yaml, lecture seule) : pour chaque fichier,
    ses valeurs (clé, valeur, source). Sert à l'onglet « Hypothèses et référentiel » et à la note."""
    n = normes.charger()
    return {"dossier": str(normes.DOSSIER),
            "fichiers": {nom: _aplatir_normes(arbre) for nom, arbre in n.donnees.items()}}


@app.get("/api/exemples")
def exemples() -> list[dict]:
    """Scripts proposés dans le menu Fichier : exemples de projet (exemples/*.yaml) puis scripts de
    vérification élémentaire (exemples/elementaires/*.yaml, résultat attendu et source en en-tête)."""
    projets = [{"nom": p.stem, "groupe": "Exemples", "texte": p.read_text(encoding="utf-8")}
               for p in sorted(EXEMPLES.glob("*.yaml"))]
    elementaires = [{"nom": p.stem, "groupe": "Vérifications élémentaires", "texte": p.read_text(encoding="utf-8")}
                    for p in sorted((EXEMPLES / "elementaires").glob("*.yaml"))]
    return projets + elementaires


@app.get("/api/validation/rapport")
def rapport_validation():
    """Rapport de la rafale d'exemples élémentaires (docs/validation, généré par
    python -m outils.rafale_elementaire) : page HTML autonome."""
    from fastapi.responses import HTMLResponse

    chemin = RACINE / "docs" / "validation" / "rafale_elementaire.html"
    if not chemin.exists():
        raise HTTPException(404, "rapport absent : lancer python -m outils.rafale_elementaire dans backend")
    return HTMLResponse(chemin.read_text(encoding="utf-8"))


@app.post("/api/valider")
def valider(t: Texte) -> dict:
    """Erreurs bloquantes (`erreurs`) et avertissements non bloquants (mots-clés inconnus ignorés)."""
    try:
        s = lire_script(t.texte)
    except ScriptInvalide as e:
        return {"ok": False, "erreurs": [x.vers_dict() for x in e.erreurs if x.niveau == "erreur"],
                "avertissements": [x.vers_dict() for x in e.erreurs if x.niveau != "erreur"]}
    return {"ok": True, "erreurs": [], "avertissements": [x.vers_dict() for x in s.avertissements_lecture]}


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

    cle = _cle_cache(empreinte(texte))
    with _VERROU_CACHE:
        if cle in _CACHE_COUPES:
            _STATS["cache"] += 1
            return _CACHE_COUPES[cle]
    ex = executer_texte(texte)
    _STATS["calculs"] += 1
    r = serialiser(ex.resultat, ex.modele, ex.script.projet, _catalogue(), normes.charger())
    r["verifications"] = [v.vers_dict() for v in ex.verifications]
    r["avertissements"] = [f"Script : {e}" for e in ex.script.avertissements_lecture] + r["avertissements"]
    r["suggestions"] = ex.suggestions
    r["jeux_eau"] = {j: {"complet": res.complet} for j, (_, res) in ex.jeux.items() if j is not None}
    from sout.maquette3d.generer import geometrie

    r["maquette"] = geometrie(ex)   # géométrie de la vue 3D (contour, paroi, appuis en plan)
    if ex.script.calcul.mode == "pseudo3d":
        from sout.pseudo3d.calcul import serialiser as serialiser_p3d

        if ex.pseudo3d is not None:          # calculé une seule fois, dans verifications.executer
            r["pseudo3d"] = serialiser_p3d(ex.pseudo3d, ex.resultat)
        r["avertissements"].extend(ex.avertissements)
    with _VERROU_CACHE:
        while len(_CACHE_COUPES) >= _CACHE_MAX:
            del _CACHE_COUPES[next(iter(_CACHE_COUPES))]
        _CACHE_COUPES[cle] = r
    return r


def _erreur(e) -> dict:
    if isinstance(e, ScriptInvalide):
        return {"ok": False, "erreurs": [x.vers_dict() for x in e.erreurs if x.niveau == "erreur"],
                "avertissements": [x.vers_dict() for x in e.erreurs if x.niveau != "erreur"]}
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
            "coupes": [{**c.vers_dict(), "en_cache": _cle_cache(c.empreinte) in _CACHE_COUPES} for c in p.coupes]}


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
    if cat is None:
        raise HTTPException(503, "base matériaux indisponible sur ce serveur")
    return {t: cat.lister(t) for t in TABLES}


@app.get("/api/materiaux/references")
def references() -> dict:
    cat = _catalogue()
    if cat is None:
        raise HTTPException(503, "base matériaux indisponible sur ce serveur")
    return cat.references()


@app.post("/api/materiaux/import")
async def importer_catalogue(fichier: UploadFile) -> dict:
    """Importe un catalogue CSV/XLSX (copié dans docs/catalogues) puis reconstruit la base."""
    import tempfile

    from sout.materiaux.importer import importer

    nom = Path(fichier.filename or "catalogue.csv").name
    if Path(nom).suffix.lower() not in (".csv", ".xlsx"):
        raise HTTPException(400, "format attendu : .csv ou .xlsx")
    if nom.lower().startswith("modele_"):
        raise HTTPException(400, "un fichier « modele_* » est un modèle d'en-têtes, pas un catalogue : renommez-le (ex. profiles_fournisseur.csv)")
    contenu = await fichier.read(TAILLE_MAX_IMPORT + 1)
    if len(contenu) > TAILLE_MAX_IMPORT:
        raise HTTPException(413, f"fichier trop volumineux (maximum {TAILLE_MAX_IMPORT // (1024 * 1024)} Mo)")
    with tempfile.TemporaryDirectory() as d:
        chemin = Path(d) / nom
        chemin.write_bytes(contenu)
        try:
            compte = importer([chemin])
        except ValueError as e:
            raise HTTPException(400, str(e)) from None
    vider_cache_coupes()   # les résultats dépendent de la base
    return {"ok": True, "lignes": compte}


class FichierRido(BaseModel):
    texte: str = Field(max_length=TAILLE_MAX_SCRIPT)
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
    except (KeyError, ValueError) as e:
        raise HTTPException(400, str(e).strip("'")) from None


@app.post("/api/assemblages/verifier")
def assemblage_verifier(d: DemandeAssemblage) -> list[dict]:
    from sout.assemblages.service import verifier as verifier_assemblage

    try:
        return [v.vers_dict() for v in verifier_assemblage(d.type, d.parametres, d.efforts, _catalogue(), normes.charger(), d.fck)]
    except (KeyError, ValueError) as e:
        raise HTTPException(400, str(e).strip("'")) from None


# Interface compilée — à garder en DERNIER : un montage sur « / » masque les routes déclarées après lui.
# Interface compilée (npm run build) servie par le même serveur en déploiement.
_DIST = RACINE / "frontend" / "dist"
if _DIST.exists():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=_DIST, html=True), name="interface")
