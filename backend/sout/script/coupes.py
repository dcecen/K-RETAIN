"""Coupes de calcul d'un projet 2D : plusieurs calculs 2D placés en plan.

Chaque coupe hérite du script principal (sol, paroi, eau, appuis, phases…) et ne redéfinit
que ce qui change (bloc `script` en ligne ou fichier). La fusion est faite clé par clé au
premier niveau : une clé présente dans la coupe remplace entièrement celle du principal
(une liste de couches locale remplace toute la liste). Le bloc `coupes` n'est jamais repris
dans une coupe ; le bloc `plan` (contour, côtés, appuis en plan) est toujours celui du principal.

Fonctions pures : aucun calcul ici, seulement la préparation (textes fusionnés, empreintes,
tronçons de paroi, phasage projet) et la synthèse des vérifications de toutes les coupes.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from .schema import Script

RACINE = Path(__file__).resolve().parents[3]
DOSSIER_SCRIPTS = RACINE / "exemples"
RECTANGLE_DEFAUT = [[0.0, 0.0], [20.0, 0.0], [20.0, 12.0], [0.0, 12.0]]
CLES_NON_HERITEES = ("coupes",)


class ErreurCoupe(Exception):
    pass


@dataclass
class CoupePreparee:
    nom: str
    k: int                       # arête du contour
    de: float                    # abscisse locale de début (m)
    a: float                     # abscisse locale de fin (m)
    trace: list[list[float]]     # [[x0, y0], [x1, y1]]
    texte: str                   # script YAML complet de la coupe (fusionné)
    empreinte: str               # hachage du script fusionné (cache)
    herite: list[str] = field(default_factory=list)
    local: list[str] = field(default_factory=list)
    automatique: bool = False     # coupe créée par calcul.coupes_automatiques (une par côté du contour)

    def vers_dict(self) -> dict:
        return {"nom": self.nom, "zone": {"k": self.k, "de": self.de, "a": self.a}, "trace": self.trace,
                "empreinte": self.empreinte, "herite": self.herite, "local": self.local, "automatique": self.automatique}


@dataclass
class Projet:
    coupes: list[CoupePreparee]
    contour: list[list[float]]
    orphelins: list[dict]
    avertissements: list[str]
    unique: bool                  # script sans bloc coupes : une coupe sur toute la paroi


# ---------------------------------------------------------------------------
# lecture et fusion
# ---------------------------------------------------------------------------
def _charger(texte: str) -> dict:
    yaml = YAML(typ="safe")
    d = yaml.load(StringIO(texte))
    if not isinstance(d, dict):
        raise ErreurCoupe("script de coupe : bloc de mots-clés attendu")
    return d


def _dumper(d: dict) -> str:
    yaml = YAML(typ="safe")
    yaml.default_flow_style = False
    yaml.allow_unicode = True
    yaml.width = 120
    out = StringIO()
    yaml.dump(d, out)
    return out.getvalue()


def empreinte(texte: str) -> str:
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()[:24]


def fusionner(principal: dict, local: dict | None) -> tuple[dict, list[str], list[str]]:
    """Script fusionné, clés héritées, clés locales. La clé `coupes` est retirée ; `plan` et `geometrie` viennent
    toujours du principal."""
    base = {k: v for k, v in principal.items() if k not in CLES_NON_HERITEES}
    local = {k: v for k, v in (local or {}).items() if k not in CLES_NON_HERITEES and k not in ("plan", "geometrie")}
    fusion = {**base, **local}
    herite = sorted(k for k in base if k not in local)
    return fusion, herite, sorted(local)


def chemin_script_coupe(script: str, nom: str) -> Path:
    """Fichier de script d'une coupe : chemin relatif, sans « .. », dans le dossier exemples (le serveur
    ne lit aucun autre fichier du poste)."""
    chemin = Path(str(script))
    if chemin.is_absolute() or ".." in chemin.parts or str(script).startswith(("\\\\", "//")):
        raise ErreurCoupe(f"coupe « {nom} » : le script doit être un fichier du dossier exemples "
                          f"(chemin relatif sans « .. »), reçu « {script} »")
    racine = DOSSIER_SCRIPTS.resolve()
    complet = (racine / chemin).resolve()
    if not complet.is_relative_to(racine):
        raise ErreurCoupe(f"coupe « {nom} » : le script doit rester dans le dossier exemples, reçu « {script} »")
    if not complet.is_file():
        raise ErreurCoupe(f"coupe « {nom} » : fichier {script} introuvable (cherché dans {DOSSIER_SCRIPTS})")
    return complet


def _script_local(c, nom: str) -> dict | None:
    if c.script is None:
        return None
    if isinstance(c.script, dict):
        return c.script
    chemin = chemin_script_coupe(c.script, nom)
    try:
        return _charger(chemin.read_text(encoding="utf-8"))
    except YAMLError as e:
        raise ErreurCoupe(f"coupe « {nom} » : fichier {c.script} illisible ({e})") from None


# ---------------------------------------------------------------------------
# géométrie en plan
# ---------------------------------------------------------------------------
def _aretes(contour: list[list[float]]) -> list[dict]:
    """Arêtes orientées du contour (géométrie partagée sout.plan.geometrie : k, A, B, L, t, ni, s0)."""
    from ..plan.geometrie import aretes
    return aretes(contour)


def _trace_defaut(ar: dict, de: float, a: float, longueur: float) -> list[list[float]]:
    """Segment perpendiculaire au milieu du tronçon, de l'extérieur (terre) vers l'intérieur (fouille)."""
    sm = 0.5 * (de + a)
    px, py = ar["A"][0] + ar["t"][0] * sm, ar["A"][1] + ar["t"][1] * sm
    nx, ny = ar["ni"]
    return [[round(px - nx * longueur, 3), round(py - ny * longueur, 3)], [round(px + nx * longueur, 3), round(py + ny * longueur, 3)]]


def _abscisse_trace(ar: dict, trace: list[list[float]], de: float, a: float) -> float:
    """Abscisse du point où la trace coupe le côté (sinon le milieu du tronçon)."""
    (px, py), (qx, qy) = trace
    dx, dy = qx - px, qy - py
    ex, ey = ar["B"][0] - ar["A"][0], ar["B"][1] - ar["A"][1]
    den = dx * ey - dy * ex
    if abs(den) < 1e-9:
        return 0.5 * (de + a)
    wx, wy = ar["A"][0] - px, ar["A"][1] - py
    u = (wx * dy - wy * dx) / den
    sl = u * ar["L"]
    return sl if de - 1e-6 <= sl <= a + 1e-6 else 0.5 * (de + a)


def _resoudre_zone(c, s: Script, aretes: list[dict]) -> tuple[int, float, float]:
    p = c.zone.paroi
    if isinstance(p, str):
        cotes = s.plan.cotes if s.plan else {}
        if p not in cotes:
            raise ErreurCoupe(f"coupe « {c.nom} » : côté « {p} » inconnu (plan.cotes)")
        k = cotes[p]
    else:
        k = int(p)
    if not 0 <= k < len(aretes):
        raise ErreurCoupe(f"coupe « {c.nom} » : arête {k} hors du contour")
    L = aretes[k]["L"]
    de = 0.0 if c.zone.de is None else max(0.0, min(L, c.zone.de))
    a = L if c.zone.a is None else max(0.0, min(L, c.zone.a))
    if a <= de:
        raise ErreurCoupe(f"coupe « {c.nom} » : tronçon vide (de = {de}, a = {a})")
    return k, de, a


def tronçons_orphelins(aretes: list[dict], coupes: list[CoupePreparee]) -> list[dict]:
    out = []
    for ar in aretes:
        if ar["L"] <= 0:
            continue
        inter = sorted((c.de, c.a) for c in coupes if c.k == ar["k"])
        pos = 0.0
        for de, a in inter:
            if de > pos + 0.01:
                out.append({"k": ar["k"], "de": round(pos, 3), "a": round(de, 3)})
            pos = max(pos, a)
        if pos < ar["L"] - 0.01:
            out.append({"k": ar["k"], "de": round(pos, 3), "a": round(ar["L"], 3)})
    return out


# ---------------------------------------------------------------------------
# préparation du projet
# ---------------------------------------------------------------------------
def position_coupe(ar: dict, sl: float, nom: str | None, cotes: dict) -> dict:
    """Bloc `coupe_calcul` : point de la coupe sur la paroi, normale vers la fouille, tangente, côté nommé."""
    nom_cote = next((n for n, k in cotes.items() if k == ar["k"]), None)
    return {"x": round(ar["A"][0] + ar["t"][0] * sl, 4), "y": round(ar["A"][1] + ar["t"][1] * sl, 4),
            "ni": [round(ar["ni"][0], 6), round(ar["ni"][1], 6)], "t": [round(ar["t"][0], 6), round(ar["t"][1], 6)],
            "k": ar["k"], "s": round(sl, 4), "cote": nom_cote, "nom": nom}


def _surcharges_en_plan(s: Script) -> bool:
    toutes = list(s.surcharges) + [sc for ph in s.phases for sc in (ph.ajouter_surcharges or [])]
    return any(sc.type in ("rectangulaire", "ponctuelle", "lineaire") or sc.cote_paroi is not None or sc.emprise is not None for sc in toutes)


def _donnees_par_cote(s: Script) -> bool:
    """Des données dépendent du côté ou de la position : surcharges en plan, zones, objets de terrain ou pente
    rattachés à certains côtés ou tronçons. Sans elles, toutes les coupes d'un contour seraient identiques."""
    from ..geometrie.normaliser import depuis_script
    return _surcharges_en_plan(s) or depuis_script(s).varie()


