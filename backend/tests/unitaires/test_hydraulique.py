"""Module hydraulique — tests analytiques écrits avant le code.

Références :
- écoulement 1D et couches en série : loi de Darcy, k_eq = Σd / Σ(d/k) ;
- Lane (1935), Security from under-seepage : longueur de cheminement pondérée L_w = ΣV + ΣH/3 ;
- Terzaghi (1943), Theoretical Soil Mechanics, § 97 : prisme de largeur D/2 et de hauteur D
  contre l'écran, F = γ'·D / (γw·h_a), h_a = excès de charge moyen à la base du prisme ;
- EN 1997-1 § 10.2 (UPL) : épaisseur minimale de bouchon ;
- Harr (1962), Groundwater and Seepage : rideau unique dans un massif profond isotrope,
  gradient de sortie contre l'écran i_E = H / (π·d).
Les coefficients partiels de ce fichier sont des valeurs de test fictives.
"""
import math

import numpy as np
import pytest

from sout.hydraulique import bouchons, ecoulement, lane, terzaghi
from sout.hydraulique.grille import Grille, resoudre_grille
from sout.normes import Normes
from sout.noyau.modele import DefAppui, Ecran, Modele, Phase
from sout.noyau.phasage import calculer
from sout.sol.couches import Couche

V = lambda x: {"valeur": x, "source": "valeur de test fictive"}  # noqa: E731


# --------------------------------------------------------------------------- 1. écoulement 1D
def test_ecoulement_1d_charge_lineaire_et_debit():
    # colonne verticale de 10 m, k = 1e-5 m/s, charge 12 m en haut et 2 m en bas
    g = Grille(x=np.array([0.0, 1.0]), z=np.linspace(-10.0, 0.0, 41))
    kx = np.full(g.forme, 1e-5)
    kz = np.full(g.forme, 1e-5)
    fixe = np.full(g.forme, np.nan)
    fixe[:, -1] = 12.0   # face supérieure
    fixe[:, 0] = 2.0     # face inférieure
    h = resoudre_grille(g, kx, kz, fixe)
    np.testing.assert_allclose(h[0], 2.0 + (g.zc + 10.0) * (10.0 / 10.0), rtol=1e-9)
    q = g.flux_face_sup(h, kz)   # m³/s par m, positif vers le haut
    assert q[0] == pytest.approx(-1e-5 * 1.0, rel=1e-9)   # i = 1, écoulement descendant


# --------------------------------------------------------------------------- 2. couches en série
def test_couches_en_serie_k_equivalent():
    g = Grille(x=np.array([0.0, 1.0]), z=np.linspace(-10.0, 0.0, 101))
    kz = np.tile(np.where(g.zc > -4.0, 1e-5, 1e-7), (2, 1))   # 4 m à 1e-5 sur 6 m à 1e-7
    kx = kz.copy()
    fixe = np.full(g.forme, np.nan)
    fixe[:, -1], fixe[:, 0] = 10.0, 0.0
    h = resoudre_grille(g, kx, kz, fixe)
    k_eq = 10.0 / (4.0 / 1e-5 + 6.0 / 1e-7)
    assert abs(g.flux_face_sup(h, kz)[0]) == pytest.approx(k_eq * 10.0 / 10.0, rel=1e-6)
    # perte de charge dans la couche peu perméable : proportion (6/1e-7) / Σ(d/k)
    perte_bas = h[0][g.zc > -4.0].min() - 0.0
    assert perte_bas == pytest.approx(10.0 * (6 / 1e-7) / (4 / 1e-5 + 6 / 1e-7), rel=2e-2)


# --------------------------------------------------------------------------- 3. Lane
def test_lane_longueur_ponderee_et_critere():
    assert lane.longueur_ponderee(verticales=[12.0, 7.5], horizontales=[3.0]) == pytest.approx(19.5 + 1.0)
    # critère : L_w / H ≥ C_lane  ->  taux = C·H / L_w
    assert lane.taux(L_w=20.5, H=5.0, C_lane=5.0) == pytest.approx(25.0 / 20.5)


# --------------------------------------------------------------------------- 4. Terzaghi
def test_terzaghi_prisme():
    # D = 6 m, γ' = 10, γw = 10, excès de charge moyen à la base 2,4 m : F = 60 / 24 = 2,5
    assert terzaghi.facteur_securite(D=6.0, gamma_prime=10.0, gamma_w=10.0, h_a=2.4) == pytest.approx(2.5)


