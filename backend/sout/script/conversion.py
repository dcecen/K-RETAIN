"""Script validé -> modèle de calcul (sout.noyau.modele.Modele)."""
from __future__ import annotations

from ..appuis.construction import ErreurAppui, construire_appui
from ..noyau.modele import Modele, Phase
from ..parois import ErreurParoi, construire_ecran
from ..sol.couches import Couche
from ..sol.surcharges import Surcharge
from .schema import Script


class ErreurConversion(Exception):
    pass


def _surcharge(s, nom_defaut: str) -> Surcharge:
    return Surcharge(nom=s.nom or nom_defaut, type=s.type, q=s.q, distance=s.distance,
                     largeur=s.largeur or 0.0, cote=s.cote, cote_ecran=s.cote_ecran)


def _liste(v) -> list[str]:
    return [v] if isinstance(v, str) else list(v or [])


def vers_modele(s: Script, catalogue=None, normes=None) -> Modele:
    try:
        ecran = construire_ecran(s.paroi, catalogue, normes)
        appuis = {nom: construire_appui(nom, a, catalogue) for nom, a in s.appuis.items()}
    except (ErreurParoi, ErreurAppui, KeyError) as e:
        raise ErreurConversion(str(e).strip("'\"")) from None

    couches = [Couche(**c.model_dump()) for c in s.sol]
    jeu = s.calcul.jeu_eau or (next(iter(s.eau)) if s.eau else None)
    eau0 = s.eau[jeu] if jeu else None

    surcharges = [_surcharge(sc, f"S{i + 1}") for i, sc in enumerate(s.surcharges)]
    n_s = len(surcharges)
    phases = []
    for ph in s.phases:
        ajout = []
        for sc in ph.ajouter_surcharges or []:
            n_s += 1
            ajout.append(_surcharge(sc, f"S{n_s}"))
        eau = {}
        if ph.eau is not None:
            for cle in ph.eau.model_fields_set:
                eau[cle] = getattr(ph.eau, cle)
        phases.append(Phase(
            nom=ph.nom, excaver=ph.excaver,
            remblayer_amont=ph.remblayer.amont if ph.remblayer else None,
            remblayer_aval=ph.remblayer.aval if ph.remblayer else None,
            poser=_liste(ph.poser), deposer=_liste(ph.deposer), eau=eau,
            ajouter_surcharges=ajout, retirer_surcharges=list(ph.retirer_surcharges or []),
        ))
    return Modele(
        ecran=ecran, couches=couches, phases=phases, appuis=appuis,
        terrain_amont=s.terrain.amont, terrain_aval=s.terrain.aval,
        eau_amont=eau0.amont if eau0 else None, eau_aval=eau0.aval if eau0 else None,
        surcharges=surcharges, gamma_w=s.calcul.gamma_w, coefficients=s.calcul.coefficients,
        pas=s.calcul.pas,
    )
