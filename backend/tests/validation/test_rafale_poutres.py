"""Rafale d'exemples élémentaires — poutres (type RDM7) et poutres sur fondation de Winkler.

Chaque cas du registre sout.validation.cas_elementaires compare des grandeurs calculées à des
formules de RDM citées ; les tolérances sont celles du registre (exactes aux nœuds pour les
charges nodales cohérentes, 1 % pour les solutions de Hetényi sur une poutre longue mais finie).

Les cas sont calculés au moment où leur test s'exécute (une fois), pas à la collecte.
"""
from functools import cache

import pytest

from sout.validation.cas_elementaires import CAS_POUTRES, cas_poutres


@cache
def _cas() -> list:
    return cas_poutres()


@pytest.mark.parametrize("i", range(len(CAS_POUTRES)), ids=[f.__name__ for f in CAS_POUTRES])
def test_cas_poutre(i):
    cas = _cas()[i]
    for g in cas.grandeurs:
        assert g.ok, (f"{cas.nom} — {g.libelle} : attendu {g.attendu:.6g} {g.unite}, calculé {g.calcule:.6g}, "
                      f"écart {g.ecart:.2e} > {g.tolerance:.0e} ({g.source})")


def test_registre_complet():
    noms = [c.nom for c in _cas()]
    assert len(noms) == len(set(noms)) >= 18
    assert all(c.courbes for c in _cas())
