"""Description géométrique d'un assemblage, partagée par le schéma 2D (projections
avec coupes hachurées) et la vue de détail 3D.

Repère de l'assemblage (mm) : x vers la paroi (le buton arrive par x < 0),
y le long de la lierne, z vertical vers le haut. Origine : point d'appui sur
la face de la lierne (ou de la paroi) à la cote de l'appui.

Un schéma contient :
- des solides repérés (boîte, cylindre, prisme extrudé) avec un numéro de
  nomenclature, un matériau et une liste de paramètres dont ils dépendent ;
- des soudures (segment, gorge a, symbole ISO 2553 : angle ou pleine pénétration) ;
- des cotes (deux points, texte, paramètre associé) par vue ;
- des efforts (point, direction, valeur) ;
- des vues : élévation (plan xz, vue depuis −y), coupe (plan de coupe), dessus (plan xy).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Solide:
    repere: int
    nom: str
    forme: str                   # "boite" | "cylindre" | "prisme"
    materiau: str = "acier"      # acier | boulon | beton | bois | soudure | sol
    centre: list = field(default_factory=lambda: [0.0, 0.0, 0.0])
    dims: list = field(default_factory=lambda: [10.0, 10.0, 10.0])   # boîte : lx, ly, lz ; cylindre : d, L
    axe: str = "x"               # cylindre / prisme : axe d'extrusion
    points: list | None = None   # prisme : polygone dans le plan ⟂ axe, [[u, v], ...] (u, v = autres axes dans l'ordre)
    parametres: list = field(default_factory=list)   # paramètres dont dépend ce solide (surlignage)
    masque: bool = False         # non compté dans la nomenclature (ex. tronçon de buton existant)


@dataclass
class Soudure:
    p1: list
    p2: list
    a: float                     # gorge (mm)
    type: str = "angle"          # angle | penetration
    contour: bool = False        # soudure périphérique
    reperes: list = field(default_factory=list)
    parametre: str | None = None


@dataclass
class Cote:
    p1: list
    p2: list
    texte: str
    vue: str                     # elevation | coupe | dessus
    parametre: str | None = None
    decalage: float = 25.0       # mm, décalage de la ligne de cote


@dataclass
class Effort:
    point: list
    direction: list              # vecteur unitaire
    valeur: float                # kN
    texte: str
    couleur: str = "effort"


@dataclass
class Vue:
    nom: str
    plan: str                    # "xz" (élévation), "yz" (vue de côté), "xy" (dessus)
    coupe: dict | None = None    # {"axe": "y", "pos": 0.0} : plan de coupe perpendiculaire à l'axe


@dataclass
class Schema:
    solides: list[Solide] = field(default_factory=list)
    soudures: list[Soudure] = field(default_factory=list)
    cotes: list[Cote] = field(default_factory=list)
    efforts: list[Effort] = field(default_factory=list)
    vues: list[Vue] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def ajouter(self, s: Solide) -> Solide:
        self.solides.append(s)
        return s

    def nomenclature(self) -> list[dict]:
        vus = {}
        for s in self.solides:
            if s.masque:
                continue
            if s.repere not in vus:
                vus[s.repere] = {"repere": s.repere, "nom": s.nom, "materiau": s.materiau, "nombre": 0}
            vus[s.repere]["nombre"] += 1
        return [vus[k] for k in sorted(vus)]

    def vers_dict(self) -> dict:
        return {"solides": [asdict(s) for s in self.solides], "soudures": [asdict(s) for s in self.soudures],
                "cotes": [asdict(c) for c in self.cotes], "efforts": [asdict(e) for e in self.efforts],
                "vues": [asdict(v) for v in self.vues], "notes": self.notes, "nomenclature": self.nomenclature()}


# ----------------------------------------------------------------------------- aides
def boite(rep, nom, centre, dims, materiau="acier", params=(), masque=False) -> Solide:
    return Solide(rep, nom, "boite", materiau, list(centre), list(dims), "x", None, list(params), masque)


def cylindre(rep, nom, centre, d, L, axe, materiau="acier", params=(), masque=False) -> Solide:
    return Solide(rep, nom, "cylindre", materiau, list(centre), [d, L], axe, None, list(params), masque)


def prisme(rep, nom, points, axe, pos, epaisseur, materiau="acier", params=()) -> Solide:
    """Prisme extrudé de `epaisseur` le long de `axe`, centré en `pos` sur cet axe ; points dans le plan ⟂."""
    return Solide(rep, nom, "prisme", materiau, [pos, pos, pos], [epaisseur], axe, [list(p) for p in points], list(params))


def boulons(schema: Schema, rep: int, nom: str, positions: list, d: float, longueur: float, axe: str,
            params=(), tete: float | None = None) -> None:
    """Boulons avec tête et écrou (deux disques) à chaque position (centre de la tige)."""
    k = {"x": 0, "y": 1, "z": 2}[axe]
    dt = tete or 1.6 * d
    for p in positions:
        schema.ajouter(cylindre(rep, nom, p, d, longueur, axe, "boulon", params))
        c1 = list(p); c1[k] -= longueur / 2 + 0.3 * d
        c2 = list(p); c2[k] += longueur / 2 + 0.3 * d
        schema.ajouter(cylindre(rep, nom, c1, dt, 0.6 * d, axe, "boulon", params, masque=True))
        schema.ajouter(cylindre(rep, nom, c2, dt, 0.8 * d, axe, "boulon", params, masque=True))


def profil_i(schema: Schema, rep: int, nom: str, centre, L: float, axe: str, h: float, b: float, tw: float, tf: float,
             params=(), materiau="acier") -> list[Solide]:
    """Profilé en I (âme verticale) : trois boîtes, extrudé le long de `axe` (x ou y)."""
    cx, cy, cz = centre
    out = []
    if axe == "y":
        out.append(schema.ajouter(boite(rep, nom, [cx, cy, cz + (h - tf) / 2], [b, L, tf], materiau, params)))
        out.append(schema.ajouter(boite(rep, nom, [cx, cy, cz - (h - tf) / 2], [b, L, tf], materiau, params, masque=True)))
        out.append(schema.ajouter(boite(rep, nom, [cx, cy, cz], [tw, L, h - 2 * tf], materiau, params, masque=True)))
    else:
        out.append(schema.ajouter(boite(rep, nom, [cx, cy, cz + (h - tf) / 2], [L, b, tf], materiau, params)))
        out.append(schema.ajouter(boite(rep, nom, [cx, cy, cz - (h - tf) / 2], [L, b, tf], materiau, params, masque=True)))
        out.append(schema.ajouter(boite(rep, nom, [cx, cy, cz], [L, tw, h - 2 * tf], materiau, params, masque=True)))
    return out


def tube(schema: Schema, rep: int, nom: str, centre, D: float, L: float, axe: str, params=(), masque=False) -> Solide:
    return schema.ajouter(cylindre(rep, nom, centre, D, L, axe, "acier", params, masque))