# --------------------------------------------------------------------------- 5. UPL, épaisseur minimale de bouchon
def test_epaisseur_minimale_bouchon():
    # toit du bouchon à −10, charge amont +0 : u à la base = γw·(0 − (−10 − e)) ; γ_dst = 1,1, γ_stb = 0,9, γ_b = 22
    e = bouchons.epaisseur_minimale(h_amont=0.0, z_toit=-10.0, gamma_bouchon=22.0, gamma_w=10.0,
                                    gamma_dst=1.1, gamma_stb=0.9, poids_sus=0.0)
    assert 1.1 * 10.0 * (0.0 - (-10.0 - e)) == pytest.approx(0.9 * 22.0 * e, rel=1e-9)
    # lestage par un radier de 50 kPa : le bouchon peut être plus mince
    e2 = bouchons.epaisseur_minimale(0.0, -10.0, 22.0, 10.0, 1.1, 0.9, poids_sus=50.0)
    assert e2 < e


# --------------------------------------------------------------------------- 6. réseau d'écoulement de référence
@pytest.fixture(scope="module")
def rideau_profond():
    """Rideau de fiche d = 4 m sous le fond, charge H = 4 m, massif isotrope profond."""
    sol = Couche("Sable", 0.0, 20, 10, 32, k_h=1e-5, k_v=1e-5)
    return ecoulement.DifferencesFinies(
        couches=[sol], z_terrain_amont=0.0, z_fond=0.0, z_pied=-4.0, z_tete=0.0,
        h_amont=4.0, h_aval=0.0, largeur_amont=60.0, largeur_aval=60.0, z_substratum=-60.0,
        pas=0.125, gamma_w=10.0).resoudre()


def test_reseau_symetrie_et_gradient_de_sortie_harr(rideau_profond):
    r = rideau_profond
    # symétrie par rapport à l'écran : h(x) + h(−x) = H_amont + H_aval
    hx = r.charge_le_long(z=-6.0, xs=np.array([-3.0, -1.5, -0.5]))
    hmx = r.charge_le_long(z=-6.0, xs=np.array([3.0, 1.5, 0.5]))
    np.testing.assert_allclose(hx + hmx, 4.0, atol=0.02)
    # gradient de sortie contre l'écran : H/(π d) = 0,318 (Harr) ; maillage fini -> tolérance 10 %
    assert r.gradient_sortie_max == pytest.approx(4.0 / (math.pi * 4.0), rel=0.10)
    assert r.debit > 0


# --------------------------------------------------------------------------- 7. non-régression hydrostatique
def test_sans_difference_de_charge_pressions_hydrostatiques():
    sol = Couche("Sable", 0.0, 20, 10, 32, k_h=1e-5, k_v=1e-5)
    m = ecoulement.DifferencesFinies([sol], 0.0, -5.0, -12.0, 0.0, h_amont=-2.0, h_aval=-2.0,
                                     largeur_amont=20.0, largeur_aval=10.0, z_substratum=-30.0, pas=0.5, gamma_w=10.0).resoudre()
    z = np.linspace(-12.0, -2.0, 21)
    np.testing.assert_allclose(m.pression("amont", z), 10.0 * (-2.0 - z), atol=1e-6)
    np.testing.assert_allclose(m.pression("aval", z), 10.0 * (-2.0 - z), atol=1e-6)
    assert m.gradient_sortie_max == pytest.approx(0.0, abs=1e-9)


