"""J1 — noyau 2D, une phase : solutions analytiques et équilibre limite."""
import numpy as np
import pytest
from scipy.sparse.linalg import spsolve

from sout.noyau.modele import Ecran, Modele, Phase
from sout.noyau.phasage import calculer
from sout.noyau.poutre import assembler, maillage
from sout.noyau.ressorts import AVAL, Ressorts
from sout.noyau.solveur import Appuis, resoudre
from sout.sol.couches import Couche


def test_console_encastree_charge_en_tete():
    # Console de longueur L encastrée en pied, charge P en tête :
    # flèche PL³/(3EI), moment d'encastrement −P·L (face amont tendue).
    L, EI, P = 5.0, 2e4, 10.0
    z = maillage([], 0.0, L, 0.5)
    K = assembler(z, np.full(len(z) - 1, EI)).tolil()
    f = np.zeros(2 * len(z)); f[-2] = P
    libres = np.arange(2, 2 * len(z))
    u = np.zeros(2 * len(z))
    u[libres] = spsolve(K.tocsc()[libres][:, libres], f[libres])
    assert u[-2] == pytest.approx(P * L**3 / (3 * EI), rel=1e-10)
    from sout.noyau.poutre import efforts_internes
    zd, M, V = efforts_internes(z, np.full(len(z) - 1, EI), u)
    assert M[0] == pytest.approx(-P * L, rel=1e-10)
    np.testing.assert_allclose(V, P, rtol=1e-10)


def test_efforts_par_statique_console_charge_repartie():
    # Console encastrée en pied (z = 0), charge répartie q sur toute la hauteur L, vers la fouille :
    # V(z) = q·(L − z), M(z) = −q·(L − z)²/2 ; nuls en tête (extrémité libre).
    from sout.noyau.poutre import efforts_par_statique
    L, q = 6.0, 12.0
    z = maillage([], 0.0, L, 0.5)
    zb, zh = z[:-1], z[1:]                       # un tronçon par élément
    zp, M, V = efforts_par_statique(z, zb, zh, np.full(len(zb), q))
    np.testing.assert_allclose(V, q * (L - zp), atol=1e-12)
    np.testing.assert_allclose(M, -q * (L - zp) ** 2 / 2, atol=1e-12)
    # avec une force ponctuelle P en tête (nœud du haut), V saute de P et M = −P·(L − z) en plus
    P = 30.0
    zp, M2, V2 = efforts_par_statique(z, zb, zh, np.full(len(zb), q), [len(z) - 1], [P])
    np.testing.assert_allclose(V2 - V, P, atol=1e-12)
    np.testing.assert_allclose(M2 - M, -P * (L - zp), atol=1e-12)


def test_tranchant_nul_aux_extremites_libres():
    """Écran autostable : aucune force ponctuelle, donc V = 0 en pied et en tête (charges
    réparties sur leurs demi-mailles). Avant correction, la charge de la demi-maille de pied,
    concentrée au nœud, donnait un saut de V de plusieurs kN au pied."""
    res = _autostable(3.0)
    ph = res.phases[-1]
    assert abs(ph.V[0]) < 1e-6 and abs(ph.V[-1]) < 1e-6
    assert ph.M[-1] == 0.0
    assert abs(ph.M[0]) < 1e-3 * abs(ph.M).max()
    # le moment maximal par la statique reste celui de la poutre (M = −EI·y'') au maillage près
    y = ph.y
    z = ph.z
    EI = 1e5
    courbure = np.gradient(np.gradient(y, z), z)
    i = int(np.argmax(np.abs(ph.M[0::2])))
    assert -EI * courbure[i] == pytest.approx(ph.M[2 * i], rel=0.05)


def _poutre_winkler(L, EI, k, pas):
    z = maillage([0.0], -L / 2, L / 2, pas)
    n = len(z)
    trib = np.zeros(n)
    trib[1:] += 0.5 * np.diff(z)
    trib[:-1] += 0.5 * np.diff(z)
    r = Ressorts(noeud=np.arange(n), s=np.full(n, AVAL, float), A=trib, kh=np.full(n, k),
                 p_ref=np.zeros(n), y_ref=np.zeros(n), pa=np.full(n, -1e12), pp=np.full(n, 1e12))
    return z, r


def test_hetenyi_poutre_infinie_charge_ponctuelle():
    # Hetényi (1946), Beams on Elastic Foundation : y0 = Pλ/(2k), M0 = P/(4λ), λ = (k/4EI)^(1/4)
    EI, k, P = 1e5, 1e4, 100.0
    lam = (k / (4 * EI)) ** 0.25
    z, r = _poutre_winkler(40.0, EI, k, 0.05)
    f = np.zeros(2 * len(z))
    ic = int(np.argmin(np.abs(z)))
    f[2 * ic] = P
    sol = resoudre(z, np.full(len(z) - 1, EI), r, Appuis(), f)
    assert sol.y[ic] == pytest.approx(P * lam / (2 * k), rel=1e-2)
    M0 = sol.M[np.argmin(np.abs(sol.z_diag))]
    assert M0 == pytest.approx(P / (4 * lam), rel=1e-2)


