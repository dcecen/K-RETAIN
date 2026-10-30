"""Lecture d'un fichier de données RIDO et conversion en script K-Retain.

Le format est décrit par docs/rido/correspondance.yaml, établie à partir du fichier réel fourni par
l'utilisateur (docs/rido/berlinoise_IPE400_excel.rid), sans le manuel RIDO : chaque position y porte son
statut (« lu » dans le fichier ou « à confirmer »). L'ordre des colonnes des couches, de l'écran, de la
nappe et des commandes est relu dans cette table ; seule la structure du fichier est codée ici :

- 1re ligne : titre ; « * » : commentaire ; « *" » : titre du calcul qui suit ;
- « #nom = expression » : variable, évaluée dans l'ordre (« # XLS=… », « # CONST=… » : directives Excel) ;
- ligne commençant par « + » : suite de la ligne de données précédente ;
- blocs successifs : écran (lignes « cote EI … ») jusqu'à une ligne d'une seule valeur (terrain), couches,
  nappe (ligne de une ou deux valeurs), puis commandes (sub, coe, ber, cal, tel, fap, rrc…, fin).

Les valeurs xlc(feuille, ligne, colonne) sont lues dans le classeur Excel associé quand il est donné
(Classeur) ; sinon elles sont signalées comme indisponibles et le script converti reste incomplet
(outils/rido_sans_excel.py écrit une version du fichier indépendante de la feuille).

Rien n'est inventé : une ligne ou une commande dont le sens n'est pas dans la table est listée dans le
rapport des données non reprises, avec son numéro de ligne.
"""
from __future__ import annotations

import ast
import math
import operator
import re
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path

from ruamel.yaml import YAML

TABLE = Path(__file__).resolve().parents[3] / "docs" / "rido" / "correspondance.yaml"

COLONNES_COUCHE = ["base", "gamma", "gamma_dejauge", "ka", "k0", "kp", "phi", "c", "delta_a", "delta_p", "kh"]
COLONNES_SUB = ["cote", "debut", "fin", "q"]
COLONNES_COE = ["haut", "bas", "rapport"]
DIRECTIVES = {"XLS", "CONST"}
FIN = {"fin"}


class ErreurExpression(ValueError):
    """Expression RIDO illisible ou variable non définie."""


class ValeurIndisponible(ValueError):
    """Valeur qui dépend de la feuille Excel, non fournie."""


@dataclass
class Classeur:
    """Cellules de la feuille Excel associée au fichier RIDO : {(feuille, ligne, colonne): valeur}, indices à
    partir de 1 comme xlc(). Les libellés textuels donnent les constantes l_<libellé> (ligne, libellés des
    colonnes 1 et 2) et c_<libellé> (colonne, libellés de la ligne 1) de la directive CONST."""
    cellules: dict[tuple[int, int, int], object]
    nom: str = "classeur"
    _constantes: dict[str, float] | None = field(default=None, repr=False, compare=False)

    def xlc(self, f: float, l: float, c: float) -> float:
        cle = (int(f), int(l), int(c))
        v = self.cellules.get(cle)
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ErreurExpression(f"xlc{cle} : cellule vide ou non numérique ({v!r}) dans {self.nom}")
        return float(v)

    def constantes(self) -> dict[str, float]:
        if self._constantes is not None:
            return self._constantes
        d: dict[str, float] = {}
        for (f, l, c), v in sorted(self.cellules.items(), key=lambda kv: (kv[0][0], -kv[0][2], kv[0][1])):
            if f == 1 and isinstance(v, str) and v.strip():
                nom = re.sub(r"\W", "_", v.strip())
                if c in (1, 2):
                    d.setdefault(f"l_{nom}", float(l))
                if l == 1:
                    d.setdefault(f"c_{nom}", float(c))
        self._constantes = d
        return d


# ---------------------------------------------------------------------------
# Expressions
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Pow: operator.pow}
_CMP = {ast.Gt: operator.gt, ast.GtE: operator.ge, ast.Lt: operator.lt, ast.LtE: operator.le,
        ast.Eq: operator.eq, ast.NotEq: operator.ne}
_FONCTIONS = {"min": min, "max": max, "abs": abs, "sqrt": math.sqrt, "exp": math.exp, "ln": math.log}


def _traduire(expr: str) -> str:
    s = expr.strip().replace("^", "**").replace(";", ",").replace("<>", "!=")
    return re.sub(r"(?<![<>=!])=(?!=)", "==", s)


