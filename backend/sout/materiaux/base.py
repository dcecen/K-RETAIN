"""Base matériaux SQLite : profilés, palplanches, butons modulaires, armatures
de tirants, aciers, bétons.

La base (backend/data/materiaux.sqlite) est reconstruite à partir :
1. du jeu DEMO livré (sout/materiaux/donnees/demo_*.csv), marqué `demo = 1` :
   valeurs d'illustration à remplacer par les catalogues fournisseurs ;
2. de tous les catalogues déposés dans docs/catalogues (CSV ou Excel).
Les profilés en I et les tubes peuvent n'être donnés que par leurs dimensions :
les propriétés manquantes sont alors calculées (sout.materiaux.sections).
"""
from __future__ import annotations

import sqlite3
from functools import lru_cache
from pathlib import Path

from . import sections

RACINE = Path(__file__).resolve().parents[3]
CHEMIN_BASE = RACINE / "backend" / "data" / "materiaux.sqlite"
DONNEES_DEMO = Path(__file__).resolve().parent / "donnees"
CATALOGUES = RACINE / "docs" / "catalogues"

# table -> colonnes (clé primaire en premier). Unités dans le nom de colonne.
TABLES: dict[str, list[str]] = {
    "profiles": ["ref", "famille", "h_mm", "b_mm", "tw_mm", "tf_mm", "r_mm", "D_mm", "t_mm",
                 "A_cm2", "Iy_cm4", "Iz_cm4", "Wel_y_cm3", "Wel_z_cm3", "Wpl_y_cm3", "Wpl_z_cm3",
                 "iy_cm", "iz_cm", "Avz_cm2", "masse_kg_m", "source", "demo"],
    "palplanches": ["ref", "fabricant", "forme", "largeur_mm", "h_mm", "t_mm", "s_mm",
                    "A_cm2_m", "I_cm4_m", "Wel_cm3_m", "Wpl_cm3_m", "masse_kg_m2", "classe", "source", "demo"],
    "butons": ["ref", "fabricant", "element", "longueur_m", "A_cm2", "I_cm4", "W_cm3", "D_mm", "t_mm",
               "N_Rd_kN", "masse_kg", "E_MPa", "acier", "source", "demo"],
    "armatures": ["ref", "type", "A_cm2", "fyk_MPa", "fpk_MPa", "fp01k_MPa", "E_MPa", "source", "demo"],
    "aciers": ["nuance", "fy_MPa", "fu_MPa", "E_MPa", "norme", "demo"],
    "betons": ["classe", "fck_MPa", "fcm_MPa", "fctm_MPa", "Ecm_MPa", "norme", "demo"],
}
TEXTE = {"ref", "famille", "fabricant", "forme", "element", "acier", "source", "type", "nuance", "norme",
         "classe"}


class ReferenceInconnue(KeyError):
    def __str__(self) -> str:
        return f"référence « {self.args[0]} » absente de la base matériaux"


def _completer_profil(ligne: dict) -> dict:
    """Calcule les propriétés manquantes d'un profilé à partir de ses dimensions."""
    if ligne.get("A_cm2") not in (None, ""):
        return ligne
    try:
        if ligne.get("D_mm") and ligne.get("t_mm"):
            calc = sections.tube(float(ligne["D_mm"]), float(ligne["t_mm"]))
        elif all(ligne.get(k) for k in ("h_mm", "b_mm", "tw_mm", "tf_mm")):
            calc = sections.profil_i(float(ligne["h_mm"]), float(ligne["b_mm"]), float(ligne["tw_mm"]),
                                     float(ligne["tf_mm"]), float(ligne.get("r_mm") or 0))
        else:
            return ligne
    except ValueError:
        return ligne
    for k, v in calc.items():
        if ligne.get(k) in (None, ""):
            ligne[k] = v
    return ligne


def creer(connexion: sqlite3.Connection) -> None:
    for table, cols in TABLES.items():
        defs = ", ".join(f"{c} {'TEXT' if c in TEXTE else 'REAL'}" + (" PRIMARY KEY" if i == 0 else "")
                         for i, c in enumerate(cols))
        connexion.execute(f"CREATE TABLE IF NOT EXISTS {table} ({defs})")


