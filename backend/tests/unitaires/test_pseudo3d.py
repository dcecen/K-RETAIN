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


def test_precharge_portee_apres_la_pose(calculs):
    """Même règle qu'en 2D : après la phase de pose seule, l'appui porte exactement sa précharge
    (20 kN/m en 2D ; en pseudo-3D chaque appui ponctuel porte 20 kN/m × espacement 4 m = 80 kN)."""
    r2, r3 = calculs
    assert r2.phases[2].appuis[0]["effort"] == pytest.approx(20.0, abs=1e-6)
    for a in r3.phases[2].appuis:
        assert a["effort"] == pytest.approx(20.0 * 4.0, abs=1e-6)


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


# ---------------------------------------------------------------------------
# Efforts 3D : effort tranchant par la statique des lignes, réactions, bilan d'équilibre
# ---------------------------------------------------------------------------
def test_tranchant_3d_identique_au_2d_en_flexion_cylindrique(calculs):
    """Avant la pose des appuis ponctuels (flexion cylindrique), les forces de transfert sont
    nulles : V et M par la statique de chaque ligne redonnent exactement les diagrammes 2D."""
    r2, r3 = calculs
    ph2, ph3 = r2.phases[1], r3.phases[1]
    np.testing.assert_allclose(ph3.z_diag, ph2.z_diag, atol=1e-12)
    for i in range(ph3.V_diag.shape[0]):
        np.testing.assert_allclose(ph3.V_diag[i], ph2.V, rtol=1e-6, atol=1e-9 * np.abs(ph2.V).max())
        np.testing.assert_allclose(ph3.M_stat[i], ph2.M, rtol=1e-6, atol=1e-9 * np.abs(ph2.M).max())
    assert np.abs(ph3.Mzs).max() < 1e-9 * np.abs(ph3.Mz).max()


def test_tranchant_nul_aux_extremites_libres_et_equilibre_3d(calculs):
    """À chaque phase : V = 0 en tête et en pied libres sur toutes les lignes ; la somme des forces
    (sol, eau, appuis, réactions) et leurs moments selon z et selon s sont nuls."""
    _, r3 = calculs
    H, L = r3.z[-1] - r3.z[0], r3.s[-1]
    for ph in r3.phases:
        if not ph.ok:
            continue
        vmax = np.abs(ph.V_diag).max()
        assert np.abs(ph.V_diag[:, 0]).max() <= 1e-6 * vmax
        assert np.abs(ph.V_diag[:, -1]).max() <= 1e-6 * vmax
        b = ph.bilan
        ech = max(b["echelle"], 1.0)          # état initial : aucune force (échelle nulle)
        assert abs(b["residu"]) <= 1e-6 * ech
        assert abs(b["moment_residu_z"]) <= 1e-6 * ech * H
        assert abs(b["moment_residu_s"]) <= 1e-6 * ech * L
        assert b["reactions"] == 0.0          # bords libres, pas d'angle
        # cohérence des forces nodales avec le bilan
        assert sum(f.sum() for f in ph.forces.values()) == pytest.approx(b["residu"], abs=1e-9 * ech)


def test_saut_de_tranchant_au_droit_des_appuis(calculs):
    """Sur la ligne d'un appui ponctuel, V saute de effort/ds au nœud de l'appui ; les forces de
    transfert, réparties sur les demi-mailles, ne créent aucun saut ailleurs."""
    from sout.pseudo3d import plaque
    _, r3 = calculs
    ph = r3.phases[-1]
    ds = plaque.largeurs_tributaires(r3.s)
    j = int(np.argmin(np.abs(r3.z - (-1.0))))
    for a in ph.appuis:
        i = int(np.argmin(np.abs(r3.s - a["s"])))
        saut = ph.V_diag[i, 2 * j] - ph.V_diag[i, 2 * j - 1]      # au-dessus − en dessous du nœud
        assert saut == pytest.approx(a["effort"] / ds[i], rel=1e-8, abs=1e-9)
    # ligne sans appui : V continu partout
    i0 = int(np.argmin(np.abs(r3.s - (ph.appuis[0]["s"] + 2.0))))
    assert all(abs(x["s"] - r3.s[i0]) > 0.5 for x in ph.appuis)
    sauts = ph.V_diag[i0, 2:-1:2] - ph.V_diag[i0, 1:-2:2]
    assert np.abs(sauts).max() <= 1e-9 * np.abs(ph.V_diag).max()


def test_angle_reactions_equilibrent_les_charges():
    """Avec un angle, la ligne d'angle (w = 0) reprend exactement ce que le sol, l'eau et les
    appuis ne reprennent pas."""
    m = _modele()
    r3 = MoteurPseudo3D(m, 48.0, 1.0, angle=90.0).calculer()
    ph = r3.phases[-1]
    b = ph.bilan
    assert b["reactions"] != 0.0
    assert b["reactions"] == pytest.approx(-(b["sol"] + b["eau"] + b["appuis"]), rel=1e-6)
    lignes = np.flatnonzero(np.abs(ph.reactions).sum(axis=1) > 0)
    assert lignes.tolist() == [int(np.argmin(np.abs(r3.s - 24.0)))]
    assert abs(b["residu"]) <= 1e-6 * b["echelle"]


