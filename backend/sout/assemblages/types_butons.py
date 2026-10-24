"""Assemblages des butons : platine d'about, liaison boulonnée, chaise, appui biais,
raboutage, boîte de vérinage, buton d'angle, raidisseurs de lierne.

Repère : x vers la paroi, y le long de la lierne, z vertical. La lierne (profilé en I à
âme horizontale, ailes verticales parallèles à la paroi) occupe x ∈ [0, h] ; le buton
arrive depuis x > h. Dimensions en mm, efforts en kN.
"""
from __future__ import annotations

import math

from .base import (lierne_de, TUBE_REPLI, Contexte, Param, TypeAssemblage, enregistrer, grille_boulons, p_boulons, p_soudure, v_ame_lierne,
                   v_boulons_cisaillement, v_boulons_traction, v_plaque_flexion, v_section, v_soudure)
from .geometrie import Cote, Effort, Schema, Soudure, Vue, boite, boulons, prisme, tube


# ----------------------------------------------------------------------------- aides géométriques
def lierne(s: Schema, ctx: Contexte, L: float = 900.0, rep: int = 1, params=()) -> dict:
    """Lierne à âme horizontale entre x = 0 et x = h ; renvoie ses dimensions."""
    p = lierne_de(ctx)
    h, b, tw, tf = p["h_mm"], p["b_mm"], p["tw_mm"], p["tf_mm"]
    s.ajouter(boite(rep, "Lierne " + str(ctx.lierne.get("ref", "") if ctx.lierne else "(profil)"), [tf / 2, 0, 0], [tf, L, b], "acier", params))
    s.ajouter(boite(rep, "Lierne", [h - tf / 2, 0, 0], [tf, L, b], "acier", params, masque=True))
    s.ajouter(boite(rep, "Lierne", [h / 2, 0, 0], [h - 2 * tf, L, tw], "acier", params, masque=True))
    s.ajouter(boite(0, "Paroi", [-150, 0, 0], [300, L, b + 400], "beton", (), masque=True))
    return {"h": h, "b": b, "tw": tw, "tf": tf, "r": p.get("r_mm") or 0.0}


def tube_buton(ctx: Contexte, p: dict) -> tuple[float, float]:
    D = p.get("D_tube") or (ctx.buton or {}).get("D_mm") or ctx.repli("tube du buton (clé buton : référence de la base, ou D_tube)", TUBE_REPLI[0])
    t = p.get("t_tube") or (ctx.buton or {}).get("t_mm") or ctx.repli("épaisseur du tube du buton (clé buton, ou t_tube)", TUBE_REPLI[1])
    return float(D), float(t)


def vues_standard(coupe_y: float = 0.0) -> list[Vue]:
    return [Vue("Élévation", "xz"), Vue("Coupe A-A", "xz", {"axe": "y", "pos": coupe_y}), Vue("Vue de dessus", "xy")]


def effort_buton(s: Schema, x: float, N: float, angle: float = 0.0, texte: str | None = None) -> None:
    a = math.radians(angle)
    s.efforts.append(Effort([x, 0, 0], [-math.cos(a), 0, -math.sin(a)], N, texte or f"N = {N:.0f} kN"))


# ----------------------------------------------------------------------------- 1. platine d'about
P_PLATINE = [
    Param("D_tube", "Diamètre du tube", "mm", 508, 100, 1500), Param("t_tube", "Épaisseur du tube", "mm", 12.5, 4, 40),
    Param("t_platine", "Épaisseur de la platine", "mm", 25, 8, 80), Param("b_platine", "Largeur de la platine (selon y)", "mm", 600, 100, 1500),
    Param("h_platine", "Hauteur de la platine (selon z)", "mm", 300, 100, 1200), p_soudure(),
    Param("n_nervures", "Nombre de nervures", "", 4, 0, 8, genre="entier"), Param("t_nervure", "Épaisseur des nervures", "mm", 12, 6, 30),
    Param("l_nervure", "Longueur des nervures", "mm", 200, 50, 600),
]


def g_platine(p: dict, e: dict, ctx: Contexte) -> Schema:
    s = Schema()
    L = lierne(s, ctx)
    D, t = tube_buton(ctx, p)
    h, tp, bp, hp = L["h"], p["t_platine"], p["b_platine"], p["h_platine"]
    s.ajouter(boite(2, "Platine d'about", [h + tp / 2, 0, 0], [tp, bp, hp], "acier", ["t_platine", "b_platine", "h_platine"]))
    tube(s, 3, f"Buton Ø{D:.0f}×{t:.0f}", [h + tp + 400, 0, 0], D, 800, "x", ["D_tube", "t_tube"])
    s.soudures.append(Soudure([h + tp, 0, D / 2], [h + tp, 0, -D / 2], p["a_soudure"], "angle", True, [2, 3], "a_soudure"))
    n = int(p["n_nervures"])
    for k in range(n):
        ang = 2 * math.pi * k / n + math.pi / n
        u, v = math.cos(ang), math.sin(ang)
        pts = [[0, D / 2], [0, D / 2 + min(p["l_nervure"], min(bp, hp) / 2 - D / 2 - 5)], [p["l_nervure"], D / 2]]
        # prisme dans le plan (x, radial) — représenté comme boîte inclinée simplifiée
        s.ajouter(boite(4, "Nervure", [h + tp + p["l_nervure"] / 2, u * (D / 2 + 40), v * (D / 2 + 40)],
                        [p["l_nervure"], max(p["t_nervure"], 80 * abs(v)), max(p["t_nervure"], 80 * abs(u))], "acier",
                        ["n_nervures", "t_nervure", "l_nervure"]))
        if k == 0:
            s.soudures.append(Soudure([h + tp, u * (D / 2 + 40), v * (D / 2 + 40)], [h + tp + p["l_nervure"], u * (D / 2 + 40), v * (D / 2 + 40)],
                                      p["a_soudure"], "angle", False, [4], "a_soudure"))
    s.cotes += [Cote([h, 0, -hp / 2 - 20], [h + tp, 0, -hp / 2 - 20], f"tp = {tp:.0f}", "elevation", "t_platine", 40),
                Cote([h + tp + 30, 0, -hp / 2], [h + tp + 30, 0, hp / 2], f"hp = {hp:.0f}", "elevation", "h_platine", 60),
                Cote([h + tp + 30, -bp / 2, 0], [h + tp + 30, bp / 2, 0], f"bp = {bp:.0f}", "dessus", "b_platine", 60),
                Cote([h + tp + 800, 0, -D / 2], [h + tp + 800, 0, D / 2], f"Ø{D:.0f} × {t:.0f}", "elevation", "D_tube", 40),
                Cote([0, 0, L["b"] / 2 + 20], [h, 0, L["b"] / 2 + 20], f"lierne h = {h:.0f}", "elevation", None, 40)]
    effort_buton(s, h + tp + 850, e.get("N", 0.0))
    s.vues = vues_standard()
    s.notes.append("Buton en appui simple par platine d'about sur l'aile de la lierne ; nervures de diffusion soudées sur le tube.")
    return s


