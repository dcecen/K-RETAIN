"""Lecture de la géométrie d'un script : bloc `geometrie` (forme normalisée) ou, à défaut, les blocs de la forme
ancienne (`plan`, `fouille`, clés de pente de `terrain`, clés de plan des surcharges), convertis vers la même
structure. Fonctions pures sur le script validé (sout.script.schema.Script).

Table de correspondance forme ancienne -> nouvelle :
  plan.contour / cotes / appuis           -> geometrie.ouvrages (ferme: true)
  terrain.amont / aval / remblai           -> geometrie.terrain.cote / geometrie.fouille.cote_initiale / terrain.remblai
  terrain.pente_beta, profil, methode_pente, cote_paroi -> geometrie.terrain.zones[0]
  fouille.risbermes / talus / gradins      -> geometrie.fouille.objets (type, cotes = cote_paroi, côté entier)
  surcharges[].cote_paroi / emprise / position / trace -> geometrie.surcharges[] (position en plan par nom)
"""
from __future__ import annotations

from .modele import Etendue, GeometrieModele, ObjetGeo, PositionSurcharge, ZoneFond, ZoneTerrain

NOMS_DEFAUT = {"risberme": "Risberme", "talus": "Talus", "gradins": "Gradins"}


def _cotes(cp) -> tuple[str, ...] | None:
    """Côtés d'un objet : noms du bloc cotes ou « #k » pour un numéro d'arête ; None = tous."""
    if cp is None or cp == "toutes":
        return None
    liste = [cp] if isinstance(cp, (str, int)) else list(cp)
    return tuple(f"#{c}" if isinstance(c, int) else str(c) for c in liste) or None


def _etendue(obj) -> Etendue:
    return Etendue(_cotes(getattr(obj, "cotes", None)), getattr(obj, "de", None), getattr(obj, "a", None))


def _profil(p) -> tuple[tuple[float, float], ...] | None:
    return None if p is None else tuple((float(d), float(z)) for d, z in p)


def _nom_objet(o, compteurs: dict[str, int]) -> str:
    """Nom par défaut Risberme1, Talus1, Gradins1 (même règle que l'ancienne conversion, par type)."""
    compteurs[o.type] = compteurs.get(o.type, 0) + 1
    return o.nom or f"{NOMS_DEFAUT.get(o.type, o.type.capitalize())}{compteurs[o.type]}"


def forme_ancienne_presente(s) -> list[str]:
    """Chemins de la forme ancienne utilisés par le script (vide si seule la forme normalisée l'est)."""
    out = []
    if s.plan is not None and not getattr(s, "plan_derive", False):
        out.append("plan")
    for cle in ("risbermes", "talus", "gradins"):
        if getattr(s.fouille, cle):
            out.append(f"fouille.{cle}")
    t = s.terrain
    for cle in ("pente_beta", "profil", "cote_paroi"):
        if getattr(t, cle) is not None:
            out.append(f"terrain.{cle}")
    return out


def _depuis_bloc(s) -> GeometrieModele:
    g = s.geometrie
    o = g.ouvrages
    contour = tuple((float(p[0]), float(p[1])) for p in o.contour) if o is not None else None
    cotes = dict(o.cotes) if o is not None else {}
    plan_appuis = tuple(a.model_dump() for a in o.appuis) if o is not None else ()
    t = g.terrain
    zones_terrain = tuple(ZoneTerrain(z.nom or f"terrain{i + 1}", _etendue(z), z.cote, z.pente_beta, _profil(z.profil), z.methode_pente)
                          for i, z in enumerate(t.zones)) if t is not None else ()
    f = g.fouille
    zones_fond = tuple(ZoneFond(z.nom, _etendue(z), _profil(z.emprise), z.largeur) for z in f.zones) if f is not None else ()
    compteurs: dict[str, int] = {}
    objets = tuple(ObjetGeo(_nom_objet(ob, compteurs), ob.type, _etendue(ob), tuple(ob.phases), ob.cote_crete, ob.largeur_crete,
                            ob.pente, ob.cote_pied, _profil(ob.marches), ob.methode, ob.cote_equivalente)
                   for ob in f.objets) if f is not None else ()
    positions = {}
    for p in g.surcharges:
        positions[p.surcharge] = PositionSurcharge(p.surcharge, _etendue(p), tuple(p.position) if p.position else None,
                                                   tuple(p.emprise) if p.emprise else None,
                                                   ((p.trace.de[0], p.trace.de[1]), (p.trace.a[0], p.trace.a[1])) if p.trace else None)
    terrain_cote = t.cote if t is not None and t.cote is not None else s.terrain.amont
    fond_initial = f.cote_initiale if f is not None and f.cote_initiale is not None else s.terrain.aval
    remblai = (t.remblai.model_dump() if t is not None and t.remblai is not None
               else s.terrain.remblai.model_dump() if s.terrain.remblai is not None else None)
    return GeometrieModele(contour, o.ferme if o is not None else True, cotes, plan_appuis, terrain_cote, remblai, zones_terrain,
                           fond_initial, zones_fond, objets, positions, forme_ancienne=False)


