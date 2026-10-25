"""Schéma du langage de script RetainWall (YAML, mots-clés français).

Unités fixes : kN, m, kPa, kN/m3, degrés, MPa pour les modules d'élasticité
des matériaux, cm² pour les sections d'acier. Cotes en mètres, axe vertical
vers le haut, dans le repère choisi pour le projet.

Chaque champ porte sa description (unité, sens) : elle sert aux messages
d'erreur et à l'aide de l'éditeur intégré.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator, model_validator


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
    coupes_automatiques: bool = Field(
        False, description="avec un bloc plan et sans bloc coupes : une coupe de calcul 2D par côté du contour dès que des "
                           "surcharges ou des objets de terrain dépendent du côté (sinon coupe unique au milieu du côté le plus long)")


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
    classe_section: int | None = Field(
        None, ge=1, le=4, description="palplanches : classe de section (EN 1993-5) si le catalogue ne la donne pas")
    perte_epaisseur: float | None = Field(
        None, ge=0, description="palplanches : perte d'épaisseur par corrosion, totale (mm)")
    largeur_reaction_fiche: float | None = Field(
        None, gt=0, description="fiche discontinue : largeur de réaction imposée sous le fond (m par élément)")
    blindage: Blindage | None = Field(None, description="berlinoise : blindage entre profilés")
    enrobage: float | None = Field(None, gt=0, description="distance du parement à l'axe des armatures (m)")
    armatures_fouille: float | None = Field(None, gt=0, description="paroi moulée : armatures côté fouille (cm²/m)")
    armatures_terre: float | None = Field(None, gt=0, description="paroi moulée : armatures côté terre (cm²/m)")
    armatures_pieu: float | None = Field(None, gt=0, description="pieux : armatures longitudinales par pieu (cm²)")
    armatures_horizontales: float | None = Field(
        None, gt=0, description="paroi moulée (pseudo-3D) : armatures horizontales par face (cm²/m de hauteur), pour le "
                                "moment horizontal Ms de la plaque")
    enrobage_horizontal: float | None = Field(
        None, gt=0, description="paroi moulée (pseudo-3D) : distance du parement à l'axe des armatures horizontales (m) ; "
                                "défaut : enrobage")
    longueur_panneau: float | None = Field(
        None, gt=0, description="paroi moulée (pseudo-3D) : longueur des panneaux (m) ; un joint entre panneaux ne transmet "
                                "ni moment ni torsion horizontaux")
    origine_panneaux: float = Field(
        0.0, ge=0, description="paroi moulée (pseudo-3D) : abscisse du premier joint le long de la paroi (m)")


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
    k_h: float | None = Field(None, gt=0, description="perméabilité horizontale (m/s), nécessaire au calcul d'écoulement")
    k_v: float | None = Field(None, gt=0, description="perméabilité verticale (m/s) ; défaut : k_h")
    cu: float | None = Field(None, gt=0, description="cohésion non drainée (kPa), stabilité du fond en argile molle")
    sol_lane: str | None = Field(None, description="type de sol de la table de Lane (clé de docs/normes/hydraulique.yaml -> lane.C)")


class BouchonScript(_Base):
    type: Literal["injecte", "jet_grouting", "radier_leste", "substratum"] = Field(description="type de bouchon")
    toit: float = Field(description="cote du toit du bouchon (m)")
    base: float = Field(description="cote de la base du bouchon (m)")
    k: float | None = Field(None, gt=0, description="perméabilité du bouchon (m/s) ; vide = imperméable")
    gamma: float = Field(20.0, gt=0, description="poids volumique du bouchon (kN/m3)")
    phase: int | str | None = Field(None, description="actif à partir de cette phase (numéro à partir de 1, ou nom) ; vide = dès le début")
    lest: float = Field(0.0, ge=0, description="charge permanente sus-jacente, radier lesté (kPa)")


class Hydraulique(_Base):
    regime: Literal["hydrostatique", "simplifie", "differences_finies"] = Field(
        "hydrostatique", description="régime de l'eau : hydrostatique, simplifié (cheminement) ou écoulement 2D en différences finies")
    substratum: float | None = Field(None, description="cote du toit du substratum imperméable (m) ; défaut : pied − 2 × hauteur")
    largeur_amont: float | None = Field(None, gt=0, le=2000, description="étendue du domaine amont (m) ; défaut : 4 × hauteur de paroi")
    largeur_fouille: float | None = Field(None, gt=0, description="largeur de la fouille (m), fouille symétrique ; défaut : 2 × hauteur")
    pas: float = Field(0.5, gt=0.05, le=2.0, description="taille des cellules du maillage d'écoulement (m)")
    bouchon: BouchonScript | None = Field(None, description="bouchon de fond de fouille")
    sol_lane: str | None = Field(None, description="type de sol pour Lane (sinon celui de la couche du fond)")


class AssemblageScript(_Base):
    type: str = Field(description="type d'assemblage (clé du registre : platine_about, chaise_buton, tete_tirant_lierne…)")
    appui: str | None = Field(None, description="appui dont les efforts sont repris (bloc appuis) ; sinon donner efforts")
    efforts: dict[str, float] | None = Field(None, description="efforts de calcul imposés, déjà pondérés (kN, kN·m) : N, V, M, T ; "
                                              "remplacent ceux déduits de l'appui (effort caractéristique × gamma_effets)")
    acier: str | None = Field(None, description="nuance des pièces d'assemblage (base matériaux)")
    lierne: str | None = Field(None, description="profilé de lierne (défaut : celui de l'appui)")
    buton: str | None = Field(None, description="élément de buton (défaut : celui de l'appui)")
    parametres: dict[str, float | str] = Field(default_factory=dict, description="paramètres géométriques du type (mm, kN, °)")


class RemblaiTerrain(_Base):
    cote: float = Field(description="cote du terrain amont après remblai (m)")
    materiau: str | None = Field(None, description="nom d'une couche du bloc sol dont le remblai prend les propriétés (défaut : 1re couche)")
    phase: int | str = Field(description="phase de mise en place (numéro à partir de 1, ou nom)")


class Terrain(_Base):
    amont: float | None = Field(None, description="cote initiale du terrain amont (m) ; défaut : toit de la 1re couche")
    aval: float | None = Field(None, description="cote initiale du terrain aval (m) ; défaut : terrain amont")
    pente_beta: float | None = Field(None, gt=-80, lt=80, description="terrain en pente uniforme côté terre : angle β sur l'horizontale (°), poussée de Coulomb avec talus")
    profil: list[list[float]] | None = Field(None, description="côté terre : ligne [distance à la paroi, cote] (m) ; le sol au-dessus de la cote amont est pris en surcharge équivalente")
    methode_pente: Literal["coulomb_beta", "surcharge_equivalente"] = Field("surcharge_equivalente", description="prise en compte du profil : coefficients avec β (pente uniforme) ou surcharge équivalente")
    cote_paroi: str | int | list[str | int] | None = Field(None, description="côté(s) concerné(s) par le profil (défaut : tous)")
    remblai: RemblaiTerrain | None = Field(None, description="remblai côté terre mis en place à une phase (couche ajoutée)")


class RisbermeScript(_Base):
    nom: str | None = Field(None, description="nom (pour la terrasser dans une phase)")
    cote_paroi: str | int | list[str | int] | None = Field(None, description="côté(s) de paroi concerné(s)")
    phases: list[int | str] = Field(min_length=2, max_length=2, description="[première, dernière] phase d'existence")
    cote_crete: float = Field(description="cote du sommet contre la paroi (m)")
    largeur_crete: float = Field(0.0, ge=0, description="largeur horizontale du sommet (m)")
    pente: float = Field(1.5, gt=0, description="pente du talus, horizontal / vertical")
    cote_pied: float = Field(description="cote du fond général au pied du talus (m)")
    largeur_banquette: float | None = Field(None, ge=0, description="talus : largeur de la banquette contre la paroi (m) = largeur_crete")
    methode: Literal["surcharge_equivalente", "fond_equivalent", "coin_de_rupture"] = Field(
        "surcharge_equivalente", description="prise en compte : surcharge équivalente (bandes de poids), fond équivalent (cote_equivalente à donner), coin de rupture (à fournir)")
    cote_equivalente: float | None = Field(None, description="méthode fond_equivalent : cote de fond de fouille équivalente choisie (m)")


class GradinsScript(_Base):
    nom: str | None = Field(None, description="nom")
    cote_paroi: str | int | list[str | int] | None = Field(None, description="côté(s) de paroi concerné(s)")
    phases: list[int | str] = Field(min_length=2, max_length=2, description="[première, dernière] phase d'existence")
    marches: list[list[float]] = Field(min_length=1, description="marches [cote, largeur] depuis la paroi (m)")
    cote_pied: float | None = Field(None, description="cote du fond général (m) ; défaut : fond de fouille à la première phase")
    methode: Literal["surcharge_equivalente", "coin_de_rupture"] = Field("surcharge_equivalente", description="prise en compte")


class Fouille(_Base):
    risbermes: list[RisbermeScript] = Field(default_factory=list, description="risbermes contre la paroi (côté fouille)")
    talus: list[RisbermeScript] = Field(default_factory=list, description="talus provisoires côté fouille (banquette puis pente)")
    gradins: list[GradinsScript] = Field(default_factory=list, description="fond de fouille en gradins")


class NiveauxEau(_Base):
    amont: float | None = Field(None, description="cote de la nappe côté amont (m) ; vide = pas de nappe")
    aval: float | None = Field(None, description="cote de la nappe côté aval (m) ; vide = pas de nappe")


class TraceSurcharge(_Base):
    de: list[float] = Field(description="début du tracé en plan [x, y] (m)")
    a: list[float] = Field(description="fin du tracé [x, y] (m)")


class Surcharge(_Base):
    nom: str | None = Field(None, description="nom (pour la retirer dans une phase, et pour la maquette)")
    type: Literal["repartie", "uniforme", "bande", "rectangulaire", "ponctuelle", "lineique", "lineaire", "convoi"] = Field(
        description="uniforme (= répartie), bande parallèle à la paroi, rectangulaire (emprise en plan), ponctuelle, "
                    "linéaire (= linéique), convoi (modèle routier à fournir)")
    q: float = Field(description="intensité : kPa (uniforme, bande, rectangulaire), kN (ponctuelle) ou kN/m (linéaire)")
    distance: float = Field(0.0, ge=0, description="bande : distance du parement au début de la bande (m)")
    largeur: float | None = Field(None, gt=0, description="bande : largeur (m) ; uniforme : largeur de la zone chargée (vide = illimitée)")
    cote: float | None = Field(None, description="cote d'application (m) ; défaut : terrain − profondeur")
    profondeur: float = Field(0.0, ge=0, description="profondeur d'application sous le terrain (m), ex. fondation d'un bâtiment")
    cote_ecran: Literal["amont", "aval"] = Field("amont", description="face de l'écran chargée")
    cote_paroi: str | int | list[str | int] | None = Field(
        None, description="côté(s) de paroi concerné(s) : nom de plan.cotes, numéro d'arête, liste ou « toutes » (défaut)")
    emprise: list[float] | dict[str, float] | None = Field(
        None, description="rectangulaire/ponctuelle : [lx, ly] (m) ; bande : {de, a} ou [de, a], étendue le long du côté (m)")
    position: list[float] | None = Field(None, description="rectangulaire/ponctuelle : centre en plan [x, y] (m)")
    trace: TraceSurcharge | None = Field(None, description="linéaire : segment en plan")
    niveaux: int | None = Field(None, ge=1, description="bâtiment : nombre de niveaux (maquette)")
    modele: str | None = Field(None, description="convoi : modèle routier (Bc, Bt…), charges à fournir dans docs/normes")
    phase: int | str | None = Field(None, description="phase d'application (numéro à partir de 1, ou nom) ; vide = dès le début")
    phases: list[int | str] | None = Field(None, min_length=2, max_length=2, description="[première, dernière] phase d'existence")


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
    lierne: str | None = Field(None, description="profilé de lierne (base matériaux) ; en pseudo-3D, poutre horizontale continue "
                                                 "E·Iy au niveau de l'appui (nuance acier requise), torsion négligée")
    nombre: int | None = Field(None, ge=1, description="tirant : nombre de torons ou de barres de l'élément")
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
    depuis: str | None = Field(None, description="phase de départ : nom d'une phase antérieure ou « État initial » ; vide = la phase précédente ; permet des branches (variantes)")
    terrasser_risberme: str | list[str] | None = Field(None, description="risberme(s), talus ou gradins terrassés dans cette phase (noms)")


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
    contour: list[list[float]] = Field(description="polygone de la fouille [[x, y], ...] (m) ; le polygone est fermé "
                                       "automatiquement (un dernier point égal au premier est ignoré)")

    @field_validator("contour")
    @classmethod
    def _contour_sans_doublon(cls, v: list[list[float]]) -> list[list[float]]:
        """Retire le point de fermeture répété ; refuse deux sommets consécutifs confondus (segment de
        longueur nulle, qui rendrait le maillage du pseudo-3D singulier)."""
        import math
        pts = [list(p) for p in v]
        if len(pts) >= 2 and all(len(p) == 2 for p in pts) and math.dist(pts[0], pts[-1]) < 1e-9:
            pts = pts[:-1]
        for i in range(1, len(pts)):
            if len(pts[i]) == 2 and len(pts[i - 1]) == 2 and math.dist(pts[i], pts[i - 1]) < 1e-9:
                raise ValueError(f"deux sommets consécutifs confondus ({pts[i - 1]}) : segment de longueur nulle")
        return pts
    appuis: list[AppuiPlan] = Field(default_factory=list, description="positions des appuis en plan")
    cote_terrain: float | None = Field(None, description="cote du terrain autour de la fouille (m)")
    cotes: dict[str, int] = Field(default_factory=dict, description="noms des côtés de la fouille -> numéro d'arête du contour (0 = premier segment)")


class TraceCoupe(_Base):
    de: list[float] = Field(description="point de départ de la trace en plan [x, y] (m)")
    a: list[float] = Field(description="point d'arrivée [x, y] (m)")


class ZoneCoupe(_Base):
    paroi: str | int = Field(description="côté de paroi auquel la coupe s'applique (nom du bloc plan.cotes ou numéro d'arête)")
    de: float | None = Field(None, description="début du tronçon, abscisse le long du côté depuis son origine (m) ; vide = début du côté")
    a: float | None = Field(None, description="fin du tronçon (m) ; vide = fin du côté")


class CoupeCalculScript(_Base):
    """Position de la coupe de calcul en plan (renseignée automatiquement par la préparation des coupes ;
    peut être écrite à la main pour rapporter des surcharges en plan à un script à coupe unique)."""
    x: float = Field(description="point de la coupe sur la paroi, x (m)")
    y: float = Field(description="point de la coupe sur la paroi, y (m)")
    ni: list[float] = Field(description="normale unitaire vers la fouille [nx, ny]")
    t: list[float] = Field(description="tangente unitaire du côté [tx, ty]")
    k: int = Field(0, ge=0, description="numéro d'arête du contour")
    s: float = Field(0.0, description="abscisse de la coupe le long du côté (m)")
    cote: str | None = Field(None, description="nom du côté (plan.cotes)")
    nom: str | None = Field(None, description="nom de la coupe")


class CoupeScript(_Base):
    nom: str = Field(description="nom de la coupe de calcul")
    trace: TraceCoupe | None = Field(None, description="trace de la coupe en plan (segment) ; vide = perpendiculaire au milieu du tronçon")
    zone: ZoneCoupe = Field(description="tronçon de paroi auquel la coupe s'applique")
    script: dict | str | None = Field(
        None, description="données locales de la coupe : bloc YAML en ligne (ou chemin d'un fichier du dossier exemples) ; "
                          "les clés absentes héritent du script principal")


class Pseudo3D(_Base):
    longueur: float | None = Field(
        None, gt=0, le=2000, description="paroi droite : longueur développée modélisée (m) ; absente avec un bloc plan : fouille "
                                "fermée sur tout le contour, butons reliant les parois en vis-à-vis (double écran)")
    pas_horizontal: float = Field(0.5, gt=0.05, description="taille des éléments selon la longueur (m)")
    bords: Literal["libres", "encastres", "appuyes"] = Field("libres", description="conditions aux extrémités")
    angle: float | None = Field(None, gt=0, lt=360, description="angle de la fouille au milieu de la paroi (degrés) ; "
                                "seule sa présence compte : la paroi perpendiculaire impose w = 0 sur la ligne d'angle "
                                "(appui simple, continuité du ferraillage d'angle négligée)")
    rigidite_horizontale: float | None = Field(
        None, ge=0, description="rigidité de flexion horizontale Ds imposée, par mètre de hauteur (kN·m²/m ; 0 = aucune) ; "
                                "défaut selon le type de paroi (paroi moulée : Ds = Dz ; palplanches, pieux, berlinoise : 0)")
    rapport_rigidite_horizontale: float | None = Field(
        None, ge=0, description="rapport Ds/Dz imposé (sans unité ; 0 = aucune flexion horizontale, 1 = plaque isotrope) ; "
                                "prioritaire sur le défaut du type, moins que rigidite_horizontale")
    torsion: float | None = Field(
        None, ge=0, description="rigidité de torsion GJ par mètre imposée (kN·m²/m) ; défaut √(Ds·Dz) (plaque de Huber)")
    largeur_appui: float | None = Field(
        None, gt=0, description="largeur sur laquelle chaque appui ponctuel est réparti le long de la paroi (m : plaque "
                                "d'appui, semelle de lierne) ; sans cette clé l'appui agit sur un seul nœud et Ms, V à "
                                "son droit dépendent du maillage")


Verification = Literal[
    "butee", "equilibre_vertical", "kranz", "fond_de_fouille", "stabilite_generale",
    "deplacements", "structure",
]


class Script(_Base):
    projet: str = Field(description="nom du projet ; ou bloc d'informations libres (nom, affaire, client, lieu…), "
                                    "dont le nom est affiché et les autres lignes conservées")
    projet_infos: dict = Field(default_factory=dict, description="informations du projet (rempli automatiquement "
                                                                 "quand projet est un bloc)")
    _avertissements_lecture: list = PrivateAttr(default_factory=list)

    @property
    def avertissements_lecture(self) -> list:
        """Avertissements de lecture (mots-clés inconnus ignorés), remplis par sout.script.lecteur."""
        return self._avertissements_lecture

    @avertissements_lecture.setter
    def avertissements_lecture(self, v: list) -> None:
        self._avertissements_lecture = list(v)

    @model_validator(mode="before")
    @classmethod
    def _projet_en_bloc(cls, d):
        """`projet:` écrit comme un bloc : le nom affiché est `nom` (ou `titre`, `intitule`, `affaire`),
        toutes les lignes sont gardées dans projet_infos."""
        if isinstance(d, dict) and isinstance(d.get("projet"), dict):
            infos = dict(d["projet"])
            nom = next((str(infos[k]) for k in ("nom", "titre", "intitule", "affaire") if infos.get(k) not in (None, "")),
                       "Projet sans nom")
            d = {**d, "projet": nom, "projet_infos": infos}
        elif isinstance(d, dict) and isinstance(d.get("projet"), (int, float)) and not isinstance(d.get("projet"), bool):
            d = {**d, "projet": str(d["projet"])}
        return d
    calcul: Calcul = Field(default_factory=Calcul)
    paroi: Paroi
    sol: list[Couche] = Field(min_length=1)
    terrain: Terrain = Field(default_factory=Terrain)
    fouille: Fouille = Field(default_factory=Fouille, description="risbermes, talus et gradins côté fouille")
    eau: dict[str, NiveauxEau] = Field(default_factory=dict, description="jeux de niveaux d'eau (service, exceptionnel…)")
    surcharges: list[Surcharge] = Field(default_factory=list)
    appuis: dict[str, Appui] = Field(default_factory=dict)
    phases: list[Phase] = Field(min_length=1)
    verifications: list[Verification] = Field(default_factory=list)
    criteres: Criteres = Field(default_factory=Criteres)
    plan: Plan | None = None
    pseudo3d: Pseudo3D | None = None
    hydraulique: Hydraulique | None = None
    assemblages: dict[str, AssemblageScript] = Field(default_factory=dict, description="assemblages à vérifier et à dessiner")
    coupes: list[CoupeScript] = Field(default_factory=list, description="coupes de calcul 2D placées en plan (vide = une coupe unique sur toute la paroi)")
    coupe_calcul: CoupeCalculScript | None = Field(None, description="position de cette coupe en plan (automatique)")
