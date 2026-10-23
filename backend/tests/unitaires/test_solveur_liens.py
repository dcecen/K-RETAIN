"""Appuis « liens » entre deux nœuds (buton entre deux parois en vis-à-vis) dans le solveur."""
import numpy as np
import pytest
from scipy import sparse

from sout.noyau.poutre import assembler, maillage
from sout.noyau.ressorts import Ressorts
from sout.noyau.solveur import Appuis, resoudre_general

L, EI, KSOL = 10.0, 1.0e5, 3000.0


def _deux_poutres():
    """Deux poutres identiques sur fondation de Winkler (ressorts bilatéraux), numérotées à la suite."""
    z = maillage([], 0.0, L, 0.25)
    n = len(z)
    K1 = assembler(z, np.full(n - 1, EI))
    K = sparse.block_diag([K1, K1]).tocsc()
    ddl_w = np.arange(0, 4 * n, 2)                      # DDL y des 2n nœuds
    t = np.zeros(n)
    t[1:] += 0.5 * np.diff(z)
    t[:-1] += 0.5 * np.diff(z)
    big = 1e12
    r = Ressorts(noeud=np.arange(2 * n), s=np.full(2 * n, -1.0), A=np.tile(t, 2), kh=np.full(2 * n, KSOL),
                 p_ref=np.zeros(2 * n), y_ref=np.zeros(2 * n), pa=np.full(2 * n, -big), pp=np.full(2 * n, big))
    return z, n, K, ddl_w, r


def test_lien_entre_deux_noeuds_action_reaction_et_souplesse():
    """Force P en tête de la poutre 1, lien de raideur k entre les deux têtes : N = k·f·P/(1 + 2kf)
    où f est la souplesse de la tête (compatibilité), la poutre 2 recule (y₂ = −f·N), et la force
    −N s'applique aux deux têtes."""
    z, n, K, ddl_w, r = _deux_poutres()
    P, k = 50.0, 2000.0
    top1, top2 = n - 1, 2 * n - 1
    f_ext = np.zeros(4 * n)
    f_ext[2 * top1] = 1.0
    u, _, _ = resoudre_general(K, ddl_w, r, Appuis(), f_ext)
    f = u[2 * top1]                                     # souplesse de la tête d'une poutre seule
    lien = Appuis(nom=["B"], noeud=np.array([top1]), k=np.array([k]), F0=np.zeros(1), y_pose=np.zeros(1),
                  unilateral=np.array([False]), noeud2=np.array([top2]), y_pose2=np.zeros(1))
    f_ext = np.zeros(4 * n)
    f_ext[2 * top1] = P
    u, _, _ = resoudre_general(K, ddl_w, r, lien, f_ext)
    y = u[ddl_w]
    N = k * f * P / (1 + 2 * k * f)
    eff, actif = lien.efforts(y)
    assert eff[0] == pytest.approx(N, rel=1e-7) and actif[0]        # 1e-7 : convergence du solveur (1e-9 sur le résidu)
    assert y[top1] == pytest.approx(f * (P - N), rel=1e-7)
    assert y[top2] == pytest.approx(-f * N, rel=1e-7)          # la paroi d'en face est poussée vers sa terre
    forces = lien.forces_nodales(eff, 2 * n)
    assert forces[top1] == pytest.approx(-N) and forces[top2] == pytest.approx(-N)
    p, _ = r.pressions(y)
    f_sol = np.bincount(r.noeud, weights=-r.s * r.A * p, minlength=2 * n)
    assert f_sol[:n].sum() + P - N == pytest.approx(0.0, abs=1e-6 * P)   # équilibre de chaque poutre (résidu du solveur)
    assert f_sol[n:].sum() - N == pytest.approx(0.0, abs=1e-6 * P)


def test_lien_symetrique_equivaut_au_ressort_de_raideur_double():
    """Chargement identique des deux poutres : le lien k donne exactement le ressort vers le sol 2k
    (règle de la demi-longueur L/2 du buton symétrique), précharge comprise."""
    z, n, K, ddl_w, r = _deux_poutres()
    P, k = 50.0, 2000.0
    top1, top2 = n - 1, 2 * n - 1
    f_ext = np.zeros(4 * n)
    f_ext[2 * top1] = P
    f_ext[2 * top2] = P
    lien = Appuis(nom=["B"], noeud=np.array([top1]), k=np.array([k]), F0=np.array([5.0]), y_pose=np.zeros(1),
                  unilateral=np.array([True]), noeud2=np.array([top2]), y_pose2=np.zeros(1))
    sol = Appuis(nom=["B1", "B2"], noeud=np.array([top1, top2]), k=np.array([2 * k, 2 * k]), F0=np.array([5.0, 5.0]),
                 y_pose=np.zeros(2), unilateral=np.array([True, True]))
    u1, _, _ = resoudre_general(K, ddl_w, r, lien, f_ext)
    u2, _, _ = resoudre_general(K, ddl_w, r, sol, f_ext)
    np.testing.assert_allclose(u1, u2, rtol=1e-6, atol=1e-8 * np.abs(u1).max())
    assert lien.efforts(u1[ddl_w])[0][0] == pytest.approx(sol.efforts(u2[ddl_w])[0][0], rel=1e-8)


def test_lien_unilateral_decolle():
    """Forces opposées (les deux parois s'écartent) : le buton unilatéral ne travaille pas."""
    z, n, K, ddl_w, r = _deux_poutres()
    top1, top2 = n - 1, 2 * n - 1
    f_ext = np.zeros(4 * n)
    f_ext[2 * top1] = -50.0
    f_ext[2 * top2] = -50.0
    lien = Appuis(nom=["B"], noeud=np.array([top1]), k=np.array([2000.0]), F0=np.zeros(1), y_pose=np.zeros(1),
                  unilateral=np.array([True]), noeud2=np.array([top2]), y_pose2=np.zeros(1))
    u, _, _ = resoudre_general(K, ddl_w, r, lien, f_ext)
    eff, actif = lien.efforts(u[ddl_w])
    assert eff[0] == 0.0 and not actif[0]
    u0, _, _ = resoudre_general(K, ddl_w, r, Appuis(), f_ext)
    np.testing.assert_allclose(u, u0, rtol=1e-6, atol=1e-8 * np.abs(u0).max())
