"""Génère la référence des mots-clés du langage à partir du schéma (docs/guide_script.md).

    python -m sout.script.documentation      # met à jour la section entre les marqueurs du guide
"""
from __future__ import annotations

from pathlib import Path
from typing import get_args, get_origin, Literal, Union
import types

from pydantic import BaseModel

from . import schema

GUIDE = Path(__file__).resolve().parents[3] / "docs" / "guide_script.md"
DEBUT, FIN = "<!-- REFERENCE:DEBUT -->", "<!-- REFERENCE:FIN -->"

def _modeles(t) -> list:
    """Modèles pydantic contenus dans une annotation (bloc, liste de blocs, blocs nommés, optionnel)."""
    o = get_origin(t)
    if o is Literal:
        return []
    if o in (Union, types.UnionType, list, dict, tuple):
        return [m for a in get_args(t) for m in _modeles(a)]
    if isinstance(t, type) and issubclass(t, BaseModel):
        return [t]
    return []


def _libelle(nom: str, t) -> str:
    o = get_origin(t)
    if o in (Union, types.UnionType):
        o = next((get_origin(a) for a in get_args(t) if a is not type(None)), None)
    if o is list:
        return f"{nom} (chaque élément)"
    if o is dict:
        return f"{nom} (chaque bloc nommé)"
    return nom


def blocs() -> list[tuple[str, type]]:
    """Tous les blocs du langage, parcourus depuis la racine : chaque modèle une fois, sous le premier
    chemin qui y mène (ainsi les blocs ajoutés au schéma — hydraulique, fouille, coupes, assemblages… —
    apparaissent dans le guide sans liste à entretenir)."""
    out: list[tuple[str, type]] = [("Racine du script", schema.Script)]
    vus = {schema.Script}
    file = [("", schema.Script)]
    while file:
        prefixe, modele = file.pop(0)
        for nom, champ in modele.model_fields.items():
            for m in _modeles(champ.annotation):
                if m in vus:
                    continue
                vus.add(m)
                chemin = f"{prefixe}{nom}"
                out.append((_libelle(chemin, champ.annotation), m))
                file.append((chemin + ".", m))
    return out


BLOCS = blocs()


def _type(t) -> str:
    o = get_origin(t)
    if o is Literal:
        return " / ".join(str(a) for a in get_args(t))
    if o in (Union, types.UnionType):
        parts = [_type(a) for a in get_args(t) if a is not type(None)]
        return " ou ".join(parts)
    if o is list:
        return f"liste de {_type(get_args(t)[0])}"
    if o is dict:
        return f"blocs nommés de {_type(get_args(t)[1])}"
    if isinstance(t, type) and issubclass(t, BaseModel):
        return "bloc"
    return {float: "nombre", int: "entier", str: "texte", bool: "true / false"}.get(t, str(t))


def reference() -> str:
    lignes = []
    for titre, modele in BLOCS:
        lignes.append(f"### {titre}\n")
        lignes.append("| Mot-clé | Type | Obligatoire | Défaut | Description |")
        lignes.append("| --- | --- | --- | --- | --- |")
        for nom, champ in modele.model_fields.items():
            oblig = "oui" if champ.is_required() else ""
            defaut = "" if champ.is_required() or champ.default is None or champ.default_factory else repr(champ.default)
            if isinstance(champ.default, str):
                defaut = champ.default
            bornes = []
            for m in champ.metadata:
                for cle, sym in (("gt", ">"), ("ge", "≥"), ("lt", "<"), ("le", "≤")):
                    v = getattr(m, cle, None)
                    if v is not None:
                        bornes.append(f"{sym} {v}")
            descr = (champ.description or "") + (f" ({', '.join(bornes)})" if bornes else "")
            lignes.append(f"| `{nom}` | {_type(champ.annotation)} | {oblig} | {defaut} | {descr} |")
        lignes.append("")
    return "\n".join(lignes)


def mettre_a_jour(guide: Path = GUIDE) -> None:
    texte = guide.read_text(encoding="utf-8")
    a, b = texte.index(DEBUT) + len(DEBUT), texte.index(FIN)
    guide.write_text(texte[:a] + "\n\n" + reference() + "\n" + texte[b:], encoding="utf-8")


if __name__ == "__main__":
    mettre_a_jour()
    print(f"référence mise à jour dans {GUIDE}")