def v_platine(p: dict, e: dict, ctx: Contexte) -> list:
    N = e.get("N", 0.0)
    D, t = tube_buton(ctx, p)
    bp, hp, tp = p["b_platine"], p["h_platine"], p["t_platine"]
    out = [v_soudure("Soudure tube / platine", math.pi * D, p["a_soudure"], N, ctx, [2, 3], " — cordon périphérique, effort N transmis en totalité (sécuritaire)")]
    q = N / (bp * hp)                          # kN/mm² sous la platine
    c = max((bp - D) / 2, (hp - D) / 2)
    out.append(v_plaque_flexion("Platine d'about — flexion en console", tp, bp, q * c * c / 2, ctx, [2], f"pression q = {q * 1000:.2f} MPa, porte-à-faux c = {c:.0f} mm"))
    L = lierne_de(ctx)
    porte = (L["b_mm"] - L["tw_mm"]) / 2
    out.append(v_plaque_flexion("Aile de lierne — flexion locale", L["tf_mm"], bp, q * porte * porte / 2, ctx, [1], f"aile en console de {porte:.0f} mm de part et d'autre de l'âme"))
    out.append(v_ame_lierne("Âme de lierne sous le buton", N, tp + hp, ctx, [1]))
    if p["n_nervures"] > 0:
        out.append(v_section("Nervures — compression", "nervure", N / 2, 0, 0, p["n_nervures"] * p["t_nervure"] * p["l_nervure"] / 2, 0, 0, ctx, [4],
                             "EN 1993-1-1 § 6.2.4 (part de N reprise par les nervures : 50 %, hypothèse)"))
    return out


enregistrer(TypeAssemblage("platine_about", "Buton – lierne : platine d'about", "Butons",
                           "Appui direct du buton tubulaire sur l'aile de la lierne par une platine d'about soudée, nervurée.",
                           P_PLATINE, g_platine, v_platine, ["N"]))


# ----------------------------------------------------------------------------- 2. platine boulonnée
P_BOULONNE = P_PLATINE[:6] + p_boulons(n=4, d=20) + [Param("angle", "Inclinaison du buton", "°", 0, -30, 30), Param("traction_acc", "Traction accidentelle", "kN", 0, 0, 5000)]


def g_boulonne(p: dict, e: dict, ctx: Contexte) -> Schema:
    s = g_platine({**p, "n_nervures": 0, "t_nervure": 10, "l_nervure": 100}, e, ctx)
    L = lierne_de(ctx)
    h, tp, bp, hp = L["h_mm"], p["t_platine"], p["b_platine"], p["h_platine"]
    pos = [[h - L["tf_mm"] / 2 + (tp + L["tf_mm"]) / 2, u, v] for u, v in grille_boulons(int(p["n_boulons"]), p["p1"], hp - 2 * p["e2"])]
    boulons(s, 5, f"Boulon M{int(p['d_boulon'])} cl. {p['classe_boulon']}", pos, p["d_boulon"], tp + L["tf_mm"], "x", ["n_boulons", "d_boulon", "classe_boulon", "e1", "e2", "p1"])
    s.cotes.append(Cote([h + tp + 20, -p["p1"] / 2, hp / 2 - p["e2"]], [h + tp + 20, p["p1"] / 2, hp / 2 - p["e2"]], f"p1 = {p['p1']:.0f}", "dessus", "p1", 40))
    s.cotes.append(Cote([h + tp + 20, bp / 2 - p["e1"], hp / 2 - p["e2"]], [h + tp + 20, bp / 2, hp / 2 - p["e2"]], f"e1 = {p['e1']:.0f}", "dessus", "e1", 70))
    s.notes = ["Platine boulonnée sur l'aile de la lierne : les boulons reprennent le cisaillement (poids propre, inclinaison) et une traction accidentelle éventuelle."]
    return s


