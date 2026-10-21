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
    ex.verifications = pire(verifs)
    return ex