def _coupes_automatiques(s: Script, principal: dict, aretes: list[dict], contour) -> Projet:
    """Coupes 2D automatiques : avec le bloc geometrie, une coupe par tronçon homogène du contour (bornes des
    étendues des zones, objets et positions) ; sinon une coupe par côté. Chaque coupe est rapportée au milieu de
    son tronçon ; le projet est un projet à coupes."""
    from ..geometrie.decoupage import troncons_automatiques
    from ..geometrie.normaliser import depuis_script
    cotes = s.plan.cotes if s.plan else {}
    noms = {k: n for n, k in cotes.items()}
    local = sorted(k for k in principal if k not in CLES_NON_HERITEES)
    par_k = {ar["k"]: ar for ar in aretes}
    if s.geometrie is not None:
        troncons = troncons_automatiques(depuis_script(s))
    else:
        troncons = [(ar["k"], 0.0, ar["L"]) for ar in aretes if ar["L"] > 1e-9]
    coupes = []
    for k, de, a in troncons:
        ar = par_k[k]
        entier = de <= 1e-9 and a >= ar["L"] - 1e-9
        nom = f"Auto — côté {noms.get(k, k)}" + ("" if entier else f" ({de:g} à {a:g} m)")
        trace = _trace_defaut(ar, de, a, min(8.0, max(4.0, 0.3 * (a - de))))
        txt = _dumper({**principal, "coupe_calcul": position_coupe(ar, 0.5 * (de + a), nom, cotes)})
        coupes.append(CoupePreparee(nom, k, float(de), float(a), trace, txt, empreinte(txt), [], local, automatique=True))
    avert = [f"Coupes automatiques : {len(coupes)} coupes 2D ({'une par tronçon homogène' if s.geometrie is not None else 'une par côté'} "
             "du contour, surcharges et objets de terrain rapportés au milieu de chaque tronçon) ; les effets d'angle de la "
             "fouille ne sont pas calculés."]
    return Projet(coupes, contour, [], avert, False)


