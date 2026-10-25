"""Lecture et validation d'un script RetainWall.

Le YAML est lu avec ruamel.yaml (mode aller-retour) pour garder le numéro de
ligne de chaque clé ; les erreurs du schéma pydantic sont traduites en
français et rattachées à leur ligne.

Un mot-clé inconnu n'empêche pas le calcul : il est ignoré et signalé comme
avertissement (niveau « avertissement », ligne et chemin), pour que des
informations descriptives ou une clé mal orthographiée ne bloquent pas l'accès
aux résultats. Toute autre erreur (mot-clé obligatoire manquant, valeur hors
bornes, type incorrect, contrôle de cohérence) reste bloquante.
"""
from __future__ import annotations

from dataclasses import dataclass
from io import StringIO

from pydantic import ValidationError
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.error import MarkedYAMLError, YAMLError

from .schema import Plan, Script


@dataclass
class ErreurScript:
    ligne: int | None
    chemin: str
    message: str
    niveau: str = "erreur"          # "erreur" (bloque le calcul) ou "avertissement" (n'empêche pas le calcul)

    def __str__(self) -> str:
        pos = f"ligne {self.ligne}" if self.ligne else "script"
        return f"{pos} ({self.chemin}) : {self.message}" if self.chemin else f"{pos} : {self.message}"

    def vers_dict(self) -> dict:
        return {"ligne": self.ligne, "chemin": self.chemin, "message": self.message, "niveau": self.niveau}


class ScriptInvalide(Exception):
    def __init__(self, erreurs: list[ErreurScript]):
        self.erreurs = erreurs
        super().__init__("\n".join(str(e) for e in erreurs))


def _python(noeud):
    """Arbre ruamel -> objets Python simples."""
    if isinstance(noeud, CommentedMap):
        return {str(k): _python(v) for k, v in noeud.items()}
    if isinstance(noeud, CommentedSeq):
        return [_python(v) for v in noeud]
    if isinstance(noeud, bool) or noeud is None:
        return noeud
    if isinstance(noeud, int):
        return int(noeud)
    if isinstance(noeud, float):
        return float(noeud)
    if isinstance(noeud, str):
        return str(noeud)
    return noeud


def ligne_de(arbre, chemin: tuple) -> int | None:
    """Numéro de ligne (1 = première) de l'élément désigné par `chemin`.

    S'arrête au dernier élément existant (clé manquante -> ligne du parent).
    """
    ligne = None
    noeud = arbre
    for cle in chemin:
        if isinstance(noeud, CommentedMap) and cle in noeud:
            ligne = noeud.lc.key(cle)[0] + 1
            noeud = noeud[cle]
        elif isinstance(noeud, CommentedSeq) and isinstance(cle, int) and 0 <= cle < len(noeud):
            ligne = noeud.lc.item(cle)[0] + 1
            noeud = noeud[cle]
        elif isinstance(noeud, (CommentedMap, CommentedSeq)):
            # étiquette technique de pydantic (ex. « list[str] ») : on l'ignore
            continue
        else:
            break
    if ligne is None and isinstance(arbre, CommentedMap) and hasattr(arbre, "lc"):
        ligne = arbre.lc.line + 1
    return ligne


_TRADUCTIONS = {
    "missing": "mot-clé obligatoire manquant",
    "extra_forbidden": "mot-clé inconnu (vérifiez l'orthographe)",
    "float_parsing": "nombre attendu",
    "float_type": "nombre attendu",
    "int_parsing": "nombre entier attendu",
    "int_type": "nombre entier attendu",
    "string_type": "texte attendu",
    "bool_parsing": "true ou false attendu",
    "bool_type": "true ou false attendu",
    "list_type": "liste attendue (lignes commençant par « - »)",
    "dict_type": "bloc de mots-clés attendu",
    "model_type": "bloc de mots-clés attendu",
    "model_attributes_type": "bloc de mots-clés attendu",
}


def _message(err: dict) -> str:
    t = err["type"]
    ctx = err.get("ctx", {}) or {}
    if t in _TRADUCTIONS:
        return _TRADUCTIONS[t]
    if t == "greater_than":
        return f"doit être strictement supérieur à {ctx.get('gt')}"
    if t == "greater_than_equal":
        return f"doit être supérieur ou égal à {ctx.get('ge')}"
    if t == "less_than":
        return f"doit être strictement inférieur à {ctx.get('lt')}"
    if t == "less_than_equal":
        return f"doit être inférieur ou égal à {ctx.get('le')}"
    if t == "literal_error":
        return f"valeur non autorisée ; valeurs possibles : {ctx.get('expected', '')}".replace("'", "")
    if t == "too_short":
        return f"au moins {ctx.get('min_length')} élément(s) attendu(s)"
    return err.get("msg", t)


