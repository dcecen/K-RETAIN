"""Fichiers RIDO de démonstration, sans feuille Excel, pour comparer K-Retain à RIDO.

    cd backend
    .venv/Scripts/python.exe -m outils.rido_exemples        # écrit exemples/rido/R01_….rid à R07_….rid
    .venv/Scripts/python.exe -m outils.comparaison_rido     # convertit, calcule, écrit le classeur

Chaque fichier reprend la structure du fichier RIDO réel fourni (docs/rido/berlinoise_IPE400_excel.rid) :
mêmes commandes, mêmes formules du kh (Schmitt borné par Ménard), même position des valeurs dans les lignes
de couche ; seules les valeurs changent et elles sont écrites en clair (#variables) au lieu de xlc().
Écarts volontaires avec le fichier fourni : coe entre FF et Zf (fiche seule), pas de rrc (sens inconnu),
pas de variable B (inutilisée, et seule la casse la distingue de b).

Sols FICTIFS, valeurs d'illustration : ces cas servent à comparer deux logiciels sur les mêmes données, pas à
dimensionner. Profilés : dimensions et inerties des tables de profilés européens (IPE, HEB) du catalogue
ArcelorMittal « Sections et laminés marchands ».
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from outils.rido_sans_excel import ecrire_rido

RACINE = Path(__file__).resolve().parents[2]
DOSSIER = RACINE / "exemples" / "rido"

# Profilé : (I cm4, h m, b m, Wel cm3), catalogue ArcelorMittal (profilés européens)
PROFILS = {"IPE400": (23130, 0.400, 0.180, 1160), "IPE500": (48200, 0.500, 0.200, 1930),
           "HEB300": (25170, 0.300, 0.300, 1680)}


@dataclass
class Couche:
    nom: str
    base: float
    gamma: float
    gamma_dejauge: float
    EM: float          # MPa
    alpha: float
    phi: float
    c: float = 0.0
    delta_a: float = 0.0   # rapport δa/φ
    delta_p: float = 0.0   # rapport δp/φ


@dataclass
class Cas:
    code: str
    titre: str
    description: list[str]
    profil: str
    esp: float
    Z0: float
    Zf: float
    TN: float
    fonds: list[tuple[str, float]]     # (titre de la phase, cote de fond)
    nappe: float
    couches: list[Couche]
    surcharge: str | None = None       # ligne sub, telle qu'écrite dans le fichier fourni
    notes: list[str] = field(default_factory=list)

    @property
    def fichier(self) -> str:
        return f"{self.code}.rid"


SABLE = [Couche("Sable", 120.0, 19, 10, 10, 0.33, 32)]
BICOUCHE = [Couche("Limon", 134.0, 19, 9, 5, 0.5, 26, 5), Couche("Sable", 120.0, 20, 10, 15, 0.33, 34)]
TRICOUCHE = [Couche("Remblai", 135.6, 18, 8, 3, 0.5, 25), Couche("Limon", 133.0, 19, 9, 6, 0.5, 27, 8),
             Couche("Sable graveleux", 118.0, 20, 11, 25, 0.33, 36)]

CAS = [
    Cas("R01_sable_homogene", "R01 IPE400 esp 2.1m sable homogene H=3m",
        ["Berlinoise autostable, sable homogène, sans nappe ni surcharge, δ = 0",
         "Cas de base : Ka et Kp de Rankine identiques aux tables de Caquot-Kérisel (δ = 0, terrain horizontal)"],
        "IPE400", 2.1, 136.6, 128.6, 136.6, [("Phase 1 - Excavation à FF", 133.6)], 120.0, SABLE),
    Cas("R02_surcharge_bande", "R02 IPE400 esp 2.1m sable + surcharge de bande",
        ["R01 avec la surcharge du fichier fourni : sub(1) TN 0.50 10.5 5"],
        "IPE400", 2.1, 136.6, 128.6, 136.6, [("Phase 1 - Excavation à FF", 133.6)], 120.0, SABLE,
        surcharge="sub(1) TN 0.50 10.5 5"),
    Cas("R03_bicouche", "R03 IPE400 esp 2.1m limon sur sable H=3m",
        ["Limon cohérent (c = 5 kPa) sur sable, sans nappe, δ = 0"],
        "IPE400", 2.1, 136.6, 128.6, 136.6, [("Phase 1 - Excavation à FF", 133.6)], 120.0, BICOUCHE),
    Cas("R04_HEB300_tricouche", "R04 HEB300 esp 2.0m tricouche H=4m",
        ["Profilé HEB 300, fouille de 4 m, fiche de 6 m, trois couches, δ = 0"],
        "HEB300", 2.0, 136.6, 126.6, 136.6, [("Phase 1 - Excavation à FF", 132.6)], 118.0, TRICOUCHE),
    Cas("R05_nappe_fiche", "R05 IPE400 esp 2.1m limon sur sable nappe dans la fiche",
        ["R03 avec une nappe à 131,0 sous le fond de fouille, même niveau des deux côtés (poids déjaugés)"],
        "IPE400", 2.1, 136.6, 128.6, 136.6, [("Phase 1 - Excavation à FF", 133.6)], 131.0, BICOUCHE),
    Cas("R06_frottement_poussee", "R06 IPE400 esp 2.1m sable delta_a=2/3 phi",
        ["R01 avec un frottement sol-écran côté poussée δa/φ = 2/3 (δp = 0)",
         "Écart attendu de quelques % sur Ka : K-Retain (Coulomb) face aux tables de Caquot-Kérisel"],
        "IPE400", 2.1, 136.6, 128.6, 136.6, [("Phase 1 - Excavation à FF", 133.6)], 120.0,
        [Couche("Sable", 120.0, 19, 10, 10, 0.33, 32, 0, 0.667, 0.0)],
        notes=["dans la sortie RIDO, δa doit être lu comme 2/3 φ (rapport) et non comme un angle de 0,667°"]),
    Cas("R07_deux_phases", "R07 IPE500 esp 2.4m deux terrassements H=3.5m",
        ["Profilé IPE 500, terrassement en deux phases (2 m puis 3,5 m), limon sur sable, δ = 0",
         "coe entre le fond final et le pied, déclaré dès la phase 1 (comme K-Retain : zone fixe)"],
        "IPE500", 2.4, 136.6, 127.1, 136.6,
        [("Phase 1 - Excavation à 134.6", 134.6), ("Phase 2 - Excavation à FF", 133.1)], 120.0, BICOUCHE),
]


def texte_rido(cas: Cas) -> str:
    I, h, b, W = PROFILS[cas.profil]
    FF = cas.fonds[-1][1]
    L = [cas.titre,
         "*Cas de démonstration K-Retain / RIDO : sol fictif, valeurs d'illustration",
         *[f"*{d}" for d in cas.description],
         *[f"*À vérifier : {n}" for n in cas.notes],
         "*Fichier indépendant de toute feuille Excel (structure du fichier RIDO fourni)",
         "*Autostable",
         "*Provisoire",
         f"#TN = {cas.TN:g}",
         f"#FF = {FF:g}",
         f"#NAPPE = {cas.nappe:g}",
         f"#Z0 = {cas.Z0:g}",
         f"#Zf = {cas.Zf:g}",
         f"*Profilé {cas.profil} : I en cm4, h et b en m, W en cm3",
         f"#I = {I}",
         f"#esp = {cas.esp:g}",
         "#EI = 2.1*I/esp",
         f"#b = {b:g}",
         f"#h = {h:g}",
         f"#W = {W}",
         "Z0 0",
         "Zf EI 0 W",
         "TN"]
    for i, c in enumerate(cas.couches, 1):
        L += [f"*Couche {i} : {c.nom}",
              f"#Zb{i} = {c.base:g}", f"#Ga{i} = {c.gamma:g}", f"#Gd{i} = {c.gamma_dejauge:g}",
              f"#EM{i} = {c.EM:g}", f"#Al{i} = {c.alpha:g}", f"#Ph{i} = {c.phi:g}", f"#Co{i} = {c.c:g}",
              f"#Da{i} = {c.delta_a:g}", f"#Dp{i} = {c.delta_p:g}",
              f"#C{i} = 2*(EM{i}*1000/Al{i})^(4/3)/(EI^(1/3))",
              f"#P{i} = 6*EM{i}*1000/(4*0.6/3/b*(2.65*b/0.6)^Al{i}+Al{i})/esp",
              f"#P{i} = (b>=0.6)*P{i}",
              f"#P{i}bis= 6*EM{i}*1000/(4/3*2.65^Al{i}+Al{i})/esp",
              f"#P{i}bis = (b<0.6)*P{i}bis",
              f"#Re{i} = min(C{i};max(P{i};P{i}bis))",
              f"Zb{i} Ga{i} Gd{i} 0 0 0 Ph{i} Co{i}",
              f"+ Da{i} Dp{i} Re{i}"]
    L.append("NAPPE .05")
    for k, (titre, fond) in enumerate(cas.fonds):
        L.append(f'*"{titre}')
        if k == 0:
            if cas.surcharge:
                L.append(cas.surcharge)
            L.append("coe FF Zf min(1;(b+2*h)/esp)")
        L += ["ber(2) FF" if fond == FF else f"ber(2) {fond:g}", "cal(2)"]
    nom = cas.fonds[-1][0].split(" - ")[0]
    L += [f'*"{nom} - MEL', "tel(0,1)",
          "fap 1.00 1.35 1/1.10 1.00 1.00 1.50/1.35 1.35 1.00 1.00 1.00", "*fap ",
          "1.00 1.00 1/1.10/1.35 1.00 1.00 1.50/1.35 1.00 1.00 1.00 1.00", "cal(2)",
          f'*"{nom} - ELU', "tel(0,0)",
          "fap 1.00 1.35 1/1.10 1.00 1.00 1.50/1.35 1.35 1.00 1.00 1.00", "*fap ",
          "1.00 1.00 1/1.10/1.35 1.00 1.00 1.50/1.35 1.00 1.00 1.00 1.00", "cal(2)",
          "fin", "bIL", "stop"]
    texte = "\n".join(L) + "\n"
    for grec, latin in (("δ", "delta "), ("φ", "phi"), ("≤", "<="), ("–", "-")):
        texte = texte.replace(grec, latin)
    return texte.replace("delta a", "delta_a").replace("delta p", "delta_p").replace("delta  ", "delta ")


# R00 : le fichier fourni, rendu indépendant de « Données RIDO.xls » par outils.rido_sans_excel, avec des cellules
# de DÉMONSTRATION (la feuille réelle n'a pas été fournie). Libellés : TN, FF, Nappe, Z0, Zf en colonne 1, « Cote » en
# ligne 1 ; profilé en colonne 6 (lignes 4 à 8) ; couches en lignes 12 à 16 (base, γ, γ', EM MPa, α, φ, c, δa, δp).
FICHIER_FOURNI = RACINE / "docs" / "rido" / "berlinoise_IPE400_excel.rid"
CELLULES_DEMO = {
    (1, 1, 3): "Cote", (1, 2, 1): "TN", (1, 2, 3): 136.6, (1, 3, 1): "FF", (1, 3, 3): 133.6,
    (1, 4, 1): "Nappe", (1, 4, 3): 125.0, (1, 5, 1): "Z0", (1, 5, 3): 136.6, (1, 6, 1): "Zf", (1, 6, 3): 128.6,
    (1, 4, 6): 23130, (1, 5, 6): 2.1, (1, 6, 6): 0.40, (1, 7, 6): 0.18, (1, 8, 6): 1160,
}
COUCHES_DEMO = [(135.6, 18, 8, 4, 0.5, 26, 0), (134.0, 19, 9, 6, 0.5, 27, 5), (132.0, 20, 10, 12, 0.33, 32, 0),
                (130.0, 20, 10, 18, 0.33, 34, 0), (120.0, 21, 11, 30, 0.33, 36, 0)]
for _i, _v in enumerate(COUCHES_DEMO):
    CELLULES_DEMO.update({(1, 12 + _i, c): x for c, x in zip((2, 4, 5, 6, 7, 8, 9, 10, 11), (*_v, 0, 0), strict=True)})


def texte_r00() -> str:
    from outils.rido_sans_excel import lire_texte, sans_excel
    from sout.script.rido import Classeur

    texte, messages = sans_excel(lire_texte(FICHIER_FOURNI), Classeur(CELLULES_DEMO), "(VALEURS DE DÉMONSTRATION)")
    if messages:
        raise RuntimeError("; ".join(messages))
    titre, _, reste = texte.partition("\n")
    avert = ("*VALEURS DE DÉMONSTRATION : la feuille Données RIDO.xls n'a pas été fournie, sol fictif (5 couches)\n"
             "*Avec la vraie feuille : python -m outils.rido_sans_excel berlinoise_IPE400_excel.rid \"Données RIDO.xlsx\"\n")
    return f"{titre}\n{avert}{reste}"


def ecrire(dossier: Path = DOSSIER) -> list[Path]:
    dossier.mkdir(parents=True, exist_ok=True)
    p = dossier / "R00_fichier_fourni_sans_excel.rid"
    ecrire_rido(p, texte_r00())
    chemins = [p]
    for cas in CAS:
        p = dossier / cas.fichier
        ecrire_rido(p, texte_rido(cas))
        chemins.append(p)
    return chemins


if __name__ == "__main__":
    for p in ecrire():
        print(p)
