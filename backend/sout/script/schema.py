"""Schéma du langage de script RetainWall (YAML, mots-clés français).

Unités fixes : kN, m, kPa, kN/m3, degrés, MPa pour les modules d'élasticité
des matériaux, cm² pour les sections d'acier. Cotes en mètres, axe vertical
vers le haut, dans le repère choisi pour le projet.

Chaque champ porte sa description (unité, sens) : elle sert aux messages
d'erreur et à l'aide de l'éditeur intégré.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Calcul(_Base):
    methode: Literal["coefficients_reaction"] = Field("coefficients_reaction", description="méthode de calcul")
    kh: Literal["schmitt", "impose"] = Field("schmitt", description="coefficient de réaction : schmitt (EM, α) ou impose (kh par couche)")
    norme: str = Field("NF P 94-282", description="norme de référence des vérifications")
    coefficients: Literal["coulomb", "kerisel_absi"] = Field(
        "coulomb", description="coefficients de poussée/butée : coulomb (formule) ou kerisel_absi (tables à fournir)")
    gamma_w: float = Field(10.0, gt=0, le=12, description="poids volumique de l'eau (kN/m3)")
    pas: float = Field(0.1, gt=0.005, le=1.0, description="longueur maximale d'élément du maillage (m)")
    jeu_eau: str | None = Field(None, description="jeu de niveaux d'eau utilisé (défaut : le premier du bloc eau)")
    mode: Literal["2d", "pseudo3d"] = Field("2d", description="2d (par section) ou pseudo3d (plaque sur ressorts)")
    largeur_fouille: float | None = Field(
        None, gt=0, description="largeur de la fouille pour la stabilité générale (m) ; défaut : 2 × hauteur de paroi")


class Blindage(_Base):
    epaisseur: float = Field(gt=0, description="épaisseur du blindage (m)")
    materiau: Literal["bois", "beton", "acier"] = Field(description="matériau du blindage")
    resistance: float | None = Field(None, gt=0, description="résistance de calcul en flexion (MPa)")


class Paroi(_Base):
    type: Literal["palplanche", "paroi_moulee", "pieux_secants", "pieux_disjoints", "berlinoise"] = Field(
        description="type de paroi")
    tete: float = Field(description="cote de la tête de paroi (m)")
    pied: float = Field(description="cote du pied de paroi (m)")
    EI: float | None = Field(None, gt=0, description="rigidité imposée par mètre linéaire (kN·m²/m) ; sinon calculée")
    profil: str | None = Field(None, description="référence de la base matériaux (palplanche ou profilé)")
    acier: str | None = Field(None, description="nuance d'acier (base matériaux)")
    beton: str | None = Field(None, description="classe de béton (base matériaux)")
    epaisseur: float | None = Field(None, gt=0, description="épaisseur de paroi moulée (m)")
    diametre: float | None = Field(None, gt=0, description="diamètre des pieux (m)")
    entraxe: float | None = Field(None, gt=0, description="entraxe des pieux ou profilés (m)")
    profil_armature: str | None = Field(None, description="profilé d'armature des pieux (base matériaux)")
    primaires_armes: bool = Field(False, description="pieux sécants : pieux primaires armés")
    rapport_EI_fissure: float | None = Field(
        None, gt=0, le=1, description="béton : rapport EI fissuré / EI non fissuré choisi par l'ingénieur")
    beta_D: float | None = Field(
        None, gt=0, le=1, description="palplanches en U : réduction d'inertie β_D (EN 1993-5, à fournir)")
    perte_epaisseur: float | None = Field(
        None, ge=0, description="palplanches : perte d'épaisseur par corrosion, totale (mm)")
    largeur_reaction_fiche: float | None = Field(
        None, gt=0, description="fiche discontinue : largeur de réaction imposée sous le fond (m par élément)")
    blindage: Blindage | None = Field(None, description="berlinoise : blindage entre profilés")
    enrobage: float | None = Field(None, gt=0, description="enrobage des armatures (m)")


class Couche(_Base):
    nom: str = Field(description="nom de la couche")
    toit: float = Field(description="cote du toit de la couche (m)")
    gamma: float = Field(gt=0, le=30, description="poids volumique hors nappe (kN/m3)")
    gamma_dejauge: float = Field(gt=0, le=20, description="poids volumique déjaugé sous nappe (kN/m3)")
    phi: float = Field(ge=0, lt=60, description="angle de frottement effectif φ' (degrés)")
    c: float = Field(0.0, ge=0, description="cohésion effective c' (kPa)")
    EM: float | None = Field(None, gt=0, description="module pressiométrique (kPa)")
    alpha: float | None = Field(None, gt=0, le=1, description="coefficient rhéologique de Ménard α")
    pl: float | None = Field(None, gt=0, description="pression limite pressiométrique (kPa)")
    qc: float | None = Field(None, gt=0, description="résistance de pointe CPT (kPa)")
    EM_sur_qc: float | None = Field(None, gt=0, description="corrélation choisie EM = (EM/qc)·qc")
    kh: float | None = Field(None, gt=0, description="coefficient de réaction imposé (kN/m3)")
    K0: float | None = Field(None, gt=0, le=3, description="coefficient des terres au repos (défaut : Jaky 1 − sin φ')")
    delta_a_sur_phi: float = Field(0.0, ge=0, le=1, description="obliquité côté poussée δa/φ'")
    delta_p_sur_phi: float = Field(0.0, ge=0, le=1, description="obliquité côté butée |δp|/φ'")
    coef_decharge: float | None = Field(None, gt=0, le=3, description="coefficient de décharge Kd (défaut : K0)")


class Terrain(_Base):
    amont: float | None = Field(None, description="cote initiale du terrain amont (m) ; défaut : toit de la 1re couche")
    aval: float | None = Field(None, description="cote initiale du terrain aval (m) ; défaut : terrain amont")


class NiveauxEau(_Base):
    amont: float | None = Field(None, description="cote de la nappe côté amont (m) ; vide = pas de nappe")
    aval: float | None = Field(None, description="cote de la nappe côté aval (m) ; vide = pas de nappe")


class Surcharge(_Base):
    nom: str | None = Field(None, description="nom (pour la retirer dans une phase)")
    type: Literal["repartie", "bande", "lineique"] = Field(description="répartie, en bande ou linéique")
    q: float = Field(description="intensité : kPa (répartie, bande) ou kN/m (linéique)")
    distance: float = Field(0.0, ge=0, description="distance au parement (m)")
    largeur: float | None = Field(None, gt=0, description="largeur de la bande (m)")
    cote: float | None = Field(None, description="cote d'application (m) ; défaut : terrain")
    cote_ecran: Literal["amont", "aval"] = Field("amont", description="côté de l'écran")


class Appui(_Base):
    type: Literal["buton", "tirant", "bracon", "dalle"] = Field(description="type d'appui")
    cote: float = Field(description="cote de l'appui sur la paroi (m)")
    element: str | None = Field(None, description="référence de la base matériaux (buton modulaire, profilé, armature)")
    E: float | None = Field(None, gt=0, description="module d'Young (MPa) si pas d'élément de la base")
    A: float | None = Field(None, gt=0, description="section (cm²) si pas d'élément de la base")
    raideur: float | None = Field(None, ge=0, description="raideur imposée (kN/m par mètre d'écran)")
    espacement: float = Field(1.0, gt=0, description="espacement horizontal des appuis (m)")
    longueur: float | None = Field(None, gt=0, description="longueur du buton ou bracon, portée de la dalle (m)")
    angle: float = Field(0.0, ge=-80, le=80, description="inclinaison sur l'horizontale (degrés)")
    precharge: float = Field(0.0, ge=0, description="précharge ou précontrainte par appui (kN, axiale)")
    symetrique: bool = Field(True, description="buton/dalle entre deux parois symétriques (longueur élastique L/2)")
    longueur_libre: float | None = Field(None, gt=0, description="tirant : longueur libre (m)")
    longueur_scellee: float | None = Field(None, gt=0, description="tirant : longueur de scellement (m)")
    longueur_elastique: float | None = Field(None, gt=0, description="tirant : longueur élastique imposée (m)")
    diametre_forage: float | None = Field(None, gt=0, description="tirant : diamètre du forage (m)")
    qs: float | None = Field(None, gt=0, description="tirant : frottement latéral limite du scellement (kPa)")
    epaisseur: float | None = Field(None, gt=0, description="dalle : épaisseur (m)")
    unilateral: bool | None = Field(None, description="ne reprend pas d'effort négatif (défaut : oui sauf dalle)")
    lierne: str | None = Field(None, description="profilé de lierne (base matériaux)")
    acier: str | None = Field(None, description="nuance d'acier de l'élément (base matériaux)")
    beton: str | None = Field(None, description="dalle : classe de béton (base matériaux)")
    pied_bracon: float | None = Field(None, description="bracon : cote de l'appui en pied (m)")


class Remblai(_Base):
    amont: float | None = Field(None, description="nouvelle cote du terrain amont (m)")
    aval: float | None = Field(None, description="nouvelle cote du terrain aval (m)")


class Phase(_Base):
    nom: str = Field(description="nom de la phase")
    excaver: float | None = Field(None, description="cote du fond de fouille atteinte (m)")
    remblayer: Remblai | None = Field(None, description="remblai jusqu'à une cote, côté amont ou aval")
    poser: str | list[str] | None = Field(None, description="appui(s) posé(s) dans cette phase")
    deposer: str | list[str] | None = Field(None, description="appui(s) déposé(s) dans cette phase")
    eau: NiveauxEau | None = Field(None, description="nouveaux niveaux d'eau (seules les clés écrites changent)")
    ajouter_surcharges: list[Surcharge] | None = Field(None, description="surcharges ajoutées")
    retirer_surcharges: list[str] | None = Field(None, description="noms des surcharges retirées")


class Criteres(_Base):
    deplacement_max_mm: float | None = Field(None, gt=0, description="déplacement admissible aux ELS (mm)")
    deplacement_tete_mm: float | None = Field(None, gt=0, description="déplacement admissible en tête aux ELS (mm)")


class PointPlan(_Base):
    x: float
    y: float


class AppuiPlan(_Base):
    appui: str = Field(description="nom de l'appui (bloc appuis)")
    de: list[float] = Field(description="point de départ [x, y] (m)")
    a: list[float] = Field(description="point d'arrivée [x, y] (m)")


class Plan(_Base):
    contour: list[list[float]] = Field(description="polygone de la fouille [[x, y], ...] (m)")
    appuis: list[AppuiPlan] = Field(default_factory=list, description="positions des appuis en plan")
    cote_terrain: float | None = Field(None, description="cote du terrain autour de la fouille (m)")


class Pseudo3D(_Base):
    longueur: float = Field(gt=0, description="longueur développée de la paroi modélisée (m)")
    pas_horizontal: float = Field(0.5, gt=0.05, description="taille des éléments selon la longueur (m)")
    bords: Literal["libres", "encastres", "appuyes"] = Field("libres", description="conditions aux extrémités")
    angle: float | None = Field(None, gt=0, lt=360, description="angle de la fouille au milieu de la paroi (degrés)")
    rigidite_horizontale: float | None = Field(None, gt=0, description="EI horizontal par mètre de hauteur (kN·m²/m)")


Verification = Literal[
    "butee", "equilibre_vertical", "kranz", "fond_de_fouille", "stabilite_generale",
    "deplacements", "structure",
]


class Script(_Base):
    projet: str = Field(description="nom du projet")
    calcul: Calcul = Field(default_factory=Calcul)
    paroi: Paroi
    sol: list[Couche] = Field(min_length=1)
    terrain: Terrain = Field(default_factory=Terrain)
    eau: dict[str, NiveauxEau] = Field(default_factory=dict, description="jeux de niveaux d'eau (service, exceptionnel…)")
    surcharges: list[Surcharge] = Field(default_factory=list)
    appuis: dict[str, Appui] = Field(default_factory=dict)
    phases: list[Phase] = Field(min_length=1)
    verifications: list[Verification] = Field(default_factory=list)
    criteres: Criteres = Field(default_factory=Criteres)
    plan: Plan | None = None
    pseudo3d: Pseudo3D | None = None
