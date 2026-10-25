"""Paroi circulaire : anneau comprimé axisymétrique.

Une paroi circulaire (puits, enceinte circulaire) chargée de façon axisymétrique travaille à la fois en flexion
verticale et en compression circonférentielle. Pour une coque cylindrique mince de rayon a et d'épaisseur h soumise
à une pression radiale Z(x) symétrique par rapport à son axe, l'équation de la flèche radiale w est

    D·w'''' + (E·h / a²)·w = Z

(Timoshenko S. & Woinowsky-Krieger S., *Theory of Plates and Shells*, 2e éd., McGraw-Hill, 1959, ch. 15, § 114 :
« symmetrical deformation of a circular cylindrical shell »). C'est l'équation d'une poutre sur fondation élastique
de module k = E·h/a² : l'anneau se comporte comme un ressort réparti supplémentaire, linéaire, sur toute la hauteur
de l'écran, qui s'ajoute aux ressorts du sol. L'effort normal circonférentiel est N_θ = E·h·w/a (compression pour w
dirigé vers l'axe, c'est-à-dire vers la fouille), soit N_θ = a·k·w : équilibre de l'anneau sous la pression qu'il
reprend (formule des chaudronniers N = p·a).

Hypothèses (affichées dans les avertissements et les fiches de vérification) :
- chargement axisymétrique (mêmes sol, eau, phases et appuis sur tout le pourtour) ;
- anneau élastique linéaire, en compression comme en traction (la traction circonférentielle n'est pas limitée :
  elle est signalée par la vérification) ; k = E·h/a² suppose la coque libre de se dilater verticalement (effort
  normal vertical nul, cas du § 114) ; si la déformation verticale était empêchée, la rigidité vaudrait
  E·h/(a²·(1 − ν²)), un peu plus forte : écart non pris en compte, signalé dans la fiche ;
- épaisseur de l'anneau : épaisseur de la paroi moulée, ou largeur du joint entre deux pieux sécants
  t = √(D² − e²) (corde commune à deux cercles de diamètre D dont les centres sont distants de e, géométrie) ;
  l'entraxe effectif au joint croît avec la profondeur si les pieux voisins dévient en sens opposés :
  e(z) = e + 2·tol·(z_tête − z) (tol : écart de verticalité, paramètre de projet, défaut 0).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


class ErreurAnneau(ValueError):
    pass


@dataclass
class Anneau:
    """Anneau comprimé d'une paroi circulaire (par mètre de hauteur)."""
    rayon: float                  # m, rayon de l'axe de la paroi
    E: float                      # kPa, module du béton
    tete: float                   # m, cote de la tête (origine de la profondeur pour la tolérance)
    epaisseur: float | None = None    # m, épaisseur imposée (paroi moulée ou valeur du script)
    diametre: float | None = None     # m, pieux sécants
    entraxe: float | None = None      # m, pieux sécants
    tolerance: float = 0.0            # m/m, écart de verticalité de chaque pieu
    source_epaisseur: str = ""

    def t(self, z) -> np.ndarray:
        """Épaisseur de l'anneau (m) à la cote z : imposée, sinon largeur du joint des pieux sécants √(D² − e(z)²),
        nulle quand les pieux ne se recouvrent plus."""
        z = np.asarray(z, float)
        if self.epaisseur is not None:
            return np.full(z.shape, float(self.epaisseur))
        e = self.entraxe + 2.0 * self.tolerance * np.maximum(self.tete - z, 0.0)
        return np.sqrt(np.maximum(self.diametre**2 - e**2, 0.0))

    def k(self, z) -> np.ndarray:
        """Module de réaction de l'anneau k = E·t/R² (kN/m³ : kPa par m de flèche radiale), Timoshenko § 114."""
        return self.E * self.t(z) / self.rayon**2

    def N(self, z, w) -> np.ndarray:
        """Effort normal circonférentiel N_θ = E·t·w/R (kN par m de hauteur), compression > 0 pour w vers la fouille."""
        return self.E * self.t(z) * np.asarray(w, float) / self.rayon

    def decrire(self) -> dict:
        return {"rayon": self.rayon, "E": self.E, "epaisseur": self.epaisseur, "diametre": self.diametre,
                "entraxe": self.entraxe, "tolerance": self.tolerance, "source_epaisseur": self.source_epaisseur}


