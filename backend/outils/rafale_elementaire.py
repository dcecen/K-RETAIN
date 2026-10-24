"""Rafale d'exemples élémentaires : rapport pour relecture (manager, revue croisée).

    cd backend
    .venv/Scripts/python.exe -m outils.rafale_elementaire            # tout (balayages 3D compris)
    .venv/Scripts/python.exe -m outils.rafale_elementaire --rapide   # sans les balayages 3D longs

Écrit docs/validation/rafale_elementaire.md (tables : cas, grandeur, attendu, calculé, écart, verdict,
source), docs/validation/figures/*.png (matplotlib, facultatif : sans lui, tables seules) et
docs/validation/rafale_elementaire.html (page autonome, figures SVG intégrées, sans JavaScript ni
ressource externe). Les cas sont ceux des tests de validation (sout.validation) : rien n'est recopié.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import io
import sys
from pathlib import Path

from sout.validation.cas_ecran import cas_ecran
from sout.validation.cas_elementaires import Cas, cas_poutres
from sout.validation.cas_plaque import cas_plaque
from sout.validation.cas_pseudo3d import cas_pseudo3d

RACINE = Path(__file__).resolve().parents[2]
DOSSIER = RACINE / "docs" / "validation"
FIGURES = DOSSIER / "figures"

FAMILLES = [
    ("poutres", "Poutres sans sol (résistance des matériaux, type RDM7)"),
    ("poutres_winkler", "Poutres sur fondation de Winkler (Hetényi)"),
    ("plaque", "Plaque sans sol (grillage pseudo-3D contre Timoshenko)"),
    ("ecran", "Écran 2D : équilibre limite, équilibre par phase, convergence"),
    ("ecran_balayage", "Écran 2D : balayages de grandeurs physiques"),
    ("pseudo3d", "Pseudo-3D : coupes 2D assemblées contre vraie plaque, double écran"),
]

LIMITES = [
    "Poutre d'Euler-Bernoulli : pas de déformation d'effort tranchant (écrans élancés), plaque mince de Huber à ν = 0 "
    "(le terme de Poisson 2νD est négligé ; pour un béton ν ≈ 0,2).",
    "Sol en ressorts de Winkler indépendants (méthode aux coefficients de réaction) : pas de diffusion dans le massif, "
    "pas d'effet de voûte autre que celui de la plaque.",
    "Angles de la fouille fermée monolithiques (rotation continue, déplacement nul) ; l'option d'angle articulé n'existe pas.",
    "Appuis ponctuels : Ms et V au droit d'un buton dépendent du maillage tant que pseudo3d.largeur_appui n'est pas donnée.",
    "Charges du sol et de l'eau concentrées aux nœuds dans le système résolu (erreur mesurée 9e-5 sur la flèche d'une console "
    "au pas 0,1 m) ; les diagrammes M et V sont calculés par la statique avec les charges réparties.",
    "Rigidité horizontale par défaut : paroi moulée Ds = Dz (panneaux continus sauf paroi.longueur_panneau), palplanches, "
    "pieux et berlinoise Ds = 0 (serrures et recouvrements libres : hypothèses, modifiables par pseudo3d.rigidite_horizontale).",
]

SIGNES_RDM7 = [
    ("Abscisse le long de la poutre", "x (horizontale)", "z (verticale, vers le haut pour un écran)"),
    ("Flèche positive", "vers le bas (sens des charges)", "y vers la fouille (sens des poussées)"),
    ("Moment positif", "fibre inférieure tendue", "face côté fouille (+y) tendue : M = −EI·y''"),
    ("Effort tranchant", "T = dM/dx", "V = dM/dz = somme des charges situées au-dessus de la section"),
    ("Travée sur deux appuis chargée", "M = +qL²/8 au milieu", "M = +qL²/8 au milieu (même signe)"),
    ("Console chargée en bout", "M = −PL à l'encastrement", "M = −PL à l'encastrement (même signe)"),
]


# ---------------------------------------------------------------------------
def _fmt(v: float, unite: str = "") -> str:
    if v == 0:
        s = "0"
    elif abs(v) >= 1e4 or abs(v) < 1e-3:
        s = f"{v:.4g}"
    else:
        s = f"{v:.4g}"
    return s.replace(".", ",") + (f" {unite}" if unite else "")


def _ecart(g) -> str:
    if g.echelle is not None:
        return f"{g.ecart:.1e} (abs.)"
    return f"{100 * g.ecart:.2f} %" if g.ecart >= 1e-4 else f"{g.ecart:.1e}"


def _verdict(ok: bool) -> str:
    return "✅ conforme" if ok else "❌ écart"


def tableau_md(cas: Cas) -> str:
    lignes = ["| Grandeur | Attendu | Calculé | Écart | Tolérance | Verdict | Source |", "|---|---|---|---|---|---|---|"]
    for g in cas.grandeurs:
        tol = f"{g.tolerance:.0e}" if g.tolerance < 1e-2 else f"{100 * g.tolerance:.0f} %"
        if g.echelle == 1.0 and g.tolerance == 0.0:      # grandeur booléenne (monotonie, condition)
            lignes.append(f"| {g.libelle} | oui | {'oui' if g.calcule == 1.0 else 'non'} | — | — | {_verdict(g.ok)} | {g.source} |")
            continue
        lignes.append(f"| {g.libelle} | {_fmt(g.attendu, g.unite)} | {_fmt(g.calcule, g.unite)} | {_ecart(g)} | {tol} | {_verdict(g.ok)} | {g.source} |")
    return "\n".join(lignes)


def tableau_balayage_md(cas: Cas) -> str:
    tab = cas.courbes.get("tableau")
    if not tab:
        return ""
    cles = list(tab[0].keys())
    out = ["| " + " | ".join(cles) + " |", "|" + "---|" * len(cles)]
    for l in tab:
        out.append("| " + " | ".join(_fmt(v) if isinstance(v, (int, float)) else str(v) for v in l.values()) + " |")
    return "\n".join(out)


# ---------------------------------------------------------------------------
def figures(cas_par_nom: dict[str, Cas]) -> dict[str, tuple[Path, str]]:
    """{nom du cas: (png, svg inline)} ; vide si matplotlib est absent."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib absent : rapport sans figures (pip install -e .[rapport])")
        return {}
    FIGURES.mkdir(parents=True, exist_ok=True)
    out = {}

    def sauver(nom, fig):
        png = FIGURES / f"{nom}.png"
        fig.savefig(png, dpi=130, bbox_inches="tight")
        buf = io.StringIO()
        fig.savefig(buf, format="svg", bbox_inches="tight")
        plt.close(fig)
        out[nom] = (png, buf.getvalue())

    # poutres : diagrammes M et V des cas les plus parlants
    for nom in ("biappuyee_repartie", "continue_2_travees", "console_force", "winkler_semi_infinie_force", "couple_milieu"):
        c = cas_par_nom.get(nom)
        if not c or not c.courbes:
            continue
        fig, axes = plt.subplots(1, 3, figsize=(11, 3.2))
        axes[0].plot(c.courbes["z"], [v * 1e3 for v in c.courbes["y"]], color="#1f77b4")
        axes[0].set_title("flèche y (mm)")
        axes[1].plot(c.courbes["z_diag"], c.courbes["M"], color="#d62728")
        axes[1].set_title("moment M (kN·m)")
        axes[2].plot(c.courbes["z_diag"], c.courbes["V"], color="#2ca02c")
        axes[2].set_title("effort tranchant V (kN)")
        for ax in axes:
            ax.set_xlabel("z (m)")
            ax.grid(alpha=0.3)
        fig.suptitle(c.description, fontsize=10)
        sauver(nom, fig)
    # plaque : profil de Navier contre grillage
    c = cas_par_nom.get("plaque_carree_appuyee")
    if c and c.courbes:
        fig, ax = plt.subplots(figsize=(6, 3.4))
        ax.plot(c.courbes["s"], [v * 1e3 for v in c.courbes["w_navier"]], "k-", label="série de Navier (Timoshenko)")
        ax.plot(c.courbes["s"], [v * 1e3 for v in c.courbes["w_grillage"]], "o", ms=4, color="#1f77b4", label="grillage pseudo-3D (20 × 20)")
        ax.set_xlabel("s (m)"); ax.set_ylabel("w (mm)"); ax.grid(alpha=0.3); ax.legend()
        ax.set_title("Plaque carrée appuyée : flèche sur la ligne médiane", fontsize=10)
        sauver("plaque_navier", fig)
    # pseudo-3D : figure clé Ds/Dz
    c = cas_par_nom.get("p3d_rigidite_horizontale")
    if c and c.courbes:
        fig, ax = plt.subplots(figsize=(8, 3.8))
        s = c.courbes["s"]
        for k, prof in c.courbes["profils_mm"].items():
            ax.plot(s, prof, label=f"Ds/Dz = {k}" + (" (coupes 2D assemblées)" if float(k) == 0 else " (plaque isotrope)" if float(k) == 1 else ""))
        ax.axhline(c.courbes["y_2d_appui_reparti_mm"], color="k", ls="--", lw=1, label="2D, appui réparti")
        ax.axhline(c.courbes["y_2d_sans_appui_mm"], color="k", ls=":", lw=1, label="2D, sans appui")
        ax.set_xlabel("abscisse le long de la paroi s (m)"); ax.set_ylabel("déplacement au niveau des butons (mm)")
        ax.set_title("Paroi de 48 m, butons tous les 4 m : de l'assemblage de coupes 2D (Ds = 0) à la vraie plaque", fontsize=10)
        ax.grid(alpha=0.3); ax.legend(fontsize=8, ncol=2)
        sauver("p3d_rigidite_horizontale", fig)
    c = cas_par_nom.get("p3d_fouille_fermee")
    if c and c.courbes:
        fig, axes = plt.subplots(1, 2, figsize=(10, 3.4))
        x = list(range(0, 21))
        axes[0].plot(x, c.courbes["W_sud_sans_mm"], "k--", label="sans grue")
        axes[0].plot(x, c.courbes["W_sud_mm"], color="#d62728", label="grue 3 000 kN derrière x = 10 m")
        axes[0].set_title("paroi sud (chargée) : |y| max (mm)", fontsize=10)
        axes[1].plot(x, c.courbes["W_nord_sans_mm"][::-1], "k--", label="sans grue")
        axes[1].plot(x, c.courbes["W_nord_mm"][::-1], color="#1f77b4", label="avec grue : poussée vers sa terre par les butons")
        axes[1].set_title("paroi nord (en face) : y au niveau des butons (mm)", fontsize=10)
        for ax in axes:
            ax.set_xlabel("x le long du côté (m)"); ax.grid(alpha=0.3); ax.legend(fontsize=8)
        fig.suptitle("Fouille fermée 20 × 12 m : interaction des deux parois par les butons (double écran)", fontsize=10)
        sauver("p3d_fouille_fermee", fig)
    # balayages 2D
    for nom in ("balayage_kh", "balayage_EI", "balayage_phi", "balayage_H", "balayage_k_appui", "balayage_precharge"):
        c = cas_par_nom.get(nom)
        if not c or not c.courbes.get("tableau"):
            continue
        tab = c.courbes["tableau"]
        p = c.courbes["parametre"]
        xs = [l[p] if l[p] is not None else 0 for l in tab]
        fig, axes = plt.subplots(1, 3, figsize=(11, 3.0))
        for ax, (g, u) in zip(axes, (("y_max_mm", "mm"), ("M_max", "kN·m/m"), ("effort_appui", "kN/m"))):
            ax.plot(xs, [l[g] for l in tab], "o-")
            ax.set_xlabel(p); ax.set_ylabel(f"{g} ({u})"); ax.grid(alpha=0.3)
            if p.startswith(("kh", "EI", "k_appui")):
                ax.set_xscale("log")
        fig.suptitle(c.description, fontsize=10)
        sauver(nom, fig)
    return out


