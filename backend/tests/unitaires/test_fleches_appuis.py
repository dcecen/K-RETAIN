"""Flèches des butons et des liernes (module de vérification, étape 4 de la vue 3D)."""
import math

import pytest

from sout.verifs_struct import ec3
from sout.verifs_struct.elements import G, fleche_barre, fleche_lierne, section_element


def _tube_711x16() -> dict:
    """Tube 711 × 16 : A = π(D² − d²)/4, I = π(D⁴ − d⁴)/64 (calculés ici, indépendamment du catalogue)."""
    D, t = 0.711, 0.016
    d = D - 2 * t
    A = math.pi * (D**2 - d**2) / 4
    I = math.pi * (D**4 - d**4) / 64
    return {"ref": "tube 711x16", "A_cm2": A * 1e4, "I_cm4": I * 1e8, "E": 210000.0, "masse_kg_m": A * 7850.0, "fy": 355.0}


def test_fleche_buton_formule_a_la_main():
    """f = 5 g L⁴ / (384 EI) × 1/(1 − N/Ncr), tube 711×16, L = 24 m, N = 3 243 kN."""
    sec = _tube_711x16()
    L, N = 24.0, 3243.0
    r = fleche_barre(sec, N, L)
    E = sec["E"] * 1e3
    I = sec["I_cm4"] * 1e-8
    g = sec["masse_kg_m"] * G / 1000
    f0 = 5 * g * L**4 / (384 * E * I)
    Ncr = math.pi**2 * E * I / L**2
    attendu = f0 / (1 - N / Ncr)
    assert r["N_cr_kN"] == pytest.approx(ec3.n_cr(sec["E"], sec["I_cm4"], L), rel=1e-9)
    assert r["fleche_poids_propre_m"] == pytest.approx(f0, rel=1e-9)
    assert r["fleche_m"] == pytest.approx(attendu, rel=0.01)
    assert r["fleche_m"] > r["fleche_poids_propre_m"]
    assert r["raccourcissement_m"] == pytest.approx(N * L / (E * sec["A_cm2"] * 1e-4), rel=1e-9)
    # sans compression : poids propre seul ; barre inclinée : poids projeté
    assert fleche_barre(sec, N, L, avec_compression=False)["fleche_m"] == pytest.approx(f0, rel=1e-9)
    assert fleche_barre(sec, 0.0, L, angle=60.0)["fleche_m"] == pytest.approx(f0 * 0.5, rel=1e-9)


def test_fleche_buton_instable_si_N_depasse_Ncr():
    sec = _tube_711x16()
    r = fleche_barre(sec, 1e6, 24.0)
    assert math.isinf(r["fleche_m"])


def test_fleche_lierne_formule():
    p = {"Iy_cm4": 57680.0, "E_MPa": 210000.0}      # HEB 400
    r = fleche_lierne(p, 141.15, 6.0)
    assert r["fleche_m"] == pytest.approx(141.15 * 6.0**4 / (384 * 210000e3 * 57680e-8), rel=1e-9)
    assert r["approchee"] is True


def test_fleche_avec_element_de_la_base():
    from sout.materiaux.base import catalogue_par_defaut

    sec = section_element("modulaire_A", None, catalogue_par_defaut())
    r = fleche_barre(sec, 846.9, 18.0)
    assert 0 < r["fleche_m"] < 0.2
    assert r["N_cr_kN"] > 846.9
