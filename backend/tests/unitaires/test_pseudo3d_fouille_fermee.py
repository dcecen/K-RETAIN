"""Pseudo-3D sur tout le contour de la fouille (« double écran ») : maillage du périmètre passant
par les sommets, butons reliant les parois en vis-à-vis, équivalence avec la règle L/2 quand tout
est symétrique, retour au 2D au milieu d'un long côté, réactions d'angle, sérialisation."""
import numpy as np
import pytest

from sout.noyau.modele import DefAppui, Ecran, Modele, Phase
from sout.noyau.phasage import calculer
from sout.plan.geometrie import perimetre
from sout.pseudo3d.calcul import MoteurPseudo3D, serialiser
from sout.sol.couches import Couche

SABLE = Couche("Sable", 0.0, 20, 10, 32, EM=12000, alpha=1 / 3)
RECT = [[0.0, 0.0], [20.0, 0.0], [20.0, 12.0], [0.0, 12.0]]


def _modele(espacement=4.0, symetrique=True, raideur=30000.0, precharge=20.0, type_="buton"):
    infos = {"espacement": espacement, "symetrique": symetrique, "type": type_}
    app = {"B": DefAppui("B", -1.0, raideur, precharge=precharge, type=type_, infos=infos)}
    return Modele(ecran=Ecran(0.0, -12.0, 1e5), couches=[SABLE], appuis=app, pas=0.25,
                  phases=[Phase("Exc1", excaver=-2.0), Phase("Pose", poser=["B"]), Phase("Exc2", excaver=-6.0)])


def test_maillage_du_perimetre_passe_par_les_sommets():
    mo = MoteurPseudo3D(_modele(), None, 1.0, contour=RECT)
    assert mo.s[0] == 0.0 and mo.s[-1] == 63.0 and mo.longueur == pytest.approx(perimetre(RECT)) == 64.0
    assert mo.fermeture == pytest.approx(1.0) and mo.nh == mo.ns == 64
    assert [float(mo.s[i]) for i in mo.i_sommets] == [0.0, 20.0, 32.0, 52.0]
    assert mo.i_angles == mo.i_sommets
    d = mo.K.diagonal()
    for i in mo.i_sommets:
        assert np.all(d[3 * (i * mo.nz + np.arange(mo.nz))] >= mo.pen)
    r = mo.calculer()
    ph = r.phases[-1]
    for i in mo.i_sommets:
        assert np.abs(ph.W[i]).max() < 1e-3 * np.abs(ph.W).max()
    assert r.fermee and r.sommets == [0.0, 20.0, 32.0, 52.0]
    assert any("fouille fermée" in a for a in r.avertissements)


def test_rectangle_symetrique_donne_une_solution_symetrique():
    """Mêmes sol, phases et butons partout : le champ est symétrique par rapport aux deux axes du
    rectangle (chaque côté est le miroir de son vis-à-vis, et symétrique par rapport à son milieu),
    ce qui exige que les quatre angles soient traités de la même façon (boucle fermée)."""
    mo = MoteurPseudo3D(_modele(), None, 1.0, contour=RECT)
    ph = mo.calculer().phases[-1]
    W = ph.W
    cote0, cote2 = W[0:21], W[32:53]           # côtés longs (x de 0 à 20, puis de 20 à 0)
    np.testing.assert_allclose(cote0, cote2[::-1], rtol=1e-6, atol=1e-9 * np.abs(W).max())   # vis-à-vis
    np.testing.assert_allclose(cote0, cote0[::-1], rtol=1e-6, atol=1e-9 * np.abs(W).max())   # miroir du côté
    cote1, cote3 = W[20:33], np.vstack([W[52:64], W[0:1]])   # côtés courts
    np.testing.assert_allclose(cote1, cote3[::-1], rtol=1e-6, atol=1e-9 * np.abs(W).max())
    eff = [a["effort"] for a in sorted(ph.appuis, key=lambda a: a["s"])]
    assert eff[0] == pytest.approx(eff[-1], rel=1e-6) and eff[1] == pytest.approx(eff[-2], rel=1e-6)


