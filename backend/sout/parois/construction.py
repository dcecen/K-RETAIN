"""Construction de l'écran de calcul à partir du bloc `paroi` du script."""
from __future__ import annotations

from ..noyau.modele import Ecran


class ErreurParoi(Exception):
    pass


def construire_ecran(p, catalogue=None, normes=None) -> Ecran:
    """Écran de calcul (EI par mètre linéaire, largeur de réaction)."""
    if p.EI is not None:
        return Ecran(tete=p.tete, pied=p.pied, EI=p.EI, infos={"type": p.type, "EI_source": "imposé"})
    raise ErreurParoi("paroi : EI non imposé et calcul depuis la base matériaux indisponible")