def v_boulonne(p: dict, e: dict, ctx: Contexte) -> list:
    out = v_platine({**p, "n_nervures": 0}, e, ctx)
    N = e.get("N", 0.0)
    V = abs(e.get("V", 0.0)) + abs(N * math.sin(math.radians(p["angle"])))
    L = lierne_de(ctx)
    n, d, cl = int(p["n_boulons"]), p["d_boulon"], p["classe_boulon"]
    out += v_boulons_cisaillement("Liaison boulonnée", n, d, cl, V, min(p["t_platine"], L["tf_mm"]), p["e1"], p["e2"], p["p1"], ctx, [5], Ft=p["traction_acc"])
    if p["traction_acc"] > 0:
        out += v_boulons_traction("Liaison boulonnée", n, d, cl, p["traction_acc"], p["t_platine"], ctx, [5, 2], 1.25)
    return out


enregistrer(TypeAssemblage("buton_lierne_boulonne", "Buton – lierne : platine boulonnée", "Butons",
                           "Platine d'about boulonnée sur l'aile de la lierne : reprise du cisaillement (inclinaison, poids propre) et d'une traction accidentelle.",
                           P_BOULONNE, g_boulonne, v_boulonne, ["N", "V"]))


# ----------------------------------------------------------------------------- 3. chaise d'appui
P_CHAISE = [Param("D_tube", "Diamètre du tube", "mm", 508, 100, 1500), Param("t_tube", "Épaisseur du tube", "mm", 12.5, 4, 40),
            Param("l_table", "Longueur de la table", "mm", 400, 100, 1200), Param("b_table", "Largeur de la table", "mm", 300, 100, 1000),
            Param("t_table", "Épaisseur de la table", "mm", 20, 8, 60), Param("h_nervure", "Hauteur de la nervure", "mm", 300, 80, 1000),
            Param("t_nervure", "Épaisseur de la nervure", "mm", 15, 6, 40), p_soudure(),
            Param("poids_buton", "Réaction verticale (poids propre, inclinaison)", "kN", 15, 0, 2000)]


def g_chaise(p: dict, e: dict, ctx: Contexte) -> Schema:
    s = Schema()
    L = lierne(s, ctx)
    D, t = tube_buton(ctx, p)
    h, lt, bt, tt, hn, tn = L["h"], p["l_table"], p["b_table"], p["t_table"], p["h_nervure"], p["t_nervure"]
    z_table = -D / 2 - tt / 2 - 5
    s.ajouter(boite(2, "Table de la chaise", [h + lt / 2, 0, z_table], [lt, bt, tt], "acier", ["l_table", "b_table", "t_table"]))
    s.ajouter(prisme(3, "Nervure de chaise", [[h, z_table - tt / 2], [h + lt, z_table - tt / 2], [h, z_table - tt / 2 - hn]], "y", 0, tn, "acier", ["h_nervure", "t_nervure"]))
    tube(s, 4, f"Buton Ø{D:.0f}×{t:.0f}", [h + 20 + 400, 0, 0], D, 800, "x", ["D_tube", "t_tube"])
    s.ajouter(boite(5, "Platine d'about", [h + 10, 0, 0], [20, min(600, L["b"] + 200), D + 60], "acier", []))
    s.soudures += [Soudure([h, 0, z_table - tt / 2], [h, 0, z_table - tt / 2 - hn], p["a_soudure"], "angle", False, [3, 1], "a_soudure"),
                   Soudure([h, -bt / 2, z_table], [h, bt / 2, z_table], p["a_soudure"], "angle", False, [2, 1], "a_soudure"),
                   Soudure([h, 0, z_table - tt / 2], [h + lt, 0, z_table - tt / 2], p["a_soudure"], "angle", False, [2, 3], "a_soudure")]
    s.cotes += [Cote([h, 0, z_table - tt / 2 - hn - 30], [h + lt, 0, z_table - tt / 2 - hn - 30], f"l = {lt:.0f}", "elevation", "l_table", 40),
                Cote([h + lt + 30, 0, z_table - tt / 2 - hn], [h + lt + 30, 0, z_table - tt / 2], f"h nervure = {hn:.0f}", "elevation", "h_nervure", 50),
                Cote([h + lt + 30, -bt / 2, z_table], [h + lt + 30, bt / 2, z_table], f"b = {bt:.0f}", "dessus", "b_table", 50)]
    effort_buton(s, h + 850, e.get("N", 0.0))
    s.efforts.append(Effort([h + lt / 2, 0, 60], [0, 0, -1], p["poids_buton"], f"R = {p['poids_buton']:.0f} kN"))
    s.vues = vues_standard()
    s.notes.append("Chaise soudée sur l'aile de la lierne : elle porte le buton pendant le montage et reprend la réaction verticale.")
    return s


def v_chaise(p: dict, e: dict, ctx: Contexte) -> list:
    R = p["poids_buton"] + abs(e.get("V", 0.0))
    lt, tn, hn, tt, bt = p["l_table"], p["t_nervure"], p["h_nervure"], p["t_table"], p["b_table"]
    out = [v_section("Nervure de chaise — section à l'encastrement", "nervure", 0, R, R * lt / 2, tn * hn, tn * hn, tn * hn * hn / 4, ctx, [3])]
    out.append(v_soudure("Soudure nervure / aile de lierne", 2 * hn, p["a_soudure"], R * (1 + 3 * lt / hn), ctx, [3, 1], " — effort équivalent cisaillement + flexion (3·V·l/h)"))
    out.append(v_soudure("Soudure table / aile de lierne", 2 * bt, p["a_soudure"], R, ctx, [2, 1]))
    out.append(v_plaque_flexion("Table — flexion entre nervure et bord", tt, lt, (R / (lt * bt)) * (bt / 2) ** 2 / 2, ctx, [2]))
    out.append(v_ame_lierne("Âme de lierne au droit de la chaise", e.get("N", 0.0), tt + hn, ctx, [1]))
    return out