def test_butons_placés_en_vis_a_vis_depuis_le_plus_long_cote():
    mo = MoteurPseudo3D(_modele(), None, 1.0, contour=RECT)
    pl = mo._placements("B")
    assert [p[0] for p in pl] == [2.0, 6.0, 10.0, 14.0, 18.0]            # côté 0 (20 m), 5 butons centrés
    assert [p[1] for p in pl] == pytest.approx([50.0, 46.0, 42.0, 38.0, 34.0])   # côté 2 : s = 32 + (20 − x)
    ph = mo.calculer().phases[-1]
    assert len(ph.appuis) == 5 and all(a["s2"] is not None for a in ph.appuis)
    # action = réaction : les deux nœuds d'un lien reçoivent la même force
    f = ph.forces["appuis"]
    j = int(np.argmin(np.abs(mo.z + 1.0)))
    for a in ph.appuis:
        i1, i2 = int(np.argmin(np.abs(mo.s - a["s"]))), int(np.argmin(np.abs(mo.s - a["s2"])))
        assert f[i1, j] == pytest.approx(-a["effort"]) and f[i2, j] == pytest.approx(-a["effort"])
    assert abs(ph.bilan["residu"]) <= 1e-6 * ph.bilan["echelle"]
    assert ph.bilan["appuis"] == pytest.approx(-2 * sum(a["effort"] for a in ph.appuis), rel=1e-9)


def test_fouille_symetrique_liens_equivalents_a_la_regle_L_sur_2():
    """Parois en vis-à-vis identiques : les liens (EA/L pleine longueur) donnent le même résultat
    que des ressorts vers le sol de raideur 2D (règle L/2) aux mêmes positions, précharge comprise."""
    m = _modele()
    r_liens = MoteurPseudo3D(m, None, 1.0, contour=RECT, liens=True).calculer()
    r_sol = MoteurPseudo3D(m, None, 1.0, contour=RECT, liens=False).calculer()
    for a, b in zip(r_liens.phases, r_sol.phases):
        np.testing.assert_allclose(a.W, b.W, rtol=1e-7, atol=1e-12)
    ea = sorted((a["s"], a["effort"]) for a in r_liens.phases[-1].appuis)
    eb = {round(a["s"], 6): a["effort"] for a in r_sol.phases[-1].appuis}
    for s, e in ea:
        assert e == pytest.approx(eb[round(s, 6)], rel=1e-7)
    assert all(a["effort"] == pytest.approx(80.0, abs=1e-6) for a in r_liens.phases[2].appuis)


def test_long_cote_retrouve_le_2d_au_milieu_et_les_angles_reagissent():
    long_ = [[0.0, 0.0], [60.0, 0.0], [60.0, 12.0], [0.0, 12.0]]
    m = _modele()
    mo = MoteurPseudo3D(m, None, 1.0, contour=long_)
    ph = mo.calculer().phases[-1]
    r2 = calculer(m).phases[-1]
    i_mid = int(np.argmin(np.abs(mo.s - 30.0)))
    zone = slice(i_mid - 4, i_mid + 5)
    assert np.abs(ph.W[zone]).max() == pytest.approx(np.abs(r2.y).max(), rel=0.05)
    assert ph.Mz[zone].max() == pytest.approx(r2.M.max(), rel=0.05)
    lignes = np.flatnonzero(np.abs(ph.reactions).sum(axis=1) > 0)
    assert lignes.tolist() == mo.i_sommets
    assert ph.bilan["reactions"] == pytest.approx(-(ph.bilan["sol"] + ph.bilan["eau"] + ph.bilan["appuis"]), rel=1e-6)


def test_segments_du_plan_et_dalle():
    m = _modele()
    pa = [{"appui": "B", "de": [10.0, 0.0], "a": [10.0, 12.0]}]
    mo = MoteurPseudo3D(m, None, 1.0, contour=RECT, plan_appuis=pa)
    assert mo._placements("B") == [(10.0, 42.0)]
    md = _modele(type_="dalle", raideur=5000.0, precharge=0.0)
    mo_d = MoteurPseudo3D(md, None, 1.0, contour=RECT)
    pl = mo_d._placements("B")
    assert len(pl) == 19 and all(p[1] is not None for p in pl)       # tous les nœuds intérieurs du côté long
    ph = mo_d.calculer().phases[-1]
    assert len(ph.appuis) == 19 and abs(ph.bilan["residu"]) <= 1e-6 * ph.bilan["echelle"]


def test_serialisation_fouille_fermee():
    m = _modele()
    r = MoteurPseudo3D(m, None, 1.0, contour=RECT).calculer()
    d = serialiser(r, calculer(m))
    assert d["fermee"] is True and d["sommets"] == [0.0, 20.0, 32.0, 52.0] and d["longueur"] == 64.0
    assert d["s"][-1] == 64.0 and len(d["s"]) == 65 and len(d["phases"][-1]["y_mm"]) == 65
    assert d["phases"][-1]["y_mm"][-1] == d["phases"][-1]["y_mm"][0]      # boucle refermée pour l'affichage
    a = d["phases"][-1]["appuis"][0]
    assert a["s2"] == pytest.approx(50.0) and a["effort"] > 0
    assert len(d["phases"][-1]["reactions"]["s"]) == 4


def test_longueur_ou_plan_obligatoire():
    with pytest.raises(Exception, match="longueur"):
        MoteurPseudo3D(_modele(), None, 1.0)
