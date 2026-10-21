"""Assemblages des tirants et des bracons : têtes de tirant sur lierne et sur paroi,
liaison en tête de bracon (axe), appui de bracon en pied."""
from __future__ import annotations

import math

from ..verifs import Lecteur, resultat
from .base import (Contexte, Param, TypeAssemblage, enregistrer, grille_boulons, p_soudure, v_ame_lierne, v_boulons_cisaillement,
                   v_compression_beton, v_plaque_flexion, v_section, v_soudure)
from . import ec3_assemblages as ec3
from .geometrie import Cote, Effort, Schema, Soudure, Vue, boite, boulons, cylindre, prisme, tube
from .types_butons import lierne

# ----------------------------------------------------------------------------- 9. tête de tirant sur lierne
P_TETE_L = [Param("angle", "Inclinaison du tirant", "°", 20, 0, 45), Param("t_plaque", "Épaisseur de la plaque d'appui", "mm", 40, 10, 120),
            Param("b_plaque", "Largeur de la plaque", "mm", 300, 100, 800), Param("h_plaque", "Hauteur de la plaque", "mm", 300, 100, 800),
            Param("d_tete", "Diamètre de la tête d'ancrage", "mm", 120, 40, 400), Param("d_trou", "Diamètre du trou de passage", "mm", 80, 20, 300),
            Param("t_cale", "Épaisseur de la cale biaise (au plus épais)", "mm", 120, 20, 500), p_soudure(defaut=8),
            Param("b_lierne_eff", "Largeur d'appui diffusée sur la lierne", "mm", 400, 100, 1500)]


def g_tete_lierne(p: dict, e: dict, ctx: Contexte) -> Schema:
    s = Schema()
    L = lierne(s, ctx)
    h, b = L["h"], L["b"]
    a = math.radians(p["angle"])
    tc, tp, bp, hp = p["t_cale"], p["t_plaque"], p["b_plaque"], p["h_plaque"]
    # cale biaise : prisme dans le plan (x, z) extrudé selon y
    s.ajouter(prisme(2, "Cale biaise", [[h, hp / 2], [h, -hp / 2], [h + tc, -hp / 2], [h + tc - hp * math.tan(a), hp / 2]], "y", 0, bp, "acier", ["t_cale", "angle", "b_plaque", "h_plaque"]))
    # plaque d'appui perpendiculaire au tirant, représentée par une boîte inclinée approchée (épaisseur selon x)
    xc = h + tc - hp * math.tan(a) / 2 + tp / 2
    s.ajouter(boite(3, "Plaque d'appui", [xc, 0, 0], [tp, bp, hp], "acier", ["t_plaque", "b_plaque", "h_plaque"]))
    s.ajouter(cylindre(4, "Tête d'ancrage", [xc + tp / 2 + 40, 0, 0], p["d_tete"], 80, "x", "boulon", ["d_tete"]))
    tube(s, 5, "Tirant (gaine)", [xc + tp / 2 + 80 + 350, 0, -350 * math.tan(a)], p["d_trou"] * 0.8, 700, "x", ["d_trou", "angle"])
    s.soudures.append(Soudure([h, 0, hp / 2], [h, 0, -hp / 2], p["a_soudure"], "angle", True, [2, 1], "a_soudure"))
    s.cotes += [Cote([h, 0, -hp / 2 - 30], [h + tc, 0, -hp / 2 - 30], f"cale {tc:.0f}", "elevation", "t_cale", 40),
                Cote([xc + tp / 2 + 120, 0, -hp / 2], [xc + tp / 2 + 120, 0, hp / 2], f"hp = {hp:.0f}", "elevation", "h_plaque", 60),
                Cote([xc + tp / 2 + 120, -bp / 2, 0], [xc + tp / 2 + 120, bp / 2, 0], f"bp = {bp:.0f}", "dessus", "b_plaque", 60),
                Cote([xc, 0, hp / 2 + 30], [xc + 300 * math.cos(a), 0, hp / 2 + 30 - 300 * math.sin(a)], f"α = {p['angle']:.0f}°", "elevation", "angle", 20)]
    T = e.get("T", e.get("N", 0.0))
    s.efforts.append(Effort([xc + tp / 2 + 80 + 750, 0, -750 * math.tan(a)], [-math.cos(a), 0, math.sin(a)], T, f"T = {T:.0f} kN"))
    s.vues = [Vue("Élévation", "xz"), Vue("Coupe A-A", "xz", {"axe": "y", "pos": 0.0}), Vue("Vue de dessus", "xy")]
    s.notes.append("Tête de tirant sur lierne : la cale biaise ramène l'appui normal à la lierne ; la plaque d'appui diffuse l'effort de la tête d'ancrage.")
    return s


