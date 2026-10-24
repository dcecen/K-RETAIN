"""Accès aux valeurs normatives fournies par l'utilisateur (docs/normes/*.yaml).

Règle absolue n° 1 (CLAUDE.md) : aucune valeur de norme n'est écrite dans le
code. Une valeur absente ou nulle lève `ValeurNormeManquante`, que les
vérifications transforment en résultat « non vérifiable ».
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ruamel.yaml import YAML

DOSSIER = Path(__file__).resolve().parents[2] / "docs" / "normes"


class ValeurNormeManquante(Exception):
    def __init__(self, fichier: str, cle: str, raison: str = "valeur manquante"):
        self.fichier, self.cle = fichier, cle
        super().__init__(f"TODO-NORME : {raison} {fichier}.yaml -> {cle}")

    @property
    def reference(self) -> str:
        return f"{self.fichier}.yaml:{self.cle}"


@dataclass
class Normes:
    """Jeu de valeurs normatives. `donnees` : {fichier: arbre YAML}."""

    donnees: dict

    def valeur(self, fichier: str, cle: str):
        """Valeur au chemin pointé `cle` (ex. "ELU.gamma_Rh" ) ; lève si absente ou nulle."""
        noeud = self.donnees.get(fichier)
        for partie in cle.split("."):
            if not isinstance(noeud, dict) or partie not in noeud:
                raise ValeurNormeManquante(fichier, cle)
            noeud = noeud[partie]
        if noeud is None:
            raise ValeurNormeManquante(fichier, cle)
        if isinstance(noeud, dict) and "valeur" in noeud:
            noeud = noeud["valeur"]
            if noeud is None:
                raise ValeurNormeManquante(fichier, cle)
        if isinstance(noeud, (int, float)) and not isinstance(noeud, bool) and noeud == 0:
            # un coefficient nul diviserait par zéro : traité comme non renseigné
            raise ValeurNormeManquante(fichier, cle, "valeur nulle")
        return noeud

    def source(self, fichier: str, cle: str) -> str:
        """Champ `source` associé à la valeur, s'il est renseigné."""
        noeud = self.donnees.get(fichier)
        for partie in cle.split("."):
            if not isinstance(noeud, dict) or partie not in noeud:
                return ""
            noeud = noeud[partie]
        if isinstance(noeud, dict):
            return str(noeud.get("source") or "")
        return ""

    def facultatif(self, fichier: str, cle: str, defaut=None):
        try:
            return self.valeur(fichier, cle)
        except ValeurNormeManquante:
            return defaut


def _simplifier(n):
    if isinstance(n, dict):
        return {str(k): _simplifier(v) for k, v in n.items()}
    if isinstance(n, list):
        return [_simplifier(v) for v in n]
    return n


def charger(dossier: Path | None = None) -> Normes:
    dossier = dossier or DOSSIER
    yaml = YAML(typ="safe")
    donnees = {}
    for f in sorted(dossier.glob("*.yaml")):
        donnees[f.stem] = _simplifier(yaml.load(f.read_text(encoding="utf-8")) or {})
    return Normes(donnees)
