"""Socle commun des vérifications géotechniques et structurelles.

Chaque vérification renvoie un `Verif` : taux de travail (sollicitation de
calcul / résistance de calcul), état, détail lisible et source. Les valeurs
normatives sont lues par un `Lecteur` qui collecte toutes les valeurs
manquantes : la vérification est alors « non vérifiable » et le détail donne
la valeur caractéristique (sans coefficients partiels) à titre indicatif.

Seuils d'affichage (convention de l'interface, pas une règle de norme) :
vert ≤ 90 %, orange ≤ 100 %, rouge au-delà.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .normes import Normes, ValeurNormeManquante

SEUIL_ATTENTION = 0.90


@dataclass
class Verif:
    nom: str
    categorie: str            # "geotechnique" ou "structure"
    element: str
    phase: str | None
    etat: str                 # "ok", "attention", "non_ok", "non_verifiable"
    taux: float | None
    detail: str
    source: str
    manquants: list[str] = field(default_factory=list)

    def vers_dict(self) -> dict:
        return asdict(self)


class Lecteur:
    """Lit les valeurs de norme en collectant celles qui manquent."""

    def __init__(self, normes: Normes | None):
        self.normes = normes
        self.manquants: list[str] = []
        self.sources: list[str] = []

    def v(self, fichier: str, cle: str) -> float | None:
        if self.normes is None:
            self.manquants.append(f"{fichier}.yaml:{cle}")
            return None
        try:
            val = self.normes.valeur(fichier, cle)
        except ValeurNormeManquante as e:
            if e.reference not in self.manquants:
                self.manquants.append(e.reference)
            return None
        s = self.normes.source(fichier, cle)
        if s and s not in self.sources:
            self.sources.append(s)
        return val


def etat_de(taux: float) -> str:
    if taux <= SEUIL_ATTENTION:
        return "ok"
    if taux <= 1.0:
        return "attention"
    return "non_ok"


def resultat(nom: str, element: str, phase: str | None, taux: float | None, detail: str, source: str,
             lecteur: Lecteur | None = None, categorie: str = "geotechnique",
             detail_non_verifiable: str | None = None) -> Verif:
    """Construit le résultat ; « non vérifiable » si une valeur de norme manque."""
    manquants = list(lecteur.manquants) if lecteur else []
    sources = (" ; ".join(lecteur.sources) + " ; " if lecteur and lecteur.sources else "") + source
    if manquants or taux is None:
        return Verif(nom, categorie, element, phase, "non_verifiable", None,
                     detail_non_verifiable or detail, sources, manquants)
    return Verif(nom, categorie, element, phase, etat_de(taux), float(taux), detail, sources, [])


def pire(verifs: list[Verif]) -> list[Verif]:
    """Garde, pour chaque (nom, élément), le résultat le plus défavorable."""
    rang = {"non_verifiable": -1}
    meilleur: dict[tuple, Verif] = {}
    for v in verifs:
        cle = (v.nom, v.element)
        cur = meilleur.get(cle)
        score = v.taux if v.taux is not None else rang[v.etat]
        if cur is None or score > (cur.taux if cur.taux is not None else rang[cur.etat]):
            meilleur[cle] = v
    return list(meilleur.values())