def preparer(texte: str, s: Script) -> Projet:
    """Coupes du projet, prêtes à calculer : textes fusionnés, tronçons, trace, avertissements."""
    contour = s.plan.contour if s.plan else RECTANGLE_DEFAUT
    aretes = _aretes(contour)
    principal = _charger(texte)
    if not s.coupes:
        txt = texte
        avert = []
        if s.plan is not None and s.coupe_calcul is None and _donnees_par_cote(s):
            if (s.calcul.coupes_automatiques or s.geometrie is not None) and s.calcul.mode != "pseudo3d":
                return _coupes_automatiques(s, principal, aretes, contour)
            # coupe unique rapportée au milieu du côté le plus long pour localiser les données dépendant du côté
            ar = max(aretes, key=lambda a: a["L"])
            txt = _dumper({**principal, "coupe_calcul": position_coupe(ar, ar["L"] / 2, "Coupe unique", s.plan.cotes)})
            if s.calcul.mode == "pseudo3d":
                avert.append(f"Calcul 2D d'accompagnement : coupe unique au milieu du côté {ar['k']} ; le pseudo-3D rapporte "
                             "les surcharges en plan et les objets de terrain à chaque ligne verticale du contour.")
            else:
                avert.append(f"Coupe unique : les surcharges et objets de terrain rattachés à un côté sont rapportés au milieu "
                             f"du côté {ar['k']} et le même profil est affiché sur toute la paroi. Pour un profil par côté : "
                             "calcul.coupes_automatiques: true (une coupe 2D par côté), un bloc coupes, ou calcul.mode: pseudo3d.")
        c0 = CoupePreparee(nom="Coupe unique", k=-1, de=0.0, a=0.0, trace=[], texte=txt, empreinte=empreinte(txt),
                           herite=[], local=sorted(k for k in principal if k not in CLES_NON_HERITEES))
        return Projet([c0], contour, [], avert, True)
    coupes = []
    for c in s.coupes:
        k, de, a = _resoudre_zone(c, s, aretes)
        fusion, herite, local = fusionner(principal, _script_local(c, c.nom))
        trace = [list(c.trace.de), list(c.trace.a)] if c.trace else _trace_defaut(aretes[k], de, a, min(8.0, max(4.0, 0.3 * aretes[k]["L"])))
        fusion["coupe_calcul"] = position_coupe(aretes[k], _abscisse_trace(aretes[k], trace, de, a), c.nom, s.plan.cotes if s.plan else {})
        txt = _dumper(fusion)
        coupes.append(CoupePreparee(c.nom, k, de, a, trace, txt, empreinte(txt), herite, local))
    orphelins = tronçons_orphelins(aretes, coupes)
    avert = []
    for o in orphelins:
        avert.append(f"Tronçon de paroi sans coupe de calcul : côté {o['k']}, de {o['de']:.1f} à {o['a']:.1f} m "
                     "(affiché en gris hachuré dans la maquette).")
    if len(coupes) > 1 or any(ar["L"] > 0 for ar in aretes if len(aretes) > 2):
        avert.append("Projet à coupes 2D : les effets d'angle de la fouille ne sont pas calculés "
                     "(chaque coupe est un calcul plan indépendant).")
    return Projet(coupes, contour, orphelins, avert, False)


