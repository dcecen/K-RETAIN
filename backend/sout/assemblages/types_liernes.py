"""Assemblages des liernes : console scellée sur la paroi, éclissage de continuité."""
from __future__ import annotations

from ..verifs import Lecteur, resultat
from .base import (lierne_de, Contexte, Param, TypeAssemblage, enregistrer, grille_boulons, p_soudure, v_boulons_cisaillement,
                   v_compression_beton, v_plaque_flexion, v_section, v_soudure)
from .geometrie import Cote, Effort, Schema, Soudure, Vue, boite, boulons, prisme
from .types_butons import lierne

# ----------------------------------------------------------------------------- 7. console de lierne scellée
P_CONSOLE = [Param("l_console", "Portée de la console", "mm", 400, 100, 1200), Param("b_console", "Largeur de la table", "mm", 300, 100, 800),
             Param("t_table", "Épaisseur de la table", "mm", 20, 8, 60), Param("h_console", "Hauteur de la nervure", "mm", 350, 100, 1200),
             Param("t_nervure", "Épaisseur de la nervure", "mm", 15, 6, 40), Param("t_platine", "Épaisseur de la platine scellée", "mm", 20, 8, 60),
             Param("b_platine", "Largeur de la platine", "mm", 400, 100, 1000), Param("h_platine", "Hauteur de la platine", "mm", 500, 100, 1500),
             Param("n_chevilles", "Nombre de chevilles", "", 4, 2, 12, genre="entier"), Param("d_cheville", "Diamètre des chevilles", "mm", 20, choix=[12, 16, 20, 24, 30], genre="choix"),
             Param("N_Rd_cheville", "Résistance de calcul en traction d'une cheville (ETE)", "kN", 0, 0, 500), Param("V_Rd_cheville", "Résistance de calcul en cisaillement (ETE)", "kN", 0, 0, 500),
             Param("entraxe_v", "Entraxe vertical des chevilles", "mm", 350, 80, 1200), Param("entraxe_h", "Entraxe horizontal", "mm", 250, 80, 800), p_soudure(),
             Param("poids_lierne", "Charge verticale sur la console (poids lierne + butons)", "kN", 30, 0, 2000)]


def g_console(p: dict, e: dict, ctx: Contexte) -> Schema:
    s = Schema()
    L = lierne(s, ctx, 900, rep=5)
    h, b = L["h"], L["b"]
    lc, bc, tt, hc, tn = p["l_console"], p["b_console"], p["t_table"], p["h_console"], p["t_nervure"]
    tp, bp, hp = p["t_platine"], p["b_platine"], p["h_platine"]
    z_table = -b / 2 - tt / 2
    s.ajouter(boite(1, "Platine scellée", [-tp / 2, 0, z_table - hc / 2 + tt], [tp, bp, hp], "acier", ["t_platine", "b_platine", "h_platine"]))
    s.ajouter(boite(3, "Table de console", [lc / 2, 0, z_table], [lc, bc, tt], "acier", ["l_console", "b_console", "t_table"]))
    s.ajouter(prisme(4, "Nervure", [[0, z_table - tt / 2], [lc, z_table - tt / 2], [0, z_table - tt / 2 - hc]], "y", 0, tn, "acier", ["h_console", "t_nervure"]))
    ev, eh = p["entraxe_v"], p["entraxe_h"]
    n = int(p["n_chevilles"])
    pos = [[-tp - 60, u, z_table - hc / 2 + tt + v] for v, u in grille_boulons(n, ev, eh)]
    boulons(s, 2, f"Cheville M{int(p['d_cheville'])}", pos, p["d_cheville"], 120 + tp, "x", ["n_chevilles", "d_cheville", "entraxe_v", "entraxe_h"])
    s.soudures += [Soudure([0, 0, z_table - tt / 2], [0, 0, z_table - tt / 2 - hc], p["a_soudure"], "angle", False, [4, 1], "a_soudure"),
                   Soudure([0, -bc / 2, z_table], [0, bc / 2, z_table], p["a_soudure"], "angle", False, [3, 1], "a_soudure")]
    s.cotes += [Cote([0, 0, z_table - tt / 2 - hc - 40], [lc, 0, z_table - tt / 2 - hc - 40], f"l = {lc:.0f}", "elevation", "l_console", 40),
                Cote([lc + 40, 0, z_table - tt / 2 - hc], [lc + 40, 0, z_table + tt / 2], f"h = {hc:.0f}", "elevation", "h_console", 50),
                Cote([-tp - 90, 0, z_table - hc / 2 + tt - ev / 2], [-tp - 90, 0, z_table - hc / 2 + tt + ev / 2], f"ev = {ev:.0f}", "elevation", "entraxe_v", 50),
                Cote([lc + 40, -bp / 2, 0], [lc + 40, bp / 2, 0], f"bp = {bp:.0f}", "dessus", "b_platine", 70)]
    s.efforts.append(Effort([h / 2, 0, b / 2 + 80], [0, 0, -1], p["poids_lierne"], f"R = {p['poids_lierne']:.0f} kN"))
    s.vues = [Vue("Élévation", "xz"), Vue("Coupe A-A", "xz", {"axe": "y", "pos": 0.0}), Vue("Vue de dessus", "xy")]
    s.notes.append("Console chevillée sur la paroi, portant la lierne : les chevilles hautes reprennent la traction due au moment R·l, toutes reprennent le cisaillement R.")
    return s


