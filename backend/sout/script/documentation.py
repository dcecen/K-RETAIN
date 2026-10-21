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

BLOCS = [
    ("Racine du script", schema.Script),
    ("calcul", schema.Calcul),
    ("paroi", schema.Paroi),
    ("paroi.blindage", schema.Blindage),
    ("sol (chaque couche)", schema.Couche),
    ("terrain", schema.Terrain),
    ("eau (chaque jeu de niveaux)", schema.NiveauxEau),
    ("surcharges (chaque surcharge)", schema.Surcharge),
    ("appuis (chaque appui)", schema.Appui),
    ("phases (chaque phase)", schema.Phase),
    ("phases.remblayer", schema.Remblai),
    ("criteres", schema.Criteres),
    ("plan", schema.Plan),
    ("plan.appuis (chaque position)", schema.AppuiPlan),
    ("pseudo3d", schema.Pseudo3D),
]


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