# --------------------------------------------------------------------------- 8. effet sur les contraintes effectives
def test_ecoulement_reduit_la_butee():
    sol = Couche("Sable", 0.0, 20, 10, 32, EM=12000, alpha=1 / 3, k_h=1e-5, k_v=1e-5)
    app = {"B": DefAppui("B", -0.5, 1e5)}
    phases = [Phase("Pose", poser=["B"]), Phase("Exc", excaver=-6.0, eau={"amont": -1.0, "aval": -6.0})]
    base = dict(ecran=Ecran(0.0, -14.0, 1e5), couches=[sol], appuis=app, phases=phases, eau_amont=-1.0, eau_aval=-1.0)
    hydro = calculer(Modele(**base))
    ecoul = calculer(Modele(**base, hydraulique={"regime": "differences_finies", "pas": 0.5, "largeur_amont": 30.0, "largeur_fouille": 20.0,
                                                 "substratum": -34.0}))
    assert hydro.complet and ecoul.complet
    ph_h, ph_e = hydro.phases[-1], ecoul.phases[-1]
    # écoulement ascendant côté fouille : pression d'eau plus forte, butée limite plus faible
    assert ph_e.eau["u_aval"].max() > ph_h.eau["u_aval"].max()
    av_h, av_e = ph_h.pressions["aval"], ph_e.pressions["aval"]
    assert np.sum(av_e["L"] * av_e["pp"]) < np.sum(av_h["L"] * av_h["pp"])
    # résultat hydraulique disponible pour l'affichage
    assert ph_e.hydro is not None and ph_e.hydro["gradient_sortie_max"] > 0


# --------------------------------------------------------------------------- 9. bouchon
def test_bouchon_reduit_le_gradient_de_sortie():
    sol = Couche("Sable", 0.0, 20, 10, 32, k_h=1e-5, k_v=1e-5)
    args = dict(couches=[sol], z_terrain_amont=0.0, z_fond=-6.0, z_pied=-12.0, z_tete=0.0, h_amont=-1.0, h_aval=-6.0,
                largeur_amont=30.0, largeur_aval=10.0, z_substratum=-30.0, pas=0.5, gamma_w=10.0)
    sans = ecoulement.DifferencesFinies(**args).resoudre()
    avec = ecoulement.DifferencesFinies(**args, bouchon=bouchons.Bouchon("injecte", toit=-6.0, base=-9.0, k=1e-8, gamma=21.0)).resoudre()
    assert avec.gradient_sortie_max < 0.2 * sans.gradient_sortie_max
    assert avec.debit < 0.2 * sans.debit
    # sous le bouchon, la charge est proche de la charge amont
    assert avec.charge_le_long(z=-9.5, xs=np.array([2.0]))[0] > -2.0


def test_verifications_hydrauliques_avec_coefficients_de_test():
    from sout.hydraulique import verifications as vh
    normes = Normes({
        "nf_p94_282": {"fond_de_fouille": {"soulevement": {"gamma_dst": V(1.1), "gamma_stb": V(0.9)},
                                           "boulance": {"gamma_dst": V(1.35), "gamma_stb": V(0.9)},
                                           "renard": {"gradient_admissible": V(0.5)}}},
        "hydraulique": {"lane": {"C": {"sable_moyen": V(6.0)}}, "terzaghi": {"F_min": V(1.5)},
                        "bouchon": {"gradient_admissible": V(3.0)}, "fond_argile": {"N_c": V(5.7), "F_min": V(1.5)}},
    })
    sol = Couche("Sable", 0.0, 20, 10, 32, EM=12000, alpha=1 / 3, k_h=1e-5, k_v=1e-5)
    app = {"B": DefAppui("B", -0.5, 1e5)}
    m = Modele(ecran=Ecran(0.0, -14.0, 1e5), couches=[sol], appuis=app,
               phases=[Phase("Pose", poser=["B"]), Phase("Exc", excaver=-6.0, eau={"amont": -1.0, "aval": -6.0})],
               eau_amont=-1.0, eau_aval=-1.0,
               hydraulique={"regime": "differences_finies", "pas": 0.5, "largeur_amont": 30.0, "largeur_fouille": 20.0,
                            "substratum": -34.0, "sol_lane": "sable_moyen"})
    r = calculer(m)
    vs = {v.nom: v for v in vh.verifier(m, r, normes)}
    assert vs["Boulance — équilibre des pressions (HYD)"].taux is not None
    assert vs["Boulance — gradient de sortie"].taux == pytest.approx(1.35 * r.phases[-1].hydro["gradient_sortie_max"] / (0.9 * 10.0 / 10.0))
    assert vs["Renard — Terzaghi"].taux is not None and vs["Renard — Lane"].taux is not None
    assert vs["Renard — gradient critique"].taux == pytest.approx(r.phases[-1].hydro["gradient_sortie_max"] / 0.5)
    assert "Débit de pompage" in vs and vs["Débit de pompage"].etat == "non_verifiable"
