"""Pseudo-3D : rigidité horizontale par type de paroi, Ds = 0 (chaque ligne = un calcul 2D
indépendant : c'est exactement « des coupes 2D assemblées »), redistribution de la plaque
isotrope (le vrai 3D), joints de panneaux, torsion imposée."""
import numpy as np
import pytest

from sout.materiaux.base import catalogue_par_defaut
from sout.noyau.modele import DefAppui, Ecran, Modele, Phase
from sout.noyau.phasage import calculer
from sout.parois import construire_ecran
from sout.pseudo3d import plaque
from sout.pseudo3d.calcul import MoteurPseudo3D
from sout.script.schema import Paroi
from sout.sol.couches import Couche

SABLE = Couche("Sable", 0.0, 20, 10, 32, EM=12000, alpha=1 / 3)
CAT = catalogue_par_defaut()


def _appui(espacement=4.0, raideur=30000.0, precharge=20.0):
    return {"B": DefAppui("B", -1.0, raideur, precharge=precharge, infos={"espacement": espacement})}


def _modele(appuis=None, ecran=None):
    app = _appui() if appuis is None else appuis
    phases = [Phase("Exc1", excaver=-2.0), Phase("Pose", poser=list(app)), Phase("Exc2", excaver=-6.0)]
    return Modele(ecran=ecran or Ecran(0.0, -12.0, 1e5), couches=[SABLE], appuis=app, pas=0.25, phases=phases)


# ---------------------------------------------------------------------------
# Défauts par type de paroi
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("paroi, rapport, mot", [
    (dict(type="paroi_moulee", epaisseur=0.6, beton="C30/37", enrobage=0.07), 1.0, "joints"),
    (dict(type="palplanche", profil="AZ 26-700", acier="S355"), 0.0, "serrures"),
    (dict(type="pieux_secants", diametre=0.8, entraxe=0.7, beton="C30/37"), 0.0, "recouvrements"),
    (dict(type="berlinoise", profil="HEB 300", acier="S355", entraxe=2.0, largeur_reaction_fiche=0.9), 0.0, "indépendants"),
])
def test_rigidite_horizontale_par_defaut_selon_le_type(paroi, rapport, mot):
    ec = construire_ecran(Paroi(tete=0.0, pied=-12.0, **paroi), CAT, None)
    rh = ec.infos["rigidite_horizontale"]
    assert rh["rapport"] == rapport
    assert mot in rh["avertissement"]
    mo = MoteurPseudo3D(_modele(ecran=ec), 24.0, 1.0)
    np.testing.assert_allclose(mo.Ds, rapport * mo.Dz, rtol=1e-12)
    assert mo.Ds_nulle == (rapport == 0.0)
    assert any(mot in a for a in mo.avertissements)
    if rapport == 0.0:
        assert np.all(mo.K.diagonal()[2::3] >= mo.pen)      # θs bloqués : lignes indépendantes
    else:
        assert np.all(mo.K.diagonal()[2::3] < mo.pen)


def test_paroi_moulee_avec_panneaux_ne_signale_plus_les_joints():
    p = Paroi(type="paroi_moulee", tete=0.0, pied=-12.0, epaisseur=0.6, beton="C30/37", longueur_panneau=6.0)
    assert construire_ecran(p, CAT, None).infos["rigidite_horizontale"]["avertissement"] is None


def test_ei_impose_retombe_sur_l_isotropie_avec_avertissement():
    ec = construire_ecran(Paroi(type="palplanche", tete=0.0, pied=-12.0, EI=1e5), CAT, None)
    assert ec.infos["rigidite_horizontale"]["rapport"] is None
    mo = MoteurPseudo3D(_modele(ecran=ec), 24.0, 1.0)
    np.testing.assert_allclose(mo.Ds, mo.Dz)
    assert any("isotrope" in a for a in mo.avertissements)


def test_priorite_des_valeurs_du_script():
    ec = construire_ecran(Paroi(type="paroi_moulee", tete=0.0, pied=-12.0, epaisseur=0.6, beton="C30/37"), CAT, None)
    m = _modele(ecran=ec)
    assert MoteurPseudo3D(m, 24.0, 1.0, rapport_rigidite_horizontale=0.3).Ds[0] == pytest.approx(0.3 * ec.EI)
    assert MoteurPseudo3D(m, 24.0, 1.0, rigidite_horizontale=1234.0, rapport_rigidite_horizontale=0.3).Ds[0] == 1234.0
    mo = MoteurPseudo3D(m, 24.0, 1.0, rapport_rigidite_horizontale=1e-9)
    assert mo.Ds_nulle and any("arrondie à 0" in a for a in mo.avertissements)