def v_console(p: dict, e: dict, ctx: Contexte) -> list:
    R = p["poids_lierne"] + abs(e.get("V", 0.0))
    lc, hc, tn = p["l_console"], p["h_console"], p["t_nervure"]
    n = int(p["n_chevilles"])
    out = [v_section("Nervure — section à l'encastrement", "nervure", 0, R, R * lc / 2, tn * hc, tn * hc, tn * hc * hc / 4, ctx, [4]),
           v_soudure("Soudure nervure / platine", 2 * hc, p["a_soudure"], R * (1 + 3 * lc / hc), ctx, [4, 1]),
           v_plaque_flexion("Table — flexion transversale", p["t_table"], lc, (R / (lc * p["b_console"])) * (p["b_console"] / 2) ** 2 / 2, ctx, [3])]
    # chevilles : bras de levier = entraxe vertical, moitié des chevilles tendues
    M = R * lc / 2
    Nt = M / p["entraxe_v"] / max(n / 2, 1)
    V = R / n
    lect = Lecteur(ctx.normes)
    k = lect.v("ec3_assemblages", "chevilles.exposant_interaction")
    NRd, VRd = p["N_Rd_cheville"], p["V_Rd_cheville"]
    if NRd <= 0 or VRd <= 0:
        lect.manquants.append("script : N_Rd_cheville et V_Rd_cheville (ETE de la cheville)")
    taux = None if (lect.manquants or k is None) else (Nt / NRd) ** k + (V / VRd) ** k
    out.append(resultat("Chevilles — traction et cisaillement", "chevilles", None, taux,
                        f"{n} chevilles M{int(p['d_cheville'])} : N = {Nt:.1f} kN (M = R·l/2 = {M / 1000:.1f} kN·m sur {p['entraxe_v']:.0f} mm), V = {V:.1f} kN par cheville",
                        "EN 1992-4 (résistances de l'ETE, interaction)", lect, "structure", reperes=[2]))
    out.append(v_plaque_flexion("Platine scellée — flexion entre chevilles", p["t_platine"], p["b_platine"], Nt / p["entraxe_h"] * (p["entraxe_h"] / 2) / 2, ctx, [1]))
    out.append(v_compression_beton("Paroi — compression sous la platine", R * lc / p["h_platine"] * 2, p["b_platine"] * p["h_platine"] / 2, p["b_platine"] * p["h_platine"], ctx, [0]))
    return out


