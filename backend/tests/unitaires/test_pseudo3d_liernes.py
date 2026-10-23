"""Pseudo-3D : liernes modélisées comme poutres horizontales continues au niveau des appuis.

Cas d'école : palplanches (aucune rigidité horizontale) butonnées ponctuellement. Sans lierne,
chaque buton ne retient que sa ligne ; une lierne infiniment raide impose le même déplacement
à toute la rangée et redonne exactement l'écran 2D à appui réparti ; une lierne réelle (HEB 400)
redistribue et travaille en poutre continue sur les butons."""
import numpy as np
import pytest

from sout.appuis.construction import construire_appui, rigidite_lierne
from sout.materiaux.base import catalogue_par_defaut
from sout.noyau.modele import DefAppui, Ecran, Modele, Phase
from sout.noyau.phasage import calculer
from sout.pseudo3d.calcul import MoteurPseudo3D, serialiser
from sout.script.schema import Appui
from sout.sol.couches import Couche

SABLE = Couche("Sable", 0.0, 20, 10, 32, EM=12000, alpha=1 / 3)
E_HEB400 = 210000e3 * 57680.5253806435e-8     # E·Iy du HEB 400 de la base DEMO (kN·m²)


def _modele(EI_lierne=None, espacement=6.0, phases=None):
    infos = {"espacement": espacement}
    if EI_lierne is not None:
        infos["EI_lierne"] = EI_lierne
    app = {"B": DefAppui("B", -1.0, 30000.0, precharge=20.0, infos=infos)}
    ph = phases or [Phase("Exc1", excaver=-2.0), Phase("Pose", poser=["B"]), Phase("Exc2", excaver=-6.0)]
    return Modele(ecran=Ecran(0.0, -12.0, 1e5), couches=[SABLE], appuis=app, pas=0.25, phases=ph)


def test_rigidite_de_la_lierne_depuis_la_base():
    cat = catalogue_par_defaut()
    a = Appui(type="buton", element="modulaire_A", cote=-1.0, espacement=6.0, longueur=20.0, lierne="HEB 400", acier="S355")
    d = construire_appui("B1", a, cat)
    assert d.infos["EI_lierne"] == pytest.approx(E_HEB400, rel=1e-9)     # 2,1e8 kPa × 57 680 cm⁴
    assert rigidite_lierne("B1", Appui(type="buton", element="modulaire_A", cote=-1.0, longueur=20.0, lierne="HEB 400"), cat)["EI_lierne"] is None
    assert rigidite_lierne("B1", Appui(type="buton", element="modulaire_A", cote=-1.0, longueur=20.0), cat) == {}
    assert "absente" in rigidite_lierne("B1", Appui(type="buton", element="modulaire_A", cote=-1.0, longueur=20.0, lierne="XXX", acier="S355"), cat)["lierne_motif"]


def test_lierne_infiniment_raide_redonne_le_2d_a_appui_reparti():
    """Palplanches (Ds = 0), butons tous les 6 m sur 48 m, lierne de rigidité 1e12 : toute la rangée
    se déplace d'un bloc, chaque ligne verticale est l'écran 2D dont l'appui réparti vaut k = k_buton
    (n·e = L) ; déplacements identiques au 2D à 1e-5 à toutes les phases, précharge comprise."""
    m = _modele(EI_lierne=1e12)
    r3 = MoteurPseudo3D(m, 48.0, 1.0, rapport_rigidite_horizontale=0.0).calculer()
    r2 = calculer(m)
    j = int(np.argmin(np.abs(r3.z + 1.0)))
    for k, ph in enumerate(r3.phases):
        if k >= 2:
            assert np.ptp(ph.W[:, j]) <= 1e-4 * max(np.abs(ph.W[:, j]).max(), 1e-9)   # rangée uniforme (E·I fini)
        for i in range(ph.W.shape[0]):
            np.testing.assert_allclose(ph.W[i], r2.phases[k].y, rtol=1e-4, atol=1e-10)
    assert all(a["effort"] == pytest.approx(20.0 * 6.0, abs=1e-6) for a in r3.phases[2].appuis)
    assert "B" in r3.phases[-1].liernes and np.abs(r3.phases[-1].liernes["B"]["M"]).max() > 0


