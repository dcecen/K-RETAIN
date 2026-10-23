"""Rafale d'exemples élémentaires — plaque (Timoshenko), écran 2D (équilibre limite, balayages), pseudo-3D
(coupes 2D assemblées contre vraie plaque, double écran). Les cas de poutres sont dans
test_rafale_poutres.py. Chaque grandeur du registre est comparée à sa référence avec la tolérance du
registre (5 % au plus pour les cas de validation, bien moins pour les cas exacts)."""
import pytest

from sout.validation.cas_ecran import cas_ecran
from sout.validation.cas_plaque import cas_plaque
from sout.validation.cas_pseudo3d import cas_pseudo3d

CAS = cas_plaque() + cas_ecran() + cas_pseudo3d(rapide=True)


@pytest.mark.parametrize("cas", CAS, ids=[c.nom for c in CAS])
def test_cas_elementaire(cas):
    assert cas.grandeurs
    for g in cas.grandeurs:
        assert g.tolerance <= 0.05 or g.echelle is not None
        assert g.ok, (f"{cas.nom} — {g.libelle} : attendu {g.attendu:.6g} {g.unite}, calculé {g.calcule:.6g}, "
                      f"écart {g.ecart:.2e} > {g.tolerance:.0e} ({g.source})")
