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
import math
from pathlib import Path

import numpy as np

ICI = Path(__file__).resolve().parent
RECTANGLE_DEFAUT = [[0.0, 0.0], [20.0, 0.0], [20.0, 12.0], [0.0, 12.0]]


def _aire(c: list) -> float:
    return 0.5 * sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(c, c[1:] + c[:1]))


def _intersection(p, d, a, b):
    """Distance t ≥ 0 le long du rayon p + t·d jusqu'au segment [a, b] (ou None)."""
    ex, ey = b[0] - a[0], b[1] - a[1]
    den = d[0] * ey - d[1] * ex
    if abs(den) < 1e-12:
        return None
    wx, wy = a[0] - p[0], a[1] - p[1]
    t = (wx * ey - wy * ex) / den
    u = (wx * d[1] - wy * d[0]) / den
    return t if t > 1e-6 and -1e-9 <= u <= 1 + 1e-9 else None


def placer_appuis(contour: list, appuis: dict) -> list[dict]:
    """Positions en plan par défaut : butons en travers de la fouille depuis le plus
    long côté, tirants vers l'extérieur et bracons vers l'intérieur sur tous les côtés,
    à l'espacement de chaque appui."""
    sens = 1.0 if _aire(contour) > 0 else -1.0
    aretes = list(zip(contour, contour[1:] + contour[:1]))
    sorties = []
    for nom, a in appuis.items():
        esp = max(a.get("espacement", 1.0) or 1.0, 0.5)
        if a["type"] == "buton":
            choix = [max(aretes, key=lambda e: math.dist(*e))]
        elif a["type"] in ("tirant", "bracon"):
            choix = aretes
        else:
            continue
        for A, B in choix:
            L = math.dist(A, B)
            if L < 1e-6:
                continue
            t = ((B[0] - A[0]) / L, (B[1] - A[1]) / L)
            n_int = (-t[1] * sens, t[0] * sens)
            n = int(L // esp)
            for k in range(n):
                s = (k + 0.5) * L / n if n else L / 2
                p = (A[0] + t[0] * s, A[1] + t[1] * s)
                if a["type"] == "buton":
                    ds = [d for e in aretes if e != (A, B) for d in [_intersection(p, n_int, *e)] if d is not None]
                    if not ds:
                        continue
                    q = (p[0] + n_int[0] * min(ds), p[1] + n_int[1] * min(ds))
                elif a["type"] == "tirant":
                    Lt = (a.get("longueur_libre") or 8.0) + (a.get("longueur_scellee") or 6.0)
                    Lh = Lt * math.cos(math.radians(a.get("angle") or 0.0))
                    q = (p[0] - n_int[0] * Lh, p[1] - n_int[1] * Lh)
                else:
                    Lh = (a.get("longueur") or 5.0) * math.cos(math.radians(a.get("angle") or 0.0))
                    q = (p[0] + n_int[0] * Lh, p[1] + n_int[1] * Lh)
                sorties.append({"appui": nom, "de": list(p), "a": list(q)})
    return sorties


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
    plan_appuis = ([ap.model_dump() for ap in s.plan.appuis] if s.plan and s.plan.appuis
                   else placer_appuis(contour, appuis))
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
    return {
        "projet": s.projet, "paroi": paroi, "contour": contour, "plan_defaut": defaut,
        "couches": couches, "z_bas": s.paroi.pied - max(3.0, 0.25 * (s.paroi.tete - s.paroi.pied)),
        "appuis": appuis, "plan_appuis": plan_appuis, "i_critique": i_crit,
        "assemblages": {nom: {"type": a.type, "appui": a.appui} for nom, a in s.assemblages.items()},
        "surcharges": surcharges_maquette(ex),
        "coupe_calcul": s.coupe_calcul.model_dump() if s.coupe_calcul is not None else None,
    }


def surcharges_maquette(ex) -> list[dict]:
    """Surcharges du script avec leur fenêtre de phases et le profil Δσv au droit de la coupe (maquette, panneau)."""
    from ..sol.terrain import CoupeCalcul, SurchargePlan, profil_pour_affichage

    s, m = ex.script, ex.modele
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
    titre = f"Maquette RetainWall — {ex.script.projet}".replace("<", "&lt;")
    return (gabarit.replace("__TITRE__", titre)
            .replace("__LICENCE__", licence.replace("*/", "* /"))
            .replace("__THREE__", three)
            .replace("__DONNEES__", d))