# ---------------------------------------------------------------------------
# phasage projet et synthèse
# ---------------------------------------------------------------------------
def phasage_projet(phases_par_coupe: list[list[str]]) -> tuple[list[str], list[list[int]]]:
    """Liste ordonnée commune des phases (réunion par nom, ordre d'apparition) et, pour chaque coupe,
    l'indice projet de chacune de ses phases. Correspondance par nom ; une phase au nom nouveau est
    insérée juste avant la première phase suivante de sa coupe déjà connue du projet (sinon à la fin)."""
    projet: list[str] = []
    for noms in phases_par_coupe:
        for i, nom in enumerate(noms):
            if nom in projet:
                continue
            suivant = next((projet.index(n) for n in noms[i + 1:] if n in projet), len(projet))
            projet.insert(suivant, nom)
    corr = [[projet.index(n) for n in noms] for noms in phases_par_coupe]
    return projet, corr


_ORDRE_ETAT = {"non_ok": 3, "attention": 2, "ok": 1, "non_verifiable": 0}


def _score_synthese(v: dict) -> float:
    """Même règle que sout.verifs.score_defaveur : taux chiffré, sinon un non_ok sans taux passe devant
    tout, un non vérifiable derrière tout."""
    if v.get("taux") is not None:
        return float(v["taux"])
    return {"non_ok": float("inf"), "attention": 1.0, "ok": 0.0}.get(v["etat"], -1.0)


def synthese_projet(verifs_par_coupe: dict[str, list[dict]]) -> list[dict]:
    """Pour chaque vérification (nom + élément), la coupe la plus défavorable : taux maximal,
    sinon l'état le plus grave. Chaque ligne indique la coupe retenue."""
    lignes: dict[tuple[str, str], dict] = {}
    for coupe, verifs in verifs_par_coupe.items():
        for v in verifs:
            cle = (v["nom"], v["element"])
            cand = {"nom": v["nom"], "element": v["element"], "categorie": v.get("categorie"), "coupe": coupe,
                    "taux": v.get("taux"), "etat": v["etat"], "phase": v.get("phase"), "detail": v.get("detail", "")}
            cur = lignes.get(cle)
            if cur is None or _score_synthese(cand) > _score_synthese(cur):
                lignes[cle] = cand
    return list(lignes.values())


def chiffres_cles(resultats_par_coupe: dict[str, dict]) -> dict:
    """Pires valeurs dimensionnantes du projet avec la coupe d'origine."""
    out: dict = {}
    for coupe, r in resultats_par_coupe.items():
        d = r.get("dimensionnant") or {}
        for cle, champ, f in (("deplacement", "valeur_mm", abs), ("moment_positif", "valeur", lambda x: x),
                               ("moment_negatif", "valeur", lambda x: -x), ("tranchant", "valeur", abs)):
            v = d.get(cle)
            if not v:
                continue
            cur = out.get(cle)
            if cur is None or f(v[champ]) > f(cur[champ]):
                out[cle] = {**v, "coupe": coupe}
        for nom, a in (d.get("appuis") or {}).items():
            cur = out.setdefault("appuis", {}).get(nom)
            if cur is None or a["effort_kN_m"] > cur["effort_kN_m"]:
                out["appuis"][nom] = {**a, "coupe": coupe}
    return out


def vers_json(o) -> str:
    return json.dumps(o, ensure_ascii=False, sort_keys=True)
