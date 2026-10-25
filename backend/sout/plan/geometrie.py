"""Géométrie du contour de la fouille en plan, partagée par les coupes 2D (sout.script.coupes),
la maquette 3D (sout.maquette3d.generer) et le pseudo-3D (sout.pseudo3d.calcul).

Fonctions pures. Convention : le contour est un polygone [[x, y], ...] fermé implicitement ;
`ni` est la normale unitaire de chaque arête tournée vers l'intérieur de la fouille (quel que
soit le sens de parcours) ; l'abscisse développée s suit les arêtes dans l'ordre du contour,
origine au premier sommet. L'interface (frontend/src/vue3d/geometrie.ts, classe Contour)
utilise la même origine et le même sens.
"""
from __future__ import annotations

import math


def aire_signee(contour: list) -> float:
    n = len(contour)
    return 0.5 * sum(contour[i][0] * contour[(i + 1) % n][1] - contour[(i + 1) % n][0] * contour[i][1] for i in range(n))


def aretes(contour: list) -> list[dict]:
    """Arêtes orientées : {k, A, B, L, t (tangente unitaire), ni (normale intérieure), s0 (abscisse
    développée du sommet A)}."""
    n = len(contour)
    sens = 1.0 if aire_signee(contour) > 0 else -1.0
    out = []
    s0 = 0.0
    for k in range(n):
        A, B = contour[k], contour[(k + 1) % n]
        L = math.dist(A, B)
        t = ((B[0] - A[0]) / L, (B[1] - A[1]) / L) if L > 0 else (1.0, 0.0)
        out.append({"k": k, "A": A, "B": B, "L": L, "t": t, "ni": (-t[1] * sens, t[0] * sens), "s0": s0})
        s0 += L
    return out


def cote_concerne(cotes_paroi, coupe) -> bool:
    """Un objet rattaché à certains côtés de la fouille (`cotes_paroi` : noms du bloc plan.cotes ou
    « #k », numéro d'arête) concerne-t-il la coupe de calcul `coupe` (attributs `cote` et `k`) ?
    Sans restriction (None) ou sans coupe : toujours. Règle unique pour les surcharges, les objets de
    terrain et l'affichage (quatre copies auparavant, dont une qui ignorait la forme « #k »)."""
    if cotes_paroi is None or coupe is None:
        return True
    if getattr(coupe, "cote", None) is not None and coupe.cote in cotes_paroi:
        return True
    return f"#{getattr(coupe, 'k', None)}" in cotes_paroi


def objet_concerne(cotes_paroi, troncon, coupe) -> bool:
    """Généralise `cote_concerne` à un objet limité à un tronçon du côté : `troncon` = (de, a), abscisses
    locales le long du côté (m) ; None = côté entier. Sans coupe : toujours concerné."""
    if not cote_concerne(cotes_paroi, coupe):
        return False
    if troncon is None or coupe is None:
        return True
    s = getattr(coupe, "s", None)
    if s is None:
        return True
    de, a = sorted(troncon)
    return de - 1e-9 <= s <= a + 1e-9


def perimetre(contour: list) -> float:
    return sum(a["L"] for a in aretes(contour))


def point(ars: list[dict], s: float) -> tuple[float, float, int, float]:
    """Point (x, y) à l'abscisse développée s, arête k et abscisse locale sl (s rabattu sur [0, périmètre])."""
    L_tot = sum(a["L"] for a in ars)
    s = min(max(s, 0.0), L_tot)
    for a in ars:
        if s <= a["s0"] + a["L"] + 1e-9 or a["k"] == len(ars) - 1:
            sl = min(max(s - a["s0"], 0.0), a["L"])
            return a["A"][0] + a["t"][0] * sl, a["A"][1] + a["t"][1] * sl, a["k"], sl
    a = ars[-1]
    return a["B"][0], a["B"][1], a["k"], a["L"]


def projeter(ars: list[dict], x: float, y: float) -> tuple[float, int, float, float]:
    """Projection d'un point sur le contour : (s, k, sl, distance)."""
    meilleur = (0.0, 0, 0.0, math.inf)
    for a in ars:
        if a["L"] <= 0:
            continue
        sl = (x - a["A"][0]) * a["t"][0] + (y - a["A"][1]) * a["t"][1]
        sl = min(max(sl, 0.0), a["L"])
        px, py = a["A"][0] + a["t"][0] * sl, a["A"][1] + a["t"][1] * sl
        d = math.hypot(x - px, y - py)
        if d < meilleur[3]:
            meilleur = (a["s0"] + sl, a["k"], sl, d)
    return meilleur


def intersection_rayon(p, d, a, b) -> float | None:
    """Distance t ≥ 0 le long du rayon p + t·d jusqu'au segment [a, b] (ou None)."""
    ex, ey = b[0] - a[0], b[1] - a[1]
    den = d[0] * ey - d[1] * ex
    if abs(den) < 1e-12:
        return None
    wx, wy = a[0] - p[0], a[1] - p[1]
    t = (wx * ey - wy * ex) / den
    u = (wx * d[1] - wy * d[0]) / den
    return t if t > 1e-6 and -1e-9 <= u <= 1 + 1e-9 else None


def vis_a_vis(ars: list[dict], k: int, sl: float) -> tuple[float, int, float, float] | None:
    """Point de la paroi d'en face atteint depuis (arête k, abscisse sl) en traversant la fouille
    perpendiculairement à la paroi : (s_opposé, k_opposé, sl_opposé, distance), ou None."""
    a = ars[k]
    p = (a["A"][0] + a["t"][0] * sl, a["A"][1] + a["t"][1] * sl)
    meilleur = None
    for b in ars:
        if b["k"] == k or b["L"] <= 0:
            continue
        t = intersection_rayon(p, a["ni"], b["A"], b["B"])
        if t is not None and (meilleur is None or t < meilleur[3]):
            q = (p[0] + a["ni"][0] * t, p[1] + a["ni"][1] * t)
            slb = min(max((q[0] - b["A"][0]) * b["t"][0] + (q[1] - b["A"][1]) * b["t"][1], 0.0), b["L"])
            meilleur = (b["s0"] + slb, b["k"], slb, t)
    return meilleur


def placer_appuis(contour: list, appuis: dict) -> list[dict]:
    """Positions en plan par défaut : butons en travers de la fouille depuis le plus long côté,
    tirants vers l'extérieur et bracons vers l'intérieur sur tous les côtés, à l'espacement de
    chaque appui. appuis : {nom: {"type", "espacement", "longueur", "longueur_libre",
    "longueur_scellee", "angle"}}. Renvoie [{"appui", "de": [x, y], "a": [x, y]}]."""
    ars = aretes(contour)
    sorties = []
    for nom, a in appuis.items():
        esp = max(a.get("espacement", 1.0) or 1.0, 0.5)
        if a["type"] == "buton":
            choix = [max(ars, key=lambda e: e["L"])]
        elif a["type"] in ("tirant", "bracon"):
            choix = ars
        else:
            continue
        for ar in choix:
            L = ar["L"]
            if L < 1e-6:
                continue
            t, n_int = ar["t"], ar["ni"]
            A = ar["A"]
            n = int(L // esp)
            for k in range(n):
                s = (k + 0.5) * L / n if n else L / 2
                p = (A[0] + t[0] * s, A[1] + t[1] * s)
                if a["type"] == "buton":
                    ds = [d for e in ars if e["k"] != ar["k"] for d in [intersection_rayon(p, n_int, e["A"], e["B"])] if d is not None]
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
