"""Découpage du contour en tronçons homogènes (coupes automatiques) et polygones des zones de fond (maquette).
Fonctions pures sur la géométrie normalisée."""
from __future__ import annotations

from ..plan.geometrie import vis_a_vis
from ..sol.terrain import CoupeCalcul
from .derivation import signature
from .modele import Etendue, GeometrieModele, ZoneFond


def _cote_de_etendue(e: Etendue, k: int, noms: dict[int, str]) -> bool:
    """L'étendue concerne-t-elle l'arête k ?"""
    if e.cotes is None:
        return True
    return f"#{k}" in e.cotes or (noms.get(k) is not None and noms[k] in e.cotes)


def points_de_rupture(geo: GeometrieModele, k: int, L: float) -> list[float]:
    """Abscisses locales où les données changent le long de l'arête k (bornes des étendues), avec 0 et L."""
    noms = geo.noms_cotes()
    pts = {0.0, L}
    etendues = [z.etendue for z in geo.zones_terrain] + [z.etendue for z in geo.zones_fond] + [o.etendue for o in geo.objets] \
        + [p.etendue for p in geo.positions.values()]
    for e in etendues:
        if not _cote_de_etendue(e, k, noms):
            continue
        for v in (e.de, e.a):
            if v is not None and 0.0 < v < L:
                pts.add(float(v))
    return sorted(pts)


def _coupe(ar: dict, sl: float, noms: dict[int, str]) -> CoupeCalcul:
    return CoupeCalcul(x=ar["A"][0] + ar["t"][0] * sl, y=ar["A"][1] + ar["t"][1] * sl, ni=tuple(ar["ni"]), t=tuple(ar["t"]),
                       k=ar["k"], s=sl, cote=noms.get(ar["k"]))


def troncons_automatiques(geo: GeometrieModele) -> list[tuple[int, float, float]]:
    """Tronçons (k, de, a) homogènes du contour : un par côté sans variation, sinon découpé aux bornes des étendues ;
    les tronçons voisins de même signature sont fusionnés."""
    noms = geo.noms_cotes()
    out: list[tuple[int, float, float]] = []
    for ar in geo.aretes():
        if ar["L"] <= 1e-9:
            continue
        pts = points_de_rupture(geo, ar["k"], ar["L"])
        courant = None
        for de, a in zip(pts, pts[1:]):
            sig = signature(geo, _coupe(ar, 0.5 * (de + a), noms))
            if courant is not None and courant[2] == sig:
                courant = (courant[0], a, sig)
            else:
                if courant is not None:
                    out.append((ar["k"], courant[0], courant[1]))
                courant = (de, a, sig)
        if courant is not None:
            out.append((ar["k"], courant[0], courant[1]))
    return out


def polygone_zone(geo: GeometrieModele, zone: ZoneFond) -> list[tuple[float, float]]:
    """Polygone en plan d'une zone de fond : son emprise, sinon une bande depuis la paroi sur les tronçons concernés
    (largeur donnée, sinon la moitié de la distance au vis-à-vis au milieu du tronçon)."""
    if zone.emprise:
        return [tuple(p) for p in zone.emprise]
    noms = geo.noms_cotes()
    ars = geo.aretes()
    for ar in ars:
        if not _cote_de_etendue(zone.etendue, ar["k"], noms):
            continue
        de = zone.etendue.de if zone.etendue.de is not None else 0.0
        a = min(zone.etendue.a if zone.etendue.a is not None else ar["L"], ar["L"])
        if a <= de:
            continue
        largeur = zone.largeur
        if largeur is None:
            vav = vis_a_vis(ars, ar["k"], 0.5 * (de + a)) if geo.ferme and len(ars) > 2 else None
            largeur = 0.5 * vav[3] if vav is not None else 0.5 * ar["L"]     # vis_a_vis : (s, k, sl, distance)
        A = (ar["A"][0] + ar["t"][0] * de, ar["A"][1] + ar["t"][1] * de)
        B = (ar["A"][0] + ar["t"][0] * a, ar["A"][1] + ar["t"][1] * a)
        return [A, B, (B[0] + ar["ni"][0] * largeur, B[1] + ar["ni"][1] * largeur), (A[0] + ar["ni"][0] * largeur, A[1] + ar["ni"][1] * largeur)]
    return []