enregistrer(TypeAssemblage("chaise_buton", "Buton – lierne : chaise d'appui", "Butons",
                           "Console (table + nervure) soudée sous le buton sur l'aile de la lierne ; reprend le poids propre et l'inclinaison.",
                           P_CHAISE, g_chaise, v_chaise, ["N", "V"]))


# ----------------------------------------------------------------------------- 4. appui biais
P_BIAIS = [Param("D_tube", "Diamètre du tube", "mm", 406, 100, 1500), Param("t_tube", "Épaisseur du tube", "mm", 10, 4, 40),
           Param("angle", "Angle du buton sur la normale à la lierne", "°", 45, 10, 70),
           Param("t_de", "Épaisseur du dé de calage (au plus épais)", "mm", 200, 50, 600), Param("b_de", "Largeur du dé", "mm", 500, 100, 1200),
           Param("h_de", "Hauteur du dé", "mm", 450, 100, 1200), Param("t_taquet", "Épaisseur du taquet de butée", "mm", 20, 8, 60),
           Param("h_taquet", "Hauteur du taquet", "mm", 150, 40, 500), p_soudure(defaut=8)]


def g_biais(p: dict, e: dict, ctx: Contexte) -> Schema:
    s = Schema()
    L = lierne(s, ctx, 1200)
    D, t = tube_buton(ctx, p)
    h, a = L["h"], math.radians(p["angle"])
    bd, hd, td = p["b_de"], p["h_de"], p["t_de"]
    # dé de calage : prisme trapézoïdal dans le plan (x, y) extrudé selon z
    s.ajouter(prisme(2, "Dé de calage", [[h, -bd / 2], [h, bd / 2], [h + td, bd / 2 - bd * math.tan(a) * 0 + 0], [h + td - bd * math.tan(a), -bd / 2]][:4],
                     "z", 0, hd, "acier", ["t_de", "b_de", "h_de", "angle"]))
    # taquet de butée côté bas de pente
    s.ajouter(boite(3, "Taquet de butée", [h + 30, bd / 2 + p["t_taquet"] / 2, 0], [60, p["t_taquet"], p["h_taquet"]], "acier", ["t_taquet", "h_taquet"]))
    # buton incliné : représenté par un cylindre d'axe x tourné (approximation : axe x) + platine
    xc, yc = h + td - bd * math.tan(a) / 2 + 400 * math.cos(a), 400 * math.sin(a)
    s.ajouter(boite(4, "Platine d'about", [h + td - bd * math.tan(a) / 2 + 10, 0, 0], [20, D + 80, D + 80], "acier", []))
    tube(s, 5, f"Buton Ø{D:.0f}×{t:.0f}", [xc, yc, 0], D, 800, "x", ["D_tube", "t_tube"])
    s.soudures += [Soudure([h, -bd / 2, hd / 2], [h, bd / 2, hd / 2], p["a_soudure"], "angle", True, [2, 1], "a_soudure"),
                   Soudure([h, bd / 2, -p["h_taquet"] / 2], [h, bd / 2, p["h_taquet"] / 2], p["a_soudure"], "angle", True, [3, 1], "a_soudure")]
    s.cotes += [Cote([h, -bd / 2 - 30, 0], [h + td, -bd / 2 - 30, 0], f"t dé = {td:.0f}", "dessus", "t_de", 40),
                Cote([h + td + 40, -bd / 2, 0], [h + td + 40, bd / 2, 0], f"b = {bd:.0f}", "dessus", "b_de", 60),
                Cote([h + td + 40, 0, -hd / 2], [h + td + 40, 0, hd / 2], f"h = {hd:.0f}", "elevation", "h_de", 60),
                Cote([h + td, 0, hd / 2 + 30], [h + td + 300 * math.cos(a), 300 * math.sin(a), hd / 2 + 30], f"β = {p['angle']:.0f}°", "dessus", "angle", 20)]
    N = e.get("N", 0.0)
    s.efforts.append(Effort([xc + 450 * math.cos(a), yc + 450 * math.sin(a), 0], [-math.cos(a), -math.sin(a), 0], N, f"N = {N:.0f} kN"))
    s.vues = [Vue("Vue de dessus", "xy"), Vue("Élévation", "xz"), Vue("Coupe A-A", "xz", {"axe": "y", "pos": 0.0})]
    s.notes.append("Buton d'angle : le dé biais ramène l'appui perpendiculaire à la lierne ; le taquet reprend la composante tangentielle N·sin β.")
    return s


def v_biais(p: dict, e: dict, ctx: Contexte) -> list:
    N = e.get("N", 0.0)
    a = math.radians(p["angle"])
    Nn, Nt = N * math.cos(a), N * math.sin(a)
    bd, hd = p["b_de"], p["h_de"]
    out = [v_soudure("Soudure dé / lierne (composante tangentielle)", 2 * (bd + hd), p["a_soudure"], Nt, ctx, [2, 1]),
           v_section("Taquet de butée — cisaillement", "taquet", 0, Nt, Nt * 30, p["t_taquet"] * p["h_taquet"], p["t_taquet"] * p["h_taquet"], p["t_taquet"] * p["h_taquet"] ** 2 / 4, ctx, [3]),
           v_soudure("Soudure taquet / lierne", 2 * p["h_taquet"], p["a_soudure"], Nt, ctx, [3, 1])]
    q = Nn / (bd * hd)
    L = lierne_de(ctx)
    porte = (L["b_mm"] - L["tw_mm"]) / 2
    out.append(v_plaque_flexion("Aile de lierne — flexion locale sous le dé", L["tf_mm"], bd, q * porte * porte / 2, ctx, [1], f"pression {q * 1000:.2f} MPa"))
    out.append(v_ame_lierne("Âme de lierne sous le dé", Nn, hd, ctx, [1]))
    return out


