"""Structures de la géométrie normalisée (indépendantes du langage de script).

Conventions : contour en plan [(x, y), ...] (m), écran sur le contour ; les côtés sont les arêtes du contour
(k = numéro d'arête, nom facultatif) ; une étendue rattache un objet à des côtés et à un tronçon [de, a] en
abscisses locales le long du côté (m). Cotes en m, axe vertical vers le haut.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Etendue:
    """Côtés concernés (noms ou « #k ») et tronçon [de, a] le long de ces côtés ; None = tous / côté entier."""
    cotes: tuple[str, ...] | None = None
    de: float | None = None
    a: float | None = None

    @property
    def troncon(self) -> tuple[float, float] | None:
        if self.de is None and self.a is None:
            return None
        return (self.de if self.de is not None else 0.0, self.a if self.a is not None else float("inf"))

    @property
    def partout(self) -> bool:
        return self.cotes is None and self.troncon is None


@dataclass(frozen=True)
class ZoneTerrain:
    nom: str
    etendue: Etendue
    cote: float | None                                  # cote du terrain amont dans la zone (m)
    pente_beta: float | None                            # pente uniforme côté terre (°)
    profil: tuple[tuple[float, float], ...] | None      # ligne (distance, cote) côté terre
    methode_pente: str = "surcharge_equivalente"


@dataclass(frozen=True)
class ZoneFond:
    nom: str
    etendue: Etendue
    emprise: tuple[tuple[float, float], ...] | None = None   # polygone en plan (maquette)
    largeur: float | None = None                              # bande depuis la paroi (m)


@dataclass(frozen=True)
class ObjetGeo:
    """Risberme, talus ou gradins côté fouille, décrits comme dans le script (profil construit à la conversion)."""
    nom: str
    type: str                                           # risberme, talus, gradins
    etendue: Etendue
    phases: tuple                                       # (première, dernière) : numéros ou noms
    cote_crete: float | None = None
    largeur_crete: float = 0.0
    pente: float = 1.5
    cote_pied: float | None = None
    marches: tuple[tuple[float, float], ...] | None = None
    methode: str = "surcharge_equivalente"
    cote_equivalente: float | None = None


@dataclass(frozen=True)
class PositionSurcharge:
    surcharge: str
    etendue: Etendue
    position: tuple[float, float] | None = None
    emprise: tuple[float, float] | None = None
    trace: tuple[tuple[float, float], tuple[float, float]] | None = None


@dataclass(frozen=True)
class GeometrieModele:
    contour: tuple[tuple[float, float], ...] | None
    ferme: bool
    cotes: dict[str, int]
    plan_appuis: tuple[dict, ...]
    terrain_cote: float | None
    remblai: dict | None
    zones_terrain: tuple[ZoneTerrain, ...]
    fond_initial: float | None
    zones_fond: tuple[ZoneFond, ...]
    objets: tuple[ObjetGeo, ...]
    positions: dict[str, PositionSurcharge] = field(default_factory=dict)
    forme_ancienne: bool = False

    def aretes(self) -> list[dict]:
        """Arêtes orientées du contour (sout.plan.geometrie), vide sans contour."""
        if not self.contour:
            return []
        from ..plan.geometrie import aretes
        return aretes([list(p) for p in self.contour], self.ferme)

    def noms_cotes(self) -> dict[int, str]:
        return {k: n for n, k in self.cotes.items()}

    def varie(self) -> bool:
        """Des données dépendent du côté ou de la position : zones, objets ou positions à étendue restreinte,
        surcharges positionnées en plan (rectangle, point, tracé)."""
        for z in self.zones_terrain:
            if not z.etendue.partout:
                return True
        for z in self.zones_fond:
            return True if z else False
        for o in self.objets:
            if not o.etendue.partout:
                return True
        for p in self.positions.values():
            if not p.etendue.partout or p.position is not None or p.trace is not None:
                return True
        return False