def v_tete_lierne(p: dict, e: dict, ctx: Contexte) -> list:
    T = e.get("T", e.get("N", 0.0))
    a = math.radians(p["angle"])
    bp, hp, tp = p["b_plaque"], p["h_plaque"], p["t_plaque"]
    q = T / (bp * hp - math.pi * p["d_trou"] ** 2 / 4)
    c = min(bp, hp) / 2 - p["d_tete"] / 2
    out = [v_plaque_flexion("Plaque d'appui — flexion autour de la tête", tp, bp, q * c * c / 2, ctx, [3], f"porte-à-faux {c:.0f} mm, pression {q * 1000:.2f} MPa")]
    out.append(v_soudure("Soudure cale / lierne (composante tangentielle T·sin α)", 2 * (bp + hp), p["a_soudure"], T * math.sin(a), ctx, [2, 1]))
    Tn = T * math.cos(a)
    L = ctx.lierne or {"b_mm": 300, "tf_mm": 19, "tw_mm": 11}
    qa = Tn / (p["b_lierne_eff"] * hp)
    out.append(v_plaque_flexion("Aile de lierne — flexion locale", L["tf_mm"], p["b_lierne_eff"], qa * ((L["b_mm"] - L["tw_mm"]) / 2) ** 2 / 2, ctx, [1]))
    out.append(v_ame_lierne("Âme de lierne sous la tête", Tn, p["b_lierne_eff"], ctx, [1]))
    return out


enregistrer(TypeAssemblage("tete_tirant_lierne", "Tête de tirant sur lierne (plaque + cale biaise)", "Tirants",
                           "Plaque d'appui de la tête d'ancrage et cale biaise soudée sur la lierne, pour un tirant incliné.",
                           P_TETE_L, g_tete_lierne, v_tete_lierne, ["T"]))


# ----------------------------------------------------------------------------- 10. tête de tirant sur paroi moulée
P_TETE_P = [Param("angle", "Inclinaison du tirant", "°", 20, 0, 45), Param("t_plaque", "Épaisseur de la plaque d'appui", "mm", 40, 10, 120),
            Param("b_plaque", "Largeur de la plaque", "mm", 400, 100, 1000), Param("h_plaque", "Hauteur de la plaque", "mm", 400, 100, 1000),
            Param("d_tete", "Diamètre de la tête d'ancrage", "mm", 120, 40, 400), Param("d_trou", "Diamètre de la réservation", "mm", 150, 40, 400),
            Param("prof_reservation", "Profondeur de la réservation biaise", "mm", 250, 0, 800), Param("diffusion", "Largeur de diffusion dans le béton", "mm", 800, 100, 2000)]


def g_tete_paroi(p: dict, e: dict, ctx: Contexte) -> Schema:
    s = Schema()
    a = math.radians(p["angle"])
    tp, bp, hp = p["t_plaque"], p["b_plaque"], p["h_plaque"]
    s.ajouter(boite(1, "Paroi moulée", [-400, 0, 0], [800, 1200, 1400], "beton", ()))
    pr = p["prof_reservation"]
    # réservation biaise : prisme retiré, représenté par un prisme « sol » (vide)
    s.ajouter(prisme(2, "Réservation (coffrage biais)", [[0, hp / 2 + 20], [0, -hp / 2 - 20], [-pr, -hp / 2 - 20], [-pr + (hp + 40) * math.tan(a), hp / 2 + 20]], "y", 0, bp + 40, "sol", ["prof_reservation", "angle"]))
    xc = -pr + (hp + 40) * math.tan(a) / 2 + tp / 2
    s.ajouter(boite(3, "Plaque d'appui", [xc, 0, 0], [tp, bp, hp], "acier", ["t_plaque", "b_plaque", "h_plaque"]))
    s.ajouter(cylindre(4, "Tête d'ancrage", [xc + tp / 2 + 40, 0, 0], p["d_tete"], 80, "x", "boulon", ["d_tete"]))
    tube(s, 5, "Tirant (gaine)", [xc + tp / 2 + 80 + 350, 0, -350 * math.tan(a)], p["d_trou"] * 0.6, 700, "x", ["d_trou", "angle"])
    s.cotes += [Cote([-pr, 0, -hp / 2 - 60], [0, 0, -hp / 2 - 60], f"réservation {pr:.0f}", "elevation", "prof_reservation", 40),
                Cote([xc + tp / 2 + 120, 0, -hp / 2], [xc + tp / 2 + 120, 0, hp / 2], f"hp = {hp:.0f}", "elevation", "h_plaque", 60),
                Cote([xc + tp / 2 + 120, -bp / 2, 0], [xc + tp / 2 + 120, bp / 2, 0], f"bp = {bp:.0f}", "dessus", "b_plaque", 60),
                Cote([xc - tp / 2, 0, -hp / 2 - 30], [xc + tp / 2, 0, -hp / 2 - 30], f"tp = {tp:.0f}", "elevation", "t_plaque", 30)]
    T = e.get("T", e.get("N", 0.0))
    s.efforts.append(Effort([xc + tp / 2 + 80 + 750, 0, -750 * math.tan(a)], [-math.cos(a), 0, math.sin(a)], T, f"T = {T:.0f} kN"))
    s.vues = [Vue("Élévation", "xz"), Vue("Coupe A-A", "xz", {"axe": "y", "pos": 0.0}), Vue("Vue de dessus", "xy")]
    s.notes.append("Tête de tirant sur paroi moulée : réservation biaise coffrée, plaque d'appui normale au tirant, compression localisée du béton.")
    return s


