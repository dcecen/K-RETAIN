"""Pseudo-3D en fouille fermée : surcharges localisées en plan, rapportées à chaque ligne verticale.
Une charge ponctuelle derrière une paroi charge la paroi près d'elle, est transmise par les butons à
la paroi d'en face (qui recule vers sa terre) : démonstration du « double écran »."""
import numpy as np
import pytest

from sout.noyau.modele import DefAppui, Ecran, Modele, Phase
from sout.noyau.phasage import calculer
from sout.pseudo3d.calcul import MoteurPseudo3D
from sout.sol.couches import Couche
from sout.sol.terrain import SurchargePlan

SABLE = Couche("Sable", 0.0, 20, 10, 32, EM=12000, alpha=1 / 3)
RECT = [[0.0, 0.0], [20.0, 0.0], [20.0, 12.0], [0.0, 12.0]]
Q = SurchargePlan(nom="grue", type="ponctuelle", q=3000.0, position=(10.0, -3.0), cote_ecran="amont")


def _modele(surcharges=(), coupe=None, cotes_paroi=None):
    app = {"B": DefAppui("B", -1.0, 30000.0, precharge=20.0, type="buton", infos={"espacement": 4.0, "symetrique": True, "type": "buton"})}
    scs = [SurchargePlan(**{**s.__dict__, "cotes_paroi": cotes_paroi}) if cotes_paroi else s for s in surcharges]
    return Modele(ecran=Ecran(0.0, -12.0, 1e5), couches=[SABLE], appuis=app, pas=0.25, surcharges=scs, coupe=coupe,
                  phases=[Phase("Exc1", excaver=-2.0), Phase("Pose", poser=["B"]), Phase("Exc2", excaver=-6.0)])


def test_coupes_par_ligne_et_detection_des_surcharges_en_plan():
    mo = MoteurPseudo3D(_modele([Q]), None, 1.0, contour=RECT, cotes_plan={"sud": 0, "est": 1})
    assert mo.sol_par_ligne and len(mo.coupes_lignes) == mo.ns
    c = mo.coupes_lignes[10]
    assert (c.x, c.y) == (10.0, 0.0) and c.ni == (0.0, 1.0) and c.k == 0 and c.cote == "sud"
    c2 = mo.coupes_lignes[int(np.argmin(np.abs(mo.s - 42.0)))]
    assert (c2.x, c2.y) == pytest.approx((10.0, 12.0)) and c2.ni == (0.0, -1.0) and c2.cote is None
    assert not MoteurPseudo3D(_modele(), None, 1.0, contour=RECT).sol_par_ligne
    assert any("rapportées à chaque ligne" in a for a in mo.avertissements)


def test_sans_rigidite_horizontale_chaque_ligne_est_le_2d_a_sa_position():
    """Ds = 0 : la ligne verticale en x est l'écran 2D calculé avec une coupe de calcul placée en x
    (même diffusion de Boussinesq), à 1e-6, pour trois distances à la charge."""
    m = _modele([Q])
    r3 = MoteurPseudo3D(m, None, 1.0, contour=RECT, rapport_rigidite_horizontale=0.0, liens=False).calculer()
    for x in (10.0, 13.0, 17.0):
        i = int(np.argmin(np.abs(r3.s - x)))
        coupe = {"x": x, "y": 0.0, "ni": [0.0, 1.0], "t": [1.0, 0.0], "k": 0, "s": x}
        if x in (2.0, 6.0, 10.0, 14.0, 18.0):      # ligne d'un buton : ressort k·e/ds, précharge F0·e/ds (ds = 1 m)
            app = {"B": DefAppui("B", -1.0, 30000.0 * 4.0, precharge=20.0 * 4.0, infos={"espacement": 4.0})}
            m2 = Modele(ecran=Ecran(0.0, -12.0, 1e5), couches=[SABLE], appuis=app, pas=0.25, surcharges=[Q], coupe=coupe,
                        phases=[Phase("Exc1", excaver=-2.0), Phase("Pose", poser=["B"]), Phase("Exc2", excaver=-6.0)])
        else:
            m2 = Modele(ecran=Ecran(0.0, -12.0, 1e5), couches=[SABLE], appuis={}, pas=0.25, surcharges=[Q], coupe=coupe,
                        phases=[Phase("Exc1", excaver=-2.0), Phase("Pose"), Phase("Exc2", excaver=-6.0)])
        r2 = calculer(m2)
        for k in range(len(r3.phases)):
            np.testing.assert_allclose(r3.phases[k].W[i], r2.phases[k].y, rtol=1e-6, atol=1e-12)


