"""Enchaînement complet : script -> calculs par jeu d'eau -> vérifications.

Jeux de niveaux d'eau (bloc `eau`) : chaque jeu est calculé (les niveaux d'eau
écrits dans les phases s'appliquent à tous les jeux). Les vérifications
retiennent, pour chaque élément, le jeu et la phase les plus défavorables ;
les déplacements ELS ne portent que sur le jeu principal (service).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .noyau.modele import Modele
from .noyau.phasage import ResultatCalcul, calculer
from .script.conversion import vers_modele
from .script.schema import Script
from .verifs import Verif, pire
from .verifs_geo import bishop, butee, deplacements, equilibre_vertical, fond_de_fouille, kranz, tirants


@dataclass
class Execution:
    script: Script
    modele: Modele
    resultat: ResultatCalcul
    jeu_principal: str | None
    jeux: dict = field(default_factory=dict)          # jeu -> (modele, resultat)
    verifications: list[Verif] = field(default_factory=list)
    suggestions: list[dict] = field(default_factory=list)
    pseudo3d: object | None = None                      # ResultatPseudo3D (calcul.mode pseudo3d)
    avertissements: list[str] = field(default_factory=list)


def _geotechniques(s: Script, m: Modele, r: ResultatCalcul, normes, jeu: str | None) -> list[Verif]:
    demandes = set(s.verifications)
    v: list[Verif] = []
    if "butee" in demandes:
        v += butee.verifier(r, normes)
    if "equilibre_vertical" in demandes:
        v += equilibre_vertical.verifier(m, r, normes)
    if "kranz" in demandes:
        v += kranz.verifier(m, r, normes)
    if "fond_de_fouille" in demandes:
        if any(p.ecoulement is not None for p in r.phases):
            from .hydraulique import verifications as verifs_hydro
            v += verifs_hydro.verifier(m, r, normes)
        else:
            v += fond_de_fouille.verifier(m, r, normes)
    if "stabilite_generale" in demandes:
        v += bishop.verifier(m, r, normes, s.calcul.largeur_fouille)
    if "structure" in demandes:
        v += tirants.verifier(m, r, normes)
    if jeu is not None:
        for x in v:
            x.phase = f"{x.phase} [{jeu}]" if x.phase else f"[{jeu}]"
    return v


def executer(s: Script, catalogue, normes) -> Execution:
    principal = s.calcul.jeu_eau or (next(iter(s.eau)) if s.eau else None)
    modele = vers_modele(s, catalogue, normes, principal)
    res = calculer(modele)
    ex = Execution(s, modele, res, principal, {principal: (modele, res)})
    for jeu in s.eau:
        if jeu != principal:
            m = vers_modele(s, catalogue, normes, jeu)
            ex.jeux[jeu] = (m, calculer(m))
    if s.calcul.mode == "pseudo3d":
        # calculé ici, avant les vérifications, pour que les STR puissent lire la plaque ; l'API le réutilise
        from .noyau.phasage import ErreurModele
        from .pseudo3d.calcul import depuis_script
        try:
            ex.pseudo3d = depuis_script(ex)
        except ErreurModele as e:
            ex.avertissements.append(f"Pseudo-3D non calculé : {e}")
    plusieurs = len(ex.jeux) > 1
    verifs: list[Verif] = []
    for jeu, (m, r) in ex.jeux.items():
        if r.complet:
            verifs += _geotechniques(s, m, r, normes, jeu if plusieurs else None)
        else:
            verifs.append(verif_rupture(jeu if plusieurs else None, r))
    if "deplacements" in s.verifications and res.complet:
        verifs += deplacements.verifier(res, s.criteres)
    if "structure" in s.verifications:
        try:
            from .verifs_struct import executer as structure
        except ImportError:
            structure = None
        if structure is not None:
            v_struct, suggestions = structure(s, ex, catalogue, normes)
            verifs += v_struct
            ex.suggestions = suggestions
    if s.assemblages:
        verifs += verifier_assemblages(s, ex, catalogue, normes)
    ex.verifications = pire(verifs)
    return ex


def efforts_assemblage(s: Script, ex: Execution, a, normes=None) -> tuple[dict, list[str]]:
    """Efforts de calcul (kN, kN·m) transmis à un assemblage.

    - `efforts:` imposés dans le script : pris tels quels (efforts de calcul, déjà pondérés).
    - depuis un appui : effort caractéristique maximal H (kN/m) de toutes les phases et de tous les
      jeux d'eau, ramené à l'appui (× espacement / cos θ) puis **multiplié par gamma_effets de la
      combinaison ELU fondamentale** (nf_p94_282.yaml -> combinaisons.ELU_fondamental.gamma_effets),
      même convention que sout.verifs_struct.elements (effets caractéristiques × γ). Si le coefficient
      manque, les efforts sont renvoyés non pondérés et la liste `manquants` le signale : la
      vérification doit alors être « non vérifiable ».
    Renvoie (efforts, manquants)."""
    if a.efforts:
        return dict(a.efforts), []
    e = {"N": 0.0, "V": 0.0, "M": 0.0, "T": 0.0}
    if a.appui is None:
        return e, []
    app = s.appuis[a.appui]
    H = 0.0
    for _jeu, (_m, r) in ex.jeux.items():
        for ph in r.phases:
            if ph.ok:
                for x in ph.appuis:
                    if x["nom"] == a.appui:
                        H = max(H, x["effort"])
    import math
    from .verifs import Lecteur
    lect = Lecteur(normes)
    g = lect.v("nf_p94_282", "combinaisons.ELU_fondamental.gamma_effets")
    H_d = H * (g if g is not None else 1.0)
    N = H_d * app.espacement / math.cos(math.radians(app.angle))
    e["N"] = e["T"] = N
    e["V"] = N * abs(math.sin(math.radians(app.angle)))
    # lierne : poutre continue sur deux travées (comme sout.verifs_struct) : M = q·e²/8, V = 0,625·q·e
    e["M"] = 0.125 * H_d * app.espacement ** 2
    e["V_lierne"] = 0.625 * H_d * app.espacement
    return e, list(lect.manquants)


def verif_rupture(jeu: str | None, r: ResultatCalcul) -> Verif:
    """Résultat « non_ok » explicite pour un jeu d'eau dont le calcul s'est interrompu (rupture du sol,
    non-convergence) : sans lui, le jeu disparaissait des vérifications en silence."""
    ph = next((p for p in r.phases if not p.ok), None)
    quoi = f"jeu d'eau « {jeu} »" if jeu else "calcul"
    return Verif("Calcul — équilibre de l'écran", "geotechnique", "écran", ph.nom if ph else None, "non_ok", None,
                 f"{quoi} : {ph.message if ph else 'calcul incomplet'} — aucune vérification n'est possible sur les phases suivantes",
                 "sout.noyau.solveur (rupture détectée par le calcul)")


def parametres_assemblage(s: Script, a) -> dict:
    p = dict(a.parametres)
    app = s.appuis.get(a.appui) if a.appui else None
    p["acier"] = a.acier or (app.acier if app and app.acier else "S355")
    p["lierne"] = a.lierne or (app.lierne if app else None) or ""
    p["buton"] = a.buton or (app.element if app else None) or ""
    if app is not None:
        p.setdefault("angle", app.angle)
    return p


def verifier_assemblages(s: Script, ex: Execution, catalogue, normes) -> list[Verif]:
    from .assemblages.service import verifier as verifier_assemblage
    out = []
    fck = None
    beton = ex.modele.ecran.infos.get("beton")
    if beton:
        fck = beton.get("fck_MPa")
    for nom, a in s.assemblages.items():
        e, manquants = efforts_assemblage(s, ex, a, normes)
        if a.type == "eclisse_lierne":
            e = {**e, "V": e.get("V_lierne", e["V"])}
        try:
            vs = verifier_assemblage(a.type, parametres_assemblage(s, a), e, catalogue, normes, fck, element=nom)
        except KeyError as err:
            out.append(Verif(f"Assemblage {nom}", "structure", nom, None, "non_verifiable", None, str(err), "", [str(err)]))
            continue
        if manquants:
            # efforts non pondérés : aucun taux ne peut être affiché comme un taux de calcul
            vs = [Verif(v.nom, v.categorie, v.element, v.phase, "non_verifiable", None,
                        v.detail + " — efforts d'appui non pondérés (coefficient gamma_effets manquant)",
                        v.source, manquants + v.manquants, v.reperes) for v in vs]
        out += vs
    return out
