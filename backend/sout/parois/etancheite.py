"""Étanchéité hydraulique d'un écran de soutènement.

Trois états, clé `paroi.etancheite` du script :
- `etanche` : aucun passage d'eau à travers l'écran (faces coupées dans le réseau d'écoulement) ;
- `non_etanche` : l'écran est transparent pour l'eau (pieux disjoints, berlinoise à blindage non jointif) ;
  hors écoulement 2D, la nappe côté terre est ramenée au niveau de l'eau côté fouille au droit de l'écran ;
- `partielle` : l'écran oppose une résistance hydraulique R = e_p / k_p (s), loi de Darcy v = Δh / R,
  placée en série avec le sol de part et d'autre (résistances hydrauliques additives : Cedergren H.R.,
  *Seepage, Drainage and Flow Nets*, 3e éd., Wiley, 1989, ch. 3 ; Bear J. (1972), *Dynamics of Fluids
  in Porous Media*, écoulement à travers des couches en série).

Valeur par défaut selon le type de paroi : HYPOTHÈSE DE PROJET (pas une valeur de norme), à ajuster dans
le script : paroi moulée, pieux sécants et palplanches (serrures) sont supposés étanches ; pieux disjoints et
berlinoise non étanches.
"""
from __future__ import annotations

DEFAUT_PAR_TYPE: dict[str, str] = {
    "paroi_moulee": "etanche", "pieux_secants": "etanche", "palplanche": "etanche",
    "pieux_disjoints": "non_etanche", "berlinoise": "non_etanche",
}
ETATS = ("etanche", "non_etanche", "partielle")


def etancheite_de(p) -> str:
    """État d'étanchéité de l'écran : clé du script, sinon défaut selon le type (hypothèse documentée ci-dessus)."""
    et = getattr(p, "etancheite", None)
    return et if et in ETATS else DEFAUT_PAR_TYPE.get(getattr(p, "type", ""), "etanche")


def epaisseur_hydraulique_de(p) -> float | None:
    """Épaisseur traversée par l'eau (m) : paroi.epaisseur_hydraulique, sinon épaisseur de paroi moulée ou diamètre des pieux."""
    for cle in ("epaisseur_hydraulique", "epaisseur", "diametre"):
        v = getattr(p, cle, None)
        if v:
            return float(v)
    return None


def resistance_paroi(p) -> float | None:
    """Résistance hydraulique R = e_p / k_p (s) d'un écran partiellement étanche (loi de Darcy : v = Δh / R) ;
    None si l'écran n'est pas « partielle » ou si une donnée manque."""
    if etancheite_de(p) != "partielle":
        return None
    k = getattr(p, "k_paroi", None)
    e = epaisseur_hydraulique_de(p)
    if not k or not e:
        return None
    return float(e) / float(k)