def _depuis_ancienne(s) -> GeometrieModele:
    plan, t, f = s.plan, s.terrain, s.fouille
    contour = tuple((float(p[0]), float(p[1])) for p in plan.contour) if plan is not None else None
    zones_terrain = ()
    if t.pente_beta is not None or t.profil is not None:
        zones_terrain = (ZoneTerrain("terrain", Etendue(_cotes(t.cote_paroi)), None, t.pente_beta, _profil(t.profil), t.methode_pente),)
    objets = []
    for type_, liste in (("risberme", f.risbermes), ("talus", f.talus), ("gradins", f.gradins)):
        for i, o in enumerate(liste):
            nom = o.nom or f"{NOMS_DEFAUT[type_]}{i + 1}"
            if type_ == "gradins":
                objets.append(ObjetGeo(nom, type_, Etendue(_cotes(o.cote_paroi)), tuple(o.phases), None, 0.0, 1.5, o.cote_pied,
                                       _profil(o.marches), o.methode, None))
            else:
                largeur = o.largeur_banquette if (type_ == "talus" and o.largeur_banquette is not None) else o.largeur_crete
                objets.append(ObjetGeo(nom, type_, Etendue(_cotes(o.cote_paroi)), tuple(o.phases), o.cote_crete, largeur, o.pente,
                                       o.cote_pied, None, o.methode, getattr(o, "cote_equivalente", None)))
    positions = {}
    toutes = list(s.surcharges) + [sc for ph in s.phases for sc in (ph.ajouter_surcharges or [])]
    n = 0
    for sc in toutes:
        n += 1
        nom = sc.nom or f"S{n}"
        if sc.cote_paroi is None and sc.emprise is None and sc.position is None and sc.trace is None:
            continue
        de = a = None
        emprise = None
        if isinstance(sc.emprise, dict):
            de, a = float(sc.emprise.get("de", 0.0)), float(sc.emprise.get("a", 0.0))
        elif isinstance(sc.emprise, list) and len(sc.emprise) == 2:
            emprise = (float(sc.emprise[0]), float(sc.emprise[1]))
        positions[nom] = PositionSurcharge(nom, Etendue(_cotes(sc.cote_paroi), de, a), tuple(sc.position) if sc.position else None, emprise,
                                           ((sc.trace.de[0], sc.trace.de[1]), (sc.trace.a[0], sc.trace.a[1])) if sc.trace else None)
    return GeometrieModele(contour, True, dict(plan.cotes) if plan is not None else {},
                           tuple(a.model_dump() for a in plan.appuis) if plan is not None else (),
                           t.amont, t.remblai.model_dump() if t.remblai is not None else None, zones_terrain, t.aval, (), tuple(objets),
                           positions, forme_ancienne=True)


def depuis_script(s) -> GeometrieModele:
    """Géométrie du script : bloc `geometrie` s'il existe, sinon la forme ancienne convertie."""
    return _depuis_bloc(s) if s.geometrie is not None else _depuis_ancienne(s)


def vers_bloc_geometrie(s) -> dict:
    """Bloc `geometrie` (dictionnaire YAML) équivalent à la forme ancienne du script (bouton « Convertir »)."""
    g = depuis_script(s)
    bloc: dict = {}
    if g.contour:
        bloc["ouvrages"] = {"contour": [list(p) for p in g.contour], **({"ferme": False} if not g.ferme else {}),
                            **({"cotes": dict(g.cotes)} if g.cotes else {}), **({"appuis": list(g.plan_appuis)} if g.plan_appuis else {})}
    terrain: dict = {}
    if g.terrain_cote is not None:
        terrain["cote"] = g.terrain_cote
    if g.remblai:
        terrain["remblai"] = dict(g.remblai)
    if g.zones_terrain:
        terrain["zones"] = [_etendue_dict(z.etendue, {"nom": z.nom, "cote": z.cote, "pente_beta": z.pente_beta,
                                                      "profil": [list(p) for p in z.profil] if z.profil else None, "methode_pente": z.methode_pente})
                            for z in g.zones_terrain]
    if terrain:
        bloc["terrain"] = terrain
    fouille: dict = {}
    if g.fond_initial is not None:
        fouille["cote_initiale"] = g.fond_initial
    if g.zones_fond:
        fouille["zones"] = [_etendue_dict(z.etendue, {"nom": z.nom, "emprise": [list(p) for p in z.emprise] if z.emprise else None, "largeur": z.largeur})
                            for z in g.zones_fond]
    if g.objets:
        fouille["objets"] = [_etendue_dict(o.etendue, {"nom": o.nom, "type": o.type, "phases": list(o.phases), "cote_crete": o.cote_crete,
                                                       "largeur_crete": o.largeur_crete if o.type != "gradins" else None,
                                                       "pente": o.pente if o.type != "gradins" else None, "cote_pied": o.cote_pied,
                                                       "marches": [list(m) for m in o.marches] if o.marches else None,
                                                       "methode": o.methode if o.methode != "surcharge_equivalente" else None,
                                                       "cote_equivalente": o.cote_equivalente})
                             for o in g.objets]
    if fouille:
        bloc["fouille"] = fouille
    if g.positions:
        bloc["surcharges"] = [_etendue_dict(p.etendue, {"surcharge": p.surcharge, "position": list(p.position) if p.position else None,
                                                        "emprise": list(p.emprise) if p.emprise else None,
                                                        "trace": {"de": list(p.trace[0]), "a": list(p.trace[1])} if p.trace else None})
                              for p in g.positions.values()]
    return bloc


def _etendue_dict(e: Etendue, d: dict) -> dict:
    out = {k: v for k, v in d.items() if v is not None}
    if e.cotes is not None:
        out["cotes"] = [int(c[1:]) if c.startswith("#") else c for c in e.cotes]
    if e.de is not None:
        out["de"] = e.de
    if e.a is not None:
        out["a"] = e.a
    return out