def v_tete_paroi(p: dict, e: dict, ctx: Contexte) -> list:
    T = e.get("T", e.get("N", 0.0))
    bp, hp, tp = p["b_plaque"], p["h_plaque"], p["t_plaque"]
    Ac0 = bp * hp - math.pi * p["d_trou"] ** 2 / 4
    out = [v_compression_beton("Paroi — compression localisée sous la plaque", T, Ac0, p["diffusion"] ** 2, ctx, [1, 3])]
    q = T / Ac0
    c = min(bp, hp) / 2 - p["d_tete"] / 2
    out.append(v_plaque_flexion("Plaque d'appui — flexion autour de la tête", tp, bp, q * c * c / 2, ctx, [3], f"porte-à-faux {c:.0f} mm"))
    out.append(resultat("Réservation et frettage", "béton", None, None, "", "EN 1992-1-1 § 6.7 / 8.10", categorie="structure", reperes=[2, 1],
                        detail_non_verifiable="armatures de frettage derrière la plaque et ferraillage de la réservation à définir par le projeteur béton (non automatisé)"))
    return out


enregistrer(TypeAssemblage("tete_tirant_paroi", "Tête de tirant sur paroi moulée (réservation)", "Tirants",
                           "Plaque d'appui dans une réservation biaise de la paroi moulée ; compression localisée du béton.",
                           P_TETE_P, g_tete_paroi, v_tete_paroi, ["T"]))


# ----------------------------------------------------------------------------- 11. bracon : liaison en tête par axe
P_BRACON_T = [Param("angle", "Inclinaison du bracon", "°", 45, 20, 70), Param("D_tube", "Diamètre du tube", "mm", 323.9, 60, 1000), Param("t_tube", "Épaisseur du tube", "mm", 10, 4, 40),
              Param("d_axe", "Diamètre de l'axe", "mm", 60, 20, 200), Param("classe_axe", "Nuance de l'axe", "", "S355", choix=["S235", "S275", "S355"], genre="choix"),
              Param("t_gousset", "Épaisseur des goussets (×2)", "mm", 25, 8, 80), Param("t_chape", "Épaisseur de la chape (centrale)", "mm", 40, 10, 120),
              Param("l_gousset", "Longueur des goussets sur la lierne", "mm", 500, 100, 1500), Param("h_gousset", "Hauteur des goussets", "mm", 350, 100, 1200),
              Param("jeu", "Jeu entre chape et goussets", "mm", 3, 0, 20), p_soudure(defaut=8)]