def pression_critique_tube(E: float, t: float, R: float, nu: float = 0.0) -> float:
    """Pression extérieure uniforme critique d'un tube long (flambement de l'anneau) :
    p_cr = 3·D/R³ avec D = E·t³/(12·(1 − ν²)), soit p_cr = E·t³/(4·(1 − ν²)·R³) (kPa).
    Source : Timoshenko S. & Gere J., *Theory of Elastic Stability*, 2e éd., McGraw-Hill, 1961, ch. 7 (anneau
    circulaire sous pression uniforme, q_cr = 3·E·I/R³) avec la rigidité de plaque d'un tube long (ch. 11).
    ν = 0 donne la borne inférieure (valeur prudente) : aucune valeur de norme n'est utilisée ici."""
    return E * t**3 / (4.0 * (1.0 - nu**2) * R**3)


def construire_anneau(p, E_kPa: float) -> Anneau | None:
    """Anneau d'une paroi `forme: circulaire` du script (None pour une paroi plane).
    Paroi moulée : épaisseur de l'anneau = epaisseur_anneau, sinon epaisseur ; pieux sécants : epaisseur_anneau, sinon
    largeur du joint √(D² − e²) avec la tolérance de verticalité. Autres types : refus (ErreurAnneau)."""
    if getattr(p, "forme", "plane") != "circulaire":
        return None
    if not p.rayon:
        raise ErreurAnneau("paroi circulaire : rayon obligatoire (m, axe de la paroi)")
    if p.type not in ("paroi_moulee", "pieux_secants"):
        raise ErreurAnneau(f"paroi circulaire en {p.type} : anneau comprimé non traité (paroi_moulee ou pieux_secants ; "
                           "palplanches : comportement des serrures en compression circonférentielle, TODO-SOURCE)")
    tol = float(getattr(p, "tolerance_verticalite", 0.0) or 0.0)
    if p.epaisseur_anneau is not None:
        return Anneau(p.rayon, E_kPa, p.tete, epaisseur=p.epaisseur_anneau, tolerance=tol, source_epaisseur="script (epaisseur_anneau)")
    if p.type == "paroi_moulee":
        if not p.epaisseur:
            raise ErreurAnneau("paroi circulaire en paroi moulée : epaisseur obligatoire")
        return Anneau(p.rayon, E_kPa, p.tete, epaisseur=p.epaisseur, source_epaisseur="épaisseur de la paroi moulée")
    D, e = p.diametre, p.entraxe
    if not D or not e:
        raise ErreurAnneau("paroi circulaire en pieux sécants : diametre et entraxe obligatoires")
    a = Anneau(p.rayon, E_kPa, p.tete, diametre=D, entraxe=e, tolerance=tol,
               source_epaisseur="largeur du joint des pieux sécants √(D² − e²)" + (f", tolérance de verticalité {tol:g} m/m" if tol else ""))
    t_pied = float(a.t(np.array([p.pied]))[0])
    if t_pied <= 0.0:
        z0 = p.tete - (D - e) / (2.0 * tol) if tol > 0 else p.tete
        raise ErreurAnneau(f"pieux sécants : plus de recouvrement {'sous la cote ' + format(z0, '.2f') + ' m' if tol > 0 else ''} "
                           f"(D = {D:g} m, e = {e:g} m{', tolérance ' + format(tol, 'g') + ' m/m' if tol else ''}) : "
                           "l'anneau n'est pas continu")
    return a


def longueur_tributaire(z: np.ndarray) -> np.ndarray:
    """Hauteur tributaire de chaque nœud d'un maillage vertical (demi-éléments de part et d'autre)."""
    z = np.asarray(z, float)
    L = np.zeros(len(z))
    d = np.diff(z)
    L[:-1] += d / 2
    L[1:] += d / 2
    return np.abs(L)


def raideurs_nodales(anneau: Anneau, z: np.ndarray) -> np.ndarray:
    """Raideur de l'anneau concentrée aux nœuds (kN/m par m de paroi) : k(z) × hauteur tributaire.
    Intégration par la règle des trapèzes de k(z)·w(z) sur chaque élément."""
    return anneau.k(z) * longueur_tributaire(z)


def nombre_cotes_polygone(rayon: float, pas: float) -> int:
    """Nombre de côtés du polygone qui représente le cercle en pseudo-3D : au moins 24, et côtés au plus égaux au pas."""
    return max(24, int(math.ceil(2 * math.pi * rayon / max(pas, 1e-6))))


def contour_polygone(rayon: float, n: int) -> list[list[float]]:
    """Polygone régulier inscrit de n côtés, centré à l'origine, parcouru dans le sens direct (m)."""
    return [[rayon * math.cos(2 * math.pi * i / n), rayon * math.sin(2 * math.pi * i / n)] for i in range(n)]
