"""Rafale d'exemples élémentaires — poutres (type RDM7) et poutres sur fondation de Winkler.

Chaque cas du registre sout.validation.cas_elementaires compare des grandeurs calculées à des
formules de RDM citées ; les tolérances sont celles du registre (exactes aux nœuds pour les
charges nodales cohérentes, 1 % pour les solutions de Hetényi sur une poutre longue mais finie).
"""
import pytest

from sout.validation.cas_elementaires import cas_poutres

CAS = cas_poutres()


@pytest.mark.parametrize("cas", CAS, ids=[c.nom for c in CAS])
def test_cas_poutre(cas):
    for g in cas.grandeurs:
        assert g.ok, (f"{cas.nom} — {g.libelle} : attendu {g.attendu:.6g} {g.unite}, calculé {g.calcule:.6g}, "
                      f"écart {g.ecart:.2e} > {g.tolerance:.0e} ({g.source})")


def test_registre_complet():
    noms = [c.nom for c in CAS]
    assert len(noms) == len(set(noms)) >= 18
    assert all(c.courbes for c in CAS)
