"""Convertisseur RIDO -> script K-Retain, piloté par une table de correspondance.

Aucun mot-clé RIDO n'est codé ici (CLAUDE.md, règle 1 ; prompt J7 : « ne devine
aucun mot-clé ») : la correspondance est décrite dans docs/rido/correspondance.yaml,
à remplir à partir du manuel RIDO. Tant qu'elle est vide, toutes les lignes du
fichier sont listées dans le rapport des données non reprises.

Format de la table (une entrée par mot-clé RIDO) :

    commentaires: ["*", "!"]          # préfixes de lignes ignorées
    separateurs: " ,;\\t"              # séparateurs de valeurs
    mots_cles:
      MOTCLE:                          # premier élément de la ligne (casse ignorée)
        cible: sol[]                   # chemin du script : « bloc », « bloc.champ », « bloc[] » (ajout à une liste)
        colonnes: [toit, gamma, phi]   # nom du champ pour chaque valeur suivant le mot-clé (null = ignorée)
        facteurs: { gamma: 1.0 }       # conversions d'unités (multiplication)
        fixes: { type: palplanche }    # champs ajoutés tels quels
        lignes_suivantes: 0            # nombre de lignes de valeurs qui suivent le mot-clé (0 = valeurs sur la même ligne)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from ruamel.yaml import YAML

TABLE = Path(__file__).resolve().parents[3] / "docs" / "rido" / "correspondance.yaml"


@dataclass
class Conversion:
    script: dict
    texte: str
    non_repris: list[str] = field(default_factory=list)
    repris: int = 0

    @property
    def rapport(self) -> list[str]:
        r = [f"{self.repris} ligne(s) reprise(s), {len(self.non_repris)} ligne(s) non reprise(s)."]
        return r + self.non_repris


def charger_table(chemin: Path = TABLE) -> dict:
    if not chemin.exists():
        return {}
    return YAML(typ="safe").load(chemin.read_text(encoding="utf-8")) or {}


def _valeur(v: str):
    try:
        return float(v.replace(",", ".")) if re.fullmatch(r"[-+]?\d+([.,]\d*)?([eE][-+]?\d+)?", v) else v
    except ValueError:
        return v


def _poser(script: dict, cible: str, valeurs: dict) -> None:
    if cible.endswith("[]"):
        script.setdefault(cible[:-2], []).append(valeurs)
        return
    bloc, _, champ = cible.partition(".")
    if champ:
        script.setdefault(bloc, {})
        if len(valeurs) == 1 and next(iter(valeurs)) == champ:
            script[bloc][champ] = valeurs[champ]
        else:
            script[bloc].setdefault(champ, {}).update(valeurs)
    else:
        if len(valeurs) == 1 and next(iter(valeurs)) == bloc:
            script[bloc] = valeurs[bloc]
        else:
            script.setdefault(bloc, {}).update(valeurs)


def convertir(texte: str, nom: str = "import RIDO", table: dict | None = None) -> Conversion:
    table = charger_table() if table is None else table
    mots = {str(k).upper(): v for k, v in (table.get("mots_cles") or {}).items()}
    comm = tuple(table.get("commentaires") or ())
    seps = table.get("separateurs") or " ,;\t"
    motif = "[" + re.escape(seps) + "]+"
    script: dict = {"projet": nom}
    conv = Conversion(script, "")
    lignes = texte.splitlines()
    i = 0
    while i < len(lignes):
        brute = lignes[i]
        l = brute.strip()
        i += 1
        if not l or (comm and l.startswith(comm)):
            continue
        jetons = [j for j in re.split(motif, l) if j]
        regle = mots.get(jetons[0].upper())
        if regle is None:
            conv.non_repris.append(f"ligne {i} : « {l[:80]} » (mot-clé « {jetons[0]} » absent de la table de correspondance)")
            continue
        blocs = [jetons[1:]]
        for _ in range(int(regle.get("lignes_suivantes") or 0)):
            if i < len(lignes):
                blocs.append([j for j in re.split(motif, lignes[i].strip()) if j])
                i += 1
        cols = regle.get("colonnes") or []
        fact = regle.get("facteurs") or {}
        for vals in blocs:
            if not vals and len(blocs) > 1:
                continue
            d = dict(regle.get("fixes") or {})
            for c, v in zip(cols, vals):
                if c is None:
                    continue
                x = _valeur(v)
                if c in fact and isinstance(x, float):
                    x *= fact[c]
                d[c] = x
            if len(vals) > len(cols):
                conv.non_repris.append(f"ligne {i} : valeurs en trop après « {jetons[0]} » : {' '.join(vals[len(cols):])}")
            _poser(script, regle["cible"], d)
        conv.repris += 1
    from io import StringIO

    flux = StringIO()
    y = YAML()
    y.default_flow_style = False
    entete = (f"# Script converti depuis RIDO ({nom}).\n# Données non reprises : voir le rapport de conversion.\n"
              "# Vérifiez chaque bloc avant calcul.\n")
    y.dump(script, flux)
    conv.texte = entete + flux.getvalue()
    return conv
