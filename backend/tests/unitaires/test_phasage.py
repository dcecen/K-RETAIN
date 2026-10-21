"""J2 — phasage, eau, surcharges, appuis."""
import numpy as np
import pytest

from sout.appuis.raideurs import effort_axial, force_horizontale, raideur_buton, raideur_tirant
from sout.noyau.modele import DefAppui, Ecran, Modele, Phase
from sout.noyau.phasage import calculer
from sout.sol.couches import Couche
from sout.sol.surcharges import Surcharge

REMBLAI = Couche("Remblai", 0.0, gamma=18, gamma_dejauge=9, phi=28, EM=4000, alpha=0.5)
SABLE = Couche("Sable dense", -3.0, gamma=20, gamma_dejauge=11, phi=35, EM=15000, alpha=1 / 3)


def _modele(phases, appuis=None, **kw):
    return Modele(ecran=Ecran(tete=0.0, pied=-14.0, EI=1.0e5), couches=[REMBLAI, SABLE],
                  phases=phases, appuis=appuis or {}, **kw)


def _equilibre(ph, gamma_w=10.0):
    """Somme des forces horizontales sur l'écran (sol + eau + appuis)."""
    am, av = ph.pressions["amont"], ph.pressions["aval"]
    F = np.sum(am["L"] * am["p"]) - np.sum(av["L"] * av["p"])
    e = ph.eau
    dz = np.diff(ph.z)
    # eau : intégrale de (u_amont − u_aval) par demi-mailles (ordre = milieux croissants)
    L = np.repeat(dz / 2, 2)
    F += np.sum((e["u_amont"] - e["u_aval"]) * L)
    F -= sum(a["effort"] for a in ph.appuis)
    return F


def test_raideurs_appuis_calcul_manuel():
    # Buton E = 210 000 MPa, A = 100 cm², L = 18 m symétrique, e = 6 m :
    # EA = 210 000e3 kPa × 100e-4 m² = 2,1e6 kN ; k = 2,1e6 / (9 × 6) = 38 889 kN/m/m
    assert raideur_buton(210000, 100, 18, 6) == pytest.approx(2.1e6 / 54)
    # Tirant incliné à 30°, L libre 10 m, e = 2 m, A = 10 cm² : EA = 2,1e5 kN
    assert raideur_tirant(210000, 10, 10, 2, 30) == pytest.approx(2.1e5 * 0.75 / 20)
    assert effort_axial(force_horizontale(100, 2.5, 20), 2.5, 20) == pytest.approx(100)


def test_phase_vide_conserve_l_etat():
    res = calculer(_modele([Phase("Exc", excaver=-2.0), Phase("Rien")]))
    assert res.complet
    np.testing.assert_allclose(res.phases[2].y, res.phases[1].y, atol=1e-12)
    np.testing.assert_allclose(res.phases[2].M, res.phases[1].M, atol=1e-8)


def test_nappe_symetrique_sans_deplacement():
    res = calculer(_modele([Phase("Nappe", eau={"amont": -2.0, "aval": -2.0})]))
    assert res.complet
    np.testing.assert_allclose(res.phases[1].y, 0.0, atol=1e-12)


def test_equilibre_global_avec_eau_et_appui():
    k = raideur_buton(210000, 100, 18, 6)
    app = {"B1": DefAppui("B1", -1.5, k, precharge=force_horizontale(50, 6))}
    res = calculer(_modele([
        Phase("Terrassement à -2,0", excaver=-2.0),
        Phase("Pose du buton B1", poser=["B1"]),
        Phase("Terrassement final et pompage", excaver=-6.5, eau={"aval": -7.0}),
    ], appuis=app, eau_amont=-2.0, eau_aval=-2.0))
    assert res.complet, [p.message for p in res.phases]
    for ph in res.phases:
        assert abs(_equilibre(ph)) < 1e-6
    final = res.phases[-1]
    assert final.appuis[0]["effort"] > 0
    # Le buton bloque la tête : déplacement au buton faible devant le ventre
    i_b = int(np.argmin(np.abs(final.z + 1.5)))
    assert abs(final.y[i_b]) < final.y.max()


def test_appui_tres_raide_bloque_le_point():
    app = {"B": DefAppui("B", -1.0, 1e9)}
    res = calculer(_modele([Phase("Pose", poser=["B"]), Phase("Exc", excaver=-5.0)], appuis=app))
    assert res.complet
    ph = res.phases[-1]
    i_b = int(np.argmin(np.abs(ph.z + 1.0)))
    assert abs(ph.y[i_b]) < 1e-6
    assert ph.appuis[0]["effort"] == pytest.approx(1e9 * ph.y[i_b], abs=1e-3)