enregistrer(TypeAssemblage("chaise_lierne", "Lierne – paroi : console scellée (chevilles)", "Liernes",
                           "Console (table + nervure) sur platine chevillée dans la paroi moulée, supportant la lierne.",
                           P_CONSOLE, g_console, v_console, ["V"]))


# ----------------------------------------------------------------------------- 8. éclissage de lierne
P_ECLISSE = [Param("t_eclisse_aile", "Épaisseur des éclisses d'aile", "mm", 15, 6, 40), Param("l_eclisse", "Longueur des éclisses", "mm", 600, 200, 2000),
             Param("t_eclisse_ame", "Épaisseur des éclisses d'âme", "mm", 10, 5, 30), Param("h_eclisse_ame", "Hauteur des éclisses d'âme", "mm", 200, 60, 800),
             Param("n_aile", "Boulons par aile et par côté", "", 4, 2, 16, genre="entier"), Param("n_ame", "Boulons d'âme par côté", "", 3, 1, 12, genre="entier"),
             Param("d_boulon", "Diamètre des boulons", "mm", 20, choix=[12, 16, 20, 24, 27, 30], genre="choix"),
             Param("classe_boulon", "Classe des boulons", "", "8.8", choix=["4.6", "5.6", "8.8", "10.9"], genre="choix"),
             Param("e1", "Pince longitudinale e1", "mm", 40, 20, 150), Param("e2", "Pince transversale e2", "mm", 40, 20, 150), Param("p1", "Entraxe p1", "mm", 70, 30, 300),
             Param("jeu", "Jeu entre tronçons", "mm", 10, 0, 50)]