enregistrer(TypeAssemblage("appui_biais", "Buton d'angle – lierne : appui biais (dé de calage)", "Butons",
                           "Buton incliné en plan sur la lierne : dé de calage biais soudé, taquet de butée pour la composante tangentielle.",
                           P_BIAIS, g_biais, v_biais, ["N"]))


# ----------------------------------------------------------------------------- 5. raboutage
P_RABOUTAGE = [Param("D_tube", "Diamètre du tube", "mm", 508, 100, 1500), Param("t_tube", "Épaisseur du tube", "mm", 12.5, 4, 40),
               Param("t_platine", "Épaisseur des platines", "mm", 25, 8, 80), Param("D_platine", "Diamètre des platines", "mm", 680, 100, 2000),
               Param("n_boulons", "Nombre de boulons sur le cercle", "", 8, 4, 36, genre="entier"), Param("d_boulon", "Diamètre des boulons", "mm", 24, choix=[12, 16, 20, 24, 27, 30, 36], genre="choix"),
               Param("classe_boulon", "Classe des boulons", "", "8.8", choix=["4.6", "5.6", "8.8", "10.9"], genre="choix"),
               Param("D_cercle", "Diamètre du cercle de boulons", "mm", 600, 100, 1900), p_soudure(), Param("traction", "Traction de calcul (température, levage)", "kN", 0, 0, 5000)]


def g_raboutage(p: dict, e: dict, ctx: Contexte) -> Schema:
    s = Schema()
    D, t = tube_buton(ctx, p)
    tp, Dp, Dc = p["t_platine"], p["D_platine"], p["D_cercle"]
    tube(s, 1, f"Buton Ø{D:.0f}×{t:.0f}", [-tp - 400, 0, 0], D, 800, "x", ["D_tube", "t_tube"])
    tube(s, 1, "Buton", [tp + 400, 0, 0], D, 800, "x", ["D_tube", "t_tube"], masque=True)
    s.ajouter(boite(2, "Platine d'about", [-tp / 2, 0, 0], [tp, Dp, Dp], "acier", ["t_platine", "D_platine"]))
    s.ajouter(boite(2, "Platine d'about", [tp / 2, 0, 0], [tp, Dp, Dp], "acier", ["t_platine", "D_platine"]))
    n = int(p["n_boulons"])
    pos = [[0, Dc / 2 * math.cos(2 * math.pi * k / n), Dc / 2 * math.sin(2 * math.pi * k / n)] for k in range(n)]
    boulons(s, 3, f"Boulon M{int(p['d_boulon'])} cl. {p['classe_boulon']}", pos, p["d_boulon"], 2 * tp, "x", ["n_boulons", "d_boulon", "classe_boulon", "D_cercle"])
    s.soudures += [Soudure([-tp, 0, D / 2], [-tp, 0, -D / 2], p["a_soudure"], "angle", True, [1, 2], "a_soudure"),
                   Soudure([tp, 0, D / 2], [tp, 0, -D / 2], p["a_soudure"], "angle", True, [1, 2], "a_soudure")]
    s.cotes += [Cote([-tp, 0, -Dp / 2 - 30], [tp, 0, -Dp / 2 - 30], f"2 × {tp:.0f}", "elevation", "t_platine", 40),
                Cote([tp + 40, 0, -Dp / 2], [tp + 40, 0, Dp / 2], f"Ø platine {Dp:.0f}", "elevation", "D_platine", 50),
                Cote([tp + 40, 0, -Dc / 2], [tp + 40, 0, Dc / 2], f"Ø cercle {Dc:.0f}", "coupe", "D_cercle", 90)]
    N = e.get("N", 0.0)
    s.efforts += [Effort([-tp - 850, 0, 0], [1, 0, 0], N, f"N = {N:.0f} kN"), Effort([tp + 850, 0, 0], [-1, 0, 0], N, "")]
    s.vues = [Vue("Élévation", "xz"), Vue("Coupe A-A (joint)", "yz", {"axe": "x", "pos": 0.0}), Vue("Vue de dessus", "xy")]
    s.notes.append("Raboutage de tronçons modulaires : platines d'about boulonnées sur un cercle ; en compression, l'effort passe par contact.")
    return s


def v_raboutage(p: dict, e: dict, ctx: Contexte) -> list:
    N, T = e.get("N", 0.0), p["traction"]
    D, t = tube_buton(ctx, p)
    out = [v_soudure("Soudure tube / platine", math.pi * D, p["a_soudure"], max(N, T), ctx, [1, 2])]
    from ..verifs import Lecteur, resultat
    lect = Lecteur(ctx.normes)
    gM0 = lect.v("ec3_assemblages", "gamma_M0")
    A = math.pi * (D * D - (D - 2 * t) ** 2) / 4
    sigma = N / A * 1000
    out.append(resultat("Contact des platines — compression", "platine", None, None if gM0 is None else sigma / (ctx.fy / gM0),
                        f"σ = N/A_tube = {sigma:.0f} MPa", "contact direct, limite fy/γM0", lect, "structure", reperes=[2]))
    if T > 0:
        out += v_boulons_traction("Raboutage", int(p["n_boulons"]), p["d_boulon"], p["classe_boulon"], T, p["t_platine"], ctx, [3, 2], 1.3)
        c = (p["D_cercle"] - D) / 2
        out.append(v_plaque_flexion("Platine en traction — flexion entre tube et boulons", p["t_platine"], math.pi * D, T / (math.pi * D) * c, ctx, [2]))
    return out