def test_precontrainte_retrouvee_dans_l_effort():
    # Raideur nulle : l'effort reste égal à la précontrainte, quel que soit le déplacement.
    app = {"T": DefAppui("T", -1.0, 0.0, precharge=80.0, type="tirant")}
    res = calculer(_modele([Phase("Exc", excaver=-2.0), Phase("Tirant", poser=["T"]),
                            Phase("Exc2", excaver=-4.0)], appuis=app))
    assert res.complet
    for ph in res.phases[2:]:
        assert ph.appuis[0]["effort"] == pytest.approx(80.0)
    # Raideur non nulle : effort = F0 + k·(y − y_pose)
    k = 5000.0
    app = {"T": DefAppui("T", -1.0, k, precharge=80.0, type="tirant")}
    res = calculer(_modele([Phase("Exc", excaver=-2.0), Phase("Tirant", poser=["T"]),
                            Phase("Exc2", excaver=-4.0)], appuis=app))
    i = int(np.argmin(np.abs(res.z + 1.0)))
    y_pose = res.phases[1].y[i]
    for ph in res.phases[2:]:
        assert ph.appuis[0]["effort"] == pytest.approx(80.0 + k * (ph.y[i] - y_pose))


def test_surcharge_ajout_puis_retrait():
    """Le retrait d'une surcharge réduit le déplacement sans revenir exactement à
    l'état antérieur : près de la surface, la décharge K0·q fait atteindre la
    coupure en traction (pa = 0), ce qui est une plastification (irréversible)."""
    s = Surcharge("S", "repartie", 10.0)
    res = calculer(_modele([Phase("Exc", excaver=-1.0), Phase("Ajout", ajouter_surcharges=[s]),
                            Phase("Retrait", retirer_surcharges=["S"])]))
    assert res.complet
    y_exc, y_ajout, y_retrait = (res.phases[i].y[-1] for i in (1, 2, 3))
    assert y_ajout > y_exc
    assert y_exc <= y_retrait < y_ajout


def test_appui_unilateral_decolle():
    # Buton posé puis l'écran est repoussé vers le sol par un remblai aval : le buton décolle.
    app = {"B": DefAppui("B", -0.5, 1e5, unilateral=True)}
    res = calculer(_modele([Phase("Exc", excaver=-4.0), Phase("Pose", poser=["B"]),
                            Phase("Remblai aval", remblayer_aval=-1.0)], appuis=app))
    assert res.complet
    assert res.phases[-1].appuis[0]["actif"] is False
    assert res.phases[-1].appuis[0]["effort"] == 0.0


def test_erreurs_de_donnees():
    res = calculer(_modele([Phase("Exc", excaver=-2.0), Phase("Faux", excaver=-1.0)]))
    assert not res.complet and "au-dessus du terrain" in res.phases[-1].message
    res = calculer(_modele([Phase("Pose", poser=["X"])]))
    assert "inconnu" in res.phases[-1].message


def test_rupture_detectee_fiche_insuffisante():
    m = Modele(ecran=Ecran(tete=0.0, pied=-6.0, EI=1e5), couches=[REMBLAI, SABLE],
               phases=[Phase("Exc", excaver=-5.0)])
    res = calculer(m)
    assert not res.complet
    assert res.phases[-1].message.startswith("Rupture")


def test_branches_de_phases():
    """Arbre de phases : une variante repart de l'état d'une phase antérieure (comme Plaxis)."""
    app = {"B": DefAppui("B", -1.0, 50000.0)}
    phases = [Phase("Exc1", excaver=-2.0), Phase("Pose", poser=["B"]), Phase("Exc2", excaver=-5.0),
              Phase("Variante sans buton", excaver=-4.0, depuis="Exc1"), Phase("Variante suite", excaver=-4.5)]
    res = calculer(_modele(phases, appuis=app))
    assert res.complet, [p.message for p in res.phases]
    assert [p.parent for p in res.phases] == [None, 0, 1, 2, 1, 4]
    # la variante repart de Exc1 : aucun buton posé, déplacement plus grand que la phase butée à -5
    var = res.phases[4]
    assert var.appuis == [] and var.terrain_aval == -4.0
    assert abs(var.y).max() > abs(res.phases[3].y).max() * 0.5
    # la branche principale n'est pas modifiée par la présence de la variante
    res_lin = calculer(_modele(phases[:3], appuis=app))
    np.testing.assert_allclose(res.phases[3].y, res_lin.phases[3].y, atol=1e-12)
    # la suite de la variante enchaîne bien sur la variante (implicite = phase précédente de la liste)
    assert res.phases[5].terrain_aval == -4.5 and res.phases[5].appuis == []


def test_branche_depuis_phase_rompue():
    phases = [Phase("Exc", excaver=-13.5), Phase("Suite", excaver=-13.8), Phase("Var", excaver=-1.0, depuis="Exc")]
    res = calculer(_modele(phases))
    assert not res.phases[1].ok and "non calculée" in res.phases[2].message and "non calculée" in res.phases[3].message