def test_la_charge_est_locale_et_symetrique():
    m = _modele([Q])
    avec = MoteurPseudo3D(m, None, 1.0, contour=RECT).calculer().phases[-1]
    sans = MoteurPseudo3D(_modele(), None, 1.0, contour=RECT).calculer().phases[-1]
    prof = np.abs(avec.W).max(axis=1)
    i10 = 10
    assert prof[i10] == prof[:21].max()                                     # maximum au droit de la charge
    np.testing.assert_allclose(avec.W[i10 - 6:i10], avec.W[i10 + 6:i10:-1], rtol=1e-6, atol=1e-9 * prof.max())
    assert prof[i10] > 1.3 * np.abs(sans.W).max(axis=1)[i10]
    assert abs(avec.bilan["residu"]) <= 1e-6 * avec.bilan["echelle"]


def test_double_ecran_la_paroi_d_en_face_recule_et_les_butons_transmettent():
    """Paroi sud chargée : les butons en vis-à-vis prennent plus d'effort et poussent la paroi nord
    vers sa terre (déplacement plus faible qu'avant la charge au droit des butons) ; sans liens (ressorts
    L/2 vers le sol), la paroi nord ignore la charge."""
    avec = MoteurPseudo3D(_modele([Q]), None, 1.0, contour=RECT).calculer().phases[-1]
    sans = MoteurPseudo3D(_modele(), None, 1.0, contour=RECT).calculer().phases[-1]
    s_app = sorted(a["s"] for a in avec.appuis)
    assert s_app == [2.0, 6.0, 10.0, 14.0, 18.0]
    e_avec = {a["s"]: a["effort"] for a in avec.appuis}
    e_sans = {a["s"]: a["effort"] for a in sans.appuis}
    assert e_avec[10.0] > 1.1 * e_sans[10.0] and e_avec[2.0] == pytest.approx(e_sans[2.0], rel=0.15)
    nord = slice(32, 53)                                 # côté nord (x de 20 à 0) ; s = 42 est le vis-à-vis de x = 10
    W_avec, W_sans = avec.W[nord], sans.W[nord]
    assert np.abs(W_avec[42 - 32]).max() < np.abs(W_sans[42 - 32]).max()   # repoussée vers sa terre
    assert (W_avec.min() < W_sans.min())                                             # recul plus marqué
    # avec des ressorts vers le sol à la place des liens, la paroi nord ne reçoit que la diffusion directe
    # de la charge (Boussinesq à 15 m : moins de 1 %) : l'effet transmis par les butons est bien plus grand
    r_sol_avec = MoteurPseudo3D(_modele([Q]), None, 1.0, contour=RECT, liens=False).calculer().phases[-1]
    r_sol_sans = MoteurPseudo3D(_modele(), None, 1.0, contour=RECT, liens=False).calculer().phases[-1]
    d_liens = np.abs(avec.W[36:49] - sans.W[36:49]).max()
    d_sol = np.abs(r_sol_avec.W[36:49] - r_sol_sans.W[36:49]).max()
    assert d_sol < 0.01 * np.abs(sans.W).max() and d_liens > 5 * d_sol


def test_filtre_des_cotes_concernes():
    """Bande de surcharge déclarée pour le côté « sud » seulement : les lignes du côté nord n'ont pas de Δσv
    (une charge ponctuelle en plan, elle, rayonne géométriquement sur toutes les parois)."""
    bande = SurchargePlan(nom="stock", type="bande", q=20.0, distance=1.0, largeur=3.0, cote_ecran="amont")
    m = _modele([bande], cotes_paroi=("sud",))
    mo = MoteurPseudo3D(m, None, 1.0, contour=RECT, cotes_plan={"sud": 0, "nord": 2})
    etat = mo.m2.etat_chantier_initial()
    sv_sud = mo.m2.etat_sol(etat, coupe=mo.coupes_lignes[10])["sv"]
    sv_nord = mo.m2.etat_sol(etat, coupe=mo.coupes_lignes[42])["sv"]
    m0 = MoteurPseudo3D(_modele(), None, 1.0, contour=RECT).m2
    sv_sans = m0.etat_sol(m0.etat_chantier_initial())["sv"]
    assert np.abs(sv_sud - sv_sans).max() > 1.0
    np.testing.assert_allclose(sv_nord, sv_sans, rtol=1e-12, atol=1e-12)