# ---------------------------------------------------------------------------
def rapport_md(cas: list[Cas], figs: dict, rapide: bool) -> str:
    n_ok = sum(c.ok for c in cas)
    L = ["# Rafale d'exemples élémentaires — RetainWall", "",
         f"Généré le {dt.date.today().isoformat()} par `python -m outils.rafale_elementaire`"
         + (" (mode rapide : balayages 3D longs omis)" if rapide else "") + ".", "",
         "Chaque cas compare une grandeur calculée par le logiciel à une **référence analytique citée** (formulaires de "
         "résistance des matériaux, Hetényi, Timoshenko & Woinowsky-Krieger, équilibre limite) ou à une propriété "
         "physique attendue (symétrie, équilibre, monotonie). Les mêmes cas sont exécutés par les tests automatiques "
         "(`backend/tests/validation`). Convention de signes : voir le tableau RDM7 en fin de document.", "",
         f"**Bilan : {n_ok} cas conformes sur {len(cas)}**" + (" — tous conformes." if n_ok == len(cas) else " — voir les écarts ci-dessous."), ""]
    L += ["## Sommaire", ""]
    for cle, titre in FAMILLES:
        n = [c for c in cas if c.famille == cle]
        if n:
            L.append(f"- {titre} : {sum(c.ok for c in n)}/{len(n)} conformes")
    L.append("")
    for cle, titre in FAMILLES:
        groupe = [c for c in cas if c.famille == cle]
        if not groupe:
            continue
        L += [f"## {titre}", ""]
        for c in groupe:
            L += [f"### {c.description}", "", f"Identifiant : `{c.nom}` — {_verdict(c.ok)} (écart max {c.ecart_max:.1e})", "", tableau_md(c), ""]
            tb = tableau_balayage_md(c)
            if tb:
                L += ["Résultats du balayage :", "", tb, ""]
            if c.nom in figs:
                L += [f"![{c.nom}](figures/{c.nom}.png)", ""]
            if c.nom == "plaque_carree_appuyee" and "plaque_navier" in figs:
                L += ["![plaque_navier](figures/plaque_navier.png)", ""]
    L += ["## Limites du modèle (à garder en tête en lisant les résultats)", ""] + [f"- {x}" for x in LIMITES] + [""]
    L += ["## Correspondance des conventions avec RDM7", "", "| Grandeur | RDM7 | RetainWall |", "|---|---|---|"]
    L += [f"| {a} | {b} | {c} |" for a, b, c in SIGNES_RDM7]
    L += ["", "Les tests `backend/tests/validation/test_rafale_poutres.py` et `test_rafale_elementaire.py` rejouent ces cas "
          "à chaque exécution de `lancer_tests.ps1`.", ""]
    return "\n".join(L)


