"""Surcharges côté terre prises en compte par les vérifications de stabilité d'ensemble (Bishop, Kranz,
fond en argile de Bjerrum-Eide).

Ces vérifications travaillent sur un profil 2D du massif : elles reprennent les surcharges
réparties (`repartie`, `uniforme` en plan) et les bandes parallèles à la paroi, présentes dès
l'état initial. Les autres (ponctuelle, rectangulaire, linéaire, convoi, surcharges ajoutées
en cours de phasage) ne sont pas modélisées par ces méthodes : elles sont **listées** pour que
le résultat le dise, au lieu d'être ignorées en silence.
"""
from __future__ import annotations

from ..plan.geometrie import cote_concerne
from ..sol.terrain import CoupeCalcul, SurchargePlan

LOIN = -1e6   # début d'une bande « infinie » côté terre (m)


def charges_amont(modele) -> tuple[list[tuple[float, float, float]], list[str]]:
    """Bandes (x_debut, x_fin, q) côté terre (x < 0 vers la terre, kPa) et surcharges ignorées (libellés)."""
    coupe = CoupeCalcul.depuis_dict(modele.coupe)
    bandes: list[tuple[float, float, float]] = []
    ignorees: list[str] = []
    for s in modele.surcharges:
        if s.cote_ecran != "amont":
            continue
        if isinstance(s, SurchargePlan):
            if not cote_concerne(s.cotes_paroi, coupe):
                continue
            if s.phase_debut is not None:
                ignorees.append(f"{s.nom} ({s.type}, à partir de la phase {s.phase_debut})")
            elif s.type == "uniforme" and s.largeur is None:
                bandes.append((LOIN, 0.0, s.q))
            elif s.type == "uniforme":
                bandes.append((-(s.distance + s.largeur), -s.distance, s.q))
            elif s.type == "bande" and s.largeur is not None:
                bandes.append((-(s.distance + s.largeur), -s.distance, s.q))
            else:
                ignorees.append(f"{s.nom} ({s.type})")
        elif s.type == "repartie":
            bandes.append((LOIN, 0.0, s.q))
        elif s.type == "bande":
            bandes.append((-(s.distance + s.largeur), -s.distance, s.q))
        else:
            ignorees.append(f"{s.nom} ({s.type})")
    for ph in modele.phases:
        for s in ph.ajouter_surcharges or []:
            ignorees.append(f"{s.nom} (ajoutée en phase « {ph.nom} »)")
    return bandes, ignorees


def q_uniforme_amont(modele) -> tuple[float, list[str]]:
    """Surcharge uniforme équivalente côté terre (kPa) : somme des bandes infinies ; les bandes
    limitées rejoignent la liste des surcharges non prises en compte."""
    bandes, ignorees = charges_amont(modele)
    q = sum(b[2] for b in bandes if b[0] <= LOIN / 2)
    autres = [f"bande {b[0]:.1f}..{b[1]:.1f} m, {b[2]:g} kPa" for b in bandes if b[0] > LOIN / 2]
    return q, ignorees + autres


def mention(ignorees: list[str]) -> str:
    return (" ; surcharges non prises en compte par cette méthode : " + ", ".join(ignorees)) if ignorees else ""
