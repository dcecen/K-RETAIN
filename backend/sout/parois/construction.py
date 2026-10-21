"""Construction de l'écran de calcul à partir du bloc `paroi` du script.

Rigidité par mètre linéaire (mécanique des poutres, sans valeur normative) :
- palplanches : EI = E·I (I par mètre de rideau, catalogue) ; profils en U :
  EI multiplié par β_D (EN 1993-5, valeur à fournir : script `beta_D` ou
  docs/normes/ec3.yaml → palplanches.beta_D) ;
- paroi moulée : EI = Ecm·e³/12, multiplié par le rapport EI fissuré / non
  fissuré choisi par l'ingénieur ;
- pieux : EI d'un pieu = Ecm·πD⁴/64 (× rapport fissuré) + Es·I du profilé
  d'armature éventuel ; pieux disjoints : EI/entraxe ; pieux sécants :
  seuls les pieux armés comptent (hypothèse documentée) : EI/entraxe si les
  primaires sont armés, EI/(2·entraxe) sinon, l'entraxe étant celui des pieux
  consécutifs ;
- berlinoise : EI = E·Iy du profilé / entraxe.

Fiches discontinues (pieux disjoints, berlinoise) : sous le fond de fouille,
pressions limites et raideur sont réduites dans le rapport
b_réaction / entraxe (≤ 1), avec b_réaction donné par le script
(`largeur_reaction_fiche`) ou par docs/normes (fiche_discontinue.rapport_largeur
× largeur physique). Sans l'une ou l'autre, le calcul est refusé (TODO-NORME).
"""
from __future__ import annotations

import math

import numpy as np

from ..noyau.modele import Ecran
from ..normes import ValeurNormeManquante


class ErreurParoi(Exception):
    pass


def _cat(catalogue, quoi: str):
    if catalogue is None:
        raise ErreurParoi(f"paroi : base matériaux indisponible ({quoi})")
    return catalogue


def _E_acier_kPa(p, catalogue) -> tuple[float, dict]:
    if p.acier is None:
        raise ErreurParoi(f"paroi {p.type} : nuance d'acier obligatoire (mot-clé acier)")
    a = _cat(catalogue, "acier").acier(p.acier)
    if a.get("E_MPa") is None:
        raise ErreurParoi(f"acier {p.acier} : module d'Young absent de la base")
    return a["E_MPa"] * 1e3, a


def _Ecm_kPa(p, catalogue) -> tuple[float, dict]:
    if p.beton is None:
        raise ErreurParoi(f"paroi {p.type} : classe de béton obligatoire (mot-clé beton)")
    b = _cat(catalogue, "béton").beton(p.beton)
    if b.get("Ecm_MPa") is None:
        raise ErreurParoi(f"béton {p.beton} : Ecm absent de la base")
    return b["Ecm_MPa"] * 1e3, b


def _rapport_fissure(p) -> float:
    return p.rapport_EI_fissure if p.rapport_EI_fissure is not None else 1.0


def _requis(p, *champs):
    manquants = [c for c in champs if getattr(p, c) is None]
    if manquants:
        raise ErreurParoi(f"paroi {p.type} : mot(s)-clé(s) obligatoire(s) : {', '.join(manquants)}")


def _largeur_reaction(p, b_physique: float, normes) -> float:
    if p.largeur_reaction_fiche is not None:
        return p.largeur_reaction_fiche
    if normes is not None:
        try:
            return float(normes.valeur("nf_p94_282", "fiche_discontinue.rapport_largeur")) * b_physique
        except ValeurNormeManquante:
            pass
    raise ErreurParoi(
        "TODO-NORME : fiche discontinue — largeur de réaction sous le fond de fouille inconnue. "
        "Donnez paroi.largeur_reaction_fiche (m) ou docs/normes/nf_p94_282.yaml → fiche_discontinue.rapport_largeur."
    )


def _fonction_fiche(rapport: float):
    def largeur(zm: np.ndarray, cote: int, z_fond: float):
        f = np.where(zm < z_fond, rapport, 1.0)
        return f, f
    return largeur


