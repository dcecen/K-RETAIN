"""Tables de Kérisel-Absi (poussée et butée, surfaces de rupture courbes).

Kérisel J., Absi E. (1990), *Tables de poussée et de butée des terres*,
Presses de l'ENPC. Les tables ne sont pas reproduites ici : elles doivent être
fournies par l'utilisateur dans docs/normes/kerisel_absi/ (voir README).

Format attendu (CSV, séparateur « ; » ou « , ») :
    ka.csv : phi;delta_sur_phi;K      (K = coefficient tabulé, incliné de δ)
    kp.csv : phi;delta_sur_phi;K
Écran vertical, terre-plein horizontal. Interpolation bilinéaire sur ln K (K varie de
façon convexe, une interpolation linéaire surestimerait Kp).
Convention : delta_sur_phi est donné en valeur absolue (≥ 0), y compris en butée où
les tables originales l'écrivent négatif.
"""
from __future__ import annotations

import csv
import math
from functools import lru_cache
from pathlib import Path

import numpy as np

DOSSIER = Path(__file__).resolve().parents[3] / "docs" / "normes" / "kerisel_absi"


class TableAbsente(Exception):
    pass


@lru_cache(maxsize=4)
def _charger(nom: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    chemin = DOSSIER / f"{nom}.csv"
    if not chemin.exists():
        raise TableAbsente(
            f"TODO-NORME : table de Kérisel-Absi absente ({chemin}). "
            "Fournissez-la ou choisissez coefficients: coulomb."
        )
    texte = chemin.read_text(encoding="utf-8-sig")
    sep = ";" if ";" in texte.splitlines()[0] else ","
    lignes = list(csv.DictReader(texte.splitlines(), delimiter=sep))
    phis = sorted({float(l["phi"]) for l in lignes})
    rapports = sorted({float(l["delta_sur_phi"]) for l in lignes})
    grille = np.full((len(phis), len(rapports)), np.nan)
    for l in lignes:
        grille[phis.index(float(l["phi"])), rapports.index(float(l["delta_sur_phi"]))] = float(l["K"])
    if np.isnan(grille).any():
        raise ValueError(f"table {chemin} incomplète : la grille phi x delta_sur_phi doit être pleine")
    return np.array(phis), np.array(rapports), grille


def _interpoler(nom: str, phi: float, delta_sur_phi: float) -> float:
    phis, rapports, g = _charger(nom)
    if not (phis[0] <= phi <= phis[-1] and rapports[0] <= delta_sur_phi <= rapports[-1]):
        raise ValueError(f"Kérisel-Absi : (φ={phi}, δ/φ={delta_sur_phi}) hors de la table {nom}")
    i = min(np.searchsorted(phis, phi, side="right") - 1, len(phis) - 2)
    j = min(np.searchsorted(rapports, delta_sur_phi, side="right") - 1, len(rapports) - 2)
    i, j = max(i, 0), max(j, 0)
    tx = (phi - phis[i]) / (phis[i + 1] - phis[i]) if len(phis) > 1 else 0.0
    ty = (delta_sur_phi - rapports[j]) / (rapports[j + 1] - rapports[j]) if len(rapports) > 1 else 0.0
    lg = np.log(g)
    return float(np.exp((1 - tx) * (1 - ty) * lg[i, j] + tx * (1 - ty) * lg[i + 1, j]
                        + (1 - tx) * ty * lg[i, j + 1] + tx * ty * lg[i + 1, j + 1]))


def kah(phi: float, delta_sur_phi: float) -> float:
    """Kah = Ka(table) · cos δ."""
    return _interpoler("ka", phi, delta_sur_phi) * math.cos(math.radians(phi * delta_sur_phi))


def kph(phi: float, delta_sur_phi: float) -> float:
    """Kph = Kp(table) · cos δ."""
    return _interpoler("kp", phi, delta_sur_phi) * math.cos(math.radians(phi * delta_sur_phi))