def evaluer(expr: str, variables: dict[str, float], classeur: Classeur | None = None,
            indisponibles: dict[str, str] | None = None) -> float:
    """Valeur d'une expression RIDO (nombres, variables, + − × / ^, comparaisons valant 1 ou 0,
    min(a;b), max(a;b), abs, sqrt, exp, ln, xlc(feuille, ligne, colonne))."""
    indisponibles = indisponibles or {}
    constantes = classeur.constantes() if classeur else {}
    try:
        arbre = ast.parse(_traduire(expr), mode="eval")
    except SyntaxError:
        raise ErreurExpression(f"expression illisible « {expr} »") from None

    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
            return float(n.value)
        if isinstance(n, ast.Name):
            if n.id in variables:
                return variables[n.id]
            if n.id in indisponibles:
                raise ValeurIndisponible(indisponibles[n.id])
            if n.id in constantes:
                return constantes[n.id]
            if n.id.startswith(("l_", "c_")) and classeur is None:
                raise ValeurIndisponible(f"{n.id} (libellé de la feuille Excel)")
            raise ErreurExpression(f"variable « {n.id} » non définie")
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
            try:
                return float(_OPS[type(n.op)](ev(n.left), ev(n.right)))
            except ZeroDivisionError:
                raise ErreurExpression(f"division par zéro dans « {expr} »") from None
            except (OverflowError, TypeError):
                raise ErreurExpression(f"calcul impossible dans « {expr} »") from None
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
            v = ev(n.operand)
            return -v if isinstance(n.op, ast.USub) else v
        if isinstance(n, ast.Compare):
            g = ev(n.left)
            for op, d in zip(n.ops, n.comparators, strict=True):
                dv = ev(d)
                if type(op) not in _CMP or not _CMP[type(op)](g, dv):
                    return 0.0
                g = dv
            return 1.0
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and not n.keywords:
            nom = n.func.id.lower()
            args = [ev(a) for a in n.args]
            if nom == "xlc":
                if len(args) != 3:
                    raise ErreurExpression(f"xlc attend 3 arguments (feuille, ligne, colonne) : « {expr} »")
                if classeur is None:
                    raise ValeurIndisponible(f"xlc({', '.join(f'{a:g}' for a in args)}) (feuille Excel non fournie)")
                return classeur.xlc(*args)
            if nom in _FONCTIONS and args:
                try:
                    return float(_FONCTIONS[nom](*args))
                except (ValueError, TypeError):
                    raise ErreurExpression(f"{nom} : argument invalide dans « {expr} »") from None
            raise ErreurExpression(f"fonction « {n.func.id} » inconnue dans « {expr} »")
        raise ErreurExpression(f"expression non reconnue « {expr} »")

    v = ev(arbre)
    if isinstance(v, complex) or not math.isfinite(v):
        raise ErreurExpression(f"résultat non fini pour « {expr} »")
    return v


def _jetons(ligne: str) -> list[str]:
    """Découpe aux espaces hors parenthèses."""
    jetons, cour, prof = [], "", 0
    for ch in ligne:
        if ch.isspace() and prof == 0:
            if cour:
                jetons.append(cour)
            cour = ""
            continue
        prof += (ch == "(") - (ch == ")")
        cour += ch
    if cour:
        jetons.append(cour)
    return jetons


# ---------------------------------------------------------------------------
# Lecture
@dataclass
class Ligne:
    """Ligne logique (suites « + » réunies) : données ou commande."""
    numero: int
    texte: str
    valeurs: list[float | None] = field(default_factory=list)
    erreurs: list[str] = field(default_factory=list)
    commande: str | None = None
    arguments: list[float | None] = field(default_factory=list)
    suites: list[Ligne] = field(default_factory=list)
    titre: str | None = None        # dernier titre « *" » lu avant la ligne


@dataclass
class LectureRido:
    titre: str
    commentaires: list[str]
    variables: dict[str, float]
    indisponibles: dict[str, str]
    lignes: list[Ligne]
    directives: list[str]
    messages: list[str]