# ---------------------------------------------------------------------------
# Ds = 0 : chaque ligne verticale est un calcul 2D indépendant (« coupes 2D assemblées »)
# ---------------------------------------------------------------------------
def test_sans_rigidite_horizontale_chaque_ligne_est_un_calcul_2d_independant():
    """Avec Ds = 0, le grillage se réduit à des poutres verticales sans lien : une ligne sans appui
    est l'écran 2D sans appui ; la ligne d'un appui est l'écran 2D avec un appui de raideur k·e/ds
    et de précharge F0·e/ds (ds : largeur tributaire de la ligne). Identité à 1e-6 à toutes les phases."""
    m = _modele()
    r3 = MoteurPseudo3D(m, 48.0, 1.0, rapport_rigidite_horizontale=0.0).calculer()
    ds = plaque.largeurs_tributaires(r3.s)
    s_app = [a["s"] for a in r3.phases[-1].appuis]
    assert len(s_app) == 12
    avec = [int(np.argmin(np.abs(r3.s - sa))) for sa in s_app]
    sans = [i for i in range(len(r3.s)) if i not in avec]
    m0 = Modele(ecran=Ecran(0.0, -12.0, 1e5), couches=[SABLE], appuis={}, pas=0.25,
                phases=[Phase("Exc1", excaver=-2.0), Phase("Pose"), Phase("Exc2", excaver=-6.0)])
    r0 = calculer(m0)
    assert len(r0.phases) == len(r3.phases) == 4
    for k, ph in enumerate(r3.phases):
        for i in sans:
            np.testing.assert_allclose(ph.W[i], r0.phases[k].y, rtol=1e-6, atol=1e-12)
            np.testing.assert_allclose(ph.V_diag[i], r0.phases[k].V, rtol=1e-6, atol=1e-6 * max(float(np.abs(r0.phases[k].V).max()), 1.0))
    for n, i in enumerate(avec):
        mi = _modele(appuis=_appui(raideur=30000.0 * 4 / ds[i], precharge=20.0 * 4 / ds[i]))
        ri = calculer(mi)
        for k, ph in enumerate(r3.phases):
            np.testing.assert_allclose(ph.W[i], ri.phases[k].y, rtol=1e-6, atol=1e-12)
        assert r3.phases[-1].appuis[n]["effort"] == pytest.approx(ri.phases[-1].appuis[0]["effort"] * ds[i], rel=1e-6)


def test_la_plaque_isotrope_redistribue_entre_les_appuis():
    """Vrai 3D : avec Ds = Dz le déplacement est quasi uniforme le long de la paroi (rapport
    max/min < 1,3 loin des bords) et encadré par le 2D à appui réparti et la bande sans appui ;
    avec Ds = 0 les lignes sans appui s'écartent plus de trois fois plus que la ligne d'appui."""
    m = _modele()
    iso = MoteurPseudo3D(m, 48.0, 1.0).calculer().phases[-1]
    nul = MoteurPseudo3D(m, 48.0, 1.0, rapport_rigidite_horizontale=0.0).calculer().phases[-1]
    prof_iso, prof_nul = np.abs(iso.W).max(axis=1), np.abs(nul.W).max(axis=1)
    inter = slice(8, -8)
    assert prof_iso[inter].max() / prof_iso[inter].min() < 1.3
    assert prof_nul[inter].max() / prof_nul[inter].min() > 3.0
    y_avec = np.abs(calculer(m).phases[-1].y).max()
    m0 = Modele(ecran=Ecran(0.0, -12.0, 1e5), couches=[SABLE], appuis={}, pas=0.25,
                phases=[Phase("Exc1", excaver=-2.0), Phase("Pose"), Phase("Exc2", excaver=-6.0)])
    y_sans = np.abs(calculer(m0).phases[-1].y).max()
    assert 0.9 * y_avec <= prof_iso[inter].min() and prof_iso[inter].max() <= y_sans
    assert prof_nul[inter].max() == pytest.approx(y_sans, rel=1e-6)
    # les efforts par appui : ≈ H_2D × e pour la plaque, et bien plus faibles pour les bandes
    # (l'appui ne retient que sa ligne de 1 m)
    H2 = calculer(m).phases[-1].appuis[0]["effort"]
    assert np.mean([a["effort"] for a in iso.appuis[3:-3]]) == pytest.approx(H2 * 4.0, rel=0.05)
    assert max(a["effort"] for a in nul.appuis) < 0.6 * H2 * 4.0