def test_charge_uniforme_sur_winkler():
    EI, k, q = 5e4, 2e4, 30.0
    z, r = _poutre_winkler(10.0, EI, k, 0.1)
    f = np.zeros(2 * len(z))
    f[0::2] = q * r.A
    sol = resoudre(z, np.full(len(z) - 1, EI), r, Appuis(), f)
    np.testing.assert_allclose(sol.y, q / k, rtol=1e-9)
    np.testing.assert_allclose(sol.M, 0.0, atol=1e-6)


SABLE = Couche("Sable", 0.0, gamma=20, gamma_dejauge=10, phi=30, c=0, kh=2e4)


def _autostable(h, D=10.0, EI=1e5, pas=0.1, couche=SABLE):
    m = Modele(ecran=Ecran(tete=0.0, pied=-D, EI=EI), couches=[couche],
               phases=[Phase("Excavation", excaver=-h)], pas=pas)
    return calculer(m)


def test_autostable_equilibre_global():
    res = _autostable(3.0)
    assert res.complet
    ph = res.phases[-1]
    am, av = ph.pressions["amont"], ph.pressions["aval"]
    F = np.sum(am["L"] * am["p"]) - np.sum(av["L"] * av["p"])
    # les forces des ressorts s'appliquent aux nœuds
    Mo = np.sum(am["L"] * am["p"] * am["z_noeud"]) - np.sum(av["L"] * av["p"] * av["z_noeud"])
    assert abs(F) < 1e-6
    assert abs(Mo) < 1e-6
    # pressions toujours entre les limites
    for c in (am, av):
        assert np.all(c["p"] >= c["pa"] - 1e-9) and np.all(c["p"] <= c["pp"] + 1e-9)
    # écran déplacé vers la fouille en tête, moment négatif (face amont tendue)
    assert ph.y[-1] > 0
    assert ph.M.min() < 0 and abs(ph.M.min()) > abs(ph.M.max())


def test_etat_initial_au_repos_sans_deplacement():
    res = _autostable(3.0)
    init = res.phases[0]
    np.testing.assert_allclose(init.y, 0.0, atol=1e-12)
    np.testing.assert_allclose(init.pressions["amont"]["p"], init.pressions["amont"]["p0"])


def test_convergence_maillage():
    y1 = _autostable(3.0, pas=0.2).phases[-1].y[-1]
    y2 = _autostable(3.0, pas=0.05).phases[-1].y[-1]
    assert y1 == pytest.approx(y2, rel=1e-2)


def _h_critique_equilibre_limite(D, ka, kp, gamma):
    from sout.validation.cas_ecran import h_critique_autostable_equilibre_limite
    return h_critique_autostable_equilibre_limite(D, ka, kp, gamma)


def test_equilibre_limite_autostable_rigide():
    """La hauteur critique du modèle à ressorts (écran très raide) tend vers
    celle de l'équilibre limite rigide-plastique."""
    D = 10.0
    h_ref = _h_critique_equilibre_limite(D, 1 / 3, 3.0, 20.0)
    bas, haut = 1.0, 9.0
    for _ in range(18):
        h = 0.5 * (bas + haut)
        if _autostable(h, D=D, EI=1e9, pas=0.1).complet:
            bas = h
        else:
            haut = h
    assert bas == pytest.approx(h_ref, rel=2e-2)


def test_efforts_par_statique_couples_appliques():
    """Couples concentrés aux nœuds (moments transmis par la plaque en pseudo-3D) : la statique
    redonne exactement les moments internes des éléments (Ke·ue, exacts pour des charges nodales)
    sur une console encastrée en pied portant un couple en tête, un couple à mi-hauteur et une
    force en tête ; V est insensible aux couples ; le saut de M au droit du couple vaut C."""
    from sout.noyau.poutre import assembler, efforts_internes, efforts_par_statique, maillage
    from scipy.sparse.linalg import spsolve

    L, EI, n = 6.0, 2.0e5, 12
    z = maillage([], 0.0, L, L / n)
    EI_elem = np.full(len(z) - 1, EI)
    K = assembler(z, EI_elem)
    f = np.zeros(2 * len(z))
    jm, jt = n // 2, n
    P, C1, C2 = 7.0, 15.0, -4.0
    f[2 * jt] = P              # force en tête (vers la fouille)
    f[2 * jt + 1] = C1         # couple en tête
    f[2 * jm + 1] = C2         # couple à mi-hauteur
    libres = np.arange(2, 2 * len(z))                      # encastrement au pied : y0 = θ0 = 0
    u = np.zeros(2 * len(z))
    u[libres] = spsolve(K[libres][:, libres].tocsc(), f[libres])
    zi, Mi, Vi = efforts_internes(z, EI_elem, u)
    zb, zh = z[:-1], z[1:]
    zs, Ms, Vs = efforts_par_statique(z, zb, zh, np.zeros(n), [jt], [P], [jt, jm], [C1, C2])
    np.testing.assert_allclose(zs, zi, atol=1e-12)
    np.testing.assert_allclose(Ms, Mi, rtol=1e-9, atol=1e-9)
    np.testing.assert_allclose(Vs, Vi, rtol=1e-9, atol=1e-9)
    # saut de M au droit du couple de mi-hauteur : M au-dessus − M en dessous = C2 ; V constant = P
    assert Ms[2 * jm] - Ms[2 * jm - 1] == pytest.approx(C2, abs=1e-9)
    assert np.allclose(Vs, P)
    # sans couple : M continu, et le couple en tête se lit directement en tête (M = −C1)
    assert Ms[-1] == pytest.approx(-C1, abs=1e-9)
