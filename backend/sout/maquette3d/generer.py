"""Maquette 3D autonome (un seul fichier HTML, three.js intégré, sans réseau).

Contenu : fouille définie en plan par un polygone, paroi extrudée selon son type
(palplanches, pieux, profilés et blindage, panneaux de paroi moulée), appuis
(butons, tirants, bracons, dalles, liernes) avec leur référence de la base,
couches de sol transparentes, nappes, fond de fouille par phase, curseur de
phase. Paroi colorée selon le déplacement ou le moment (profil 2D, ou champ
pseudo-3D quand il est disponible).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

ICI = Path(__file__).resolve().parent
RECTANGLE_DEFAUT = [[0.0, 0.0], [20.0, 0.0], [20.0, 12.0], [0.0, 12.0]]


def coupe_infinie(hauteur: float) -> tuple[list[list[float]], str]:
    """Contour d'affichage d'une étude 2D sans tracé en plan : un tronçon droit d'écran, ouvert aux deux bouts
    (l'écran est supposé infini, déformation plane), long de deux hauteurs d'écran et au moins 16 m. Aucune géométrie
    de fouille n'est inventée : terre d'un côté, fouille de l'autre, coupées net aux deux bouts."""
    L = float(max(16.0, round(2.0 * hauteur)))
    return ([[0.0, 0.0], [L, 0.0]],
            f"Coupe 2D : écran supposé de longueur infinie (déformation plane), tronçon de {L:g} m dessiné, coupé aux deux "
            "bouts ; aucune géométrie en plan n'est inventée. Le tracé réel se saisit dans l'étape Géométrie.")


def contour_paroi_droite(longueur: float, angle: float | None) -> tuple[list[list[float]], str]:
    """Contour d'affichage d'une paroi droite pseudo-3D sans tracé en plan, et la note qui l'explique : polyligne
    ouverte de la longueur modélisée, droite, ou en deux côtés égaux de part et d'autre de l'angle de fouille placé
    à mi-longueur (pseudo3d.angle). Le calcul n'utilise pas ce contour : seule la présence de l'angle compte."""
    L = float(longueur)
    if angle is None or abs(angle - 180.0) < 1e-6:
        return ([[0.0, 0.0], [L, 0.0]],
                f"Paroi droite pseudo-3D de {L:g} m sans tracé en plan : dessinée droite, ouverte aux deux bouts. Le tracé "
                "réel se saisit dans l'étape Géométrie.")
    a = angle if 0.0 < angle < 180.0 else 90.0      # angle rentrant : dessiné à 90°, sans effet sur le calcul
    h, t = L / 2, np.radians(a)
    A, B, C = [0.0, h], [0.0, 0.0], [float(h * np.sin(t)), float(h * np.cos(t))]
    note = (f"Paroi pseudo-3D de {L:g} m avec un angle de fouille à mi-longueur : deux côtés de {h:g} m de part et "
            f"d'autre de l'angle{' (angle rentrant dessiné à 90°)' if a != angle else ''}, ouverts aux bouts. Le tracé réel "
            "se saisit dans l'étape Géométrie.")
    return [[round(x, 6) for x in p] for p in (A, B, C)], note


from ..plan.geometrie import placer_appuis  # noqa: E402  (géométrie partagée)


def _l(a) -> list:
    return [round(float(v), 4) for v in np.asarray(a, float)]


def geometrie(ex) -> dict:
    """Géométrie de la maquette, indépendante des résultats de phase : paroi, contour en
    plan, couches, appuis et leur position en plan. Sert à la maquette autonome et à la
    vue 3D de l'interface (renvoyée avec les résultats du calcul)."""
    s, m, res = ex.script, ex.modele, ex.resultat
    inf = m.ecran.infos
    sec = inf.get("section") or {}
    paroi = {
        "type": s.paroi.type, "tete": s.paroi.tete, "pied": s.paroi.pied,
        "epaisseur": s.paroi.epaisseur or 0.6, "diametre": s.paroi.diametre or 0.8,
        "entraxe": s.paroi.entraxe or 1.0, "profil": s.paroi.profil,
        "b": (sec.get("b_mm") or sec.get("largeur_mm") or 300) / 1000,
        "h": (sec.get("h_mm") or 400) / 1000, "tf": (sec.get("tf_mm") or 15) / 1000,
        "tw": (sec.get("tw_mm") or 10) / 1000,
        "blindage": s.paroi.blindage.epaisseur if s.paroi.blindage else None,
    }
    appuis = {}
    for nom, a in s.appuis.items():
        D = 0.3
        if a.element:
            try:
                from ..materiaux.base import catalogue_par_defaut
                el = catalogue_par_defaut().element(a.element)
                D = (el.get("D_mm") or el.get("h_mm") or 300) / 1000
            except KeyError:
                pass
        appuis[nom] = {"type": a.type, "cote": a.cote, "angle": a.angle, "element": a.element, "lierne": a.lierne,
                       "longueur": a.longueur, "longueur_libre": a.longueur_libre,
                       "longueur_scellee": a.longueur_scellee, "epaisseur": a.epaisseur,
                       "pied_bracon": a.pied_bracon, "espacement": a.espacement, "D": D}
    defaut = s.plan is None
    contour = s.plan.contour if s.plan else RECTANGLE_DEFAUT
    note_plan, ouvert = None, False
    if defaut:
        # sans tracé en plan, rien n'est inventé : coupe 2D infinie, ou paroi droite pseudo-3D sur sa longueur
        ouvert = True
        if s.calcul.mode == "pseudo3d" and s.pseudo3d is not None and s.pseudo3d.longueur:
            contour, note_plan = contour_paroi_droite(s.pseudo3d.longueur, s.pseudo3d.angle)
        else:
            contour, note_plan = coupe_infinie(s.paroi.tete - s.paroi.pied)
    if getattr(s.paroi, "forme", "plane") == "circulaire" and s.paroi.rayon:
        # paroi circulaire : polygone d'affichage (celui du calcul en pseudo-3D, 48 côtés en 2D axisymétrique)
        from ..parois.anneau import contour_polygone, nombre_cotes_polygone
        n = (nombre_cotes_polygone(s.paroi.rayon, s.pseudo3d.pas_horizontal)
             if s.calcul.mode == "pseudo3d" and s.pseudo3d is not None else 48)
        contour, defaut, note_plan, ouvert = contour_polygone(s.paroi.rayon, n), False, None, False
        paroi.update(forme="circulaire", rayon=s.paroi.rayon)
    plan_appuis = ([ap.model_dump() for ap in s.plan.appuis] if s.plan and s.plan.appuis
                   else placer_appuis(contour, appuis, ferme=not ouvert))
    couches = sorted(({"nom": c.nom, "toit": c.toit} for c in m.couches), key=lambda c: -c["toit"])
    # gradient critique de la couche du fond, par phase (flèches de gradient de la maquette)
    from ..sol.couches import indice_couche
    couches_t = sorted(m.couches, key=lambda c: -c.toit)
    i_crit = []
    for ph in res.phases:
        if ph.ok and ph.hydro:
            c_fond = couches_t[indice_couche(couches_t, ph.terrain_aval - 1e-6)]
            i_crit.append(c_fond.gamma_dejauge / m.gamma_w)
        else:
            i_crit.append(None)
    geo = getattr(m, "geometrie", None)
    zones = []
    if geo is not None:
        from ..geometrie.decoupage import polygone_zone
        for z in geo.zones_fond:
            zones.append({"nom": z.nom, "cotes": list(z.etendue.cotes) if z.etendue.cotes else None, "de": z.etendue.de, "a": z.etendue.a,
                          "polygone": [[round(float(x), 4), round(float(y), 4)] for x, y in polygone_zone(geo, z)]})
    return {
        "projet": s.projet, "paroi": paroi, "contour": contour, "plan_defaut": defaut, "note_plan": note_plan,
        "couches": couches, "z_bas": s.paroi.pied - max(3.0, 0.25 * (s.paroi.tete - s.paroi.pied)),
        "appuis": appuis, "plan_appuis": plan_appuis, "i_critique": i_crit,
        "assemblages": {nom: {"type": a.type, "appui": a.appui} for nom, a in s.assemblages.items()},
        "surcharges": surcharges_maquette(ex),
        "terrain": terrain_maquette(ex),
        "coupe_calcul": s.coupe_calcul.model_dump() if s.coupe_calcul is not None else None,
        # géométrie normalisée (bloc geometrie ou forme ancienne convertie) : côtés nommés, fermeture, zones de fond,
        # longueur de plaque modélisée (paroi droite pseudo-3D : au-delà, pas de résultat)
        "cotes": dict(geo.cotes) if geo is not None else (s.plan.cotes if s.plan else {}),
        "ferme": False if ouvert else (geo.ferme if geo is not None else True),
        "zones": zones,
        "longueur_modele": s.pseudo3d.longueur if s.pseudo3d is not None else None,
    }


def terrain_maquette(ex) -> dict:
    """Géométrie du terrain pour la maquette : profil côté terre, pente, remblai, objets phasés (risbermes,
    talus, gradins) avec leur ligne, leur méthode et leur fenêtre de phases."""
    s, m = ex.script, ex.modele
    t = s.terrain
    objets = []
    for o in m.terrain_objets:
        tr = getattr(o, "troncon", None)
        objets.append({"nom": o.nom, "type": o.type, "face": o.face, "profil": [list(p) for p in o.profil], "base": o.base,
                       "gamma": o.gamma, "methode": o.methode, "phase_debut": o.phase_debut or 0,
                       "phase_fin": o.phase_fin if o.phase_fin is not None else len(m.phases),
                       "cotes_paroi": list(o.cotes_paroi) if o.cotes_paroi else None, "cote_equivalente": o.cote_equivalente,
                       "troncon": [tr[0], tr[1] if tr[1] != float("inf") else None] if tr else None})
    geo = getattr(m, "geometrie", None)
    zones_terrain = [{"nom": z.nom, "cotes": list(z.etendue.cotes) if z.etendue.cotes else None, "de": z.etendue.de, "a": z.etendue.a,
                      "cote": z.cote, "pente_beta": z.pente_beta, "profil": [list(p) for p in z.profil] if z.profil else None,
                      "methode_pente": z.methode_pente} for z in geo.zones_terrain] if geo is not None else []
    return {"profil": t.profil, "pente_beta": m.beta_amont, "methode_pente": t.methode_pente, "cote_paroi": t.cote_paroi,
            "zones_terrain": zones_terrain,
            "remblai": t.remblai.model_dump() if t.remblai else None, "objets": objets}


def surcharges_maquette(ex) -> list[dict]:
    """Surcharges du script avec leur fenêtre de phases et le profil Δσv au droit de la coupe (maquette, panneau)."""
    from ..sol.terrain import CoupeCalcul, SurchargePlan, profil_pour_affichage

    m = ex.modele
    coupe = CoupeCalcul.depuis_dict(m.coupe)
    z_terrain = m.terrain_amont if m.terrain_amont is not None else max(c.toit for c in m.couches)
    objets = []
    # surcharges du moteur, dans l'ordre d'apparition, avec leur fenêtre de phases (1 = première phase)
    n_phases = len(m.phases)
    vus: dict[str, dict] = {}
    for sc in m.surcharges:
        vus[sc.nom] = {"obj": sc, "debut": 0, "fin": n_phases}
    for k, ph in enumerate(m.phases, start=1):
        for sc in ph.ajouter_surcharges:
            vus[sc.nom] = {"obj": sc, "debut": k, "fin": n_phases}
        for nom in ph.retirer_surcharges:
            if nom in vus:
                vus[nom]["fin"] = k - 1
    for nom, d in vus.items():
        if nom.startswith("~terrain:"):
            continue
        sc = d["obj"]
        base = {"nom": nom, "type": sc.type, "q": sc.q, "cote_ecran": sc.cote_ecran, "phase_debut": d["debut"], "phase_fin": d["fin"],
                "distance": getattr(sc, "distance", 0.0), "largeur": getattr(sc, "largeur", None), "cote": getattr(sc, "cote", None)}
        if isinstance(sc, SurchargePlan):
            base.update({"emprise": list(sc.emprise) if sc.emprise else None, "position": list(sc.position) if sc.position else None,
                         "trace": [list(sc.trace[0]), list(sc.trace[1])] if sc.trace else None, "profondeur": sc.profondeur,
                         "cotes_paroi": list(sc.cotes_paroi) if sc.cotes_paroi else None, "niveaux": sc.infos.get("niveaux"), "modele": sc.modele})
        base["profil"] = profil_pour_affichage(sc, z_terrain, m.ecran.pied, coupe)
        objets.append(base)
    return objets


def donnees(ex, p3d: dict | None = None) -> dict:
    res = ex.resultat
    g = geometrie(ex)
    phases = []
    for k, ph in enumerate(res.phases):
        d = {"nom": ph.nom, "ok": ph.ok, "fond": ph.terrain_aval, "terrain": ph.terrain_amont,
             "eau_amont": ph.eau_amont, "eau_aval": ph.eau_aval,
             "appuis": [a["nom"] for a in ph.appuis if a["actif"]] if ph.ok else []}
        if ph.ok:
            zm = 0.5 * (ph.z_diag[0::2] + ph.z_diag[1::2])
            Mm = 0.5 * (ph.M[0::2] + ph.M[1::2])
            d["profil"] = {"z": _l(ph.z), "y_mm": _l(ph.y * 1e3), "zM": _l(zm), "M": _l(Mm),
                           "zu": _l(ph.eau["z"]), "u_amont": _l(ph.eau["u_amont"]), "u_aval": _l(ph.eau["u_aval"])}
            if ph.hydro:
                h = ph.hydro
                d["hydro"] = {
                    "regime": h["regime"], "charge_fond": h.get("charge_fond"), "equipotentielles": h.get("equipotentielles", []),
                    "bouchon": h.get("bouchon"), "gradient_sortie_x": h["gradient_sortie_x"], "gradient_sortie": h["gradient_sortie"],
                    "gradient_sortie_max": h["gradient_sortie_max"], "i_critique": g["i_critique"][k],
                    "h_amont": h["h_amont"], "h_aval": h["h_aval"],
                }
        phases.append(d)
    sortie = {k: v for k, v in g.items() if k not in ("i_critique", "assemblages")}
    return {**sortie, "phases": phases, "p3d": p3d}


def generer_html(ex, p3d: dict | None = None) -> str:
    gabarit = (ICI / "gabarit.html").read_text(encoding="utf-8")
    three = (ICI / "vendor" / "three.min.js").read_text(encoding="utf-8")
    licence = (ICI / "vendor" / "LICENSE-three.txt").read_text(encoding="utf-8")
    d = json.dumps(donnees(ex, p3d), ensure_ascii=False).replace("</", "<\\/")
    titre = f"Maquette K-Retain — {ex.script.projet}".replace("<", "&lt;")
    return (gabarit.replace("__TITRE__", titre)
            .replace("__LICENCE__", licence.replace("*/", "* /"))
            .replace("__THREE__", three)
            .replace("__DONNEES__", d))