enregistrer(TypeAssemblage("raboutage_buton", "Raboutage de buton (platines boulonnées)", "Butons",
                           "Jonction de deux tronçons tubulaires par platines d'about boulonnées sur un cercle de boulons.",
                           P_RABOUTAGE, g_raboutage, v_raboutage, ["N"]))


# ----------------------------------------------------------------------------- 6. boîte de vérinage
P_VERIN = [Param("D_tube", "Diamètre du tube", "mm", 508, 100, 1500), Param("t_tube", "Épaisseur du tube", "mm", 12.5, 4, 40),
           Param("t_platine", "Épaisseur des platines", "mm", 30, 10, 80), Param("b_boite", "Largeur de la boîte", "mm", 700, 200, 1500),
           Param("h_boite", "Hauteur de la boîte", "mm", 700, 200, 1500), Param("course", "Course / écartement des platines", "mm", 250, 50, 600),
           Param("n_cales", "Nombre de cales", "", 2, 1, 8, genre="entier"), Param("b_cale", "Largeur des cales", "mm", 150, 40, 500),
           Param("t_cale", "Épaisseur des cales", "mm", 40, 10, 150), Param("t_gousset", "Épaisseur des goussets", "mm", 15, 6, 40), p_soudure()]


def g_verin(p: dict, e: dict, ctx: Contexte) -> Schema:
    s = Schema()
    D, t = tube_buton(ctx, p)
    tp, bb, hb, c = p["t_platine"], p["b_boite"], p["h_boite"], p["course"]
    tube(s, 1, f"Buton Ø{D:.0f}×{t:.0f}", [-c / 2 - tp - 400, 0, 0], D, 800, "x", ["D_tube", "t_tube"])
    tube(s, 1, "Buton", [c / 2 + tp + 400, 0, 0], D, 800, "x", [], masque=True)
    s.ajouter(boite(2, "Platine de la boîte", [-c / 2 - tp / 2, 0, 0], [tp, bb, hb], "acier", ["t_platine", "b_boite", "h_boite"]))
    s.ajouter(boite(2, "Platine de la boîte", [c / 2 + tp / 2, 0, 0], [tp, bb, hb], "acier", ["t_platine", "b_boite", "h_boite"]))
    n = int(p["n_cales"])
    for k in range(n):
        y = (k - (n - 1) / 2) * (bb / (n + 1))
        s.ajouter(boite(3, "Cale de blocage", [0, y, 0], [c, p["b_cale"], p["t_cale"]], "acier", ["n_cales", "b_cale", "t_cale", "course"]))
    s.ajouter(boite(4, "Vérin", [0, 0, -hb / 4], [c, 200, 200], "boulon", ["course"]))
    for sg in (-1, 1):
        s.ajouter(prisme(5, "Gousset", [[-c / 2 - tp, sg * bb / 2], [-c / 2 - tp - 200, sg * (bb / 2 - 0)], [-c / 2 - tp, sg * (bb / 2 - 200)]], "z", 0, p["t_gousset"], "acier", ["t_gousset"]))
        s.ajouter(prisme(5, "Gousset", [[c / 2 + tp, sg * bb / 2], [c / 2 + tp + 200, sg * bb / 2], [c / 2 + tp, sg * (bb / 2 - 200)]], "z", 0, p["t_gousset"], "acier", ["t_gousset"]))
    s.soudures += [Soudure([-c / 2 - tp, 0, D / 2], [-c / 2 - tp, 0, -D / 2], p["a_soudure"], "angle", True, [1, 2], "a_soudure"),
                   Soudure([c / 2 + tp, 0, D / 2], [c / 2 + tp, 0, -D / 2], p["a_soudure"], "angle", True, [1, 2], "a_soudure")]
    s.cotes += [Cote([-c / 2, 0, -hb / 2 - 30], [c / 2, 0, -hb / 2 - 30], f"course = {c:.0f}", "elevation", "course", 40),
                Cote([c / 2 + tp + 40, 0, -hb / 2], [c / 2 + tp + 40, 0, hb / 2], f"h = {hb:.0f}", "elevation", "h_boite", 50),
                Cote([c / 2 + tp + 40, -bb / 2, 0], [c / 2 + tp + 40, bb / 2, 0], f"b = {bb:.0f}", "dessus", "b_boite", 50)]
    N = e.get("N", 0.0)
    s.efforts += [Effort([-c / 2 - tp - 850, 0, 0], [1, 0, 0], N, f"N = {N:.0f} kN"), Effort([c / 2 + tp + 850, 0, 0], [-1, 0, 0], N, "")]
    s.vues = [Vue("Élévation", "xz"), Vue("Vue de dessus", "xy"), Vue("Coupe A-A", "yz", {"axe": "x", "pos": 0.0})]
    s.notes.append("Boîte de vérinage : le vérin met en précharge, les cales reprennent l'effort en service ; goussets de raidissement des platines.")
    return s


