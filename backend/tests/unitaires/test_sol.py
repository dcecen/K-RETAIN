"""Tests du module sol : valeurs calculées à la main ou publiées."""
import math

import numpy as np
import pytest

from sout.sol import coefficients as coef
from sout.sol.couches import Couche, contraintes_verticales
from sout.sol.kh import em_depuis_cpt, kh_schmitt
from sout.sol.surcharges import Surcharge, delta_sigma_v


def test_rankine_phi30():
    # Rankine : Ka = tan²(30°) = 1/3, Kp = 3
    assert coef.ka_coulomb(30, 0) == pytest.approx(1 / 3, rel=1e-12)
    assert coef.kp_coulomb(30, 0) == pytest.approx(3.0, rel=1e-12)


def test_coulomb_phi30_delta20():
    # Valeurs de Coulomb publiées (Das, table Ka de Coulomb) : Ka(30°, 20°) = 0,2973
    assert coef.ka_coulomb(30, 20) == pytest.approx(0.2973, abs=1e-4)
    # Kp(30°, 20°) = 6,105 (calcul manuel de la formule de Coulomb)
    assert coef.kp_coulomb(30, 20) == pytest.approx(6.105, abs=2e-3)
    assert coef.kah(30, 20) == pytest.approx(0.2973 * math.cos(math.radians(20)), abs=1e-4)


def test_obliquite_superieure_a_phi_refusee():
    with pytest.raises(ValueError):
        coef.ka_coulomb(30, 31)


def test_jaky():
    assert coef.k0_jaky(30) == pytest.approx(0.5)


def test_cohesion_etats_correspondants_egale_rankine_si_delta_nul():
    # Pour δ = 0 : H(1 − Ka) = 2c√Ka et H(Kp − 1) = 2c√Kp
    phi, c = 30.0, 10.0
    ka, kp = coef.kah(phi), coef.kph(phi)
    assert coef.terme_cohesion_poussee(phi, c, ka) == pytest.approx(2 * c * math.sqrt(ka))
    assert coef.terme_cohesion_butee(phi, c, kp) == pytest.approx(2 * c * math.sqrt(kp))
    assert coef.terme_cohesion_poussee(0.0, c, 1.0) == pytest.approx(2 * c)


def test_kh_schmitt_calcul_manuel():
    # EM = 15 000 kPa, α = 1/3, EI = 100 000 kN·m²/m
    # (EM/α) = 45 000 ; 45 000^(4/3) = 1,5981e6 ; EI^(1/3) = 46,416 ; kh = 2,1 × 1,5981e6 / 46,416
    attendu = 2.1 * 45000 ** (4 / 3) / 100000 ** (1 / 3)
    assert kh_schmitt(15000, 1 / 3, 1e5) == pytest.approx(attendu, rel=1e-12)
    assert kh_schmitt(15000, 1 / 3, 1e5) == pytest.approx(72_300, rel=2e-3)


def test_cpt_sans_correlation_refuse():
    with pytest.raises(ValueError):
        em_depuis_cpt(5000, None)
    assert em_depuis_cpt(5000, 3.0) == 15000


def test_contraintes_verticales_bicouche_avec_nappe():
    couches = [
        Couche("Remblai", 0.0, gamma=18, gamma_dejauge=9, phi=28),
        Couche("Sable", -3.0, gamma=20, gamma_dejauge=11, phi=35),
    ]
    z = np.array([0.0, -1.0, -2.0, -3.0, -5.0])
    sv, u = contraintes_verticales(z, 0.0, -2.0, couches, gamma_w=10.0)
    # à -1 : 18 ; à -2 : 36 ; à -3 : 36 + 9 = 45 ; à -5 : 45 + 2×11 = 67
    np.testing.assert_allclose(sv, [0, 18, 36, 45, 67])
    np.testing.assert_allclose(u, [0, 0, 0, 10, 30])


def test_surcharge_repartie_et_bande():
    z = np.array([-1.0, -5.0, -20.0])
    rep = Surcharge("q", "repartie", 20.0)
    np.testing.assert_allclose(delta_sigma_v(rep, z, 0.0), 20.0)
    # Bande très large commençant au droit de l'écran : point au bord -> q/2
    bord = Surcharge("b", "bande", 20.0, distance=0.0, largeur=1e6)
    np.testing.assert_allclose(delta_sigma_v(bord, z, 0.0), 10.0, rtol=1e-4)
    # Bande lointaine : effet quasi nul en surface
    loin = Surcharge("l", "bande", 20.0, distance=100.0, largeur=2.0)
    assert delta_sigma_v(loin, np.array([-0.5]), 0.0)[0] < 1e-3


def test_flamant_valeur_manuelle():
    # Q = 50 kN/m à d = 2 m, point à 2 m de profondeur : 2·50·8/(π·64) = 1,989 kPa
    s = Surcharge("L", "lineique", 50.0, distance=2.0)
    assert delta_sigma_v(s, np.array([-2.0]), 0.0)[0] == pytest.approx(2 * 50 * 8 / (math.pi * 64))