def _chemin_lisible(loc: tuple, donnees) -> str:
    parties = []
    noeud = donnees
    for c in loc:
        if isinstance(noeud, dict) and c in noeud:
            parties.append(str(c)); noeud = noeud[c]
        elif isinstance(noeud, list) and isinstance(c, int) and c < len(noeud):
            parties.append(f"[{c + 1}]"); noeud = noeud[c]
        elif isinstance(c, str) and isinstance(noeud, dict):
            if "[" in c or c in ("str", "float", "int", "bool"):
                continue
            parties.append(c); noeud = None
        else:
            continue
    return ".".join(parties).replace(".[", "[")


def _controles(s: Script) -> list[tuple[tuple, str]]:
    """Contrôles de cohérence entre blocs (renvoie (chemin, message))."""
    e: list[tuple[tuple, str]] = []
    if s.paroi.tete <= s.paroi.pied:
        e.append((("paroi", "pied"), "le pied doit être sous la tête"))
    # étanchéité de l'écran : « partielle » exige k_paroi, une épaisseur traversée et le régime differences_finies
    from ..parois.etancheite import epaisseur_hydraulique_de, etancheite_de
    et = etancheite_de(s.paroi)
    if et == "partielle":
        if s.paroi.k_paroi is None:
            e.append((("paroi", "etancheite"), "étanchéité partielle : donnez paroi.k_paroi (m/s), perméabilité équivalente de l'écran"))
        if epaisseur_hydraulique_de(s.paroi) is None:
            e.append((("paroi", "etancheite"), "étanchéité partielle : épaisseur traversée inconnue, donnez paroi.epaisseur_hydraulique (m)"))
        if (s.hydraulique.regime if s.hydraulique is not None else "hydrostatique") != "differences_finies":
            e.append((("paroi", "etancheite"), "étanchéité partielle : seul le régime hydraulique differences_finies calcule le passage "
                                               "de l'eau à travers l'écran (bloc hydraulique)"))
    elif s.paroi.k_paroi is not None or s.paroi.epaisseur_hydraulique is not None:
        e.append((("paroi", "k_paroi"), f"k_paroi / epaisseur_hydraulique sans effet : l'écran est « {et} » "
                                        "(paroi.etancheite: partielle pour les prendre en compte)"))
    toits = [c.toit for c in s.sol]
    if len(set(toits)) != len(toits):
        e.append((("sol",), "deux couches ont le même toit"))
    for i, c in enumerate(s.sol):
        if c.kh is not None:
            continue
        if s.calcul.kh == "impose":
            e.append((("sol", i, "nom"), f"couche « {c.nom} » : kh imposé manquant (calcul.kh = impose)"))
        elif c.alpha is None or (c.EM is None and (c.qc is None or c.EM_sur_qc is None)):
            e.append((("sol", i, "nom"),
                      f"couche « {c.nom} » : Schmitt demande α et EM (ou qc avec EM_sur_qc), ou un kh imposé"))
    if s.calcul.jeu_eau is not None and s.calcul.jeu_eau not in s.eau:
        e.append((("calcul", "jeu_eau"), f"jeu d'eau « {s.calcul.jeu_eau} » absent du bloc eau"))
    for i, sc in enumerate(s.surcharges):
        if sc.type == "bande" and sc.largeur is None:
            e.append((("surcharges", i, "type"), "surcharge en bande : largeur obligatoire"))
    for nom, a in s.appuis.items():
        if not s.paroi.pied <= a.cote <= s.paroi.tete:
            e.append((("appuis", nom, "cote"), f"appui {nom} hors de la paroi"))
        if a.raideur is None and a.element is None and (a.E is None or a.A is None) and not (a.type == "dalle" and a.epaisseur):
            e.append((("appuis", nom), f"appui {nom} : donnez raideur, element, ou E et A"))
        if a.raideur is None and a.type in ("buton", "bracon", "dalle") and a.longueur is None:
            e.append((("appuis", nom), f"appui {nom} : longueur obligatoire pour calculer la raideur"))
        if a.raideur is None and a.type == "tirant" and a.longueur_libre is None and a.longueur_elastique is None:
            e.append((("appuis", nom), f"tirant {nom} : longueur_libre obligatoire"))
    noms_surcharges = {sc.nom for sc in s.surcharges if sc.nom}
    noms_phases = [ph.nom for ph in s.phases]
    for i, n in enumerate(noms_phases):
        if n in noms_phases[:i]:
            e.append((("phases", i, "nom"), f"plusieurs phases s'appellent « {n} » : renommez-les "
                                            "(les résultats, les coupes et le pseudo-3D repèrent les phases par leur nom)"))
    parents: list[int] = []   # indice du parent (−1 = état initial)
    for i, ph in enumerate(s.phases):
        if ph.depuis is None:
            parents.append(i - 1)
        elif ph.depuis == "État initial":
            parents.append(-1)
        elif ph.depuis not in noms_phases[:i]:
            e.append((("phases", i, "depuis"), f"phase de départ « {ph.depuis} » inconnue ou postérieure"))
            parents.append(i - 1)
        else:
            if noms_phases[:i].count(ph.depuis) > 1:
                e.append((("phases", i, "depuis"), f"plusieurs phases s'appellent « {ph.depuis} » : renommez-les"))
            parents.append(noms_phases.index(ph.depuis))
    poses_par_phase: list[set[str]] = []
    for i, ph in enumerate(s.phases):
        poses = set(poses_par_phase[parents[i]]) if parents[i] >= 0 else set()
        for cle in ("poser", "deposer"):
            v = getattr(ph, cle)
            for nom in ([v] if isinstance(v, str) else (v or [])):
                if nom not in s.appuis:
                    e.append((("phases", i, cle), f"appui « {nom} » non défini dans le bloc appuis"))
                elif cle == "poser":
                    if nom in poses:
                        e.append((("phases", i, cle), f"appui « {nom} » déjà posé : déposez-le avant de le reposer "
                                                      "(sinon sa mise en charge serait comptée deux fois)"))
                    poses.add(nom)
                elif nom not in poses:
                    e.append((("phases", i, cle), f"appui « {nom} » déposé avant d'avoir été posé"))
                else:
                    poses.discard(nom)
        poses_par_phase.append(poses)
        for sc in ph.ajouter_surcharges or []:
            if sc.nom:
                noms_surcharges.add(sc.nom)
            if sc.type == "bande" and sc.largeur is None:
                e.append((("phases", i, "ajouter_surcharges"), "surcharge en bande : largeur obligatoire"))
        for nom in ph.retirer_surcharges or []:
            if nom not in noms_surcharges:
                e.append((("phases", i, "retirer_surcharges"), f"surcharge « {nom} » inconnue"))
        if ph.excaver is not None:
            valeurs = ph.excaver.values() if isinstance(ph.excaver, dict) else [ph.excaver]
            if any(not s.paroi.pied < v <= s.paroi.tete for v in valeurs):
                e.append((("phases", i, "excaver"), "cote d'excavation hors de la paroi"))
            if isinstance(ph.excaver, dict):
                zones = {z.nom for z in s.geometrie.fouille.zones} if s.geometrie is not None and s.geometrie.fouille is not None else set()
                for cle in ph.excaver:
                    if cle != "defaut" and cle not in zones:
                        e.append((("phases", i, "excaver", cle), f"zone de fond « {cle} » inconnue (geometrie.fouille.zones, ou « defaut »)"))
    if s.hydraulique is not None and s.hydraulique.regime != "hydrostatique":
        for i, c in enumerate(s.sol):
            if c.k_h is None:
                e.append((("sol", i, "nom"), f"couche « {c.nom} » : k_h (m/s) obligatoire avec hydraulique.regime = {s.hydraulique.regime}"))
    if s.hydraulique is not None:
        b = s.hydraulique.bouchon
        if b is not None and b.base >= b.toit:
            e.append((("hydraulique", "bouchon", "base"), "la base du bouchon doit être sous son toit"))
        if b is not None and isinstance(b.phase, str) and b.phase not in noms_phases:
            e.append((("hydraulique", "bouchon", "phase"), f"phase « {b.phase} » inconnue"))
        if b is not None and isinstance(b.phase, int) and not (1 <= b.phase <= max(1, len(s.phases))):
            e.append((("hydraulique", "bouchon", "phase"), f"numéro de phase {b.phase} hors de 1..{len(s.phases)}"))
    for nom, a in s.assemblages.items():
        from ..assemblages.service import REGISTRE
        if a.type not in REGISTRE:
            e.append((("assemblages", nom, "type"), f"type d'assemblage inconnu « {a.type} » (attendu : {', '.join(REGISTRE)})"))
        if a.appui is not None and a.appui not in s.appuis:
            e.append((("assemblages", nom, "appui"), f"appui « {a.appui} » non défini"))
        if a.appui is None and not a.efforts:
            e.append((("assemblages", nom), f"assemblage {nom} : donnez appui ou efforts"))
    if s.plan is not None:
        if len(s.plan.contour) < 3 or any(len(p) != 2 for p in s.plan.contour):
            e.append((("plan", "contour"), "le contour doit compter au moins 3 points [x, y]"))
        for j, ap in enumerate(s.plan.appuis):
            if ap.appui not in s.appuis:
                e.append((("plan", "appuis", j, "appui"), f"appui « {ap.appui} » non défini"))
    e += _controles_geometrie(s)
    o = s.geometrie.ouvrages if s.geometrie is not None else None
    n_aretes = len(s.plan.contour) if s.plan else (len(o.contour) - (0 if o.ferme else 1)) if o is not None else 4
    cotes = s.plan.cotes if s.plan else (o.cotes if o is not None else {})
    toutes = [(("surcharges", i), sc) for i, sc in enumerate(s.surcharges)]
    for j, ph in enumerate(s.phases):
        toutes += [(("phases", j, "ajouter_surcharges", i), sc) for i, sc in enumerate(ph.ajouter_surcharges or [])]
    noms_phases = [p.nom for p in s.phases]
    def _num(ref):
        return noms_phases.index(ref) + 1 if isinstance(ref, str) and ref in noms_phases else (ref if isinstance(ref, int) else None)
    objets = ([(("fouille", "risbermes", i), o) for i, o in enumerate(s.fouille.risbermes)]
              + [(("fouille", "talus", i), o) for i, o in enumerate(s.fouille.talus)]
              + [(("fouille", "gradins", i), o) for i, o in enumerate(s.fouille.gradins)])
    noms_objets = []
    for chemin, o in objets:
        nom = o.nom or f"{chemin[1][:-1].capitalize()}{chemin[2] + 1}"
        if nom in noms_objets:
            e.append((chemin + ("nom",), f"nom « {nom} » en double"))
        noms_objets.append(nom)
        a, b = (_num(o.phases[0]), _num(o.phases[1]))
        for ref, k in zip(o.phases, (a, b)):
            if k is None or not 1 <= k <= len(s.phases):
                e.append((chemin + ("phases",), f"phase « {ref} » inconnue"))
        if a is not None and b is not None and b < a:
            e.append((chemin + ("phases",), "la dernière phase doit suivre la première"))
        if hasattr(o, "cote_crete") and o.cote_pied > o.cote_crete:
            e.append((chemin + ("cote_pied",), "le pied doit être sous la crête"))
        if getattr(o, "methode", "") == "fond_equivalent" and getattr(o, "cote_equivalente", None) is None:
            e.append((chemin + ("cote_equivalente",), "méthode fond_equivalent : cote_equivalente obligatoire (choix de l'ingénieur)"))
        cp = o.cote_paroi
        for c in ([cp] if isinstance(cp, (str, int)) else cp or []):
            if isinstance(c, str) and c != "toutes" and c not in cotes:
                e.append((chemin + ("cote_paroi",), f"côté « {c} » inconnu : déclarez-le dans plan.cotes"))
    for j, ph in enumerate(s.phases):
        tr = ph.terrasser_risberme
        for nom in ([tr] if isinstance(tr, str) else tr or []):
            if nom not in noms_objets:
                e.append((("phases", j, "terrasser_risberme"), f"risberme « {nom} » inconnue"))
    t = s.terrain
    if t.pente_beta is not None and s.sol and abs(t.pente_beta) > min(c.phi for c in s.sol) + 1e-9:
        e.append((("terrain", "pente_beta"), f"β = {t.pente_beta}° dépasse le φ' le plus faible des couches : pas d'équilibre de Coulomb"))
    if t.profil is not None:
        if any(len(p) != 2 for p in t.profil) or any(t.profil[i + 1][0] <= t.profil[i][0] for i in range(len(t.profil) - 1)):
            e.append((("terrain", "profil"), "profil : points [distance, cote] à distances strictement croissantes"))
        elif t.methode_pente == "coulomb_beta" and len(t.profil) > 2 and t.pente_beta is None:
            e.append((("terrain", "methode_pente"), "coulomb_beta demande une pente uniforme : donnez pente_beta ou un profil à deux points"))
    if t.remblai is not None:
        k = _num(t.remblai.phase)
        if k is None or not 1 <= k <= len(s.phases):
            e.append((("terrain", "remblai", "phase"), f"phase « {t.remblai.phase} » inconnue"))
        if t.remblai.materiau is not None and t.remblai.materiau not in [c.nom for c in s.sol]:
            e.append((("terrain", "remblai", "materiau"), f"couche « {t.remblai.materiau} » inconnue dans le bloc sol"))
    positions = {p.surcharge: p for p in (s.geometrie.surcharges if s.geometrie is not None else [])}
    n_sc = 0
    contour_present = s.plan is not None or s.coupe_calcul is not None or (s.geometrie is not None and s.geometrie.ouvrages is not None)
    for chemin, sc in toutes:
        n_sc += 1
        pos = positions.get(sc.nom or f"S{n_sc}")
        position = sc.position if sc.position is not None else (pos.position if pos is not None else None)
        emprise = sc.emprise if sc.emprise is not None else (pos.emprise if pos is not None else None)
        trace = sc.trace if sc.trace is not None else (pos.trace if pos is not None else None)
        if sc.type == "bande" and not sc.largeur:
            e.append((chemin + ("largeur",), "surcharge en bande : largeur obligatoire"))
        if sc.type in ("rectangulaire", "ponctuelle") and position is None:
            e.append((chemin + ("position",), f"surcharge {sc.type} : position [x, y] obligatoire (surcharge ou geometrie.surcharges)"))
        if sc.type == "rectangulaire" and (not isinstance(emprise, list) or len(emprise) != 2):
            e.append((chemin + ("emprise",), "surcharge rectangulaire : emprise [lx, ly] obligatoire (surcharge ou geometrie.surcharges)"))
        if sc.type in ("lineaire", "lineique") and trace is None and position is None and (sc.distance is None):
            e.append((chemin + ("trace",), "surcharge linéaire : trace en plan obligatoire"))
        if sc.type == "lineaire" and trace is None:
            e.append((chemin + ("trace",), "surcharge linéaire en plan : trace {de, a} obligatoire (surcharge ou geometrie.surcharges)"))
        if sc.type == "convoi" and not sc.modele:
            e.append((chemin + ("modele",), "surcharge de type convoi : modèle obligatoire (Bc, Bt…)"))
        if sc.type in ("rectangulaire", "ponctuelle", "lineaire") and not contour_present:
            e.append((chemin + ("type",), f"surcharge {sc.type} : un contour en plan (geometrie.ouvrages ou plan) est nécessaire pour la rapporter à la coupe"))
        cp = sc.cote_paroi
        for nom in ([cp] if isinstance(cp, (str, int)) else cp or []):
            if isinstance(nom, str) and nom != "toutes" and nom not in cotes:
                e.append((chemin + ("cote_paroi",), f"côté « {nom} » inconnu : déclarez-le dans plan.cotes"))
            if isinstance(nom, int) and not 0 <= nom < n_aretes:
                e.append((chemin + ("cote_paroi",), f"numéro d'arête {nom} hors du contour"))
        for cle, refs in (("phase", [sc.phase] if sc.phase is not None else []), ("phases", sc.phases or [])):
            for ref in refs:
                if isinstance(ref, str) and ref not in noms_phases:
                    e.append((chemin + (cle,), f"phase « {ref} » inconnue"))
                if isinstance(ref, int) and not 1 <= ref <= len(s.phases):
                    e.append((chemin + (cle,), f"numéro de phase {ref} hors de la liste (1 à {len(s.phases)})"))
    # côtés du bloc plan (forme ancienne) ; ceux de geometrie.ouvrages sont contrôlés par _controles_geometrie
    for nom, k in (s.plan.cotes.items() if s.plan else ()):
        if not 0 <= k < n_aretes:
            e.append((("plan", "cotes", nom), f"côté « {nom} » : numéro d'arête {k} hors du contour (0 à {n_aretes - 1})"))
    noms_coupes = set()
    for j, c in enumerate(s.coupes):
        if c.nom in noms_coupes:
            e.append((("coupes", j, "nom"), f"nom de coupe « {c.nom} » en double"))
        noms_coupes.add(c.nom)
        p = c.zone.paroi
        if isinstance(p, str) and p not in cotes:
            e.append((("coupes", j, "zone", "paroi"), f"côté « {p} » inconnu : déclarez-le dans plan.cotes"))
        elif isinstance(p, int) and not 0 <= p < n_aretes:
            e.append((("coupes", j, "zone", "paroi"), f"numéro d'arête {p} hors du contour (0 à {n_aretes - 1})"))
        if isinstance(c.script, dict):
            for cle in ("coupes", "plan"):
                if cle in c.script:
                    e.append((("coupes", j, "script", cle), f"le bloc « {cle} » ne peut pas être redéfini dans une coupe"))
            if "projet" in c.script and not isinstance(c.script["projet"], (str, dict)):
                e.append((("coupes", j, "script", "projet"), "projet : texte ou bloc (nom, affaire…) attendu"))
    return e