def lire(texte: str, classeur: Classeur | None = None) -> LectureRido:
    variables: dict[str, float] = {}
    indisponibles: dict[str, str] = {}
    definies: set[str] = set()
    lignes: list[Ligne] = []
    commentaires, directives, messages = [], [], []
    titre, titre_calcul = None, None

    def valeur(expr: str, num: int, erreurs: list[str]) -> float | None:
        try:
            return evaluer(expr, variables, classeur, indisponibles)
        except ValeurIndisponible as e:
            erreurs.append(f"ligne {num} : « {expr} » dépend de {e}")
        except ErreurExpression as e:
            erreurs.append(f"ligne {num} : {e}")
        return None

    def definir(nom: str, expr: str, num: int) -> None:
        try:
            variables[nom] = evaluer(expr, variables, classeur, indisponibles)
            indisponibles.pop(nom, None)
        except ValeurIndisponible as e:
            variables.pop(nom, None)
            indisponibles[nom] = str(e)
        except ErreurExpression as e:
            variables.pop(nom, None)
            indisponibles[nom] = f"la variable {nom}, non calculable (ligne {num})"
            messages.append(f"ligne {num} : {e}")

    for num, brute in enumerate(texte.splitlines(), 1):
        s = brute.strip()
        if titre is None:
            if s:
                titre = s
            continue
        if not s:
            continue
        if s.startswith("*"):
            if s.startswith('*"'):
                titre_calcul = s[2:].strip().strip('"').strip()
            else:
                commentaires.append(s[1:].strip())
            continue
        if s.startswith("#"):
            m = re.match(r"#\s*([A-Za-z_]\w*)\s*=(.*)$", s)
            if m and m.group(1).upper() in DIRECTIVES:
                directives.append(f"ligne {num} : {s}")
            elif m:
                definies.add(m.group(1))
                definir(m.group(1), m.group(2), num)
            else:
                commentaires.append(s[1:].strip())
            continue
        if s.startswith("+"):
            if not lignes:
                messages.append(f"ligne {num} : suite « + » sans ligne précédente, ignorée")
                continue
            l = lignes[-1]
            l.texte += " " + s
            for j in _jetons(s[1:]):
                l.valeurs.append(valeur(j, num, l.erreurs))
            continue
        jetons = _jetons(s)
        m = re.fullmatch(r"([A-Za-z]\w*)(?:\((.*)\))?", jetons[0])
        if m and m.group(1) not in definies and m.group(1).lower() not in _FONCTIONS and m.group(1).lower() != "xlc":
            l = Ligne(num, s, commande=m.group(1).lower(), titre=titre_calcul)
            if m.group(2):
                l.arguments = [valeur(a, num, l.erreurs) for a in m.group(2).split(",") if a.strip()]
            l.valeurs = [valeur(j, num, l.erreurs) for j in jetons[1:]]
        else:
            l = Ligne(num, s, titre=titre_calcul)
            l.valeurs = [valeur(j, num, l.erreurs) for j in jetons]
        lignes.append(l)
    return LectureRido(titre or "Import RIDO", commentaires, variables, indisponibles, lignes, directives, messages)


# ---------------------------------------------------------------------------
# Conversion
@dataclass
class Conversion:
    script: dict
    texte: str
    non_repris: list[str] = field(default_factory=list)
    repris: int = 0
    hypotheses: list[str] = field(default_factory=list)
    erreurs: list[str] = field(default_factory=list)
    calculs_non_repris: list[str] = field(default_factory=list)

    @property
    def complet(self) -> bool:
        return not self.erreurs

    @property
    def rapport(self) -> list[str]:
        r = [f"{self.repris} ligne(s) reprise(s), {len(self.non_repris)} donnée(s) non reprise(s)"
             + (f", {len(self.erreurs)} valeur(s) manquante(s) : script incomplet." if self.erreurs else ".")]
        r += [f"Manquant : {e}" for e in self.erreurs]
        r += [f"Non repris : {n}" for n in self.non_repris]
        r += [f"Calcul non repris : {c}" for c in self.calculs_non_repris]
        r += [f"Hypothèse : {h}" for h in self.hypotheses]
        return r


def charger_table(chemin: Path = TABLE) -> dict:
    if not chemin.exists():
        return {}
    return YAML(typ="safe").load(chemin.read_text(encoding="utf-8")) or {}


def _colonnes(table: dict, bloc: str, defaut: list) -> list:
    if bloc == "couches":
        return list((table.get("couches") or {}).get("colonnes") or defaut)
    return list(((table.get("commandes") or {}).get(bloc) or {}).get("colonnes") or defaut)