def inserer(connexion: sqlite3.Connection, table: str, lignes: list[dict]) -> int:
    if table not in TABLES:
        raise ValueError(f"table inconnue : {table} (attendu : {', '.join(TABLES)})")
    cols = TABLES[table]
    n = 0
    for brut in lignes:
        ligne = {k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in brut.items() if k}
        if table == "profiles":
            ligne = _completer_profil(ligne)
        if not ligne.get(cols[0]):
            continue
        valeurs = []
        for c in cols:
            v = ligne.get(c)
            if v in ("", None):
                v = None
            elif c not in TEXTE:
                v = float(str(v).replace(",", "."))
            valeurs.append(v)
        connexion.execute(f"INSERT OR REPLACE INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                          valeurs)
        n += 1
    return n


class Catalogue:
    """Accès en lecture à la base matériaux."""

    def __init__(self, chemin: Path):
        self.chemin = chemin

    def _connexion(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.chemin)
        c.row_factory = sqlite3.Row
        return c

    def _ligne(self, table: str, cle: str) -> dict | None:
        col = TABLES[table][0]
        with self._connexion() as c:
            r = c.execute(f"SELECT * FROM {table} WHERE {col} = ?", (cle,)).fetchone()
        return dict(r) if r else None

    def lister(self, table: str) -> list[dict]:
        with self._connexion() as c:
            return [dict(r) for r in c.execute(f"SELECT * FROM {table} ORDER BY {TABLES[table][0]}")]

    def references(self) -> dict[str, list[str]]:
        return {t: [r[TABLES[t][0]] for r in self.lister(t)] for t in TABLES}

    def profil(self, ref: str) -> dict:
        r = self._ligne("profiles", ref)
        if r is None:
            raise ReferenceInconnue(ref)
        return r

    def palplanche(self, ref: str) -> dict:
        r = self._ligne("palplanches", ref)
        if r is None:
            raise ReferenceInconnue(ref)
        return r

    def acier(self, nuance: str) -> dict:
        r = self._ligne("aciers", nuance)
        if r is None:
            raise ReferenceInconnue(nuance)
        return r

    def beton(self, classe: str) -> dict:
        r = self._ligne("betons", classe)
        if r is None:
            raise ReferenceInconnue(classe)
        return r

    def element(self, ref: str) -> dict:
        """Élément d'appui : buton modulaire, profilé ou armature (dans cet ordre)."""
        for table in ("butons", "profiles", "armatures"):
            r = self._ligne(table, ref)
            if r is not None:
                return {**r, "categorie": table}
        raise ReferenceInconnue(ref)


def _lire_fichiers(dossier: Path) -> list[tuple[str, list[dict]]]:
    from .importer import lire_fichier

    lots = []
    for f in sorted(dossier.glob("*")):
        if f.suffix.lower() in (".csv", ".xlsx") and not f.name.startswith("modele_"):
            lots.extend(lire_fichier(f))
    return lots


def reconstruire(chemin: Path = CHEMIN_BASE, catalogues: Path = CATALOGUES) -> dict[str, int]:
    """Recrée la base : jeu DEMO puis catalogues utilisateur (qui remplacent la démo à référence égale)."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    if chemin.exists():
        chemin.unlink()
    compte: dict[str, int] = {}
    with sqlite3.connect(chemin) as c:
        creer(c)
        for dossier in (DONNEES_DEMO, catalogues):
            if not dossier.exists():
                continue
            for table, lignes in _lire_fichiers(dossier):
                compte[table] = compte.get(table, 0) + inserer(c, table, lignes)
    catalogue_par_defaut.cache_clear()
    return compte


@lru_cache(maxsize=1)
def catalogue_par_defaut() -> Catalogue:
    if not CHEMIN_BASE.exists():
        reconstruire()
    return Catalogue(CHEMIN_BASE)