def _controles_geometrie(s: Script) -> list[tuple[tuple, str]]:
    """Cohérence du bloc geometrie : exclusion avec la forme ancienne, côtés connus, tronçons de < a ≤ L, noms
    uniques, phases des objets, zones de fond nommées, surcharges positionnées existantes."""
    e: list[tuple[tuple, str]] = []
    g = s.geometrie
    if g is None:
        return e
    from ..geometrie.normaliser import forme_ancienne_presente
    anciens = forme_ancienne_presente(s)
    if anciens:
        e.append((("geometrie",), "bloc geometrie et forme ancienne (" + ", ".join(anciens) + ") dans le même script : "
                                   "décrivez toute la géométrie dans geometrie (menu Convertir) ou retirez le bloc geometrie"))
    o = g.ouvrages
    cotes = o.cotes if o is not None else {}
    aretes_L: dict[int, float] = {}
    if o is not None:
        if len(o.contour) < (3 if o.ferme else 2) or any(len(p) != 2 for p in o.contour):
            e.append((("geometrie", "ouvrages", "contour"), "le contour doit compter au moins 3 points [x, y] (2 pour une polyligne ouverte)"))
        else:
            from ..plan.geometrie import aretes
            aretes_L = {ar["k"]: ar["L"] for ar in aretes(o.contour, o.ferme)}
        for nom, k in cotes.items():
            if k not in aretes_L and aretes_L:
                e.append((("geometrie", "ouvrages", "cotes", nom), f"côté « {nom} » : numéro d'arête {k} hors du contour (0 à {len(aretes_L) - 1})"))
        for j, ap in enumerate(o.appuis):
            if ap.appui not in s.appuis:
                e.append((("geometrie", "ouvrages", "appuis", j, "appui"), f"appui « {ap.appui} » non défini"))
    noms_phases = [p.nom for p in s.phases]

    def _num(ref):
        return noms_phases.index(ref) + 1 if isinstance(ref, str) and ref in noms_phases else (ref if isinstance(ref, int) else None)

    def _etendue(chemin: tuple, obj) -> None:
        for c in obj.cotes or []:
            if isinstance(c, str) and c not in cotes:
                e.append((chemin + ("cotes",), f"côté « {c} » inconnu : déclarez-le dans geometrie.ouvrages.cotes"))
            if isinstance(c, int) and aretes_L and c not in aretes_L:
                e.append((chemin + ("cotes",), f"numéro d'arête {c} hors du contour"))
        if obj.de is not None and obj.a is not None and obj.a <= obj.de:
            e.append((chemin + ("a",), "la fin du tronçon (a) doit dépasser son début (de)"))
        if aretes_L and obj.cotes:
            L = min(aretes_L[c if isinstance(c, int) else cotes[c]] for c in obj.cotes if (isinstance(c, int) and c in aretes_L) or (isinstance(c, str) and c in cotes)) if any(
                (isinstance(c, int) and c in aretes_L) or (isinstance(c, str) and c in cotes) for c in obj.cotes) else None
            for cle in ("de", "a"):
                v = getattr(obj, cle)
                if L is not None and v is not None and v > L + 1e-9:
                    e.append((chemin + (cle,), f"{cle} = {v} m au-delà de la longueur du côté ({L:.2f} m)"))

    t = g.terrain
    if t is not None:
        noms_z = set()
        for i, z in enumerate(t.zones):
            ch = ("geometrie", "terrain", "zones", i)
            _etendue(ch, z)
            nom = z.nom or f"terrain{i + 1}"
            if nom in noms_z:
                e.append((ch + ("nom",), f"nom de zone « {nom} » en double"))
            noms_z.add(nom)
            if z.pente_beta is not None and s.sol and abs(z.pente_beta) > min(c.phi for c in s.sol) + 1e-9:
                e.append((ch + ("pente_beta",), f"β = {z.pente_beta}° dépasse le φ' le plus faible des couches : pas d'équilibre de Coulomb"))
            if z.profil is not None and (any(len(p) != 2 for p in z.profil) or any(z.profil[k + 1][0] <= z.profil[k][0] for k in range(len(z.profil) - 1))):
                e.append((ch + ("profil",), "profil : points [distance, cote] à distances strictement croissantes"))
        if t.remblai is not None:
            k = _num(t.remblai.phase)
            if k is None or not 1 <= k <= len(s.phases):
                e.append((("geometrie", "terrain", "remblai", "phase"), f"phase « {t.remblai.phase} » inconnue"))
            if t.remblai.materiau is not None and t.remblai.materiau not in [c.nom for c in s.sol]:
                e.append((("geometrie", "terrain", "remblai", "materiau"), f"couche « {t.remblai.materiau} » inconnue dans le bloc sol"))
    f = g.fouille
    if f is not None:
        noms_zf = set()
        for i, z in enumerate(f.zones):
            ch = ("geometrie", "fouille", "zones", i)
            _etendue(ch, z)
            if z.nom in noms_zf or z.nom == "defaut":
                e.append((ch + ("nom",), f"nom de zone de fond « {z.nom} » en double ou réservé"))
            noms_zf.add(z.nom)
            if z.emprise is not None and (len(z.emprise) < 3 or any(len(p) != 2 for p in z.emprise)):
                e.append((ch + ("emprise",), "emprise : polygone d'au moins 3 points [x, y]"))
        noms_o: list[str] = []
        compteurs: dict[str, int] = {}
        for i, ob in enumerate(f.objets):
            ch = ("geometrie", "fouille", "objets", i)
            _etendue(ch, ob)
            compteurs[ob.type] = compteurs.get(ob.type, 0) + 1
            nom = ob.nom or f"{ob.type.capitalize()}{compteurs[ob.type]}"
            if nom in noms_o:
                e.append((ch + ("nom",), f"nom « {nom} » en double"))
            noms_o.append(nom)
            a, b = (_num(ob.phases[0]), _num(ob.phases[1]))
            for ref, k in zip(ob.phases, (a, b)):
                if k is None or not 1 <= k <= len(s.phases):
                    e.append((ch + ("phases",), f"phase « {ref} » inconnue"))
            if a is not None and b is not None and b < a:
                e.append((ch + ("phases",), "la dernière phase doit suivre la première"))
            if ob.type == "gradins":
                if not ob.marches:
                    e.append((ch + ("marches",), "gradins : marches [cote, largeur] obligatoires"))
            else:
                if ob.cote_crete is None or ob.cote_pied is None:
                    e.append((ch + ("cote_crete",), f"{ob.type} : cote_crete et cote_pied obligatoires"))
                elif ob.cote_pied > ob.cote_crete:
                    e.append((ch + ("cote_pied",), "le pied doit être sous la crête"))
            if ob.methode == "fond_equivalent" and ob.cote_equivalente is None:
                e.append((ch + ("cote_equivalente",), "méthode fond_equivalent : cote_equivalente obligatoire (choix de l'ingénieur)"))
        for j, ph in enumerate(s.phases):
            tr = ph.terrasser_risberme
            for nom in ([tr] if isinstance(tr, str) else tr or []):
                if nom not in noms_o:
                    e.append((("phases", j, "terrasser_risberme"), f"risberme « {nom} » inconnue"))
    noms_s = set()
    n = 0
    for sc in list(s.surcharges) + [x for ph in s.phases for x in (ph.ajouter_surcharges or [])]:
        n += 1
        noms_s.add(sc.nom or f"S{n}")
    for i, p in enumerate(g.surcharges):
        ch = ("geometrie", "surcharges", i)
        _etendue(ch, p)
        if p.surcharge not in noms_s:
            e.append((ch + ("surcharge",), f"surcharge « {p.surcharge} » inconnue dans le bloc surcharges"))
        if p.emprise is not None and (len(p.emprise) != 2 or p.emprise[0] <= 0 or p.emprise[1] <= 0):
            e.append((ch + ("emprise",), "emprise [lx, ly] strictement positive attendue"))
    return e