def test_sans_lierne_les_butons_ne_retiennent_que_leur_ligne_et_la_lierne_redistribue():
    m0, m1 = _modele(), _modele(EI_lierne=E_HEB400)
    sans = MoteurPseudo3D(m0, 48.0, 1.0, rapport_rigidite_horizontale=0.0).calculer().phases[-1]
    avec = MoteurPseudo3D(m1, 48.0, 1.0, rapport_rigidite_horizontale=0.0).calculer().phases[-1]
    inter = slice(6, -6)
    prof_sans, prof_avec = np.abs(sans.W).max(axis=1), np.abs(avec.W).max(axis=1)
    assert prof_sans[inter].max() / prof_sans[inter].min() > 3.0
    assert prof_avec[inter].max() / prof_avec[inter].min() < 1.5
    assert prof_avec.max() < 0.6 * prof_sans.max()
    assert sans.liernes == {}
    li = avec.liernes["B"]
    assert li["EI"] == E_HEB400 and li["cote"] == -1.0 and len(li["M"]) == avec.W.shape[0]
    # poutre continue sur les butons : moment négatif aux butons, positif à mi-travée
    s = np.linspace(0, 48, avec.W.shape[0])
    i_app = [int(np.argmin(np.abs(s - a["s"]))) for a in avec.appuis[2:-2]]
    i_mid = [int(np.argmin(np.abs(s - (a["s"] + 3.0)))) for a in avec.appuis[2:-3]]
    assert all(li["M"][i] < 0 for i in i_app) and all(li["M"][i] > 0 for i in i_mid)
    assert abs(avec.bilan["residu"]) <= 1e-6 * avec.bilan["echelle"]


def test_lierne_raide_travaille_en_poutre_continue_sur_les_butons():
    """Lierne très raide devant les bandes (E·I = 1e8 kN·m²) : la charge qu'elle reçoit est quasi
    uniforme et son moment est celui de la poutre continue à travées égales : −R·e/12 aux butons
    intérieurs, +R·e/24 à mi-travée (R = effort d'un buton), à 10 % près."""
    m = _modele(EI_lierne=1e8)
    mo = MoteurPseudo3D(m, 48.0, 0.5, rapport_rigidite_horizontale=0.0)
    ph = mo.calculer().phases[-1]
    li = ph.liernes["B"]
    R = float(np.mean([a["effort"] for a in ph.appuis[2:-2]]))
    e = 6.0
    i_app = [int(np.argmin(np.abs(mo.s - a["s"]))) for a in ph.appuis[3:5]]
    i_mid = [int(np.argmin(np.abs(mo.s - (a["s"] + 3.0)))) for a in ph.appuis[3:5]]
    assert np.mean(li["M"][i_app]) == pytest.approx(-R * e / 12, rel=0.10)
    assert np.mean(li["M"][i_mid]) == pytest.approx(R * e / 24, rel=0.10)
    assert np.mean(li["M"][i_mid]) - np.mean(li["M"][i_app]) == pytest.approx(R * e / 8, rel=0.05)


def test_lierne_posee_et_deposee_avec_son_appui():
    phases = [Phase("Exc1", excaver=-2.0), Phase("Pose", poser=["B"]), Phase("Exc2", excaver=-4.0),
              Phase("Depose", deposer=["B"])]
    m = _modele(EI_lierne=E_HEB400, phases=phases)
    mo = MoteurPseudo3D(m, 24.0, 1.0, rapport_rigidite_horizontale=0.0)
    r = mo.calculer()
    assert [bool(p.liernes) for p in r.phases] == [False, False, True, True, False]
    assert len(mo._K_liernes) == 2                      # matrices sans et avec lierne, mises en cache
    d = serialiser(r)
    assert d["phases"][3]["liernes"]["B"]["M_absmax"] > 0 and d["phases"][4]["liernes"] == {}
    assert any("lierne de l'appui B" in a for a in r.avertissements)
