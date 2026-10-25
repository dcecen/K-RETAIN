"""Résolution non linéaire d'une phase : poutre + ressorts élasto-plastiques + appuis.

Équation d'équilibre : K_poutre·u − f_sol(u) − f_appuis(u) − f_ext = 0.
La loi des ressorts étant linéaire par morceaux et monotone, on utilise une
méthode de Newton semi-lisse (raideur tangente : kh sur les ressorts
élastiques, 0 sur les ressorts plastifiés) avec recherche linéaire sur la
norme du résidu. Une fois les statuts stabilisés, la solution est exacte.

Si aucun équilibre n'existe (butée insuffisante, mécanisme), les
déplacements divergent : le calcul est déclaré en rupture.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import spsolve

from .poutre import assembler, efforts_internes
from .ressorts import Ressorts


@dataclass
class Appuis:
    """Appuis ponctuels (par mètre linéaire d'écran).

    Ressort vers le sol : effort = F0 + k·(y − y_pose) ; force sur l'écran = −effort.
    Lien entre deux nœuds (buton entre deux parois en vis-à-vis, noeud2 ≥ 0) :
    effort = F0 + k·[(y₁ − y_pose) + (y₂ − y_pose2)] — chaque paroi qui avance vers la
    fouille raccourcit le buton — avec k = EA/L sur la longueur **entière** ; la force
    −effort s'applique aux deux nœuds (action = réaction). Pour deux parois symétriques
    (y₁ = y₂), le lien équivaut au ressort vers le sol de raideur 2k, soit la règle L/2.
    Effort positif = appui qui retient l'écran côté fouille (buton comprimé,
    tirant tendu). Un appui unilatéral ne travaille pas en effort négatif.
    """

    nom: list[str] = field(default_factory=list)
    noeud: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=int))
    k: np.ndarray = field(default_factory=lambda: np.zeros(0))       # kN/m/m
    F0: np.ndarray = field(default_factory=lambda: np.zeros(0))      # kN/m
    y_pose: np.ndarray = field(default_factory=lambda: np.zeros(0))  # m
    unilateral: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=bool))
    noeud2: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=int))   # −1 : ressort vers le sol
    y_pose2: np.ndarray = field(default_factory=lambda: np.zeros(0))

    def __post_init__(self):
        n = len(self.nom)
        if len(self.noeud2) != n:
            self.noeud2 = np.full(n, -1, dtype=int)
        if len(self.y_pose2) != n:
            self.y_pose2 = np.zeros(n)

    def __len__(self) -> int:
        return len(self.nom)

    @property
    def liens(self) -> np.ndarray:
        return self.noeud2 >= 0

    def efforts(self, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        d = y[self.noeud] - self.y_pose
        lien = self.liens
        if lien.any():
            d = d + np.where(lien, y[np.where(lien, self.noeud2, 0)] - self.y_pose2, 0.0)
        eff = self.F0 + self.k * d
        actif = ~(self.unilateral & (eff < 0.0))
        return np.where(actif, eff, 0.0), actif

    def forces_nodales(self, eff: np.ndarray, n: int) -> np.ndarray:
        """Force exercée sur l'écran par nœud (kN par mètre, positive vers la fouille) : −effort
        au nœud porteur et, pour un lien, au second nœud."""
        f = -np.bincount(self.noeud, weights=eff, minlength=n)
        lien = self.liens
        if lien.any():
            f = f - np.bincount(self.noeud2[lien], weights=eff[lien], minlength=n)
        return f


class RuptureEquilibre(Exception):
    """Aucun équilibre trouvé : mécanisme de rupture ou divergence."""


def _recherche_lineaire(derivee, a_max: float = 1024.0) -> float:
    """Pas α minimisant l'énergie potentielle le long de la direction de Newton.

    Le problème est convexe (lois de ressort monotones) : l'énergie le long de
    la direction est convexe, de dérivée φ'(α) = R(u + α·du)·du croissante et
    linéaire par morceaux. On cherche φ'(α) = 0 par sécante encadrée.
    """
    d0 = derivee(0.0)
    if d0 >= 0.0:
        return 1.0  # direction non descendante (bruit numérique) : pas de Newton
    a_haut, d_haut = 1.0, derivee(1.0)
    a_bas, d_bas = 0.0, d0
    while d_haut < 0.0 and a_haut < a_max:
        a_bas, d_bas = a_haut, d_haut
        a_haut *= 2.0
        d_haut = derivee(a_haut)
    if d_haut < 0.0:
        return a_haut
    if abs(d_haut) <= 1e-12 * abs(d0):
        return a_haut
    for _ in range(60):
        a = a_bas - d_bas * (a_haut - a_bas) / (d_haut - d_bas)
        # garde-fou : rester strictement dans l'intervalle
        if not (a_bas < a < a_haut):
            a = 0.5 * (a_bas + a_haut)
        d = derivee(a)
        if abs(d) <= 1e-12 * abs(d0) or (a_haut - a_bas) <= 1e-12 * a_haut:
            return a
        if d < 0.0:
            a_bas, d_bas = a, d
        else:
            a_haut, d_haut = a, d
    return 0.5 * (a_bas + a_haut)


@dataclass
class SolutionPhase:
    z: np.ndarray
    u: np.ndarray            # vecteur (y0, θ0, y1, θ1, ...)
    y: np.ndarray            # m
    z_diag: np.ndarray       # 2 points par élément
    M: np.ndarray            # kN·m/m
    V: np.ndarray            # kN/m
    p: np.ndarray            # kPa, pression de chaque ressort
    statut: np.ndarray       # −1 / 0 / +1
    efforts_appuis: np.ndarray  # kN/m
    appuis_actifs: np.ndarray
    iterations: int
    residu: float


def resoudre_general(
    K: sparse.spmatrix,
    ddl_w: np.ndarray,
    ressorts: Ressorts,
    appuis: Appuis,
    f_ext: np.ndarray,
    u0: np.ndarray | None = None,
    max_iter: int = 200,
    y_rupture: float = 5.0,
) -> tuple[np.ndarray, int, float]:
    """Équilibre K·u − f_sol(u) − f_appuis(u) − f_ext = 0 pour une structure quelconque.

    K : rigidité de la structure (N × N, creuse) ; ddl_w : indice du degré de liberté
    transversal de chaque nœud (les ressorts et les appuis désignent des nœuds).
    Renvoie (u, itérations, résidu).
    """
    N = K.shape[0]
    n = len(ddl_w)
    Kb = sparse.csc_matrix(K)
    u = np.zeros(N) if u0 is None else u0.astype(float).copy()
    ddl_y = np.asarray(ddl_w)
    p_init, _ = ressorts.pressions(u[ddl_y])
    echelle = max(1.0, float(np.abs(f_ext).max(initial=0.0)),
                  float(np.abs(ressorts.A * p_init).max(initial=0.0)),
                  float(np.abs(appuis.F0).max(initial=0.0)))
    tol = 1e-9 * echelle
    # Régularisation des seuls modes de corps rigide (tous ressorts plastifiés) :
    # petite devant la raideur du sol pour ne pas fausser la direction de Newton.
    reg = 1e-9 * max(1.0, float((ressorts.A * ressorts.kh).max(initial=0.0)),
                     float(appuis.k.max(initial=0.0)))
    diag = Kb.diagonal()

    lien = appuis.liens if len(appuis) else np.zeros(0, dtype=bool)

    def residu_et_tangente(u_: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        y = u_[ddl_y]
        f_sol, k_sol = ressorts.forces_et_raideurs(y, n)
        eff, actif = appuis.efforts(y)
        f_app = appuis.forces_nodales(eff, n) if len(appuis) else np.zeros(n)
        ka = np.where(actif, appuis.k, 0.0) if len(appuis) else np.zeros(0)
        k_app = np.bincount(appuis.noeud, weights=ka, minlength=n) if len(appuis) else np.zeros(n)
        if lien.any():
            k_app = k_app + np.bincount(appuis.noeud2[lien], weights=ka[lien], minlength=n)
        f_int = np.zeros(N)
        f_int[ddl_y] = f_sol + f_app
        R = Kb @ u_ - f_int - f_ext
        return R, k_sol + k_app, ka

    def couplages(ka: np.ndarray) -> sparse.csc_matrix | None:
        """Termes hors diagonale des liens entre deux nœuds (k sur (n₁, n₂) et (n₂, n₁))."""
        if not lien.any():
            return None
        i1, i2, kv = ddl_y[appuis.noeud[lien]], ddl_y[appuis.noeud2[lien]], ka[lien]
        return sparse.csc_matrix((np.concatenate([kv, kv]), (np.concatenate([i1, i2]), np.concatenate([i2, i1]))), shape=(N, N))

    def statuts(u_: np.ndarray) -> np.ndarray:
        y = u_[ddl_y]
        return np.concatenate([ressorts.pressions(y)[1], appuis.efforts(y)[1].astype(int)])

    R, kt, ka = residu_et_tangente(u)
    nR = np.abs(R).max()
    st = statuts(u)
    it = 0
    pas_negligeable = False
    tol_it = tol
    for it in range(1, max_iter + 1):   # noqa: B007 (it est renvoyé après la boucle)
        # Tolérance : forces en jeu + bruit d'arrondi du produit K·u, estimé par max|K_ii·u_i|
        # (pour un degré de liberté pénalisé — bord, angle du pseudo-3D — c'est la réaction
        # physique, et non la pénalité multipliée par un déplacement quelconque).
        tol_it = tol + 1e-13 * max(float(np.abs(diag * u).max()), 1e-6)
        if nR < tol_it or pas_negligeable:
            break
        J = Kb + sparse.csc_matrix((kt + reg, (ddl_y, ddl_y)), shape=(N, N))
        C = couplages(ka)
        if C is not None:
            J = J + C
        du = spsolve(J, -R)
        if not np.all(np.isfinite(du)):
            raise RuptureEquilibre("système singulier : aucun équilibre (mécanisme)")
        alpha = _recherche_lineaire(lambda a: float(residu_et_tangente(u + a * du)[0] @ du))   # noqa: B023 (utilisée dans l'itération)
        u_new = u + alpha * du
        R_new, kt_new, ka = residu_et_tangente(u_new)
        n_new = np.abs(R_new).max()
        u, R, kt, nR = u_new, R_new, kt_new, n_new
        if np.abs(u[ddl_y]).max() > y_rupture:
            raise RuptureEquilibre(
                f"déplacement supérieur à {y_rupture} m : butée ou appuis insuffisants (rupture)"
            )
        st_new = statuts(u)
        # Statuts stabilisés et pas complet négligeable : le système linéaire
        # par morceaux est résolu au bruit d'arrondi près.
        pas_negligeable = (alpha == 1.0 and np.array_equal(st, st_new)
                           and np.abs(du).max() <= 1e-10 * max(float(np.abs(u).max()), 1e-6))
        st = st_new
    else:
        # même tolérance que dans la boucle (tol + bruit d'arrondi) : un résidu accepté en cours
        # d'itération ne doit pas être refusé à la sortie
        if nR >= tol_it and not pas_negligeable:
            raise RuptureEquilibre(f"non-convergence après {max_iter} itérations (résidu {nR:.3e} kN)")
    return u, it, float(nR)


def resoudre(
    z: np.ndarray,
    EI_elem: np.ndarray,
    ressorts: Ressorts,
    appuis: Appuis,
    f_ext: np.ndarray,
    u0: np.ndarray | None = None,
    max_iter: int = 200,
    y_rupture: float = 5.0,
    k_noeuds: np.ndarray | None = None,
) -> SolutionPhase:
    """Résout l'équilibre d'une phase de l'écran 2D (poutre).

    f_ext : vecteur 2n des forces imposées (eau, forces nodales), kN/m et kN·m/m.
    y_rupture : déplacement (m) au-delà duquel on déclare la rupture.
    k_noeuds : raideurs linéaires supplémentaires sur le déplacement de chaque nœud (kN/m par m d'écran),
               par exemple l'anneau comprimé d'une paroi circulaire (sout.parois.anneau) ; force = −k·y.
    """
    n = len(z)
    ddl_y = np.arange(0, 2 * n, 2)
    K = assembler(z, EI_elem)
    if k_noeuds is not None:
        diag = np.zeros(2 * n)
        diag[ddl_y] = k_noeuds
        K = K + sparse.diags(diag)
    u, it, nR = resoudre_general(K, ddl_y, ressorts, appuis, f_ext, u0, max_iter, y_rupture)
    y = u[ddl_y]
    p, statut = ressorts.pressions(y)
    eff, actif = appuis.efforts(y)
    zd, M, V = efforts_internes(z, EI_elem, u)
    return SolutionPhase(z=z, u=u, y=y, z_diag=zd, M=M, V=V, p=p, statut=statut,
                         efforts_appuis=eff, appuis_actifs=actif, iterations=it, residu=nR)
