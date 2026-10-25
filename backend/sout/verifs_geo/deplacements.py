"""Déplacements aux ELS, comparés aux critères fixés par l'ingénieur (bloc `criteres`)."""
from __future__ import annotations

import numpy as np

from ..noyau.phasage import ResultatCalcul
from ..verifs import Verif, donnee, resultat

SOURCE = "Critères de déplacement du projet (bloc criteres du script)"
PRINCIPE = ("Vérification aux états limites de service : le déplacement calculé de l'écran (jeu d'eau principal, toutes "
            "phases) est comparé au critère fixé par l'ingénieur dans le bloc `criteres` du script (déplacement maximal "
            "sur la hauteur, déplacement en tête). Aucun coefficient partiel : taux = déplacement / valeur admissible.")


def _schema(res: ResultatCalcul, ph, adm: float | None, quoi: str) -> dict:
    z, y = np.asarray(res.z, float), np.asarray(ph.y, float) * 1e3
    idx = np.unique(np.linspace(0, len(z) - 1, min(len(z), 80)).round().astype(int))
    return {"type": "profil", "phase": ph.nom, "quoi": quoi, "z": [round(float(v), 3) for v in z[idx]],
            "y_mm": [round(float(v), 3) for v in y[idx]], "limite_mm": adm, "tete": float(z.max()), "pied": float(z.min())}


def verifier(res: ResultatCalcul, criteres) -> list[Verif]:
    phases = [ph for ph in res.phases[1:] if ph.ok]
    if not phases:
        return []
    sorties = []
    ph = max(phases, key=lambda p: np.abs(p.y).max())
    y = float(np.abs(ph.y).max() * 1e3)
    z_y = float(res.z[int(np.argmax(np.abs(ph.y)))])
    adm = criteres.deplacement_max_mm if criteres else None
    sorties.append(resultat("Déplacement maximal (ELS)", "écran", ph.nom,
                            None if adm is None else y / adm,
                            f"|y| max = {y:.1f} mm" + (f" pour {adm:.0f} mm admissibles" if adm else ""),
                            SOURCE, detail_non_verifiable=f"|y| max = {y:.1f} mm — critère non fixé (criteres.deplacement_max_mm)",
                            famille="deplacements", principe=PRINCIPE,
                            donnees=[donnee("|y| max", "déplacement maximal sur la hauteur (phase retenue)", y, "mm"),
                                     donnee("z", "cote du déplacement maximal", z_y, "m"),
                                     donnee("y_adm", "déplacement admissible (criteres.deplacement_max_mm)", adm, "mm", "script")],
                            etapes=[f"Phase retenue « {ph.nom} » : |y| max = {y:.1f} mm à la cote {z_y:.2f} m",
                                    f"taux = |y| max / y_adm = {y:.1f} / {adm:.0f} = {y / adm:.3f}" if adm else "critère non fixé : taux non calculable"],
                            schema=_schema(res, ph, adm, "maximal")))
    ph = max(phases, key=lambda p: abs(p.y[-1]))
    yt = float(abs(ph.y[-1]) * 1e3)
    adm = criteres.deplacement_tete_mm if criteres else None
    sorties.append(resultat("Déplacement en tête (ELS)", "écran", ph.nom,
                            None if adm is None else yt / adm,
                            f"|y| tête = {yt:.1f} mm" + (f" pour {adm:.0f} mm admissibles" if adm else ""),
                            SOURCE, detail_non_verifiable=f"|y| tête = {yt:.1f} mm — critère non fixé (criteres.deplacement_tete_mm)",
                            famille="deplacements", principe=PRINCIPE,
                            donnees=[donnee("|y| tête", "déplacement en tête de l'écran (phase retenue)", yt, "mm"),
                                     donnee("y_adm", "déplacement en tête admissible (criteres.deplacement_tete_mm)", adm, "mm", "script")],
                            etapes=[f"Phase retenue « {ph.nom} » : |y| en tête = {yt:.1f} mm",
                                    f"taux = |y| tête / y_adm = {yt:.1f} / {adm:.0f} = {yt / adm:.3f}" if adm else "critère non fixé : taux non calculable"],
                            schema=_schema(res, ph, adm, "tête")))
    return sorties