def _ratio_delta(v: float | None, phi: float | None) -> float:
    """δ/φ positif : la valeur est un rapport si |v| ≤ 1, sinon un angle en degrés (table, couches.unites.delta)."""
    if not v:
        return 0.0
    if abs(v) <= 1.0:
        return abs(v)
    return min(abs(v) / phi, 1.0) if phi else 0.0


def convertir(texte: str, nom: str = "import RIDO", table: dict | None = None,
              classeur: Classeur | None = None) -> Conversion:
    """Script K-Retain (dict et texte YAML) équivalent au fichier RIDO, avec le rapport des données non reprises,
    des valeurs manquantes (feuille Excel) et des hypothèses de lecture."""
    table = charger_table() if table is None else table
    lec = lire(texte, classeur)
    conv = Conversion({}, "")
    conv.non_repris += lec.messages
    conv.non_repris += [f"{d} (directive Excel)" for d in lec.directives] if classeur is None else []
    erreurs = conv.erreurs

    def vals(l: Ligne) -> list[float | None]:
        for e in l.erreurs:
            if e not in erreurs:
                erreurs.append(e)
        return l.valeurs

    ecran: list[Ligne] = []
    terrain: Ligne | None = None
    couches: list[Ligne] = []
    nappe: Ligne | None = None
    commandes: list[Ligne] = []
    etat = "ecran"
    fin = False
    for l in lec.lignes:
        if fin:
            conv.non_repris.append(f"ligne {l.numero} : « {l.texte[:60]} » après « fin », ignorée")
            continue
        if l.commande is not None:
            etat = "commandes"
            if l.commande in FIN:
                fin = True
                conv.repris += 1
                continue
            commandes.append(l)
            continue
        n = len(l.valeurs)
        if etat == "ecran":
            if n == 1:
                terrain, etat = l, "sol"
            else:
                ecran.append(l)
        elif etat == "sol":
            if n >= 3:
                couches.append(l)
            else:
                nappe, etat = l, "commandes"
        elif commandes:
            commandes[-1].suites.append(l)
        else:
            conv.non_repris.append(f"ligne {l.numero} : « {l.texte[:60]} » (ligne de données hors bloc)")

    # Écran
    paroi: dict = {}
    if len(ecran) < 2:
        erreurs.append("écran incomplet : il faut une ligne de tête « cote … » puis au moins une ligne « cote EI »")
    else:
        conv.repris += len(ecran)
        tete = vals(ecran[0])[0]
        sections = [vals(l) for l in ecran[1:]]
        paroi = {"type": "palplanche", "tete": tete, "pied": sections[-1][0],
                 "EI": sections[0][1] if len(sections[0]) > 1 else None, "etancheite": "etanche"}
        if len(ecran[0].valeurs) > 1:
            conv.non_repris.append(f"ligne {ecran[0].numero} : 2e valeur de la ligne de tête ({_f(ecran[0].valeurs[1])}), sens inconnu")
        for l, v in zip(ecran[1:], sections, strict=True):
            if len(v) > 2:
                conv.non_repris.append(f"ligne {l.numero} : valeurs {', '.join(_f(x) for x in v[2:])} de la section d'écran "
                                       "(après cote et EI), sens inconnu")
        ei = {x[1] for x in sections if len(x) > 1 and x[1] is not None}
        if len(ei) > 1:
            conv.non_repris.append(f"écran à EI variable ({', '.join(_f(e) for e in sorted(ei))}) : seul le 1er tronçon est repris")
        if paroi["EI"] is None and not any("EI" in e for e in erreurs):
            erreurs.append(f"ligne {ecran[1].numero} : EI de l'écran manquant")
        conv.hypotheses.append("EI en kN·m²/m et par mètre d'écran (EI = 2,1·I/esp dans le fichier fourni)")

    # Terrain et couches
    tn = vals(terrain)[0] if terrain else None
    if terrain:
        conv.repris += 1
    else:
        erreurs.append("cote du terrain (ligne d'une seule valeur après l'écran) absente")
    cols = _colonnes(table, "couches", COLONNES_COUCHE)
    premiere = (table.get("couches") or {}).get("premiere_valeur", "base")
    sol = []
    lus = []
    for l in couches:
        v = vals(l)
        d = {c: (v[i] if i < len(v) else None) for i, c in enumerate(cols) if c}
        if len(v) > len(cols):
            conv.non_repris.append(f"ligne {l.numero} : valeurs en trop après les {len(cols)} colonnes de la couche")
        lus.append((l, d))
        conv.repris += 1
    en_toit = premiere == "toit" or (lus and tn is not None and lus[0][1].get("base") is not None
                                     and abs(lus[0][1]["base"] - tn) < 1e-6)
    if en_toit and premiere != "toit":
        conv.hypotheses.append("1re valeur des couches égale à la cote du terrain : lue comme cote du toit de chaque couche")
    toit = tn
    for i, (l, d) in enumerate(lus):
        c_toit = d.get("base") if en_toit else toit
        couche = {"nom": f"Couche {i + 1}", "toit": c_toit, "gamma": d.get("gamma"), "gamma_dejauge": d.get("gamma_dejauge"),
                  "phi": d.get("phi"), "c": d.get("c") or 0.0}
        for cle in ("gamma", "gamma_dejauge", "phi"):
            if couche[cle] is None and not l.erreurs:
                erreurs.append(f"ligne {l.numero} : {cle} de la couche {i + 1} manquant")
        if d.get("k0"):
            couche["K0"] = d["k0"]
        for cle in ("ka", "kp"):
            if d.get(cle):
                conv.non_repris.append(f"ligne {l.numero} : {cle} = {_f(d[cle])} imposé, K-Retain recalcule {cle} à partir de φ et δ")
        couche["delta_a_sur_phi"] = round(_ratio_delta(d.get("delta_a"), d.get("phi")), 6)
        couche["delta_p_sur_phi"] = round(_ratio_delta(d.get("delta_p"), d.get("phi")), 6)
        if d.get("kh") is not None:
            couche["kh"] = round(d["kh"], 2)
        elif not l.erreurs:
            erreurs.append(f"ligne {l.numero} : kh de la couche {i + 1} manquant")
        if couche["delta_p_sur_phi"] > 1 / 3 + 1e-9:
            conv.hypotheses.append(f"couche {i + 1} : δp/φ = {_f(couche['delta_p_sur_phi'])} > 1/3 : K-Retain refuse la butée de "
                                   "Coulomb au-delà (côté insécurité) ; il faut les tables de Kérisel-Absi (docs/normes/kerisel_absi)")
        sol.append(couche)
        toit = d.get("base")
    if couches:
        conv.hypotheses.append("couches : " + ", ".join(c for c in cols if c) + " (docs/rido/correspondance.yaml, à confirmer)")
        conv.hypotheses.append("ka, k0, kp nuls = calcul automatique ; K-Retain : Ka, Kp de Coulomb (Rankine si δ = 0), K0 de Jaky")
    else:
        erreurs.append("aucune couche de sol lue")

    # Nappe
    eau = {}
    if nappe is not None:
        v = vals(nappe)
        conv.repris += 1
        if v and v[0] is not None:
            eau = {"rido": {"amont": v[0], "aval": v[0]}}
            conv.hypotheses.append("nappe au même niveau des deux côtés, régime hydrostatique, écran étanche (pressions d'eau "
                                   "des deux côtés comme données)")
        if len(v) > 1:
            conv.non_repris.append(f"ligne {nappe.numero} : 2e valeur de la ligne de nappe ({_f(v[1])}), sens inconnu")

    # Commandes et phases
    phases: list[dict] = []
    surcharges: list[dict] = []
    zones: list[dict] = []
    actions: dict = {}
    aval = tn
    amont = tn
    mel = pondere = False
    noms: set[str] = set()
    for c in commandes:
        v = vals(c)
        a = c.arguments
        cote = int(a[0]) if a and a[0] is not None else None
        if c.commande == "sub":
            d = dict(zip(_colonnes(table, "sub", COLONNES_SUB), v, strict=False))
            if None in (d.get("debut"), d.get("q")) or (d.get("fin") is None and d.get("largeur") is None):
                erreurs.append(f"ligne {c.numero} : surcharge sub incomplète")
                continue
            largeur = d["fin"] - d["debut"] if d.get("fin") is not None else d["largeur"]
            surcharges.append({"nom": f"sub{len(surcharges) + 1}", "type": "bande", "q": d["q"], "distance": d["debut"],
                               "largeur": largeur, "cote": d.get("cote", tn), "cote_ecran": "aval" if cote == 2 else "amont",
                               "phase": len(phases) + 1})
            conv.hypotheses.append(f"ligne {c.numero} : sub = bande de Boussinesq ({', '.join(d)}) appliquée à la phase "
                                   f"{len(phases) + 1}")
        elif c.commande == "coe":
            d = dict(zip(_colonnes(table, "coe", COLONNES_COE), v, strict=False))
            if None in (d.get("haut"), d.get("bas"), d.get("rapport")):
                erreurs.append(f"ligne {c.numero} : coe incomplet")
                continue
            zones.append({"haut": max(d["haut"], d["bas"]), "bas": min(d["haut"], d["bas"]), "rapport": round(d["rapport"], 6)})
            conv.hypotheses.append(f"ligne {c.numero} : coe = pressions et kh multipliés par {_f(d['rapport'])} entre "
                                   f"{_f(d['bas'])} et {_f(d['haut'])} m, des deux côtés"
                                   + (" (commande après un calcul : appliquée à toutes les phases)" if phases else ""))
        elif c.commande == "ber":
            z = v[0] if v else None
            if z is None or cote not in (1, 2):
                erreurs.append(f"ligne {c.numero} : ber incomplet (côté et cote)")
                continue
            if cote == 2 and (aval is None or z <= aval):
                actions["excaver"], aval = z, z
            elif cote == 2:
                actions["remblayer"], aval = {**actions.get("remblayer", {}), "aval": z}, z
            elif amont is not None and z > amont:
                actions["remblayer"], amont = {**actions.get("remblayer", {}), "amont": z}, z
            else:
                conv.non_repris.append(f"ligne {c.numero} : terrassement côté 1 (terres retenues) non repris")
                continue
        elif c.commande == "tel":
            mel = len(a) > 1 and a[1] == 1
        elif c.commande == "fap":
            facteurs = [x for x in v + [y for s in c.suites for y in vals(s)] if x is not None]
            pondere = any(abs(x - 1.0) > 1e-12 for x in facteurs)
        elif c.commande == "cal":
            titre = c.titre or f"Calcul {len(phases) + 1}"
            if mel or pondere:
                raison = "calcul à l'équilibre limite (tel)" if mel else "calcul pondéré (fap)"
                conv.calculs_non_repris.append(f"« {titre} » (ligne {c.numero}) : {raison} ; K-Retain fait ses propres "
                                               "vérifications ELU (docs/normes)")
                continue
            nom_ph = titre
            k = 2
            while nom_ph in noms:
                nom_ph, k = f"{titre} ({k})", k + 1
            noms.add(nom_ph)
            phases.append({"nom": nom_ph, **actions})
            actions = {}
        else:
            conv.non_repris.append(f"ligne {c.numero} : commande « {c.texte[:60]} » non reprise (sens inconnu)")
            continue
        conv.repris += 1
        for s in c.suites:
            if c.commande != "fap":
                conv.non_repris.append(f"ligne {s.numero} : « {s.texte[:60]} » après « {c.commande} », non reprise")
    if actions:
        conv.non_repris.append(f"actions sans calcul « cal » final, non reprises : {', '.join(actions)}")
    if not phases:
        erreurs.append("aucun calcul « cal » repris : pas de phase")
    if zones:
        paroi["type"] = "berlinoise"
        paroi["coefficients_largeur"] = zones

    script: dict = {"projet": lec.titre, "calcul": {"kh": "impose"}, "paroi": paroi, "sol": sol}
    if eau:
        script["eau"] = eau
    if surcharges:
        script["surcharges"] = surcharges
    script["phases"] = phases
    conv.script = script

    flux = StringIO()
    y = YAML()
    y.default_flow_style = None
    y.width = 120
    y.dump(script, flux)
    entete = [f"Script converti depuis RIDO ({nom}) : {lec.titre}",
              "Lecture du format : docs/rido/correspondance.yaml (interprétations à confirmer). Vérifiez chaque bloc."]
    entete += [f"Commentaire RIDO : {c}" for c in lec.commentaires if c]
    entete += [f"MANQUANT : {e}" for e in erreurs]
    entete += [f"Non repris : {n}" for n in conv.non_repris]
    entete += [f"Calcul non repris : {n}" for n in conv.calculs_non_repris]
    entete += [f"Hypothèse : {h}" for h in conv.hypotheses]
    conv.texte = "".join(f"# {e}\n" for e in entete) + flux.getvalue()
    return conv


def _f(x: float | None) -> str:
    return "?" if x is None else f"{x:.6g}".replace(".", ",")