def _pont_plan(s: Script) -> None:
    """Le bloc plan (contour, côtés, appuis en plan) est dérivé de geometrie.ouvrages pour les consommateurs qui
    lisent encore `plan` (coupes, maquette, pseudo-3D)."""
    if s.geometrie is not None and s.plan is None and s.geometrie.ouvrages is not None:
        o = s.geometrie.ouvrages
        s.plan = Plan(contour=[list(p) for p in o.contour], cotes=dict(o.cotes), appuis=list(o.appuis))
        s.plan_derive = True


def _retirer(donnees, loc: tuple) -> None:
    """Supprime de l'arbre Python la clé désignée par `loc` (mot-clé inconnu)."""
    noeud = donnees
    for c in loc[:-1]:
        if isinstance(noeud, dict) and c in noeud:
            noeud = noeud[c]
        elif isinstance(noeud, list) and isinstance(c, int) and 0 <= c < len(noeud):
            noeud = noeud[c]
        else:
            return
    if isinstance(noeud, dict):
        noeud.pop(loc[-1], None)


def _lire(arbre, donnees) -> tuple[Script, list[ErreurScript]]:
    """Valide l'arbre ; les mots-clés inconnus sont retirés et rendus comme avertissements."""
    avertissements: list[ErreurScript] = []
    vus_av = set()
    for _ in range(3):   # les clés inconnues retirées, une nouvelle validation suffit (marge pour les imbrications)
        try:
            return Script.model_validate(donnees), avertissements
        except ValidationError as ex:
            erreurs, inconnues = [], []
            vus = set()
            for err in ex.errors(include_url=False):
                loc = tuple(err["loc"])
                cle = (loc, err["type"])
                if cle in vus:
                    continue
                vus.add(cle)
                if err["type"] == "extra_forbidden":
                    inconnues.append(loc)
                else:
                    erreurs.append(ErreurScript(ligne_de(arbre, loc), _chemin_lisible(loc, donnees), _message(err)))
            for loc in inconnues:
                if loc not in vus_av:
                    vus_av.add(loc)
                    avertissements.append(ErreurScript(ligne_de(arbre, loc), _chemin_lisible(loc, donnees),
                                                       "mot-clé inconnu, ignoré par le calcul (vérifiez l'orthographe)",
                                                       "avertissement"))
            if erreurs or not inconnues:
                erreurs.sort(key=lambda e: e.ligne or 0)
                raise ScriptInvalide(erreurs + avertissements) from None
            for loc in inconnues:
                _retirer(donnees, loc)
    try:
        return Script.model_validate(donnees), avertissements
    except ValidationError as ex:
        erreurs = [ErreurScript(ligne_de(arbre, tuple(err["loc"])), _chemin_lisible(tuple(err["loc"]), donnees), _message(err))
                   for err in ex.errors(include_url=False)]
        raise ScriptInvalide(erreurs + avertissements) from None