def g_eclisse(p: dict, e: dict, ctx: Contexte) -> Schema:
    s = Schema()
    L = lierne(s, ctx, 1200)
    h, b, tw, tf = L["h"], L["b"], L["tw"], L["tf"]
    le, ta, tam, ham = p["l_eclisse"], p["t_eclisse_aile"], p["t_eclisse_ame"], p["h_eclisse_ame"]
    for x in (-ta / 2, h + ta / 2):   # éclisses extérieures des deux ailes
        s.ajouter(boite(2, "Éclisse d'aile", [x, 0, 0], [ta, le, b - 20], "acier", ["t_eclisse_aile", "l_eclisse"]))
    for z in (tw / 2 + tam / 2, -tw / 2 - tam / 2):   # éclisses d'âme (dessus et dessous)
        s.ajouter(boite(3, "Éclisse d'âme", [h / 2, 0, z], [ham, le, tam], "acier", ["t_eclisse_ame", "h_eclisse_ame"]))
    na, nm, d = int(p["n_aile"]), int(p["n_ame"]), p["d_boulon"]
    pa = [[tf / 2, sg * (p["e1"] + p["jeu"] / 2 + k * p["p1"]), v] for sg in (-1, 1) for k in range(max(1, na // 2)) for v in (b / 2 - p["e2"], -(b / 2 - p["e2"]))]
    boulons(s, 4, f"Boulon M{int(d)} cl. {p['classe_boulon']}", pa[: 2 * na], d, ta + tf, "x", ["n_aile", "d_boulon", "classe_boulon", "e1", "e2", "p1"])
    pa2 = [[h - tf / 2, q[1], q[2]] for q in pa[: 2 * na]]
    boulons(s, 4, "Boulon", pa2, d, ta + tf, "x", ["n_aile", "d_boulon"])
    pm = [[h / 2 + (k - (nm - 1) / 2) * 0 + (j - (max(1, nm // 2) - 1) / 2) * p["p1"] * 0, sg * (p["e1"] + p["jeu"] / 2 + k * p["p1"]), 0] for sg in (-1, 1) for k in range(nm) for j in (0,)]
    boulons(s, 5, f"Boulon d'âme M{int(d)}", pm, d, tw + 2 * tam, "z", ["n_ame", "d_boulon"])
    s.cotes += [Cote([-ta - 40, -le / 2, 0], [-ta - 40, le / 2, 0], f"L éclisse = {le:.0f}", "dessus", "l_eclisse", 40),
                Cote([h + ta + 40, 0, -b / 2], [h + ta + 40, 0, b / 2], f"b = {b:.0f}", "elevation", None, 40),
                Cote([-ta - 40, p["jeu"] / 2, b / 2 + 20], [-ta - 40, p["jeu"] / 2 + p["e1"], b / 2 + 20], f"e1 = {p['e1']:.0f}", "dessus", "e1", 60),
                Cote([h + ta + 20, 0, -b / 2 - 30], [h + ta + 20, 0, -b / 2 - 30 - 1], f"éclisse d'aile {ta:.0f} mm", "elevation", "t_eclisse_aile", 10)]
    M, V = e.get("M", 0.0), e.get("V", 0.0)
    s.efforts += [Effort([h / 2, -le / 2 - 150, 0], [0, 1, 0], V, f"V = {V:.0f} kN"), Effort([h + ta, le / 2 + 150, 0], [-1, 0, 0], M / (h / 1000) if h else 0, f"M = {M:.0f} kN·m → F aile = {M / (h / 1000) if h else 0:.0f} kN")]
    s.vues = [Vue("Vue de dessus", "xy"), Vue("Élévation (côté fouille)", "yz"), Vue("Coupe A-A", "xz", {"axe": "y", "pos": p["jeu"] / 2 + p["e1"]})]
    s.notes.append("Joint de continuité de lierne : le moment passe par les éclisses d'aile (couple F = M/h), l'effort tranchant par les éclisses d'âme.")
    return s


def v_eclisse(p: dict, e: dict, ctx: Contexte) -> list:
    L = lierne_de(ctx)
    h = L["h_mm"] / 1000
    M, V, N = abs(e.get("M", 0.0)), abs(e.get("V", 0.0)), abs(e.get("N", 0.0))
    F = M / h + N / 2 if h else 0
    na, nm, d, cl = int(p["n_aile"]), int(p["n_ame"]), p["d_boulon"], p["classe_boulon"]
    out = v_boulons_cisaillement("Éclisses d'aile", na, d, cl, F, min(p["t_eclisse_aile"], L["tf_mm"]), p["e1"], p["e2"], p["p1"], ctx, [4, 2])
    An = p["t_eclisse_aile"] * (L["b_mm"] - 20 - 2 * (d + 2))
    out.append(v_section("Éclisse d'aile — section nette", "éclisse", F, 0, 0, An, 0, 0, ctx, [2], "EN 1993-1-1 § 6.2.3 (section nette, A·fy/γM0 — à compléter par 0,9·Anet·fu/γM2)"))
    out += v_boulons_cisaillement("Éclisses d'âme", nm, d, cl, V, min(2 * p["t_eclisse_ame"], L["tw_mm"]), p["e1"], p["e2"], p["p1"], ctx, [5, 3], plans=2)
    out.append(v_section("Éclisses d'âme — cisaillement", "éclisse", 0, V, V * (p["jeu"] + 2 * p["e1"]) / 2, 2 * p["t_eclisse_ame"] * p["h_eclisse_ame"], 2 * p["t_eclisse_ame"] * p["h_eclisse_ame"], 2 * p["t_eclisse_ame"] * p["h_eclisse_ame"] ** 2 / 4, ctx, [3]))
    return out


enregistrer(TypeAssemblage("eclisse_lierne", "Lierne – lierne : éclissage boulonné", "Liernes",
                           "Joint de continuité par éclisses d'ailes et d'âme boulonnées (moment, effort tranchant, effort normal).",
                           P_ECLISSE, g_eclisse, v_eclisse, ["M", "V", "N"]))