def construire_ecran(p, catalogue=None, normes=None) -> Ecran:
    """Écran de calcul (EI par mètre linéaire, largeur de réaction)."""
    infos: dict = {"type": p.type}
    largeur = None
    EI = None
    if p.type == "palplanche" and p.profil is not None:
        pal = _cat(catalogue, "palplanche").palplanche(p.profil)
        E, acier = _E_acier_kPa(p, catalogue)
        EI = E * pal["I_cm4_m"] * 1e-8
        beta_D = 1.0
        if pal.get("forme") == "U":
            beta_D = p.beta_D
            if beta_D is None and normes is not None:
                beta_D = normes.facultatif("ec3", "palplanches.beta_D")
            if beta_D is None:
                raise ErreurParoi(
                    f"TODO-NORME : palplanche en U {p.profil} — coefficient β_D (EN 1993-5) manquant : "
                    "paroi.beta_D ou docs/normes/ec3.yaml → palplanches.beta_D")
            EI *= beta_D
        infos.update(section=pal, acier=acier, beta_D=beta_D, demo=bool(pal.get("demo") or acier.get("demo")))
    elif p.type == "paroi_moulee" and p.EI is None:
        _requis(p, "epaisseur")
        Ec, beton = _Ecm_kPa(p, catalogue)
        EI = Ec * p.epaisseur**3 / 12 * _rapport_fissure(p)
        infos.update(beton=beton, epaisseur=p.epaisseur, enrobage=p.enrobage, demo=bool(beton.get("demo")))
    elif p.type in ("pieux_secants", "pieux_disjoints") and p.EI is None:
        _requis(p, "diametre", "entraxe")
        Ec, beton = _Ecm_kPa(p, catalogue)
        EI_pieu = Ec * math.pi * p.diametre**4 / 64 * _rapport_fissure(p)
        demo = bool(beton.get("demo"))
        if p.profil_armature:
            prof = _cat(catalogue, "profilé").profil(p.profil_armature)
            Es, acier = _E_acier_kPa(p, catalogue)
            EI_pieu += Es * prof["Iy_cm4"] * 1e-8
            infos.update(profil_armature=prof, acier=acier)
            demo = demo or bool(prof.get("demo") or acier.get("demo"))
        if p.type == "pieux_secants":
            EI = EI_pieu / (p.entraxe if p.primaires_armes else 2 * p.entraxe)
        else:
            EI = EI_pieu / p.entraxe
            b_reac = _largeur_reaction(p, p.diametre, normes)
            infos["rapport_largeur_fiche"] = min(b_reac / p.entraxe, 1.0)
            largeur = _fonction_fiche(infos["rapport_largeur_fiche"])
        infos.update(beton=beton, diametre=p.diametre, entraxe=p.entraxe, EI_pieu=EI_pieu,
                     enrobage=p.enrobage, demo=demo)
    elif p.type == "berlinoise" and p.profil is not None:
        _requis(p, "entraxe")
        prof = _cat(catalogue, "profilé").profil(p.profil)
        E, acier = _E_acier_kPa(p, catalogue)
        EI = E * prof["Iy_cm4"] * 1e-8 / p.entraxe
        b_reac = _largeur_reaction(p, prof["b_mm"] / 1000 if prof.get("b_mm") else (prof.get("D_mm") or 0) / 1000, normes)
        infos.update(section=prof, acier=acier, entraxe=p.entraxe,
                     rapport_largeur_fiche=min(b_reac / p.entraxe, 1.0),
                     blindage=p.blindage.model_dump() if p.blindage else None,
                     demo=bool(prof.get("demo") or acier.get("demo")))
        largeur = _fonction_fiche(infos["rapport_largeur_fiche"])

    if p.EI is not None:
        EI = p.EI
        infos["EI_source"] = "imposé"
        if p.type in ("pieux_disjoints", "berlinoise") and largeur is None and p.entraxe:
            b = p.diametre if p.type == "pieux_disjoints" else None
            if p.largeur_reaction_fiche is not None or b is not None:
                infos["rapport_largeur_fiche"] = min(_largeur_reaction(p, b or 0.0, normes) / p.entraxe, 1.0)
                largeur = _fonction_fiche(infos["rapport_largeur_fiche"])
    elif EI is None:
        attendu = {"palplanche": "profil et acier", "berlinoise": "profil, acier et entraxe",
                   "paroi_moulee": "epaisseur et beton", "pieux_secants": "diametre, entraxe et beton",
                   "pieux_disjoints": "diametre, entraxe et beton"}[p.type]
        raise ErreurParoi(f"paroi {p.type} : donnez {attendu} (ou EI imposé)")
    else:
        infos["EI_source"] = "calculé (base matériaux)"
    infos["EI"] = EI
    return Ecran(tete=p.tete, pied=p.pied, EI=EI, largeur_reaction=largeur, infos=infos)