def lire_script(texte: str) -> Script:
    """Lit et valide un script. Lève ScriptInvalide avec la liste des erreurs (les erreurs bloquantes
    d'abord, puis les avertissements). Les avertissements d'un script valide sont dans
    `script.avertissements_lecture` (mots-clés inconnus ignorés)."""
    yaml = YAML(typ="rt")
    try:
        arbre = yaml.load(StringIO(texte))
    except MarkedYAMLError as ex:
        ligne = ex.problem_mark.line + 1 if ex.problem_mark else None
        raise ScriptInvalide([ErreurScript(ligne, "", f"syntaxe YAML : {ex.problem}")]) from None
    except YAMLError as ex:   # caractère interdit, encodage… (erreur sans position)
        raise ScriptInvalide([ErreurScript(None, "", f"syntaxe YAML : {ex}")]) from None
    if not isinstance(arbre, CommentedMap):
        raise ScriptInvalide([ErreurScript(1, "", "le script doit être un bloc de mots-clés (projet:, paroi:, sol:…)")])
    donnees = _python(arbre)
    script, avertissements = _lire(arbre, donnees)
    autres = _controles(script)
    if autres:
        raise ScriptInvalide([ErreurScript(ligne_de(arbre, c), _chemin_lisible(c, donnees), m) for c, m in autres]
                             + avertissements)
    _pont_plan(script)
    script.avertissements_lecture = avertissements
    return script


def valider(texte: str) -> list[ErreurScript]:
    """Erreurs et avertissements du script (niveau de chaque élément)."""
    try:
        s = lire_script(texte)
    except ScriptInvalide as e:
        return e.erreurs
    return list(s.avertissements_lecture)
