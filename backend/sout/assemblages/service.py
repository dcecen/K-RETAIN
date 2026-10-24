"""Service des assemblages : registre des types, contexte matériaux, schéma et vérifications."""
from __future__ import annotations

from dataclasses import asdict

from ..verifs import Verif
from . import types_butons, types_liernes, types_tirants_bracons  # noqa: F401  (enregistrement des types)
from .base import REGISTRE, Contexte, Param, TypeAssemblage

PARAMS_COMMUNS = [
    Param("acier", "Nuance d'acier des pièces", "", "S355", genre="acier"),
    Param("lierne", "Profilé de lierne (base matériaux)", "", "", genre="profil"),
    Param("buton", "Élément de buton (base matériaux)", "", "", genre="tube"),
]


def liste_types() -> list[dict]:
    return [{"cle": t.cle, "nom": t.nom, "famille": t.famille, "description": t.description, "efforts": t.efforts,
             "parametres": [asdict(p) for p in PARAMS_COMMUNS + t.parametres]} for t in REGISTRE.values()]


def type_de(cle: str) -> TypeAssemblage:
    if cle not in REGISTRE:
        raise KeyError(f"type d'assemblage inconnu : {cle} (attendu : {', '.join(REGISTRE)})")
    return REGISTRE[cle]


def contexte(params: dict, catalogue, normes, fck: float | None = None) -> Contexte:
    nuance = params.get("acier") or "S355"
    fy, fu, demo = 355.0, 490.0, True
    replis: list[str] = []
    try:
        if catalogue is None:
            raise KeyError(nuance)
        a = catalogue.acier(nuance)
        fy, fu, demo = a["fy_MPa"], a["fu_MPa"], bool(a.get("demo"))
    except KeyError:
        # fy, fu de repli pour dessiner ; la vérification sera « non vérifiable » (service.verifier)
        replis.append(f"nuance d'acier « {nuance} » absente de la base matériaux (fy, fu)")
    lierne = None
    if params.get("lierne") and catalogue is not None:
        try:
            lierne = catalogue.profil(params["lierne"])
            demo = demo or bool(lierne.get("demo"))
        except KeyError:
            lierne = None
    buton = None
    if params.get("buton") and catalogue is not None:
        try:
            buton = catalogue.element(params["buton"])
            demo = demo or bool(buton.get("demo"))
        except KeyError:
            buton = None
    return Contexte(normes, catalogue, fy, fu, nuance, lierne, buton, fck, demo, replis)


def completer(t: TypeAssemblage, params: dict) -> dict:
    """Paramètres avec les valeurs par défaut, nombres convertis."""
    out = {}
    for p in PARAMS_COMMUNS + t.parametres:
        v = params.get(p.cle, p.defaut)
        if p.genre in ("nombre", "entier") and isinstance(v, str) and v.strip() != "":
            try:
                v = float(v.strip().replace(",", "."))
            except ValueError:
                raise ValueError(f"paramètre « {p.cle} » ({p.libelle}) : nombre attendu, reçu « {v} »") from None
        if p.genre in ("nombre", "entier", "choix") and v not in ("", None) and not isinstance(v, str):
            v = float(v)
            if p.genre == "entier":
                v = int(round(v))
        elif p.genre == "choix" and isinstance(v, str) and p.choix and all(isinstance(c, (int, float)) for c in p.choix):
            try:
                v = float(v)
            except ValueError:
                pass
        if p.genre in ("nombre", "entier") and isinstance(v, (int, float)):
            if p.mini is not None:
                v = max(v, p.mini)
            if p.maxi is not None:
                v = min(v, p.maxi)
        out[p.cle] = v
    return out


def schema(cle: str, params: dict, efforts: dict, catalogue=None, normes=None, fck=None) -> dict:
    t = type_de(cle)
    p = completer(t, params)
    ctx = contexte(p, catalogue, normes, fck)
    sch = t.geometrie(p, efforts, ctx)
    d = sch.vers_dict()
    d["type"] = cle
    d["parametres"] = p
    d["demo"] = ctx.demo
    return d


def verifier(cle: str, params: dict, efforts: dict, catalogue=None, normes=None, fck=None, element: str | None = None) -> list[Verif]:
    t = type_de(cle)
    p = completer(t, params)
    ctx = contexte(p, catalogue, normes, fck)
    vs = t.verifications(p, efforts, ctx)
    if ctx.replis:
        # une donnée a été remplacée par un gabarit (règle 1 du CLAUDE.md : pas de valeur inventée dans un
        # résultat) : la vérification est rendue « non vérifiable » et nomme ce qui manque
        vs = [Verif(v.nom, v.categorie, v.element, v.phase, "non_verifiable", None,
                    v.detail + " — calculé avec des dimensions de repli : " + " ; ".join(ctx.replis),
                    v.source, list(dict.fromkeys(ctx.replis + v.manquants)), v.reperes) for v in vs]
    for v in vs:
        v.categorie = "structure"
        if element:
            v.element = f"{element} ({t.nom}) · {v.element}"
    return vs