def rapport_html(md: str, figs: dict) -> str:
    """Page autonome : le Markdown est converti simplement (titres, tableaux, listes, paragraphes), les figures PNG
    sont remplacées par leur SVG intégré."""
    corps = []
    table: list[str] = []

    def vider_table():
        if not table:
            return
        corps.append("<table>")
        for i, ligne in enumerate(table):
            cells = [html.escape(x.strip()) for x in ligne.strip("|").split("|")]
            tag = "th" if i == 0 else "td"
            corps.append("<tr>" + "".join(f"<{tag}>{c}</{tag}>" for c in cells) + "</tr>")
        corps.append("</table>")
        table.clear()

    liste = False
    for ligne in md.splitlines():
        if ligne.startswith("|"):
            if ligne.startswith("|---"):
                continue
            table.append(ligne)
            continue
        vider_table()
        if ligne.startswith("- "):
            if not liste:
                corps.append("<ul>")
                liste = True
            corps.append(f"<li>{_inline(ligne[2:])}</li>")
            continue
        if liste:
            corps.append("</ul>")
            liste = False
        if ligne.startswith("!["):
            nom = ligne[2:ligne.index("]")]
            if nom in figs:
                corps.append(f'<figure>{figs[nom][1]}</figure>')
            continue
        for niveau in (3, 2, 1):
            if ligne.startswith("#" * niveau + " "):
                corps.append(f"<h{niveau}>{_inline(ligne[niveau + 1:])}</h{niveau}>")
                break
        else:
            if ligne.strip():
                corps.append(f"<p>{_inline(ligne)}</p>")
    vider_table()
    if liste:
        corps.append("</ul>")
    style = ("body{font-family:Segoe UI,Arial,sans-serif;max-width:1100px;margin:24px auto;padding:0 16px;color:#1d2330;line-height:1.45}"
             "table{border-collapse:collapse;margin:8px 0 16px;font-size:13px}th,td{border:1px solid #cfd6e0;padding:4px 8px;text-align:left}"
             "th{background:#eef2f7}h1{font-size:24px}h2{font-size:19px;margin-top:32px;border-bottom:2px solid #cfd6e0}h3{font-size:15px;margin-top:22px}"
             "code{background:#f1f4f8;padding:1px 4px;border-radius:3px}figure{margin:8px 0}figure svg{max-width:100%;height:auto}"
             "@media (prefers-color-scheme: dark){body{background:#13171f;color:#e6e9ef}th{background:#232a36}th,td{border-color:#3a4252}code{background:#232a36}h2{border-color:#3a4252}}")
    return ("<!doctype html><html lang=\"fr\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            f"<title>Rafale d'exemples élémentaires</title><style>{style}</style></head><body>" + "\n".join(corps) + "</body></html>")


def _inline(txt: str) -> str:
    t = html.escape(txt)
    while "**" in t:
        t = t.replace("**", "<b>", 1).replace("**", "</b>", 1)
    while "`" in t:
        t = t.replace("`", "<code>", 1).replace("`", "</code>", 1)
    return t


def generer(rapide: bool = False) -> tuple[Path, Path]:
    cas = cas_poutres() + cas_plaque() + cas_ecran() + cas_pseudo3d(rapide=rapide)
    figs = figures({c.nom: c for c in cas})
    DOSSIER.mkdir(parents=True, exist_ok=True)
    md = rapport_md(cas, figs, rapide)
    chemin_md = DOSSIER / "rafale_elementaire.md"
    chemin_md.write_text(md, encoding="utf-8")
    chemin_html = DOSSIER / "rafale_elementaire.html"
    chemin_html.write_text(rapport_html(md, figs), encoding="utf-8")
    return chemin_md, chemin_html


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rapide", action="store_true", help="sans les balayages 3D longs")
    args = ap.parse_args()
    md, h = generer(rapide=args.rapide)
    sys.stdout.reconfigure(encoding="utf-8")
    print(md, "\n", h)
