"""Dérivation des données 2D locales en un point de la paroi (coupe de calcul) à partir de la géométrie normalisée,
et classes de lignes verticales du pseudo-3D (lignes partageant les mêmes données locales).

Règle unique de rattachement : `sout.plan.geometrie.objet_concerne(cotes, troncon, coupe)` ; sans coupe (calcul 2D
sans plan, ou plaque pseudo-3D prise globalement), tout concerne la coupe.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..plan.geometrie import objet_concerne
from .modele import Etendue, GeometrieModele, ObjetGeo, PositionSurcharge, ZoneFond, ZoneTerrain

ZONE_DEFAUT = "defaut"


def etendue_concerne(e: Etendue, coupe) -> bool:
    return objet_concerne(e.cotes, e.troncon, coupe)


def zone_fond_de(geo: GeometrieModele, coupe) -> ZoneFond | None:
    """Première zone de fond concernant la coupe (None = zone par défaut) ; sans coupe : aucune zone."""
    if coupe is None:
        return None
    for z in geo.zones_fond:
        if etendue_concerne(z.etendue, coupe):
            return z
    return None


def zone_terrain_de(geo: GeometrieModele, coupe) -> ZoneTerrain | None:
    """Première zone de terrain côté terre concernant la coupe ; sans coupe, une zone sans restriction s'applique."""
    for z in geo.zones_terrain:
        if coupe is None and z.etendue.partout:
            return z
        if coupe is not None and etendue_concerne(z.etendue, coupe):
            return z
    return None


def excaver_local(excaver, zone: str) -> float | None:
    """Cote d'excavation d'une phase pour une zone de fond : nombre = toutes les zones ; bloc = zone ou `defaut`."""
    if excaver is None or isinstance(excaver, (int, float)):
        return None if excaver is None else float(excaver)
    v = excaver.get(zone, excaver.get(ZONE_DEFAUT))
    return None if v is None else float(v)


@dataclass(frozen=True)
class DonneesLocales:
    coupe: object                                   # CoupeCalcul ou None
    zone_fond: str                                  # nom de la zone de fond ou « defaut »
    terrain_amont: float | None
    beta: float | None
    profil: tuple[tuple[float, float], ...] | None
    methode_pente: str
    cotes_pente: tuple[str, ...] | None             # côtés de la zone de pente (filtrage des bandes équivalentes)
    fond_initial: float | None
    objets: tuple[ObjetGeo, ...]                    # objets concernant la coupe (tous sans coupe)
    positions: dict[str, PositionSurcharge]

    @property
    def zone_est_defaut(self) -> bool:
        return self.zone_fond == ZONE_DEFAUT


def locale(geo: GeometrieModele, coupe, tous_objets: bool = False) -> DonneesLocales:
    """Données locales au droit de la coupe. `tous_objets` : garder tous les objets (plaque pseudo-3D : chaque
    ligne filtre ensuite elle-même par sa propre coupe)."""
    zf = zone_fond_de(geo, coupe)
    zt = zone_terrain_de(geo, coupe)
    terrain = geo.terrain_cote
    if zt is not None and zt.cote is not None:
        terrain = zt.cote
    objets = tuple(o for o in geo.objets if tous_objets or coupe is None or etendue_concerne(o.etendue, coupe))
    return DonneesLocales(coupe, zf.nom if zf is not None else ZONE_DEFAUT, terrain,
                          zt.pente_beta if zt is not None else None, zt.profil if zt is not None else None,
                          zt.methode_pente if zt is not None else "surcharge_equivalente",
                          zt.etendue.cotes if zt is not None else None,
                          geo.fond_initial, objets, dict(geo.positions))


def signature(geo: GeometrieModele, coupe) -> tuple:
    """Clé d'homogénéité d'une ligne verticale : zone de fond, zone de terrain, objets et positions la concernant."""
    zf = zone_fond_de(geo, coupe)
    zt = zone_terrain_de(geo, coupe)
    objets = frozenset(o.nom for o in geo.objets if etendue_concerne(o.etendue, coupe))
    positions = frozenset(p.surcharge for p in geo.positions.values() if p.position is None and p.trace is None and etendue_concerne(p.etendue, coupe))
    return (zf.nom if zf else ZONE_DEFAUT, zt.nom if zt else None, objets, positions)


def classes_lignes(geo: GeometrieModele, coupes: list) -> tuple[list[int], list]:
    """Classe de chaque ligne (indice dans la liste des représentants) et un représentant par classe."""
    classes: list[int] = []
    representants: list = []
    index: dict[tuple, int] = {}
    for c in coupes:
        sig = signature(geo, c)
        if sig not in index:
            index[sig] = len(representants)
            representants.append(c)
        classes.append(index[sig])
    return classes, representants


def fonds_par_zone(geo: GeometrieModele, excaver_phases: list, fond_initial: float | None) -> dict[str, float | None]:
    """Cote du fond de chaque zone (et `defaut`) après la liste des `excaver` des phases jouées."""
    noms = [ZONE_DEFAUT] + [z.nom for z in geo.zones_fond]
    fonds: dict[str, float | None] = {n: fond_initial for n in noms}
    for ex in excaver_phases:
        for n in noms:
            v = excaver_local(ex, n)
            if v is not None:
                fonds[n] = v
    return fonds
