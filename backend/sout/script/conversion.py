"""Script validé -> modèle de calcul (sout.noyau.modele.Modele)."""
from __future__ import annotations

from ..appuis.construction import ErreurAppui, construire_appui
from ..noyau.modele import Modele, Phase
from ..parois import ErreurParoi, construire_ecran
from ..sol.couches import Couche
from ..sol.surcharges import Surcharge
from ..sol.terrain import SurchargePlan
from .schema import Script


class ErreurConversion(Exception):
    pass


def _surcharge(s, nom_defaut: str):
    """Surcharge du moteur : forme historique (répartie, bande, linéique au droit de la coupe) quand aucun
    champ de plan n'est utilisé, sinon surcharge étendue rapportée à la coupe (sol.terrain)."""
    etendue = (s.type in ("uniforme", "rectangulaire", "ponctuelle", "lineaire", "convoi") or s.cote_paroi is not None
               or s.emprise is not None or s.position is not None or s.trace is not None or s.profondeur)
    if not etendue:
        return Surcharge(nom=s.nom or nom_defaut, type=s.type, q=s.q, distance=s.distance,
                         largeur=s.largeur or 0.0, cote=s.cote, cote_ecran=s.cote_ecran)
    cp = s.cote_paroi
    cotes = None if cp is None or cp == "toutes" else tuple(f"#{c}" if isinstance(c, int) else str(c) for c in ([cp] if isinstance(cp, (str, int)) else cp))
    emprise = None
    if isinstance(s.emprise, dict):
        emprise = (float(s.emprise.get("de", 0.0)), float(s.emprise.get("a", 0.0)))
    elif isinstance(s.emprise, list) and len(s.emprise) == 2:
        emprise = (float(s.emprise[0]), float(s.emprise[1]))
    return SurchargePlan(nom=s.nom or nom_defaut, type=s.type, q=s.q, distance=s.distance, largeur=s.largeur, emprise=emprise,
                         position=tuple(s.position) if s.position else None,
                         trace=((s.trace.de[0], s.trace.de[1]), (s.trace.a[0], s.trace.a[1])) if s.trace else None,
                         profondeur=s.profondeur, cote=s.cote, cote_ecran=s.cote_ecran, cotes_paroi=cotes, modele=s.modele,
                         infos={"niveaux": s.niveaux})


def _indice_phase(ref, noms: list[str]) -> int:
    """Numéro de phase (1 = première) depuis un numéro ou un nom."""
    if isinstance(ref, str):
        return noms.index(ref) + 1
    return int(ref)


def _liste(v) -> list[str]:
    return [v] if isinstance(v, str) else list(v or [])


def vers_modele(s: Script, catalogue=None, normes=None, jeu: str | None = None) -> Modele:
    """Modèle de calcul ; `jeu` choisit le jeu de niveaux d'eau (défaut : calcul.jeu_eau ou le premier)."""
    try:
        ecran = construire_ecran(s.paroi, catalogue, normes)
        appuis = {nom: construire_appui(nom, a, catalogue) for nom, a in s.appuis.items()}
    except (ErreurParoi, ErreurAppui, KeyError) as e:
        raise ErreurConversion(str(e).strip("'\"")) from None

    couches = [Couche(**c.model_dump()) for c in s.sol]
    jeu = jeu or s.calcul.jeu_eau or (next(iter(s.eau)) if s.eau else None)
    eau0 = s.eau[jeu] if jeu else None

    # surcharges initiales ; celles qui portent une phase d'application sont ajoutées (et retirées) dans les phases
    noms_phases = [p.nom for p in s.phases]
    surcharges = []
    ajouts_par_phase: dict[int, list] = {}
    retraits_par_phase: dict[int, list[str]] = {}
    n_s = 0
    for i, sc in enumerate(s.surcharges):
        n_s += 1
        obj = _surcharge(sc, f"S{i + 1}")
        debut = fin = None
        if sc.phases:
            debut, fin = _indice_phase(sc.phases[0], noms_phases), _indice_phase(sc.phases[1], noms_phases)
        elif sc.phase is not None:
            debut = _indice_phase(sc.phase, noms_phases)
        if isinstance(obj, SurchargePlan):
            obj = SurchargePlan(**{**obj.__dict__, "phase_debut": debut, "phase_fin": fin})
        if debut is None:
            surcharges.append(obj)
        else:
            ajouts_par_phase.setdefault(debut, []).append(obj)
        if fin is not None and fin + 1 <= len(s.phases):
            retraits_par_phase.setdefault(fin + 1, []).append(obj.nom)
    phases = []
    for k_ph, ph in enumerate(s.phases, start=1):
        ajout = list(ajouts_par_phase.get(k_ph, []))
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
            ajouter_surcharges=ajout, retirer_surcharges=list(ph.retirer_surcharges or []) + retraits_par_phase.get(k_ph, []),
            depuis=ph.depuis,
        ))
    return Modele(
        ecran=ecran, couches=couches, phases=phases, appuis=appuis,
        terrain_amont=s.terrain.amont, terrain_aval=s.terrain.aval,
        eau_amont=eau0.amont if eau0 else None, eau_aval=eau0.aval if eau0 else None,
        surcharges=surcharges, gamma_w=s.calcul.gamma_w, coefficients=s.calcul.coefficients,
        pas=s.calcul.pas,
        hydraulique=s.hydraulique.model_dump() if s.hydraulique is not None else None,
        coupe=s.coupe_calcul.model_dump() if s.coupe_calcul is not None else None,
    )