def g_bracon_tete(p: dict, e: dict, ctx: Contexte) -> Schema:
    s = Schema()
    L = lierne(s, ctx)
    h = L["h"]
    a = math.radians(p["angle"])
    tg, tc, lg, hg, j = p["t_gousset"], p["t_chape"], p["l_gousset"], p["h_gousset"], p["jeu"]
    xa, za = h + hg * 0.6, 0.0
    for sg in (-1, 1):
        s.ajouter(prisme(2, "Gousset", [[h, hg / 2], [h, -hg / 2], [h + lg * 0.9, -hg / 2 + 60], [h + lg * 0.9, hg / 2 - 60]], "y", sg * (tc / 2 + j + tg / 2), tg, "acier", ["t_gousset", "l_gousset", "h_gousset", "jeu"]))
    s.ajouter(prisme(3, "Chape du bracon", [[xa - 120, 100], [xa - 120, -100], [xa + 150, -100], [xa + 150, 100]], "y", 0, tc, "acier", ["t_chape"]))
    s.ajouter(cylindre(4, f"Axe Ø{p['d_axe']:.0f}", [xa, 0, za], p["d_axe"], tc + 2 * j + 2 * tg + 40, "y", "boulon", ["d_axe", "jeu"]))
    D, t = p["D_tube"], p["t_tube"]
    tube(s, 5, f"Bracon Ø{D:.0f}×{t:.0f}", [xa + 150 + 350 * math.cos(a), 0, -350 * math.sin(a)], D, 700, "x", ["D_tube", "t_tube", "angle"])
    s.soudures.append(Soudure([h, tc / 2 + j, hg / 2], [h, tc / 2 + j, -hg / 2], p["a_soudure"], "angle", False, [2, 1], "a_soudure"))
    s.cotes += [Cote([h, 0, -hg / 2 - 40], [h + lg * 0.9, 0, -hg / 2 - 40], f"l = {lg:.0f}", "elevation", "l_gousset", 40),
                Cote([h + lg * 0.9 + 40, 0, -hg / 2], [h + lg * 0.9 + 40, 0, hg / 2], f"h = {hg:.0f}", "elevation", "h_gousset", 50),
                Cote([xa, -tc / 2 - j - tg, hg / 2 + 30], [xa, tc / 2 + j + tg, hg / 2 + 30], f"{tg:.0f} / jeu {j:.0f} / chape {tc:.0f}", "dessus", "t_chape", 40),
                Cote([xa - p["d_axe"] / 2, 0, hg / 2 + 30], [xa + p["d_axe"] / 2, 0, hg / 2 + 30], f"Ø axe {p['d_axe']:.0f}", "elevation", "d_axe", 20)]
    N = e.get("N", 0.0)
    s.efforts.append(Effort([xa + 150 + 750 * math.cos(a), 0, -750 * math.sin(a)], [-math.cos(a), 0, math.sin(a)], N, f"N = {N:.0f} kN"))
    s.vues = [Vue("Élévation", "xz"), Vue("Vue de dessus", "xy"), Vue("Coupe A-A (axe)", "yz", {"axe": "x", "pos": xa})]
    s.notes.append("Articulation en tête de bracon : chape du bracon entre deux goussets soudés sur la lierne, axe en double cisaillement.")
    return s


def v_bracon_tete(p: dict, e: dict, ctx: Contexte) -> list:
    N = e.get("N", 0.0)
    d, tg, tc, j = p["d_axe"], p["t_gousset"], p["t_chape"], p["jeu"]
    lect = Lecteur(ctx.normes)
    acier = ctx.catalogue.acier(p["classe_axe"]) if ctx.catalogue else {"fy_MPa": ctx.fy, "fu_MPa": ctx.fu}
    r = ec3.axe(d, acier["fy_MPa"], acier["fu_MPa"], tg, ctx.fy, lect)
    M_axe = N / 8 * (tc + 4 * j + 2 * tg)   # EN 1993-1-8 fig. 3.11 : M = F/8·(b + 4c + 2a)
    out = []
    if r is None:
        out.append(resultat("Axe — cisaillement, flexion, pression diamétrale", "axe", None, None, "", "EN 1993-1-8 § 3.13", lect, "structure", reperes=[4]))
    else:
        out += [resultat("Axe — cisaillement (2 plans)", "axe", None, N / (2 * r["Fv_Rd"]), f"Fv,Ed = {N / 2:.0f} kN par plan, Fv,Rd = {r['Fv_Rd']:.0f} kN", "EN 1993-1-8 tableau 3.10", Lecteur(ctx.normes), "structure", reperes=[4]),
                resultat("Axe — flexion", "axe", None, M_axe / r["M_Rd"], f"M = N/8·(b + 4c + 2a) = {M_axe / 1000:.2f} kN·m, MRd = {r['M_Rd'] / 1000:.2f} kN·m", "EN 1993-1-8 § 3.13.2", Lecteur(ctx.normes), "structure", reperes=[4]),
                resultat("Goussets — pression diamétrale de l'axe", "gousset", None, N / 2 / r["Fb_Rd"], f"F = {N / 2:.0f} kN par gousset, Fb,Rd = {r['Fb_Rd']:.0f} kN", "EN 1993-1-8 tableau 3.10", Lecteur(ctx.normes), "structure", reperes=[2, 4])]
    a = math.radians(p["angle"])
    out.append(v_section("Goussets — section nette au trou", "gousset", N * math.cos(a), N * math.sin(a), N * math.sin(a) * p["l_gousset"] * 0.6, 2 * tg * (p["h_gousset"] - d - 2), 2 * tg * (p["h_gousset"] - d - 2), 2 * tg * (p["h_gousset"] - d) ** 2 / 4, ctx, [2]))
    out.append(v_soudure("Soudures goussets / lierne", 4 * p["h_gousset"], p["a_soudure"], N * (1 + 2 * p["l_gousset"] * 0.6 * math.sin(a) / p["h_gousset"]), ctx, [2, 1]))
    out.append(v_section("Chape du bracon — section nette", "chape", N, 0, 0, tc * (200 - d - 2), 0, 0, ctx, [3]))
    out.append(v_ame_lierne("Âme de lierne au droit des goussets", N * math.cos(a), p["l_gousset"] * 0.9, ctx, [1]))
    return out


