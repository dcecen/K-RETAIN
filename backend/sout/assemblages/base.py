"""Socle des types d'assemblage : paramètres, contexte matériaux, vérifications communes."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

from ..verifs import Lecteur, Verif, resultat
from . import ec3_assemblages as ec3
from .geometrie import Schema

CLASSES_BOULONS = ["4.6", "5.6", "8.8", "10.9"]
DIAMETRES = [12, 16, 20, 24, 27, 30, 36]


@dataclass
class Param:
    cle: str
    libelle: str
    unite: str = "mm"
    defaut: float | str | int = 0
    mini: float | None = None
    maxi: float | None = None
    choix: list | None = None          # liste de valeurs admises (menu)
    genre: str = "nombre"              # nombre | entier | choix | profil | tube | acier | beton


@dataclass
class Contexte:
    """Matériaux résolus pour les vérifications."""
    normes: object
    catalogue: object
    fy: float                          # MPa, acier des pièces d'assemblage
    fu: float
    nuance: str
    lierne: dict | None = None         # profilé de lierne (h_mm, b_mm, tw_mm, tf_mm, r_mm, ...)
    buton: dict | None = None          # tube du buton (D_mm, t_mm)
    fck: float | None = None
    demo: bool = False
    replis: list = field(default_factory=list)   # données remplacées par une valeur de repli (dessin seulement)

    def repli(self, quoi: str, valeur):
        """Enregistre l'emploi d'une valeur de repli (non normative, non issue de la base) et la renvoie.
        Une vérification qui en a eu besoin est rendue « non vérifiable » par service.verifier."""
        if quoi not in self.replis:
            self.replis.append(quoi)
        return valeur


LIERNE_REPLI = {"h_mm": 300, "b_mm": 300, "tw_mm": 11, "tf_mm": 19, "r_mm": 27}   # gabarit de dessin seulement
TUBE_REPLI = (508.0, 12.5)                                                       # idem (D_mm, t_mm)


def lierne_de(ctx: "Contexte") -> dict:
    """Profilé de lierne du contexte, ou gabarit de repli (signalé)."""
    return ctx.lierne or ctx.repli("profilé de lierne (clé lierne : référence de la base matériaux)", dict(LIERNE_REPLI))


@dataclass
class TypeAssemblage:
    cle: str
    nom: str
    famille: str
    description: str
    parametres: list[Param]
    geometrie: Callable[[dict, dict, Contexte], Schema]
    verifications: Callable[[dict, dict, Contexte], list[Verif]]
    efforts: list[str] = field(default_factory=lambda: ["N"])   # efforts attendus (kN) : N axial, V transversal, T tirant

    def defauts(self) -> dict:
        return {p.cle: p.defaut for p in self.parametres}


REGISTRE: dict[str, TypeAssemblage] = {}


def enregistrer(t: TypeAssemblage) -> TypeAssemblage:
    REGISTRE[t.cle] = t
    return t


# ----------------------------------------------------------------------------- paramètres usuels
def p_boulons(prefixe: str = "", n: int = 4, d: int = 20, classe: str = "8.8") -> list[Param]:
    return [
        Param(prefixe + "n_boulons", "Nombre de boulons", "", n, 1, 24, genre="entier"),
        Param(prefixe + "d_boulon", "Diamètre des boulons", "mm", d, choix=DIAMETRES, genre="choix"),
        Param(prefixe + "classe_boulon", "Classe des boulons", "", classe, choix=CLASSES_BOULONS, genre="choix"),
        Param(prefixe + "e1", "Pince longitudinale e1", "mm", 40, 20, 200),
        Param(prefixe + "e2", "Pince transversale e2", "mm", 40, 20, 200),
        Param(prefixe + "p1", "Entraxe des boulons p1", "mm", 70, 30, 400),
    ]


def p_soudure(cle: str = "a_soudure", libelle: str = "Gorge des soudures d'angle", defaut: float = 6) -> Param:
    return Param(cle, libelle, "mm", defaut, 3, 20)


def grille_boulons(n: int, p1: float, p2: float) -> list[tuple[float, float]]:
    """Positions (u, v) d'une grille de n boulons sur 2 files (ou 1 si n = 1)."""
    if n == 1:
        return [(0.0, 0.0)]
    files = 2 if n % 2 == 0 else 1
    rangs = max(1, n // files)
    out = []
    for i in range(rangs):
        for j in range(files):
            out.append(((i - (rangs - 1) / 2) * p1, (j - (files - 1) / 2) * p2))
    return out[:n]


# ----------------------------------------------------------------------------- vérifications communes
def v_soudure(nom: str, longueur: float, a: float, F: float, ctx: Contexte, reperes, source_sup: str = "") -> Verif:
    lect = Lecteur(ctx.normes)
    amin = lect.v("ec3_assemblages", "soudures.gorge_min")
    fw = ec3.fw_rd(a, ctx.fu, ctx.nuance, lect)
    taux = None
    detail = f"F = {F:.0f} kN sur {longueur:.0f} mm de cordon, gorge a = {a:.0f} mm"
    if fw is not None and amin is not None:
        FRd = fw * longueur
        taux = F / FRd if FRd > 0 else math.inf
        detail += f", Fw,Rd = {FRd:.0f} kN"
        if a < amin:
            taux = max(taux, 1.01)
            detail += f" ; gorge inférieure au minimum {amin:.0f} mm"
    return resultat(nom, "soudure", None, taux, detail, "EN 1993-1-8 § 4.5.3.3 (méthode simplifiée)" + source_sup, lect,
                    "structure", reperes=reperes)


def v_boulons_traction(nom: str, n: int, d: float, classe: str, Ft: float, tp: float, ctx: Contexte, reperes,
                       effet_levier: float = 1.0) -> list[Verif]:
    """Traction de n boulons (effort total Ft, kN) et poinçonnement de la platine."""
    lect = Lecteur(ctx.normes)
    FtRd = ec3.ft_rd(d, classe, lect)
    par = Ft * effet_levier / n
    detail = f"{n} × M{int(d)} classe {classe} : Ft,Ed = {par:.1f} kN par boulon" + (f" (effet de levier ×{effet_levier:.2f})" if effet_levier != 1 else "")
    v1 = resultat(nom + " — traction des boulons", "boulons", None, None if FtRd is None else par / FtRd,
                  detail + (f", Ft,Rd = {FtRd:.1f} kN" if FtRd else ""), "EN 1993-1-8 tableau 3.4", lect, "structure", reperes=reperes)
    lect2 = Lecteur(ctx.normes)
    BpRd = ec3.bp_rd(d, tp, ctx.fu, lect2)
    v2 = resultat(nom + " — poinçonnement de la platine", "platine", None, None if BpRd is None else par / BpRd,
                  f"tp = {tp:.0f} mm" + (f", Bp,Rd = {BpRd:.1f} kN" if BpRd else ""), "EN 1993-1-8 tableau 3.4", lect2, "structure", reperes=reperes)
    return [v1, v2]


def v_boulons_cisaillement(nom: str, n: int, d: float, classe: str, Fv: float, t_min: float, e1: float, e2: float,
                           p1: float | None, ctx: Contexte, reperes, plans: int = 1, Ft: float = 0.0) -> list[Verif]:
    """Cisaillement de n boulons (effort total Fv, kN), pression diamétrale sur la pièce d'épaisseur t_min, interaction."""
    lect = Lecteur(ctx.normes)
    FvRd = ec3.fv_rd(d, classe, lect)
    par = Fv / n
    v1 = resultat(nom + " — cisaillement des boulons", "boulons", None, None if FvRd is None else par / (plans * FvRd),
                  f"{n} × M{int(d)} classe {classe}, {plans} plan(s) : Fv,Ed = {par:.1f} kN par boulon" + (f", Fv,Rd = {plans * FvRd:.1f} kN" if FvRd else ""),
                  "EN 1993-1-8 tableau 3.4", lect, "structure", reperes=reperes)
    lect2 = Lecteur(ctx.normes)
    FbRd = ec3.fb_rd(d, t_min, ctx.fu, classe, e1, e2, p1, lect2)
    v2 = resultat(nom + " — pression diamétrale", "pièce", None, None if FbRd is None else par / FbRd,
                  f"t = {t_min:.0f} mm, e1 = {e1:.0f}, e2 = {e2:.0f}" + (f", p1 = {p1:.0f}" if p1 else "") + (f" : Fb,Rd = {FbRd:.1f} kN" if FbRd else ""),
                  "EN 1993-1-8 tableau 3.4", lect2, "structure", reperes=reperes)
    out = [v1, v2]
    if Ft > 0:
        lect3 = Lecteur(ctx.normes)
        FtRd = ec3.ft_rd(d, classe, lect3)
        FvRd3 = ec3.fv_rd(d, classe, lect3)
        inter = None if (FtRd is None or FvRd3 is None) else ec3.interaction_boulon(par, plans * FvRd3, Ft / n, FtRd, lect3)
        out.append(resultat(nom + " — interaction traction-cisaillement", "boulons", None, inter,
                            f"Ft,Ed = {Ft / n:.1f} kN et Fv,Ed = {par:.1f} kN par boulon", "EN 1993-1-8 tableau 3.4", lect3, "structure", reperes=reperes))
    return out


def v_plaque_flexion(nom: str, t: float, largeur: float, m_Ed: float, ctx: Contexte, reperes, detail: str = "") -> Verif:
    """Flexion d'une plaque : moment m_Ed (kN·mm par mm de largeur) contre mpl = t²fy/(4γM0)."""
    lect = Lecteur(ctx.normes)
    mpl = ec3.m_pl_plaque(t, ctx.fy, lect)
    return resultat(nom, "platine", None, None if mpl is None else m_Ed / mpl,
                    (detail + " ; " if detail else "") + f"t = {t:.0f} mm, m_Ed = {m_Ed:.2f} kN·mm/mm" + (f", m_pl,Rd = {mpl:.2f}" if mpl else ""),
                    "EN 1993-1-8 § 6.2.4 (plaque en console, méthode simplifiée)", lect, "structure", reperes=reperes)


def v_ame_lierne(nom: str, F: float, ss: float, ctx: Contexte, reperes) -> Verif:
    """Âme de la lierne sous l'effort concentré F appliqué sur la longueur ss."""
    lect = Lecteur(ctx.normes)
    L = ctx.lierne
    if not L:
        lect.manquants.append("profilé de lierne (base matériaux)")
        return resultat(nom, "lierne", None, None, "", "EN 1993-1-5 § 6", lect, "structure", reperes=reperes)
    FRd = ec3.ame_charge_transversale(ctx.fy, L["tw_mm"], ss, L["tf_mm"], L.get("r_mm") or 0.0, lect)
    return resultat(nom, "lierne", None, None if FRd is None else F / FRd,
                    f"F = {F:.0f} kN sur ss = {ss:.0f} mm, âme tw = {L['tw_mm']:.1f} mm" + (f", FRd = {FRd:.0f} kN" if FRd else "")
                    + " — sans raidisseur ; ajouter des raidisseurs si le taux dépasse 100 %",
                    "EN 1993-1-5 § 6 (longueur efficace simplifiée, à confirmer)", lect, "structure", reperes=reperes)


def v_compression_beton(nom: str, F: float, Ac0: float, Ac1: float, ctx: Contexte, reperes) -> Verif:
    lect = Lecteur(ctx.normes)
    if ctx.fck is None:
        lect.manquants.append("classe de béton de la paroi (fck)")
        return resultat(nom, "béton", None, None, "", "EN 1992-1-1 § 6.7", lect, "structure", reperes=reperes)
    FRdu = ec3.compression_localisee_beton(ctx.fck, Ac0, Ac1, lect)
    return resultat(nom, "béton", None, None if FRdu is None else F / FRdu,
                    f"F = {F:.0f} kN sur Ac0 = {Ac0 / 100:.0f} cm² (diffusion Ac1 = {Ac1 / 100:.0f} cm²)" + (f", FRdu = {FRdu:.0f} kN" if FRdu else ""),
                    "EN 1992-1-1 § 6.7", lect, "structure", reperes=reperes)


def v_section(nom: str, element: str, N: float, V: float, M: float, A: float, Av: float, W: float, ctx: Contexte, reperes,
              source: str = "EN 1993-1-1 § 6.2") -> Verif:
    """Section d'une pièce (console, gousset, éclisse) : N/Npl + M/Mpl (+ V/Vpl si > 50 %), mm², mm³, kN, kN·mm."""
    lect = Lecteur(ctx.normes)
    Npl = ec3.n_pl(A, ctx.fy, lect) if A else None
    Vpl = ec3.v_pl(Av, ctx.fy, lect) if Av else None
    gM0 = lect.v("ec3_assemblages", "gamma_M0")
    Mpl = W * ctx.fy / gM0 / 1000 if (gM0 and W) else None
    taux = None
    detail = f"N = {N:.0f} kN, V = {V:.0f} kN, M = {M / 1000:.1f} kN·m"
    if gM0 is not None:
        taux = 0.0
        if Npl: taux += abs(N) / Npl
        if Mpl: taux += abs(M) / Mpl
        if Vpl:
            r = abs(V) / Vpl
            taux = max(taux, r) if r <= 0.5 else taux / (1 - (2 * r - 1) ** 2) if r < 1 else max(taux, r)
        detail += " ; " + ", ".join(x for x in [f"Npl = {Npl:.0f} kN" if Npl else "", f"Vpl = {Vpl:.0f} kN" if Vpl else "",
                                              f"Mpl = {Mpl / 1000:.1f} kN·m" if Mpl else ""] if x)
    return resultat(nom, element, None, taux, detail, source + " (interaction linéaire simplifiée)", lect, "structure", reperes=reperes)
