"""Description d'un calcul d'écran, indépendante du langage de script.

Le lecteur de script (sout.script) produit un `Modele` ; le moteur de phases
(sout.noyau.phasage) le calcule.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from ..sol.couches import Couche
from ..sol.surcharges import Surcharge

# (z_milieux, côté −1/+1, cote du fond de fouille) -> (facteur limites, facteur raideur)
FonctionLargeur = Callable[[np.ndarray, int, float], tuple[np.ndarray, np.ndarray]]


@dataclass
class Ecran:
    tete: float                     # m
    pied: float                     # m
    EI: float                       # kN·m²/m (par mètre linéaire)
    segments_EI: list[tuple[float, float, float]] = field(default_factory=list)  # (z_bas, z_haut, EI)
    largeur_reaction: FonctionLargeur | None = None
    infos: dict = field(default_factory=dict)  # type, section, etc. (pour les vérifications)

    def EI_en(self, z: np.ndarray) -> np.ndarray:
        out = np.full(np.shape(z), float(self.EI))
        for z_bas, z_haut, ei in self.segments_EI:
            out[(z >= z_bas) & (z <= z_haut)] = ei
        return out


@dataclass
class DefAppui:
    nom: str
    cote: float                 # m
    raideur: float              # kN/m par mètre linéaire d'écran
    precharge: float = 0.0      # kN/m par mètre linéaire (précharge ou précontrainte horizontale)
    unilateral: bool = True     # ne reprend pas d'effort négatif
    type: str = "buton"
    infos: dict = field(default_factory=dict)


@dataclass
class Phase:
    nom: str
    excaver: float | None = None          # nouvelle cote du terrain aval
    remblayer_amont: float | None = None  # nouvelle cote du terrain amont
    remblayer_aval: float | None = None   # nouvelle cote du terrain aval (remontée)
    poser: list[str] = field(default_factory=list)
    deposer: list[str] = field(default_factory=list)
    eau: dict = field(default_factory=dict)  # {"amont": z | None, "aval": z | None} ; clé absente = inchangé
    ajouter_surcharges: list[Surcharge] = field(default_factory=list)
    retirer_surcharges: list[str] = field(default_factory=list)
    depuis: str | None = None             # phase de départ (nom) ; None = la phase précédente de la liste


@dataclass
class Modele:
    ecran: Ecran
    couches: list[Couche]
    phases: list[Phase]
    appuis: dict[str, DefAppui] = field(default_factory=dict)
    terrain_amont: float | None = None   # défaut : toit de la première couche
    terrain_aval: float | None = None    # défaut : terrain amont
    eau_amont: float | None = None
    eau_aval: float | None = None
    surcharges: list[Surcharge] = field(default_factory=list)
    gamma_w: float = 10.0                # kN/m3, choisi par projet
    coefficients: str = "coulomb"        # "coulomb" ou "kerisel_absi"
    pas: float = 0.1                     # m, longueur maximale d'élément
    y_rupture: float = 5.0               # m
    hydraulique: dict | None = None      # bloc hydraulique du script (régime, substratum, bouchon...)
    coupe: dict | None = None            # position de la coupe en plan (surcharges et terrain rapportés à la coupe)