def test_bords_appuyes_bloquent_w_et_la_rotation_tangente():
    """Bord appuyé : w = 0 et θz = 0 (pente le long du bord) pénalisés, θs libre ; bord encastré :
    les trois ; les bords encastrés retiennent davantage la paroi que les bords appuyés."""
    m = _modele()
    ma = MoteurPseudo3D(m, 20.0, 1.0, bords="appuyes")
    me = MoteurPseudo3D(m, 20.0, 1.0, bords="encastres")
    nz = ma.nz
    da, de = ma.K.diagonal(), me.K.diagonal()
    for i in (0, ma.ns - 1):
        for j in (0, nz // 2, nz - 1):
            k = i * nz + j
            assert da[3 * k] >= ma.pen and da[3 * k + 1] >= ma.pen and da[3 * k + 2] < ma.pen
            assert de[3 * k] >= me.pen and de[3 * k + 1] >= me.pen and de[3 * k + 2] >= me.pen
    k = (ma.ns // 2) * nz + nz // 2
    assert da[3 * k] < ma.pen and da[3 * k + 1] < ma.pen
    ra, re = ma.calculer().phases[-1], me.calculer().phases[-1]
    assert np.abs(ra.W[0]).max() < 1e-3 * np.abs(ra.W).max()
    assert np.abs(re.W[1]).max() < np.abs(ra.W[1]).max()
    assert ra.bilan["reactions"] == pytest.approx(-(ra.bilan["sol"] + ra.bilan["eau"] + ra.bilan["appuis"]), rel=1e-6)


def test_serialisation_efforts_3d(calculs):
    r2, r3 = calculs
    d = serialiser(r3, r2)
    ph = d["phases"][-1]
    assert len(ph["V"]) == len(d["s"]) and len(ph["V"][0]) == len(d["z"])
    assert ph["V_absmax"] > 0 and "Mzs_absmax" in ph and ph["reactions"] == {"s": [], "total_kN": []}
    assert abs(ph["bilan"]["residu"]) <= 1e-6 * ph["bilan"]["echelle"]
    assert all(a["espacement"] == 4.0 and a["angle"] == 0.0 for a in ph["appuis"])
    # appariement 2D/3D par nom de phase, pas par indice
    assert ph["y_max_2d_mm"] == pytest.approx(np.abs(next(p for p in r2.phases if p.nom == ph["nom"]).y).max() * 1e3)


# ---------------------------------------------------------------------------
# largeur_appui : appui réparti sur une largeur (plaque d'appui, semelle de lierne)
# ---------------------------------------------------------------------------
def test_largeur_appui_repartit_l_appui_sans_changer_sa_resultante():
    """Poids par recouvrement exact des bandes tributaires (somme 1) ; après la phase de pose seule,
    chaque appui réel porte F0·e ; la somme des efforts est celle du cas ponctuel à 2 % près."""
    m = _modele()
    mo = MoteurPseudo3D(m, 24.0, 0.5, largeur_appui=2.0)
    pts = mo._noeuds_appui(10.0)
    assert sum(w for _, w in pts) == pytest.approx(1.0, abs=1e-12)
    assert len(pts) == 5 and all(abs(mo.s[i] - 10.0) <= 1.0 + 1e-9 for i, _ in pts)
    poids = dict(pts)
    i10 = int(np.argmin(np.abs(mo.s - 10.0)))
    assert poids[i10] == pytest.approx(0.25) and poids[i10 - 2] == pytest.approx(0.125)   # nœuds extrêmes : quart de bande
    r = mo.calculer()
    assert len(r.phases[2].appuis) == 6 and all(a["effort"] == pytest.approx(80.0, abs=1e-6) for a in r.phases[2].appuis)
    r0 = MoteurPseudo3D(m, 24.0, 0.5).calculer()
    assert sum(a["effort"] for a in r.phases[-1].appuis) == pytest.approx(sum(a["effort"] for a in r0.phases[-1].appuis), rel=0.02)
    assert any("largeur_appui" in a for a in r0.avertissements)
    assert not any("largeur_appui" in a for a in r.avertissements)


def test_largeur_appui_fait_converger_ms_et_v_au_droit_des_appuis():
    """Sans largeur, Ms et V au droit d'un appui ponctuel croissent sans limite avec le raffinement
    (singularité d'une charge concentrée sur une plaque) ; avec largeur_appui = 2 m ils convergent.
    W et Mz convergent dans les deux cas."""
    m = _modele()

    def mesure(pas, larg):
        mo = MoteurPseudo3D(m, 24.0, pas, largeur_appui=larg)
        ph = mo.calculer().phases[-1]
        j = int(np.argmin(np.abs(mo.z + 1.0)))
        a = ph.appuis[2]
        i = int(np.argmin(np.abs(mo.s - a["s"])))
        return abs(ph.Ms[i, j]), float(np.abs(ph.V_diag).max()), float(np.abs(ph.W).max()), float(ph.Mz.max())

    p5, p25 = mesure(0.5, None), mesure(0.25, None)
    l5, l25 = mesure(0.5, 2.0), mesure(0.25, 2.0)
    assert p25[1] > 1.6 * p5[1] and p25[0] > 1.15 * p5[0]          # cas ponctuel : divergence
    assert l25[0] == pytest.approx(l5[0], rel=0.05) and l25[1] == pytest.approx(l5[1], rel=0.02)
    for a, b in ((p5, p25), (l5, l25)):
        assert b[2] == pytest.approx(a[2], rel=0.01) and b[3] == pytest.approx(a[3], rel=0.01)