enregistrer(TypeAssemblage("bracon_tete", "Bracon – lierne : chaise à goussets et axe", "Bracons",
                           "Liaison articulée en tête de bracon : chape entre deux goussets soudés, axe en double cisaillement.",
                           P_BRACON_T, g_bracon_tete, v_bracon_tete, ["N"]))


# ----------------------------------------------------------------------------- 12. bracon : appui en pied
P_BRACON_P = [Param("angle", "Inclinaison du bracon", "°", 45, 20, 70), Param("D_tube", "Diamètre du tube", "mm", 323.9, 60, 1000), Param("t_tube", "Épaisseur du tube", "mm", 10, 4, 40),
              Param("b_platine", "Largeur de la platine de pied", "mm", 500, 100, 1500), Param("l_platine", "Longueur de la platine", "mm", 600, 100, 2000),
              Param("t_platine", "Épaisseur de la platine", "mm", 30, 10, 80), Param("n_tiges", "Nombre de tiges d'ancrage", "", 4, 0, 12, genre="entier"),
              Param("d_tige", "Diamètre des tiges", "mm", 24, choix=[16, 20, 24, 27, 30, 36], genre="choix"), Param("classe_tige", "Classe des tiges", "", "8.8", choix=["4.6", "5.6", "8.8", "10.9"], genre="choix"),
              Param("h_beche", "Hauteur de la bêche", "mm", 150, 0, 600), Param("t_beche", "Épaisseur de la bêche", "mm", 20, 6, 60),
              Param("diffusion", "Largeur de diffusion dans le massif", "mm", 1200, 100, 3000), p_soudure(defaut=8), Param("fck_massif", "fck du massif / radier", "MPa", 30, 12, 60)]