def v_verin(p: dict, e: dict, ctx: Contexte) -> list:
    N = e.get("N", 0.0)
    D, _ = tube_buton(ctx, p)
    n = int(p["n_cales"])
    A = n * p["b_cale"] * p["t_cale"]
    out = [v_section("Cales — compression (effort en service)", "cale", N, 0, 0, A, 0, 0, ctx, [3], "EN 1993-1-1 § 6.2.4 (cales courtes, sans flambement)")]
    out.append(v_plaque_flexion("Platine — flexion entre cales", p["t_platine"], p["h_boite"], (N / (p["b_boite"] * p["h_boite"])) * (p["b_boite"] / (n + 1)) ** 2 / 8, ctx, [2]))
    out.append(v_soudure("Soudure tube / platine", math.pi * D, p["a_soudure"], N, ctx, [1, 2]))
    out.append(v_soudure("Soudures des goussets", 4 * 2 * 200, p["a_soudure"], 0.3 * N, ctx, [5, 2], " — 30 % de N par les goussets (hypothèse)"))
    return out


enregistrer(TypeAssemblage("boite_verin", "Buton : boîte de vérinage et cales de précharge", "Butons",
                           "Boîte à deux platines entre tronçons de buton : vérin de mise en précharge, cales de blocage, goussets.",
                           P_VERIN, g_verin, v_verin, ["N"]))


# ----------------------------------------------------------------------------- 13. buton d'angle (coin de fouille)
P_ANGLE = [Param("D_tube", "Diamètre du tube", "mm", 406, 100, 1500), Param("t_tube", "Épaisseur du tube", "mm", 10, 4, 40),
           Param("angle", "Angle du buton sur la lierne", "°", 45, 20, 70), Param("t_gousset", "Épaisseur du gousset d'angle", "mm", 20, 8, 60),
           Param("l_gousset", "Longueur du gousset sur chaque lierne", "mm", 600, 200, 2000), Param("h_gousset", "Hauteur du gousset", "mm", 300, 100, 1000),
           Param("t_platine", "Épaisseur de la platine d'about", "mm", 25, 8, 80), p_soudure(defaut=8)]


def g_angle(p: dict, e: dict, ctx: Contexte) -> Schema:
    s = Schema()
    L = lierne(s, ctx, 1400)
    h, lg, hg, tg = L["h"], p["l_gousset"], p["h_gousset"], p["t_gousset"]
    # seconde lierne perpendiculaire (coin) : le long de x à y = 700
    s.ajouter(boite(1, "Lierne (retour d'angle)", [700, 700 - L["tf"] / 2, 0], [1400, L["tf"], L["b"]], "acier", (), masque=True))
    s.ajouter(boite(1, "Lierne", [700, 700 - h + L["tf"] / 2, 0], [1400, L["tf"], L["b"]], "acier", (), masque=True))
    a = math.radians(p["angle"])
    # gousset d'angle : plaque horizontale triangulaire entre les deux liernes, deux exemplaires (haut et bas)
    for z in (hg / 2, -hg / 2):
        s.ajouter(prisme(2, "Gousset d'angle", [[h, 700 - h], [h, 700 - h - lg], [h + lg, 700 - h]], "z", z, tg, "acier", ["t_gousset", "l_gousset", "h_gousset"]))
    D, t = tube_buton(ctx, p)
    xc, yc = h + lg * 0.5 + 300 * math.cos(a), 700 - h - lg * 0.5 - 300 * math.sin(a)
    s.ajouter(boite(3, "Platine d'about", [h + lg * 0.5, 700 - h - lg * 0.5, 0], [p["t_platine"], D + 100, D + 100], "acier", ["t_platine"]))
    tube(s, 4, f"Buton d'angle Ø{D:.0f}×{t:.0f}", [xc + 400 * math.cos(a), yc - 400 * math.sin(a), 0], D, 800, "x", ["D_tube", "t_tube"])
    s.soudures += [Soudure([h, 700 - h, hg / 2], [h, 700 - h - lg, hg / 2], p["a_soudure"], "angle", False, [2, 1], "a_soudure"),
                   Soudure([h, 700 - h, hg / 2], [h + lg, 700 - h, hg / 2], p["a_soudure"], "angle", False, [2, 1], "a_soudure")]
    s.cotes += [Cote([h, 700 - h - lg - 40, 0], [h + lg, 700 - h - lg - 40, 0], f"l = {lg:.0f}", "dessus", "l_gousset", 40),
                Cote([h + lg + 60, 0, -hg / 2], [h + lg + 60, 0, hg / 2], f"h = {hg:.0f}", "elevation", "h_gousset", 50)]
    N = e.get("N", 0.0)
    s.efforts.append(Effort([xc + 850 * math.cos(a), yc - 850 * math.sin(a), 0], [-math.cos(a), math.sin(a), 0], N, f"N = {N:.0f} kN"))
    s.vues = [Vue("Vue de dessus", "xy"), Vue("Élévation", "xz"), Vue("Coupe A-A", "xz", {"axe": "y", "pos": 700 - h - lg * 0.5})]
    s.notes.append("Coin de fouille : le buton d'angle s'appuie sur des goussets horizontaux soudés sur les deux liernes ; chaque lierne reçoit N·cos β.")
    return s


def v_angle(p: dict, e: dict, ctx: Contexte) -> list:
    N = e.get("N", 0.0)
    a = math.radians(p["angle"])
    F = N * math.cos(a)   # composante sur chaque lierne
    tg, lg, hg = p["t_gousset"], p["l_gousset"], p["h_gousset"]
    out = [v_soudure("Soudures gousset / lierne (par lierne, 2 goussets)", 2 * lg, p["a_soudure"], F, ctx, [2, 1]),
           v_section("Gousset d'angle — cisaillement et flexion", "gousset", N, F, F * lg / 4, 2 * tg * lg * 0.7, 2 * tg * lg * 0.7, 2 * tg * (0.7 * lg) ** 2 / 4, ctx, [2],
                     "EN 1993-1-1 § 6.2 (section efficace 70 % de la longueur, hypothèse)")]
    L = lierne_de(ctx)
    q = F / (lg * hg)
    out.append(v_plaque_flexion("Aile de lierne — flexion locale sous le gousset", L["tf_mm"], lg, q * ((L["b_mm"] - L["tw_mm"]) / 2) ** 2 / 2, ctx, [1]))
    out.append(v_ame_lierne("Âme de lierne au droit du gousset", F, lg, ctx, [1]))
    return out


