"""Déplacements aux ELS, comparés aux critères fixés par l'ingénieur (bloc `criteres`)."""
from __future__ import annotations

import numpy as np

from ..noyau.phasage import ResultatCalcul
from ..verifs import Verif, resultat

SOURCE = "Critères de déplacement du projet (bloc criteres du script)"


def verifier(res: ResultatCalcul, criteres) -> list[Verif]:
    phases = [ph for ph in res.phases[1:] if ph.ok]
    if not phases:
        return []
    sorties = []
    ph = max(phases, key=lambda p: np.abs(p.y).max())
    y = float(np.abs(ph.y).max() * 1e3)
    adm = criteres.deplacement_max_mm if criteres else None
    sorties.append(resultat("Déplacement maximal (ELS)", "écran", ph.nom,
                            None if adm is None else y / adm,
                            f"|y| max = {y:.1f} mm" + (f" pour {adm:.0f} mm admissibles" if adm else ""),
                            SOURCE, detail_non_verifiable=f"|y| max = {y:.1f} mm — critère non fixé (criteres.deplacement_max_mm)"))
    ph = max(phases, key=lambda p: abs(p.y[-1]))
    yt = float(abs(ph.y[-1]) * 1e3)
    adm = criteres.deplacement_tete_mm if criteres else None
    sorties.append(resultat("Déplacement en tête (ELS)", "écran", ph.nom,
                            None if adm is None else yt / adm,
                            f"|y| tête = {yt:.1f} mm" + (f" pour {adm:.0f} mm admissibles" if adm else ""),
                            SOURCE, detail_non_verifiable=f"|y| tête = {yt:.1f} mm — critère non fixé (criteres.deplacement_tete_mm)"))
    return sorties
