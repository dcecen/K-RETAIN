"""J9 — pseudo-3D : paroi en plaque (grillage) sur ressorts élasto-plastiques."""
import numpy as np
import pytest

from sout.noyau.modele import DefAppui, Ecran, Modele, Phase
from sout.noyau.phasage import calculer
from sout.pseudo3d.calcul import MoteurPseudo3D, serialiser
from sout.sol.couches import Couche

SABLE = Couche("Sable", 0.0, 20, 10, 32, EM=12000, alpha=1 / 3)


def _modele(espacement=4.0):
    app = {"B": DefAppui("B", -1.0, 30000.0, precharge=20.0, infos={"espacement": espacement})}
    return Modele(ecran=Ecran(0.0, -12.0, 1e5), couches=[SABLE], appuis=app, pas=0.25,
                  phases=[Phase("Exc1", excaver=-2.0), Phase("Pose", poser=["B"]), Phase("Exc2", excaver=-6.0)])


@pytest.fixture(scope="module")
def calculs():
    m = _modele()
    return calculer(m), MoteurPseudo3D(m, 48.0, 1.0).calculer()


def test_flexion_cylindrique_identique_au_2d(calculs):
    r2, r3 = calculs
    # Avant la pose des appuis ponctuels, rien ne varie le long de la paroi : le grillage = la poutre 2D
    W = r3.phases[1].W
    for i in range(W.shape[0]):
        np.testing.assert_allclose(W[i], r2.phases[1].y, rtol=1e-6, atol=1e-10)
    np.testing.assert_allclose(r3.phases[1].Mz[W.shape[0] // 2], np.interp(
        r2.z, 0.5 * (r2.phases[1].z_diag[0::2] + r2.phases[1].z_diag[1::2]),
        0.5 * (r2.phases[1].M[0::2] + r2.phases[1].M[1::2])), atol=0.5)


def test_paroi_tres_longue_retrouve_le_2d(calculs):
    """Appuis ponctuels tous les 4 m sur une paroi de 48 m à bords libres : au centre,
    déplacement et moment maximaux à moins de 5 % du calcul 2D (appuis répartis)."""
    r2, r3 = calculs
    fin2, fin3 = r2.phases[-1], r3.phases[-1]
    ic = fin3.W.shape[0] // 2
    zone = slice(ic - 4, ic + 5)   # une travée entre appuis autour du centre
    assert np.abs(fin3.W[zone]).max() == pytest.approx(np.abs(fin2.y).max(), rel=0.05)
    assert fin3.Mz[zone].max() == pytest.approx(fin2.M.max(), rel=0.05)
    # effort moyen par appui ≈ effort 2D × espacement
    eff = [a["effort"] for a in fin3.appuis[3:-3]]
    assert np.mean(eff) == pytest.approx(fin2.appuis[0]["effort"] * 4.0, rel=0.05)


def test_effet_d_angle_coherent():
    m = _modele()
    r2 = calculer(m)
    r3 = MoteurPseudo3D(m, 48.0, 1.0, angle=90.0).calculer()
    W = r3.phases[-1].W
    ns = W.shape[0]
    ic = r3.phases and int(np.argmin(np.abs(r3.s - 24.0)))
    assert np.abs(W[ic]).max() < 1e-3 * np.abs(W).max()            # l'angle tient la paroi
    np.testing.assert_allclose(W, W[::-1], atol=1e-6 * np.abs(W).max())  # symétrie
    prof = np.abs(W).max(axis=1)
    assert prof[ic + 2] < prof[ic + 6] < prof[ic + 12]                # le déplacement croît en s'éloignant
    loin = prof[2:6].max()                                            # loin de l'angle : proche du 2D
    assert loin == pytest.approx(np.abs(r2.phases[-1].y).max(), rel=0.10)
    assert ns == len(r3.s)


def test_bords_encastres():
    m = _modele()
    r3 = MoteurPseudo3D(m, 20.0, 1.0, bords="encastres").calculer()
    W = r3.phases[-1].W
    assert np.abs(W[0]).max() < 1e-3 * np.abs(W).max()
    assert np.abs(W[-1]).max() < 1e-3 * np.abs(W).max()


def test_serialisation(calculs):
    r2, r3 = calculs
    d = serialiser(r3, r2)
    assert len(d["phases"]) == 4 and len(d["phases"][-1]["y_mm"]) == len(d["s"])
    assert len(d["phases"][-1]["y_mm"][0]) == len(d["z"])
    assert d["phases"][-1]["y_max_2d_mm"] == pytest.approx(np.abs(r2.phases[-1].y).max() * 1e3)
