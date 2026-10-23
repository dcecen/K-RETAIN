"""Passage d'un appui du script (sout.script.schema.Appui) à un appui de calcul
(sout.noyau.modele.DefAppui) : raideur et précharge par mètre linéaire."""
from __future__ import annotations

from ..noyau.modele import DefAppui
from . import raideurs


class ErreurAppui(Exception):
    pass


def _E_A(nom: str, a, catalogue) -> tuple[float, float]:
    """Module (MPa) et section (cm²) de l'appui, donnés ou tirés de la base."""
    if a.E is not None and a.A is not None:
        return a.E, a.A
    if a.element is None:
        raise ErreurAppui(f"appui {nom} : E et A ou element obligatoires")
    if catalogue is None:
        raise ErreurAppui(f"appui {nom} : base matériaux indisponible pour l'élément « {a.element} »")
    el = catalogue.element(a.element)
    E = a.E if a.E is not None else el.get("E_MPa")
    if E is None:
        nuance = a.acier or el.get("acier")
        if nuance is None:
            raise ErreurAppui(f"appui {nom} : module d'Young inconnu (donnez E ou acier)")
        E = catalogue.acier(nuance)["E_MPa"]
    A = a.A if a.A is not None else el.get("A_cm2")
    if A is None:
        raise ErreurAppui(f"appui {nom} : section de l'élément « {a.element} » inconnue")
    return float(E), float(A)


def construire_appui(nom: str, a, catalogue=None) -> DefAppui:
    angle = a.angle
    if a.raideur is not None:
        k = a.raideur
    elif a.type == "buton":
        E, A = _E_A(nom, a, catalogue)
        k = raideurs.raideur_buton(E, A, a.longueur, a.espacement, angle, a.symetrique)
    elif a.type == "bracon":
        E, A = _E_A(nom, a, catalogue)
        k = raideurs.raideur_barre(E, A, a.longueur, a.espacement, angle)
    elif a.type == "tirant":
        if a.longueur_libre is None and a.longueur_elastique is None:
            raise ErreurAppui(f"tirant {nom} : longueur_libre (ou longueur_elastique) obligatoire")
        E, A = _E_A(nom, a, catalogue)
        k = raideurs.raideur_tirant(E, A, a.longueur_libre or a.longueur_elastique, a.espacement, angle,
                                    a.longueur_elastique)
    elif a.type == "dalle":
        if a.E is not None and a.A is not None:
            k = raideurs.raideur_buton(a.E, a.A, a.longueur, a.espacement, 0.0, a.symetrique)
        else:
            if a.epaisseur is None:
                raise ErreurAppui(f"dalle {nom} : épaisseur obligatoire")
            if a.E is not None:
                E = a.E
            elif a.beton is not None and catalogue is not None:
                E = catalogue.beton(a.beton)["Ecm_MPa"]
            else:
                raise ErreurAppui(f"dalle {nom} : donnez E (MPa) ou une classe de béton de la base")
            k = raideurs.raideur_dalle(E, a.epaisseur, a.longueur, a.symetrique)  # déjà par mètre d'écran
    else:
        raise ErreurAppui(f"appui {nom} : type inconnu {a.type}")
    F0 = raideurs.force_horizontale(a.precharge, a.espacement, angle) if a.precharge else 0.0
    unilateral = a.unilateral if a.unilateral is not None else a.type != "dalle"
    infos = a.model_dump()
    infos.update(rigidite_lierne(nom, a, catalogue))
    return DefAppui(nom=nom, cote=a.cote, raideur=float(k), precharge=float(F0), unilateral=unilateral,
                    type=a.type, infos=infos)


def rigidite_lierne(nom: str, a, catalogue=None) -> dict:
    """Rigidité de flexion E·Iy (kN·m²) de la lierne d'un appui, pour la modéliser en pseudo-3D
    comme une poutre horizontale continue au niveau des appuis (flexion autour de son axe fort,
    âme horizontale et ailes parallèles à la paroi, comme dans le module assemblages ; torsion
    négligée). Renvoie {} sans lierne, et {"EI_lierne": None, "lierne_motif": …} si la base ne
    permet pas de la chiffrer (profil inconnu, nuance d'acier absente)."""
    if not a.lierne:
        return {}
    if catalogue is None:
        return {"EI_lierne": None, "lierne_motif": f"appui {nom} : base matériaux indisponible pour la lierne {a.lierne}"}
    try:
        prof = catalogue.profil(a.lierne)
    except KeyError:
        return {"EI_lierne": None, "lierne_motif": f"appui {nom} : lierne {a.lierne} absente de la base"}
    if not a.acier:
        return {"EI_lierne": None, "lierne_motif": f"appui {nom} : nuance d'acier de la lierne {a.lierne} non donnée (mot-clé acier)"}
    try:
        E = catalogue.acier(a.acier).get("E_MPa")
    except KeyError:
        E = None
    if E is None or not prof.get("Iy_cm4"):
        return {"EI_lierne": None, "lierne_motif": f"appui {nom} : module d'Young ou inertie de la lierne {a.lierne} inconnus"}
    return {"EI_lierne": float(E) * 1e3 * float(prof["Iy_cm4"]) * 1e-8}
