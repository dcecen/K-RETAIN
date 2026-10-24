"""Poutre droite en résistance des matériaux (à la manière de RDM7) sur l'élément d'Hermite
du noyau : cas de référence des tests de validation et du rapport d'exemples élémentaires.

Ce que le moteur de production ne fait pas et qui est nécessaire pour des cas RDM exacts :
charges réparties **cohérentes** (déplacements et rotations exacts aux nœuds pour une charge
uniforme par élément), couples concentrés, encastrements et appuis simples par élimination,
ressorts de translation et de rotation, réactions. Les diagrammes M et V sont obtenus par la
statique (sout.noyau.poutre.efforts_par_statique) avec les réactions et les forces de ressorts.

Convention (CLAUDE.md) : axe z le long de la poutre (vers le haut pour un écran), y positif
vers la fouille, M = −EI·y'' positif quand la face côté fouille (+y) est tendue, V = dM/dz =
somme des charges situées au-dessus de la section, q = dV/dz. Pour une poutre horizontale
« RDM7 », lire z comme l'abscisse x et +y comme le sens des charges : une travée sur deux
appuis chargée dans le sens +y a M > 0 au milieu (fibre côté charges tendue), une console
chargée en bout a M < 0 à l'encastrement.

Sources : Przemieniecki J.S. (1968), *Theory of Matrix Structural Analysis* (élément de
poutre d'Hermite et charges nodales équivalentes qL/2, ±qL²/12) ; formulaires de RDM :
Timoshenko S., *Résistance des matériaux* ; Roark's *Formulas for Stress and Strain*, 7e éd.,
tableau 8.1.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import spsolve

from .poutre import assembler, efforts_par_statique, maillage


def charges_reparties_coherentes(z: np.ndarray, q_elem: np.ndarray) -> np.ndarray:
    """Vecteur de charges (2n) équivalent à une charge q uniforme par élément (kN/m, positive
    vers +y) : (qL/2, +qL²/12, qL/2, −qL²/12) sur (y₁, θ₁, y₂, θ₂) avec θ = dy/dz et z₂ > z₁
    (Przemieniecki 1968). Les déplacements et rotations nodaux de l'élément d'Hermite sont
    alors exacts pour une charge uniforme par élément."""
    L = np.diff(np.asarray(z, float))
    q = np.asarray(q_elem, float)
    f = np.zeros(2 * len(z))
    f[0:-2:2] += q * L / 2
    f[2::2] += q * L / 2
    f[1:-2:2] += q * L ** 2 / 12
    f[3::2] -= q * L ** 2 / 12
    return f


def charges_reparties_nodales(z: np.ndarray, q_elem: np.ndarray) -> np.ndarray:
    """Charges concentrées aux nœuds (qL/2 à chaque extrémité, sans couple) : c'est ce que fait
    le moteur de production pour le sol et l'eau ; l'erreur sur les déplacements est en O(h²)."""
    L = np.diff(np.asarray(z, float))
    q = np.asarray(q_elem, float)
    f = np.zeros(2 * len(z))
    f[0:-2:2] += q * L / 2
    f[2::2] += q * L / 2
    return f


@dataclass
class SolutionRDM:
    z: np.ndarray
    y: np.ndarray             # m
    theta: np.ndarray         # rad (dy/dz)
    z_diag: np.ndarray        # 2 points par élément
    M: np.ndarray             # kN·m
    V: np.ndarray             # kN
    reactions: dict           # nœud -> (force, couple) transmis à l'appui, positifs dans le sens +y
    forces_ressorts: np.ndarray   # kN par nœud, exercées par les ressorts sur la poutre
    couples_ressorts: np.ndarray  # kN·m par nœud
    controles: dict           # résidus de la statique (voir PoutreRDM.resoudre)


@dataclass
class PoutreRDM:
    """Poutre de longueur L (de z = 0 à z = L) et de rigidité EI, maillée au pas donné en passant
    par les cotes imposées (appuis, charges ponctuelles, bornes des charges réparties)."""
    L: float
    EI: float
    pas: float = 0.05
    cotes: list = field(default_factory=list)

    def __post_init__(self):
        self.z = maillage(list(self.cotes), 0.0, self.L, self.pas)
        n = len(self.z)
        self.EI_elem = np.full(n - 1, float(self.EI))
        self.q = np.zeros(n - 1)
        self.F = np.zeros(n)
        self.C = np.zeros(n)
        self.k_y = np.zeros(n)
        self.k_t = np.zeros(n)
        self.k_rep = 0.0                       # fondation de Winkler (kN/m par mètre), répartie
        self.t = np.zeros(n)                   # longueurs tributaires des nœuds
        self.t[1:] += 0.5 * np.diff(self.z)
        self.t[:-1] += 0.5 * np.diff(self.z)
        self.bloc_y: set[int] = set()
        self.bloc_t: set[int] = set()

    # --- géométrie
    def noeud(self, x: float) -> int:
        i = int(np.argmin(np.abs(self.z - x)))
        if abs(self.z[i] - x) > 1e-6:
            raise ValueError(f"aucun nœud en z = {x} : ajoutez-le aux cotes imposées")
        return i

    # --- appuis
    def appui_simple(self, x: float) -> PoutreRDM:
        self.bloc_y.add(self.noeud(x))
        return self

    def encastrement(self, x: float) -> PoutreRDM:
        i = self.noeud(x)
        self.bloc_y.add(i)
        self.bloc_t.add(i)
        return self

    def ressort(self, x: float, k_y: float = 0.0, k_theta: float = 0.0) -> PoutreRDM:
        i = self.noeud(x)
        self.k_y[i] += k_y
        self.k_t[i] += k_theta
        return self

    def ressorts_repartis(self, k: float) -> PoutreRDM:
        """Fondation de Winkler k (kN/m par mètre) : raideur concentrée aux nœuds au prorata des
        longueurs tributaires dans le système résolu, et réaction répartie sur ces longueurs dans la
        statique (comme les ressorts de sol du moteur : V nul aux extrémités libres)."""
        self.k_rep += k
        self.k_y += k * self.t
        return self

    # --- charges
    def force(self, x: float, P: float) -> PoutreRDM:
        self.F[self.noeud(x)] += P
        return self

    def couple(self, x: float, C: float) -> PoutreRDM:
        self.C[self.noeud(x)] += C
        return self

    def repartie(self, x1: float, x2: float, q: float) -> PoutreRDM:
        zm = 0.5 * (self.z[1:] + self.z[:-1])
        self.q[(zm > x1) & (zm < x2)] += q
        return self

    def repartie_lineaire(self, x1: float, x2: float, q1: float, q2: float) -> PoutreRDM:
        """Charge variant linéairement de q1 (en x1) à q2 (en x2), prise uniforme par élément à la
        valeur du milieu de l'élément (erreur en O(h²))."""
        zm = 0.5 * (self.z[1:] + self.z[:-1])
        sel = (zm > x1) & (zm < x2)
        self.q[sel] += q1 + (q2 - q1) * (zm[sel] - x1) / (x2 - x1)
        return self

    # --- résolution
    def resoudre(self, coherentes: bool = True) -> SolutionRDM:
        z, n = self.z, len(self.z)
        K = assembler(z, self.EI_elem)
        kd = np.zeros(2 * n)
        kd[0::2], kd[1::2] = self.k_y, self.k_t
        Kt = (K + sparse.diags(kd)).tocsc()
        f = (charges_reparties_coherentes if coherentes else charges_reparties_nodales)(z, self.q)
        f[0::2] += self.F
        f[1::2] += self.C
        bloques = sorted({2 * i for i in self.bloc_y} | {2 * i + 1 for i in self.bloc_t})
        libres = np.array([d for d in range(2 * n) if d not in set(bloques)])
        u = np.zeros(2 * n)
        if len(libres):
            u[libres] = spsolve(Kt[libres][:, libres], f[libres])
        r = Kt @ u - f                       # forces exercées par les blocages sur la poutre (DDL bloqués)
        y, theta = u[0::2], u[1::2]
        f_res, c_res = -self.k_y * y, -self.k_t * theta
        reactions = {}
        for i in sorted(self.bloc_y | self.bloc_t):
            reactions[i] = (-r[2 * i] if i in self.bloc_y else 0.0, -r[2 * i + 1] if i in self.bloc_t else 0.0)
        # Statique : ressorts ponctuels et réactions concentrés aux nœuds ; fondation de Winkler
        # répartie sur les bandes tributaires (charge uniforme par élément −k·(y_e + y_e+1)/2)
        f_point = -(self.k_y - self.k_rep * self.t) * y
        q_stat = self.q - self.k_rep * 0.5 * (y[:-1] + y[1:])
        forces = self.F + f_point + np.where([i in self.bloc_y for i in range(n)], r[0::2], 0.0)
        couples = self.C + c_res + np.where([i in self.bloc_t for i in range(n)], r[1::2], 0.0)
        tous = np.arange(n)
        z_diag, M, V = efforts_par_statique(z, z[:-1], z[1:], q_stat, tous, forces, tous, couples)
        # Contrôles de statique : équilibre global du système nodal résolu (identités exactes),
        # V = dM/dz et q = dV/dz élément par élément sur les diagrammes
        Le = np.diff(z)
        f_nod = self.F + f_res + np.where([i in self.bloc_y for i in range(n)], r[0::2], 0.0)
        residu_F = float(f_nod.sum() + (self.q * Le).sum())
        residu_M = float((f_nod * z).sum() + couples.sum() + (self.q * Le * 0.5 * (z[1:] + z[:-1])).sum())
        dM = (M[1::2] - M[0::2]) / Le - 0.5 * (V[0::2] + V[1::2])
        dV = (V[1::2] - V[0::2]) / Le + q_stat
        # échelle : charges brutes (pas la charge nette, qui peut être nulle : Winkler sous charge uniforme)
        echelle_F = max(float(np.abs(self.F).sum() + np.abs(self.q * Le).sum() + np.abs(self.k_y * y).sum()
                              + sum(abs(v[0]) for v in reactions.values())), 1e-12)
        controles = {
            "residu_forces": residu_F / echelle_F,
            "residu_moments": residu_M / (echelle_F * max(self.L, 1e-12)),
            "V_egale_dM_dz": float(np.abs(dM).max()) / max(float(np.abs(V).max()), 1e-12),
            "q_egale_dV_dz": float(np.abs(dV).max()) / max(float(np.abs(q_stat).max()), float(np.abs(V).max()) / self.L, 1e-12),
        }
        controles["echelle_forces"] = echelle_F
        return SolutionRDM(z, y, theta, z_diag, M, V, reactions, f_res, c_res, controles)