def g_bracon_pied(p: dict, e: dict, ctx: Contexte) -> Schema:
    s = Schema()
    a = math.radians(p["angle"])
    bp, lp, tp = p["b_platine"], p["l_platine"], p["t_platine"]
    s.ajouter(boite(1, "Massif / radier", [0, 0, -400], [2000, 1400, 800], "beton", ()))
    s.ajouter(boite(2, "Platine de pied", [0, 0, tp / 2], [lp, bp, tp], "acier", ["b_platine", "l_platine", "t_platine"]))
    if p["h_beche"] > 0:
        s.ajouter(boite(3, "Bêche", [-lp / 4, 0, -p["h_beche"] / 2], [p["t_beche"], bp - 100, p["h_beche"]], "acier", ["h_beche", "t_beche"]))
    n = int(p["n_tiges"])
    if n:
        pos = [[u, v, -100] for u, v in grille_boulons(n, lp - 120, bp - 120)]
        boulons(s, 4, f"Tige d'ancrage M{int(p['d_tige'])}", pos, p["d_tige"], 200 + tp, "z", ["n_tiges", "d_tige", "classe_tige"])
    D, t = p["D_tube"], p["t_tube"]
    # goussets d'about et tube incliné
    s.ajouter(prisme(5, "Gousset d'about", [[-D / 2, tp], [D / 2, tp], [D / 2 + 120 * math.cos(a), tp + 120 * math.sin(a) + 150], [-D / 2 + 150 * math.cos(a), tp + 150 * math.sin(a) + 150]], "y", 0, 20, "acier", ["angle"]))
    tube(s, 6, f"Bracon Ø{D:.0f}×{t:.0f}", [-100 - 400 * math.cos(a), 0, tp + 150 + 400 * math.sin(a)], D, 800, "x", ["D_tube", "t_tube", "angle"])
    s.soudures.append(Soudure([-D / 2, 0, tp], [D / 2, 0, tp], p["a_soudure"], "angle", True, [5, 2], "a_soudure"))
    s.cotes += [Cote([-lp / 2, 0, -p["h_beche"] - 60], [lp / 2, 0, -p["h_beche"] - 60], f"l = {lp:.0f}", "elevation", "l_platine", 40),
                Cote([lp / 2 + 40, -bp / 2, tp], [lp / 2 + 40, bp / 2, tp], f"b = {bp:.0f}", "dessus", "b_platine", 50),
                Cote([lp / 2 + 40, 0, 0], [lp / 2 + 40, 0, tp], f"tp = {tp:.0f}", "elevation", "t_platine", 30),
                Cote([-lp / 4 - p["t_beche"] / 2 - 40, 0, -p["h_beche"]], [-lp / 4 - p["t_beche"] / 2 - 40, 0, 0], f"bêche {p['h_beche']:.0f}", "elevation", "h_beche", 30)]
    N = e.get("N", 0.0)
    s.efforts.append(Effort([-100 - 850 * math.cos(a), 0, tp + 150 + 850 * math.sin(a)], [math.cos(a), 0, -math.sin(a)], N, f"N = {N:.0f} kN"))
    s.vues = [Vue("Élévation", "xz"), Vue("Vue de dessus", "xy"), Vue("Coupe A-A", "yz", {"axe": "x", "pos": 0.0})]
    s.notes.append("Pied de bracon sur massif ou radier : la composante verticale est reprise par compression du béton, la composante horizontale par la bêche (ou les tiges en cisaillement).")
    return s


def v_bracon_pied(p: dict, e: dict, ctx: Contexte) -> list:
    N = e.get("N", 0.0)
    a = math.radians(p["angle"])
    H, V = N * math.cos(a), N * math.sin(a)
    bp, lp, tp = p["b_platine"], p["l_platine"], p["t_platine"]
    ctx2 = Contexte(ctx.normes, ctx.catalogue, ctx.fy, ctx.fu, ctx.nuance, ctx.lierne, ctx.buton, p["fck_massif"], ctx.demo)
    out = [v_compression_beton("Massif — compression sous la platine", V, bp * lp, p["diffusion"] ** 2, ctx2, [1, 2])]
    q = V / (bp * lp)
    out.append(v_plaque_flexion("Platine de pied — flexion en console", tp, bp, q * ((lp - p["D_tube"]) / 2) ** 2 / 2, ctx, [2]))
    if p["h_beche"] > 0:
        hb, tb = p["h_beche"], p["t_beche"]
        out.append(v_section("Bêche — flexion et cisaillement", "bêche", 0, H, H * hb / 2, tb * (bp - 100), tb * (bp - 100), (bp - 100) * tb * tb / 4, ctx, [3]))
        out.append(v_compression_beton("Massif — butée sur la bêche", H, hb * (bp - 100), 3 * hb * (bp - 100), ctx2, [1, 3]))
    n = int(p["n_tiges"])
    if n and p["h_beche"] <= 0:
        out += v_boulons_cisaillement("Tiges d'ancrage", n, p["d_tige"], p["classe_tige"], H, tp, 60, 60, lp - 120, ctx, [4])
    elif n:
        out.append(resultat("Tiges d'ancrage", "tiges", None, None, "", "EN 1993-1-8 § 6.2.6.12", categorie="structure", reperes=[4],
                            detail_non_verifiable="tiges de positionnement : l'effort horizontal est repris par la bêche (hypothèse)"))
    out.append(v_soudure("Soudure tube / platine (gousset d'about)", math.pi * p["D_tube"], p["a_soudure"], N, ctx, [5, 2, 6]))
    return out


enregistrer(TypeAssemblage("bracon_pied", "Bracon : appui en pied sur massif ou radier", "Bracons",
                           "Platine de pied avec bêche et tiges d'ancrage sur un massif béton ; compression du béton et reprise de la composante horizontale.",
                           P_BRACON_P, g_bracon_pied, v_bracon_pied, ["N"]))