# ---------------------------------------------------------------------------
# Joints de panneaux, torsion imposée
# ---------------------------------------------------------------------------
def test_joints_de_panneaux_rendent_les_panneaux_independants():
    """Joints tous les 6 m (origine 0) sur 24 m, butons tous les 6 m au centre des panneaux : l'élément
    qui porte chaque joint ne transmet rien, les panneaux intérieurs sont identiques (périodicité à
    1e-6), la paroi fléchit plus qu'une plaque continue, l'équilibre global est conservé."""
    m6 = _modele(appuis=_appui(espacement=6.0))
    mo = MoteurPseudo3D(m6, 24.0, 0.5, longueur_panneau=6.0)
    assert mo.joints == [6.0, 12.0, 18.0]
    assert mo.coef_h is not None and np.all(mo.coef_h[[12, 24, 36]] == 0.0) and mo.coef_h.sum() == (mo.ns - 1 - 3) * mo.nz
    r = mo.calculer()
    ph = r.phases[-1]
    np.testing.assert_allclose(ph.W[13:25], ph.W[25:37], rtol=1e-6, atol=1e-12)   # panneaux 2 et 3
    np.testing.assert_allclose(ph.Mz[13:25], ph.Mz[25:37], rtol=1e-6, atol=1e-9)
    assert [a["s"] for a in ph.appuis] == [3.0, 9.0, 15.0, 21.0]
    continu = MoteurPseudo3D(m6, 24.0, 0.5).calculer().phases[-1]
    assert np.abs(ph.W).max() > 1.05 * np.abs(continu.W).max()
    assert abs(ph.bilan["residu"]) <= 1e-6 * ph.bilan["echelle"]
    assert any("joints de panneaux" in a for a in r.avertissements)
    # panneaux plus longs que la paroi : aucun joint, résultat identique au continu
    sans = MoteurPseudo3D(m6, 24.0, 0.5, longueur_panneau=30.0).calculer().phases[-1]
    np.testing.assert_allclose(sans.W, continu.W, rtol=1e-12, atol=1e-15)
    with pytest.raises(Exception, match="longueur_panneau"):
        MoteurPseudo3D(m6, 24.0, 0.5, longueur_panneau=0.6)


def test_torsion_imposee():
    """GJ imposé égal à √(Ds·Dz) : matrice et résultats identiques au défaut ; GJ = 0 : la plaque
    perd sa torsion et fléchit davantage entre les appuis."""
    m = _modele()
    defaut = MoteurPseudo3D(m, 24.0, 1.0)
    meme = MoteurPseudo3D(m, 24.0, 1.0, torsion=1e5)       # Ds = Dz = 1e5 → √(Ds·Dz) = 1e5
    assert abs(defaut.K - meme.K).max() <= 1e-9 * abs(defaut.K).max()
    np.testing.assert_allclose(meme.calculer().phases[-1].W, defaut.calculer().phases[-1].W, rtol=1e-9, atol=1e-15)
    sans = MoteurPseudo3D(m, 24.0, 1.0, torsion=0.0)
    assert np.all(sans.GJ == 0.0)
    ph0, ph1 = sans.calculer().phases[-1], defaut.calculer().phases[-1]
    assert np.abs(ph0.Mzs).max() == 0.0 and np.abs(ph1.Mzs).max() > 0.0
    prof0, prof1 = np.abs(ph0.W).max(axis=1), np.abs(ph1.W).max(axis=1)
    assert prof0[8:-8].max() / prof0[8:-8].min() > prof1[8:-8].max() / prof1[8:-8].min()


def test_moment_horizontal_integre_sur_la_hauteur_suit_la_poutre_continue():
    """Paroi très raide horizontalement (Ds = 100·Dz), butons tous les e = 4 m : l'intégrale de Ms sur
    la hauteur est le moment de la poutre-cloison horizontale continue à travées égales sous charge
    uniforme (théorème des trois moments ; Timoshenko, *Résistance des matériaux*) : −R·e/12 sur
    appui, +R·e/24 à mi-travée, différence R·e/8, R étant l'effort d'un buton. Avec un appui réparti
    sur b = 2 m, la différence devient R·(e − b)/8 (réaction uniforme sur la largeur b)."""
    m = _modele()

    def integrales(largeur):
        mo = MoteurPseudo3D(m, 48.0, 0.5, rapport_rigidite_horizontale=100.0, largeur_appui=largeur)
        ph = mo.calculer().phases[-1]
        integ = (ph.Ms * np.gradient(mo.z)[None, :]).sum(axis=1)
        R = float(np.mean([a["effort"] for a in ph.appuis[3:-3]]))
        i_app = [int(np.argmin(np.abs(mo.s - a["s"]))) for a in ph.appuis[4:8]]
        i_mid = [int(np.argmin(np.abs(mo.s - (a["s"] + 2.0)))) for a in ph.appuis[4:8]]
        return R, float(np.mean(integ[i_app])), float(np.mean(integ[i_mid]))

    e = 4.0
    R, sur_appui, mi_travee = integrales(None)
    assert sur_appui == pytest.approx(-R * e / 12, rel=0.05)
    assert mi_travee == pytest.approx(R * e / 24, rel=0.08)
    assert mi_travee - sur_appui == pytest.approx(R * e / 8, rel=0.02)
    R, sur_appui, mi_travee = integrales(2.0)
    assert mi_travee - sur_appui == pytest.approx(R * (e - 2.0) / 8, rel=0.02)
