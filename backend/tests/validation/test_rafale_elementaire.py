"""Rafale d'exemples élémentaires — plaque (Timoshenko), écran 2D (équilibre limite, balayages), pseudo-3D
(coupes 2D assemblées contre vraie plaque, double écran). Les cas de poutres sont dans
test_rafale_poutres.py. Chaque grandeur du registre est comparée à sa référence avec la tolérance du
registre (5 % au plus pour les cas de validation, bien moins pour les cas exacts).

Les cas sont calculés au moment où leur test s'exécute (une fois par famille), pas à la collecte :
`pytest -k autre_chose` ne lance plus les 45 calculs."""
from functools import cache

import pytest

from sout.validation.cas_ecran import CAS_ECRAN, cas_ecran
from sout.validation.cas_plaque import CAS_PLAQUE, cas_plaque
from sout.validation.cas_pseudo3d import CAS_PSEUDO3D_RAPIDES, cas_pseudo3d

FAMILLES = {"plaque": (CAS_PLAQUE, cas_plaque), "ecran": (CAS_ECRAN, cas_ecran),
            "pseudo3d": (CAS_PSEUDO3D_RAPIDES, lambda: cas_pseudo3d(rapide=True))}
PARAMS = [(fam, i) for fam, (fabriques, _) in FAMILLES.items() for i in range(len(fabriques))]
IDS = [f"{fam}-{FAMILLES[fam][0][i].__name__}" for fam, i in PARAMS]


@cache
def _cas(famille: str) -> list:
    return FAMILLES[famille][1]()


@pytest.mark.parametrize("famille,i", PARAMS, ids=IDS)
def test_cas_elementaire(famille, i):
    cas = _cas(famille)[i]
    assert cas.grandeurs
    for g in cas.grandeurs:
        assert g.tolerance <= 0.05 or g.echelle is not None
        assert g.ok, (f"{cas.nom} — {g.libelle} : attendu {g.attendu:.6g} {g.unite}, calculé {g.calcule:.6g}, "
                      f"écart {g.ecart:.2e} > {g.tolerance:.0e} ({g.source})")