enregistrer(TypeAssemblage("buton_angle", "Buton d'angle en coin de fouille (goussets)", "Butons",
                           "Buton d'angle appuyé sur des goussets horizontaux soudés sur les deux liernes du coin.",
                           P_ANGLE, g_angle, v_angle, ["N"]))


# ----------------------------------------------------------------------------- 14. raidisseurs de lierne
P_RAID = [Param("D_tube", "Diamètre du tube", "mm", 508, 100, 1500), Param("t_tube", "Épaisseur du tube", "mm", 12.5, 4, 40),
          Param("t_raidisseur", "Épaisseur des raidisseurs", "mm", 15, 6, 40), Param("n_raidisseurs", "Nombre de raidisseurs (paires)", "", 2, 1, 4, genre="entier"),
          Param("espacement", "Espacement des raidisseurs", "mm", 300, 100, 1000), Param("t_platine", "Épaisseur de la platine du buton", "mm", 25, 8, 80), p_soudure()]


def g_raid(p: dict, e: dict, ctx: Contexte) -> Schema:
    s = Schema()
    L = lierne(s, ctx)
    h, b, tw, tf = L["h"], L["b"], L["tw"], L["tf"]
    D, t = tube_buton(ctx, p)
    n, esp, tr = int(p["n_raidisseurs"]), p["espacement"], p["t_raidisseur"]
    for k in range(n):
        y = (k - (n - 1) / 2) * esp
        for sg in (1, -1):   # au-dessus et au-dessous de l'âme horizontale
            s.ajouter(boite(2, "Raidisseur d'âme", [h / 2, y, sg * (tw / 2 + (b - tw) / 4)], [h - 2 * tf, tr, (b - tw) / 2], "acier", ["t_raidisseur", "n_raidisseurs", "espacement"]))
    s.ajouter(boite(3, "Platine du buton", [h + p["t_platine"] / 2, 0, 0], [p["t_platine"], max(D + 100, (n - 1) * esp + 200), D + 60], "acier", ["t_platine"]))
    tube(s, 4, f"Buton Ø{D:.0f}×{t:.0f}", [h + p["t_platine"] + 400, 0, 0], D, 800, "x", ["D_tube", "t_tube"])
    s.soudures += [Soudure([tf, -esp * (n - 1) / 2, b / 2], [h - tf, -esp * (n - 1) / 2, b / 2], p["a_soudure"], "angle", False, [2, 1], "a_soudure"),
                   Soudure([h, 0, D / 2], [h, 0, -D / 2], p["a_soudure"], "angle", True, [3, 4], "a_soudure")]
    s.cotes += [Cote([h + p["t_platine"] + 40, -esp * (n - 1) / 2, b / 2 + 20], [h + p["t_platine"] + 40, esp * (n - 1) / 2 if n > 1 else esp / 2, b / 2 + 20], f"e = {esp:.0f}", "dessus", "espacement", 40),
                Cote([tf, 0, -b / 2 - 30], [h - tf, 0, -b / 2 - 30], f"raidisseur {h - 2 * tf:.0f} × {tr:.0f}", "coupe", "t_raidisseur", 40)]
    effort_buton(s, h + p["t_platine"] + 850, e.get("N", 0.0))
    s.vues = [Vue("Élévation", "xz"), Vue("Coupe A-A", "xz", {"axe": "y", "pos": 0.0}), Vue("Vue de dessus", "xy")]
    s.notes.append("Raidisseurs transversaux d'âme au droit du buton : ils évitent l'écrasement de l'âme et la flexion locale de l'aile.")
    return s


def v_raid(p: dict, e: dict, ctx: Contexte) -> list:
    N = e.get("N", 0.0)
    L = lierne_de(ctx)
    n, tr = int(p["n_raidisseurs"]), p["t_raidisseur"]
    A_raid = 2 * n * tr * (L["b_mm"] - L["tw_mm"]) / 2
    A_ame = L["tw_mm"] * (p["t_platine"] + 2 * (L["tf_mm"] + (L.get("r_mm") or 0)) + 2 * n * 15 * L["tw_mm"] / 10)
    out = [v_section("Raidisseurs + âme — compression", "raidisseur", N, 0, 0, A_raid + A_ame, 0, 0, ctx, [2, 1],
                     "EN 1993-1-5 § 9 (section efficace raidisseurs + 15·ε·tw d'âme de part et d'autre, simplifié)")]
    out.append(v_soudure("Soudures raidisseurs / ailes et âme", 2 * n * 2 * (L["h_mm"] - 2 * L["tf_mm"] + (L["b_mm"] - L["tw_mm"])), p["a_soudure"], N, ctx, [2, 1]))
    out.append(v_ame_lierne("Âme de lierne sans raidisseur (pour mémoire)", N, p["t_platine"], ctx, [1]))
    return out


enregistrer(TypeAssemblage("raidisseurs_lierne", "Raidisseurs d'âme de lierne au droit du buton", "Butons",
                           "Raidisseurs transversaux soudés dans la lierne sous la platine du buton (écrasement et voilement de l'âme).",
                           P_RAID, g_raid, v_raid, ["N"]))
