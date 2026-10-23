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


def efforts_assemblage(s: Script, ex: Execution, a) -> dict:
    """Efforts (kN, kN·m) transmis à un assemblage depuis l'appui calculé, ou imposés."""
    if a.efforts:
        return dict(a.efforts)
    e = {"N": 0.0, "V": 0.0, "M": 0.0, "T": 0.0}
    if a.appui is None:
        return e
    app = s.appuis[a.appui]
    H = 0.0
    for _, (m, r) in ex.jeux.items():
        for ph in r.phases:
            if ph.ok:
                for x in ph.appuis:
                    if x["nom"] == a.appui:
                        H = max(H, x["effort"])
    import math
    N = H * app.espacement / math.cos(math.radians(app.angle))
    e["N"] = e["T"] = N
    e["V"] = N * abs(math.sin(math.radians(app.angle)))
    # lierne : poutre continue sur deux travées (comme sout.verifs_struct) : M = q·e²/8, V = 0,625·q·e
    e["M"] = 0.125 * H * app.espacement ** 2
    e["V_lierne"] = 0.625 * H * app.espacement
    return e


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
        e = efforts_assemblage(s, ex, a)
        if a.type == "eclisse_lierne":
            e = {**e, "V": e.get("V_lierne", e["V"])}
        try:
            out += verifier_assemblage(a.type, parametres_assemblage(s, a), e, catalogue, normes, fck, element=nom)
        except KeyError as err:
            out.append(Verif(f"Assemblage {nom}", "structure", nom, None, "non_verifiable", None, str(err), "", [str(err)]))
    return out
