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
    reperes: list[int] = field(default_factory=list)   # composants concernés (assemblages : surlignage du schéma)
    # Fiche détaillée (sous-onglet de la famille dans l'interface, note de calcul), remplie module par module :
    famille: str = ""                                   # butee, equilibre_vertical, massif_ancrage, fond_de_fouille, stabilite_generale,
                                                        # deplacements, hydraulique, ecran, appuis, liernes, assemblages, anneau, calcul
    principe: str = ""                                  # la méthode en français, avec l'article de norme
    donnees: list[dict] = field(default_factory=list)   # {symbole, libelle, valeur, unite, origine} ; origine : calcul | script | norme:<fichier>:<clé>
    etapes: list[str] = field(default_factory=list)     # étapes du calcul : formule puis valeurs numériques
    schema: dict | None = None                          # données du schéma dessiné par l'interface ({"type": ..., ...})

    def vers_dict(self) -> dict:
        return asdict(self)


class Lecteur:
    """Lit les valeurs de norme en collectant celles qui manquent (et toutes celles lues, pour la fiche)."""

    def __init__(self, normes: Normes | None):
        self.normes = normes
        self.manquants: list[str] = []
        self.sources: list[str] = []
        self.lus: list[tuple[str, str, float | None]] = []   # (fichier, clé, valeur) de chaque lecture

    def v(self, fichier: str, cle: str) -> float | None:
        if self.normes is None:
            self.manquants.append(f"{fichier}.yaml:{cle}")
            self.lus.append((fichier, cle, None))
            return None
        try:
            val = self.normes.valeur(fichier, cle)
        except ValeurNormeManquante as e:
            if e.reference not in self.manquants:
                self.manquants.append(e.reference)
            self.lus.append((fichier, cle, None))
            return None
        s = self.normes.source(fichier, cle)
        if s and s not in self.sources:
            self.sources.append(s)
        self.lus.append((fichier, cle, val))
        return val


def donnee(symbole: str, libelle: str, valeur, unite: str = "", origine: str = "calcul") -> dict:
    """Une donnée de la fiche détaillée : symbole, libellé en français, valeur (nombre ou texte), unité, origine."""
    try:
        v = None if valeur is None else float(valeur)
    except (TypeError, ValueError):
        v = valeur
    return {"symbole": symbole, "libelle": libelle, "valeur": v, "unite": unite, "origine": origine}


# Famille d'une vérification d'après le début de son nom (sous-onglets de l'interface, regroupement de la note) ;
# les modules qui remplissent une fiche la donnent explicitement, les autres passent par ce repli.
_FAMILLES = (
    ("Mobilisation de la butée", "butee"), ("Équilibre vertical", "equilibre_vertical"), ("Stabilité du massif", "massif_ancrage"),
    ("Fond de fouille", "fond_de_fouille"), ("Stabilité générale", "stabilite_generale"), ("Déplacement", "deplacements"),
    ("Scellement du tirant", "appuis"), ("Boulance", "hydraulique"), ("Renard", "hydraulique"), ("Soulèvement du bouchon", "hydraulique"),
    ("Gradient à travers", "hydraulique"), ("Débit de pompage", "hydraulique"), ("Stabilité du fond en argile", "hydraulique"),
    ("Calcul", "calcul"), ("Buton", "appuis"), ("Bracon", "appuis"), ("Tirant", "appuis"), ("Dalle", "appuis"), ("Lierne", "liernes"),
    ("Palplanches", "ecran"), ("Profilés de berlinoise", "ecran"), ("Blindage", "ecran"), ("Paroi moulée", "ecran"), ("Pieux", "ecran"),
    ("Flexion horizontale", "ecran"), ("Anneau", "anneau"), ("Assemblage", "assemblages"),
)


def famille_de(nom: str, categorie: str) -> str:
    """Famille d'une vérification (butee, ecran, appuis…) d'après son nom ; repli sur la catégorie."""
    for prefixe, fam in _FAMILLES:
        if nom.startswith(prefixe):
            return fam
    return "geotechnique" if categorie == "geotechnique" else "structure"


def etat_de(taux: float) -> str:
    if taux <= SEUIL_ATTENTION:
        return "ok"
    if taux <= 1.0:
        return "attention"
    return "non_ok"


def resultat(nom: str, element: str, phase: str | None, taux: float | None, detail: str, source: str,
             lecteur: Lecteur | None = None, categorie: str = "geotechnique",
             detail_non_verifiable: str | None = None, reperes: list[int] | None = None,
             famille: str = "", principe: str = "", donnees: list[dict] | None = None, etapes: list[str] | None = None,
             schema: dict | None = None) -> Verif:
    """Construit le résultat ; « non vérifiable » si une valeur de norme manque. Les valeurs normatives lues par le
    lecteur sont ajoutées aux données de la fiche (origine norme:<fichier>:<clé>)."""
    manquants = list(lecteur.manquants) if lecteur else []
    sources = (" ; ".join(lecteur.sources) + " ; " if lecteur and lecteur.sources else "") + source
    liste = list(donnees or [])
    if lecteur:
        vus: set[tuple[str, str]] = set()
        for fichier, cle, val in lecteur.lus:
            if (fichier, cle) in vus:
                continue
            vus.add((fichier, cle))
            liste.append(donnee(cle.split(".")[-1], f"valeur normative docs/normes/{fichier}.yaml : {cle}", val, "", f"norme:{fichier}:{cle}"))
    fiche = dict(famille=famille or famille_de(nom, categorie), principe=principe, donnees=liste, etapes=list(etapes or []), schema=schema)
    if manquants or taux is None:
        return Verif(nom, categorie, element, phase, "non_verifiable", None,
                     detail_non_verifiable or detail, sources, manquants, list(reperes or []), **fiche)
    import math
    if math.isnan(taux) or math.isinf(taux):
        # résistance nulle ou critère de stabilité dépassé (ex. N ≥ N_cr) : taux borné pour l'affichage et le JSON
        return Verif(nom, categorie, element, phase, "non_ok", 99.0,
                     detail + " — résistance nulle ou instabilité (taux non défini, affiché 9 900 %)", sources, [], list(reperes or []), **fiche)
    return Verif(nom, categorie, element, phase, etat_de(taux), float(taux), detail, sources, [], list(reperes or []), **fiche)


# Score de défaveur d'un résultat sans taux : un « non_ok » sans taux (section insuffisante, instabilité)
# passe devant tout taux chiffré ; un « non vérifiable » passe derrière tout résultat chiffré.
_RANG_SANS_TAUX = {"non_ok": float("inf"), "attention": 1.0, "ok": 0.0, "non_verifiable": -1.0}


def score_defaveur(v: Verif) -> float:
    """Plus grand = plus défavorable (taux de travail, ou rang de l'état si le taux manque)."""
    if v.taux is not None:
        return float(v.taux)
    return _RANG_SANS_TAUX.get(v.etat, -1.0)


def pire(verifs: list[Verif]) -> list[Verif]:
    """Garde, pour chaque (nom, élément), le résultat le plus défavorable."""
    meilleur: dict[tuple, Verif] = {}
    for v in verifs:
        cle = (v.nom, v.element)
        cur = meilleur.get(cle)
        if cur is None or score_defaveur(v) > score_defaveur(cur):
            meilleur[cle] = v
    return list(meilleur.values())
