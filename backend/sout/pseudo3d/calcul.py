"""Calcul pseudo-3D phasé : paroi en plaque (grillage) sur ressorts élasto-plastiques.

Le sol reste en ressorts, avec exactement la même loi et le même phasage que le
calcul 2D (sout.noyau.phasage) : chaque ligne verticale du grillage porte les
ressorts de la section 2D, multipliés par sa largeur tributaire, avec sa propre
mémoire d'état. Les appuis deviennent ponctuels, répartis à leur espacement le
long de la paroi (raideur et précharge 2D × espacement).

Conditions aux extrémités : libres, appuyées (w = 0 et rotation le long du bord
nulle) ou encastrées (w = 0, les deux rotations nulles).
Angle de fouille au milieu de la paroi : les deux parois se tiennent mutuellement
dans leur plan, d'où w = 0 sur la ligne d'angle (parois supposées indéformables
dans leur plan). Seule la présence d'un angle compte : sa valeur n'intervient pas,
et la continuité du ferraillage d'angle (encastrement partiel) est négligée.

Fouille fermée (contour du bloc `plan`) : la plaque parcourt tout le périmètre, le
maillage passe par les sommets (w = 0 à chaque angle), et les butons sont des liens
entre les deux parois en vis-à-vis (raideur EA/L sur la longueur entière, action =
réaction, voir sout.noyau.solveur.Appuis) : les deux écrans interagissent au lieu
d'être calculés chacun comme une paroi infinie (« double écran »). Positions des
butons : bloc plan.appuis, sinon placement automatique depuis le plus long côté
vers le côté d'en face (sout.plan.geometrie.placer_appuis). Tirants et bracons
restent des ressorts vers le sol ; une dalle relie chaque nœud au nœud d'en face.
Même sol et mêmes phases sur tous les côtés.

Efforts restitués par phase : déplacement W, moments Mz (vertical) et Ms (horizontal)
du grillage, torsion Mzs, effort tranchant V par la statique de chaque ligne verticale
(charges du sol, de l'eau, des appuis et forces de transfert de la plaque, voir
plaque.efforts_lignes), réactions des lignes pénalisées (bords, angle) et bilan
d'équilibre global.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import sparse

from ..noyau.modele import Modele, Phase
from ..noyau.phasage import ErreurModele, MoteurPhases
from ..noyau.ressorts import Ressorts
from ..noyau.solveur import Appuis, RuptureEquilibre, resoudre_general
from ..sol.terrain import CoupeCalcul, SurchargePlan
from . import plaque


@dataclass
class PhasePseudo3D:
    nom: str
    ok: bool
    message: str
    W: np.ndarray = field(default_factory=lambda: np.zeros((0, 0)))    # m, (ns, nz)
    Mz: np.ndarray = field(default_factory=lambda: np.zeros((0, 0)))   # kN·m/m
    Ms: np.ndarray = field(default_factory=lambda: np.zeros((0, 0)))   # kN·m/m
    appuis: list = field(default_factory=list)  # [{"nom", "s", "effort", "actif", "espacement", "angle"}] kN par appui
    V: np.ndarray = field(default_factory=lambda: np.zeros((0, 0)))    # kN/m aux nœuds (ns, nz)
    V_diag: np.ndarray = field(default_factory=lambda: np.zeros((0, 0)))   # kN/m, 2 points par élément
    M_stat: np.ndarray = field(default_factory=lambda: np.zeros((0, 0)))   # kN·m/m par la statique, 2 points par élément
    z_diag: np.ndarray = field(default_factory=lambda: np.zeros(0))
    Mzs: np.ndarray = field(default_factory=lambda: np.zeros((0, 0)))  # kN·m/m, torsion
    p: np.ndarray = field(default_factory=lambda: np.zeros(0))         # kPa, pression de chaque ressort
    reactions: np.ndarray = field(default_factory=lambda: np.zeros((0, 0)))  # kN par nœud pénalisé (bords, angle), positif = retient
    forces: dict = field(default_factory=dict)   # {"sol", "eau", "appuis", "reactions"} : kN par nœud (ns, nz), positifs vers la fouille
    bilan: dict = field(default_factory=dict)    # sommes (kN) et moments résiduels (kN·m)
    liernes: dict = field(default_factory=dict)  # nom -> {"cote", "EI", "M" (ns,) kN·m, "V" (ns,) kN} : poutre horizontale réelle


@dataclass
class ResultatPseudo3D:
    s: np.ndarray
    z: np.ndarray
    phases: list[PhasePseudo3D]
    avertissements: list[str]
    sommets: list = field(default_factory=list)   # abscisses s des angles (sommets du contour ou angle)
    fermee: bool = False
    longueur: float = 0.0                         # longueur développée (périmètre si fermée)
    appuis_repartis: bool = False                 # largeur_appui donnée (Ms et V au droit des appuis convergés)

    @property
    def complet(self) -> bool:
        return bool(self.phases) and all(ph.ok for ph in self.phases)


class MoteurPseudo3D:
    def __init__(self, modele: Modele, longueur: float | None, pas_horizontal: float = 0.5, bords: str = "libres",
                 angle: float | None = None, rigidite_horizontale: float | None = None,
                 largeur_appui: float | None = None, rapport_rigidite_horizontale: float | None = None,
                 torsion: float | None = None, longueur_panneau: float | None = None,
                 origine_panneaux: float = 0.0, contour: list | None = None, plan_appuis: list | None = None,
                 liens: bool = True, cotes_plan: dict | None = None):
        self.m = modele
        self.largeur_appui = largeur_appui
        self.cotes_plan = dict(cotes_plan or {})
        self.m2 = MoteurPhases(modele)
        self.z = self.m2.z
        nz = len(self.z)
        self.avertissements = list(self.m2.avertissements)
        self.aretes = None
        self.liens = liens
        self.plan_appuis = plan_appuis
        if contour is not None:
            # Fouille fermée : abscisse développée le long du périmètre, maillage passant par les sommets
            from ..plan.geometrie import aretes
            self.aretes = aretes(contour)
            longueur = sum(a["L"] for a in self.aretes)
            s_list = [0.0]
            for a in self.aretes:
                n_e = max(1, int(round(a["L"] / pas_horizontal)))
                s_list.extend((a["s0"] + a["L"] * np.arange(1, n_e + 1) / n_e).tolist())
            self.s = np.array(s_list[:-1])            # le dernier nœud (s = périmètre) est le premier : boucle fermée
            self.fermeture = float(longueur - self.s[-1])   # élément horizontal qui referme la boucle
            self.i_sommets = [int(np.argmin(np.abs(self.s - a["s0"]))) for a in self.aretes]
            if bords != "libres":
                self.avertissements.append("Pseudo-3D : fouille fermée, la clé bords est sans objet (w = 0 à chaque sommet).")
            if angle is not None:
                self.avertissements.append("Pseudo-3D : fouille fermée, la clé angle est sans objet (angles aux sommets du contour).")
            angle = None
            self.avertissements.append(
                f"Pseudo-3D : fouille fermée de périmètre {longueur:.1f} m à {len(self.aretes)} sommets (w = 0 aux angles) ; "
                + ("butons reliant les parois en vis-à-vis (raideur EA/L sur la longueur entière, action = réaction)."
                   if liens else "butons traités comme des ressorts vers le sol (règle L/2)."))
        elif longueur is None:
            raise ErreurModele("pseudo3d : donnez longueur (paroi droite) ou un bloc plan avec contour (fouille fermée)")
        else:
            ns = max(3, int(round(longueur / pas_horizontal)) + 1)
            self.s = np.linspace(0.0, longueur, ns)
            self.i_sommets = []
            self.fermeture = None
        ns = len(self.s)
        self.ns, self.nz = ns, nz
        self.longueur = float(longueur)
        self.nh = ns if self.fermeture is not None else ns - 1   # éléments horizontaux
        # Surcharges localisées en plan : une coupe de calcul par ligne verticale (position sur le contour,
        # normale vers la fouille, côté nommé), état du sol calculé ligne par ligne si une surcharge en plan existe
        self.coupes_lignes: list[CoupeCalcul] | None = None
        self.sol_par_ligne = False
        if self.aretes is not None:
            from ..plan.geometrie import point
            noms_cotes = {k: n for n, k in self.cotes_plan.items()}
            self.coupes_lignes = []
            for s_i in self.s:
                x, y, k, sl = point(self.aretes, float(s_i))
                a = self.aretes[k]
                self.coupes_lignes.append(CoupeCalcul(x=x, y=y, ni=tuple(a["ni"]), t=tuple(a["t"]), k=k, s=sl,
                                                      cote=noms_cotes.get(k), nom=f"ligne s = {s_i:.2f} m"))
            toutes = list(modele.surcharges) + [sc for ph in modele.phases for sc in ph.ajouter_surcharges]
            self.sol_par_ligne = any(isinstance(sc, SurchargePlan) for sc in toutes)
            if self.sol_par_ligne:
                self.avertissements.append(
                    "Pseudo-3D : surcharges en plan rapportées à chaque ligne verticale de la paroi (diffusion élastique "
                    "depuis sa position sur le contour) : le chargement varie le long de la paroi.")
        self.Dz = self.m2.EI_elem
        # Rigidité horizontale : valeur du script > rapport du script > défaut du type de paroi
        # (sout.parois.construction.rigidite_horizontale) > isotropie avec avertissement.
        defaut = modele.ecran.infos.get("rigidite_horizontale") or {}
        if rigidite_horizontale is not None:
            self.Ds = np.full_like(self.Dz, float(rigidite_horizontale))
            source = f"Ds = {rigidite_horizontale:g} kN·m²/m imposé par le script"
        elif rapport_rigidite_horizontale is not None:
            self.Ds = float(rapport_rigidite_horizontale) * self.Dz
            source = f"Ds = {rapport_rigidite_horizontale:g}·Dz imposé par le script"
        elif defaut.get("rapport") is not None:
            self.Ds = float(defaut["rapport"]) * self.Dz
            source = f"Ds = {defaut['rapport']:g}·Dz, {defaut['source']}"
            if defaut.get("avertissement"):
                self.avertissements.append(defaut["avertissement"])
        else:
            self.Ds = self.Dz.copy()
            source = "Ds = Dz, plaque isotrope par défaut"
            self.avertissements.append(
                "Pseudo-3D : rigidité horizontale non donnée, plaque isotrope (Ds = Dz). Pour des palplanches, "
                "des pieux disjoints ou une paroi moulée à joints, donnez pseudo3d.rigidite_horizontale.")
        if 0.0 < float(self.Ds.max()) < 1e-6 * float(self.Dz.max()):
            self.avertissements.append(
                "Pseudo-3D : rigidité horizontale inférieure à 1e-6·Dz, arrondie à 0 (conditionnement numérique).")
            self.Ds = np.zeros_like(self.Dz)
        self.Ds_nulle = bool(float(self.Ds.max()) <= 0.0)
        self.GJ = np.sqrt(self.Ds * self.Dz) if torsion is None else np.full_like(self.Dz, float(torsion))
        self.avertissements.append(
            f"Pseudo-3D : rigidité horizontale {source} ; torsion GJ = "
            + ("√(Ds·Dz) (plaque de Huber, ν = 0)" if torsion is None else f"{torsion:g} kN·m²/m imposée") + ".")
        # Joints de panneaux : aucun moment ni torsion horizontaux à travers l'élément qui porte le joint
        self.coef_h = None
        self.joints: list[float] = []
        if longueur_panneau is not None and longueur_panneau < longueur - 1e-9:
            if longueur_panneau < 2 * pas_horizontal:
                raise ErreurModele(f"pseudo3d : longueur_panneau ({longueur_panneau} m) doit valoir au moins deux fois "
                                   f"pas_horizontal ({pas_horizontal} m)")
            x = float(origine_panneaux)
            while x < longueur - 1e-9:
                if x > 1e-9:
                    self.joints.append(x)
                x += longueur_panneau
            self.coef_h = np.ones((self.nh, nz))
            for x in self.joints:
                i = min(int(np.searchsorted(self.s, x + 1e-9) - 1), self.nh - 1)
                self.coef_h[max(i, 0), :] = 0.0
            self.avertissements.append(
                f"Pseudo-3D : joints de panneaux en s = {', '.join(f'{x:g}' for x in self.joints)} m : "
                "aucun moment horizontal ni torsion transmis (panneaux indépendants en flexion horizontale).")
        # Liernes : poutres horizontales réelles (E·Iy, kN·m²) ajoutées aux éléments horizontaux de la
        # rangée de leur appui, présentes tant que l'appui est posé (sout.appuis.construction.rigidite_lierne)
        self.liernes: dict[str, tuple[int, float]] = {}
        for nom, d in modele.appuis.items():
            if "EI_lierne" not in d.infos:
                continue
            if d.infos.get("EI_lierne") is None:
                self.avertissements.append(f"Pseudo-3D : lierne non modélisée ({d.infos.get('lierne_motif')}).")
                continue
            j = int(np.argmin(np.abs(self.z - d.cote)))
            self.liernes[nom] = (j, float(d.infos["EI_lierne"]))
            self.avertissements.append(
                f"Pseudo-3D : lierne de l'appui {nom} modélisée comme poutre horizontale continue "
                f"(E·I = {d.infos['EI_lierne']:.3g} kN·m², flexion autour de l'axe fort, torsion négligée).")
        K = plaque.assembler(self.s, self.z, self.Dz, self.Ds, coef_h=self.coef_h, GJ_elem=self.GJ,
                             fermeture=self.fermeture)
        # Grillage réduit à la flexion verticale (forces de transfert, voir plaque.forces_transfert)
        self.K_v = plaque.assembler(self.s, self.z, self.Dz, np.zeros_like(self.Ds), GJ_elem=np.zeros_like(self.Dz),
                                    fermeture=self.fermeture)
        # Conditions aux limites par pénalité
        self.pen = 1e4 * float(K.diagonal().max())
        diag = np.zeros(K.shape[0])
        if self.Ds_nulle:
            # Sans flexion horizontale, θs n'est tenu que par la torsion des poutres verticales, qui
            # laisse libre la rotation d'ensemble de chaque ligne : θs est bloqué (bandes indépendantes).
            diag[2::3] = self.pen
        if bords in ("appuyes", "encastres"):
            for i in (0, ns - 1):
                for j in range(nz):
                    k = i * nz + j
                    diag[3 * k] = self.pen          # w = 0
                    diag[3 * k + 1] = self.pen      # θz = 0 : w nul tout le long du bord ⇒ pente tangente nulle
                    if bords == "encastres":
                        diag[3 * k + 2] = self.pen  # θs = 0 : rotation normale au bord bloquée
        self.i_angle = None
        if angle is not None and abs(angle - 180.0) > 1e-6:
            self.i_angle = int(np.argmin(np.abs(self.s - longueur / 2)))
        self.i_angles = sorted(set(self.i_sommets + ([self.i_angle] if self.i_angle is not None else [])))
        for i in self.i_angles:
            for j in range(nz):
                diag[3 * (i * nz + j)] = self.pen
        self.ddl_pen_w = np.flatnonzero(diag[0::3] > 0)   # nœuds dont w est pénalisé (réactions)
        self._diag_pen = diag                              # pénalités sans lierne posée
        self.K = (K + sparse.diags(diag)).tocsc()          # sans lierne
        self._K_liernes: dict[frozenset, sparse.csc_matrix] = {frozenset(): self.K}
        self.ddl_w = np.arange(0, 3 * ns * nz, 3)
        # Ressorts : les demi-mailles 2D de chaque ligne verticale
        r2 = self.m2.ressorts
        m2 = len(r2)
        self.ds = plaque.largeurs_tributaires(self.s, self.fermeture)
        self.ressorts = Ressorts(
            noeud=np.concatenate([i * nz + r2.noeud for i in range(ns)]),
            s=np.tile(r2.s, ns), A=np.zeros(ns * m2), kh=np.zeros(ns * m2),
            p_ref=np.zeros(ns * m2), y_ref=np.zeros(ns * m2), pa=np.zeros(ns * m2), pp=np.zeros(ns * m2),
        )
        self.largeur = np.repeat(self.ds, m2)
        self.m2_taille = m2
        if largeur_appui is None and modele.appuis:
            self.avertissements.append(
                "Pseudo-3D : chaque appui ponctuel agit sur un seul nœud ; le moment horizontal Ms et l'effort "
                "tranchant V à son droit dépendent du maillage (singularité d'une charge concentrée sur une plaque). "
                "Donnez pseudo3d.largeur_appui (plaque d'appui, semelle de lierne) pour le répartir.")

    def _noeuds_appui(self, sp: float) -> list[tuple[int, float]]:
        """Nœuds (indice i, part) portant un appui placé en s = sp : le plus proche, ou, avec
        largeur_appui, chaque nœud au prorata du recouvrement de sa bande tributaire
        [milieu avec le voisin de gauche, milieu avec le voisin de droite] par l'intervalle
        [sp − largeur/2, sp + largeur/2] (répartition uniforme exacte sur la largeur)."""
        if self.fermeture is not None and sp > self.s[-1] + 0.5 * self.fermeture:
            sp = sp - self.longueur                        # au-delà du dernier nœud : c'est le premier (boucle fermée)
        if self.largeur_appui is not None:
            bords = np.concatenate([[self.s[0]], 0.5 * (self.s[1:] + self.s[:-1]), [self.s[-1]]])
            lo, hi = sp - self.largeur_appui / 2, sp + self.largeur_appui / 2
            rec = np.clip(np.minimum(bords[1:], hi) - np.maximum(bords[:-1], lo), 0.0, None)
            if rec.sum() > 1e-12:
                sel = np.flatnonzero(rec > 1e-12)
                return [(int(i), float(rec[i] / rec.sum())) for i in sel]
        return [(int(np.argmin(np.abs(self.s - sp))), 1.0)]

    def _matrice(self, posees: frozenset) -> sparse.csc_matrix:
        """Rigidité du grillage avec les liernes des appuis posés (mise en cache par jeu posé)."""
        posees = frozenset(n for n in posees if n in self.liernes)
        if posees not in self._K_liernes:
            sup = np.zeros((self.nh, self.nz))
            diag = self._diag_pen.copy()
            for nom in posees:
                j, EI = self.liernes[nom]
                sup[:, j] += EI
                if self.Ds_nulle:
                    # la lierne tient la rotation θs de sa rangée : plus de pénalité (sinon elle ne fléchit pas)
                    diag[3 * (np.arange(self.ns) * self.nz + j) + 2] = 0.0
            K = plaque.assembler(self.s, self.z, self.Dz, self.Ds, EI_h_sup=sup, coef_h=self.coef_h, GJ_elem=self.GJ,
                                 fermeture=self.fermeture)
            self._K_liernes[posees] = (K + sparse.diags(diag)).tocsc()
        return self._K_liernes[posees]

    def _efforts_liernes(self, u: np.ndarray, posees) -> dict:
        """Moment (kN·m) et effort tranchant (kN) de chaque lierne posée le long de s : efforts
        d'extrémité des éléments de poutre E·I de la rangée (convention de Ms : positif face fouille
        tendue), moyennés aux nœuds."""
        ns, nz = self.ns, self.nz
        W = u[0::3].reshape(ns, nz)
        Ts = u[2::3].reshape(ns, nz)
        out = {}
        for nom in posees:
            if nom not in self.liernes:
                continue
            j, EI = self.liernes[nom]
            M = np.zeros(ns)
            V = np.zeros(ns)
            c = np.zeros(ns)
            for i in range(self.nh):
                i1 = (i + 1) % ns
                L = (self.s[i + 1] - self.s[i]) if i < ns - 1 else self.fermeture
                fe = plaque.rigidite_element(EI, L) @ np.array([W[i, j], Ts[i, j], W[i1, j], Ts[i1, j]])
                M[i] += fe[1]
                M[i1] += -fe[3]
                v = (-fe[3] - fe[1]) / L
                V[i] += v
                V[i1] += v
                c[i] += 1
                c[i1] += 1
            out[nom] = {"cote": float(self.z[j]), "EI": EI, "M": M / c, "V": V / c}
        return out

    def _positions_appui(self, espacement: float) -> np.ndarray:
        """Appuis réels à leur espacement exact, centrés sur la longueur modélisée (paroi droite)."""
        L = self.s[-1]
        nb = max(1, int(np.floor(L / espacement + 1e-9)))
        debut = (L - (nb - 1) * espacement) / 2
        return debut + espacement * np.arange(nb)

    def _placements(self, nom: str) -> list[tuple[float, float | None]]:
        """Positions (s_départ, s_arrivée ou None) de chaque appui réel d'un appui du script.
        Paroi droite : à l'espacement, sans vis-à-vis. Fouille fermée : segments du bloc plan.appuis
        projetés sur le contour (l'arrivée n'est un vis-à-vis que si elle tombe sur la paroi), sinon
        placement automatique (sout.plan.geometrie.placer_appuis) ; une dalle relie chaque nœud du
        côté le plus long à son vis-à-vis."""
        d = self.m.appuis[nom]
        e = d.infos.get("espacement", 1.0) or 1.0
        if self.aretes is None:
            return [(float(sp), None) for sp in self._positions_appui(e)]
        from ..plan.geometrie import placer_appuis, projeter, vis_a_vis
        if d.type == "dalle":
            ar = max(self.aretes, key=lambda a: a["L"])
            out = []
            for i in range(self.ns):
                if abs(self.s[i] - ar["s0"]) < 1e-9 or self.s[i] <= ar["s0"] + 1e-9 or self.s[i] >= ar["s0"] + ar["L"] - 1e-9:
                    continue
                v = vis_a_vis(self.aretes, ar["k"], self.s[i] - ar["s0"])
                if v is not None:
                    out.append((float(self.s[i]), float(v[0])))
            return out
        segments = [pa for pa in (self.plan_appuis or []) if pa.get("appui") == nom]
        if not segments:
            segments = [pa for pa in placer_appuis([a["A"] for a in self.aretes], {nom: dict(d.infos, type=d.type)})]
        out = []
        for seg in segments:
            s_de, _, _, d_de = projeter(self.aretes, *seg["de"])
            s_a, _, _, d_a = projeter(self.aretes, *seg["a"])
            if d_de > 0.5:
                self.avertissements.append(f"Pseudo-3D : appui {nom}, point de départ {seg['de']} à {d_de:.1f} m du contour, "
                                           "rapporté au point le plus proche.")
            vis = s_a if (d.type in ("buton", "dalle") and d_a <= 0.5) else None
            if vis is not None and not self.liens:
                out.append((float(s_de), None))       # règle L/2 : un ressort vers le sol à chaque extrémité
                out.append((float(vis), None))
            else:
                out.append((float(s_de), None if vis is None else float(vis)))
        return out

    # ------------------------------------------------------------------
    def _efforts_phase(self, u: np.ndarray, r: Ressorts, appuis: Appuis, f_ext: np.ndarray,
                       u_am: np.ndarray, u_av: np.ndarray, K: sparse.spmatrix | None = None) -> dict:
        """Champs d'efforts d'une phase résolue : moments du grillage, torsion, V par la statique
        de chaque ligne (plaque.efforts_lignes), réactions, forces nodales et bilan d'équilibre."""
        m2, ns, nz = self.m2, self.ns, self.nz
        W = u[0::3]
        Mz, Ms = plaque.moments(self.s, self.z, self.Dz, self.Ds, u, coef_h=self.coef_h, fermeture=self.fermeture)
        Mzs = plaque.torsion(self.s, self.z, self.Dz, self.Ds, u, GJ_elem=self.GJ)
        p, _ = r.pressions(W)
        nd, m2n = m2.nd, self.m2_taille
        A, P = r.A.reshape(ns, m2n), p.reshape(ns, m2n)
        # charge nette sol + eau de chaque demi-maille, par mètre de paroi (comme en 2D)
        q_lignes = (A[:, :nd] * P[:, :nd] - A[:, nd:] * P[:, nd:]) / (m2.d_L[None, :] * self.ds[:, None]) \
            + (u_am - u_av)[None, :]
        eff, _ = appuis.efforts(W)
        f_app = appuis.forces_nodales(eff, ns * nz) if len(appuis) else np.zeros(ns * nz)
        t_w, t_th = plaque.forces_transfert(self.K if K is None else K, self.K_v, u, ns, nz)
        z_diag, M_stat, V_diag = plaque.efforts_lignes(self.z, m2.d_zb, m2.d_zh, m2.d_noeud, q_lignes,
                                                       f_app.reshape(ns, nz), t_w, t_th, self.ds)
        V = np.empty((ns, nz))
        V[:, 0], V[:, -1] = V_diag[:, 0], V_diag[:, -1]
        V[:, 1:-1] = 0.5 * (V_diag[:, 1:-2:2] + V_diag[:, 2:-1:2])
        reactions = np.zeros(ns * nz)
        reactions[self.ddl_pen_w] = self.pen * W[self.ddl_pen_w]
        f_sol = np.bincount(r.noeud, weights=-r.s * r.A * p, minlength=ns * nz)
        f_eau = f_ext[0::3]
        forces = {"sol": f_sol.reshape(ns, nz), "eau": f_eau.reshape(ns, nz), "appuis": f_app.reshape(ns, nz),
                  "reactions": (-reactions).reshape(ns, nz)}
        total = f_sol + f_eau + f_app - reactions
        Z = np.tile(self.z - self.z[0], ns)
        S = np.repeat(self.s, nz)
        bilan = {"sol": float(f_sol.sum()), "eau": float(f_eau.sum()), "appuis": float(f_app.sum()),
                 "reactions": float(-reactions.sum()), "residu": float(total.sum()),
                 "moment_residu_z": float((total * Z).sum()), "moment_residu_s": float((total * S).sum()),
                 "echelle": float(np.abs(f_sol).sum() + np.abs(f_eau).sum() + np.abs(f_app).sum() + np.abs(reactions).sum())}
        return {"W": W.reshape(ns, nz), "Mz": Mz, "Ms": Ms, "Mzs": Mzs, "V": V, "V_diag": V_diag, "M_stat": M_stat,
                "z_diag": z_diag, "p": p, "reactions": reactions.reshape(ns, nz), "forces": forces, "bilan": bilan}

    def calculer(self) -> ResultatPseudo3D:
        m, m2 = self.m, self.m2
        ns, nz = self.ns, self.nz
        etat = m2.etat_chantier_initial()
        r = self.ressorts
        u = np.zeros(3 * ns * nz)
        sv_prec = np.zeros(ns * self.m2_taille)
        present_prec = np.zeros(ns * self.m2_taille, dtype=bool)
        poses: dict[str, list] = {}   # nom -> [(nœud, s, y_pose, k, F0)]
        f_ext_prec = np.zeros_like(u)  # forces imposées (eau) de la dernière phase calculée
        sorties: list[PhasePseudo3D] = []
        signales: set[str] = set()

        def _points(nom: str, W: np.ndarray, raideur: float, F0: float) -> list:
            """Nœuds porteurs d'un appui : (nœud, s, y_pose, k, F0, nœud2, y_pose2, s2) ; nœud2 = −1
            pour un ressort vers le sol. Un lien (buton entre deux parois) porte la raideur 2D de
            la longueur entière : la raideur du script vaut EA/(L/2) si l'appui est symétrique."""
            d = m.appuis[nom]
            e = d.infos.get("espacement", 1.0) or 1.0
            if d.type == "dalle" and self.aretes is not None:
                e = 1.0
            j = int(np.argmin(np.abs(self.z - d.cote)))
            pts = []
            for sp, s2 in self._placements(nom):
                de = self._noeuds_appui(sp)
                if d.type == "dalle" and self.aretes is not None:
                    i0 = int(np.argmin(np.abs(self.s - sp)))
                    de = [(i0, 1.0)]
                    e = float(self.ds[i0])
                for i, part in de:
                    if i in self.i_angles and nom not in signales:
                        signales.add(nom)
                        self.avertissements.append(
                            f"Pseudo-3D : un point de l'appui {nom} tombe sur une ligne d'angle (s = {self.s[i]:.1f} m), "
                            "où le déplacement est nul : il ne porte rien.")
                    k = i * nz + j
                    if s2 is None:
                        pts.append((k, float(sp), float(W[k]), raideur * e * part, F0 * e * part, -1, 0.0, None))
                        continue
                    kl = raideur * (0.5 if d.infos.get("symetrique", True) else 1.0)
                    for i2, part2 in self._noeuds_appui(s2):
                        k2 = i2 * nz + j
                        pts.append((k, float(sp), float(W[k]), kl * e * part * part2, F0 * e * part * part2,
                                    k2, float(W[k2]), float(s2)))
            return pts

        def _appuis(dico: dict[str, list]) -> tuple[Appuis, list]:
            noms, noeuds, ks, F0s, yps, unis, ss, n2, yp2 = [], [], [], [], [], [], [], [], []
            for nom, pts in dico.items():
                for (k, sp, yp, kk, F0, k2, y2, s2) in pts:
                    noms.append(nom); noeuds.append(k); ks.append(kk); F0s.append(F0); yps.append(yp)
                    unis.append(m.appuis[nom].unilateral); ss.append((sp, s2)); n2.append(k2); yp2.append(y2)
            return Appuis(nom=noms, noeud=np.array(noeuds, dtype=int), k=np.array(ks, float),
                          F0=np.array(F0s, float), y_pose=np.array(yps, float), unilateral=np.array(unis, bool),
                          noeud2=np.array(n2, dtype=int), y_pose2=np.array(yp2, float)), ss

        for ph in [Phase(nom="État initial")] + chaine_principale(m.phases):
            try:
                poser, deposer = m2.appliquer_actions(etat, ph)
            except ErreurModele as e:
                sorties.append(PhasePseudo3D(ph.nom, False, f"Erreur de données : {e}"))
                break
            for nom in deposer:
                poses.pop(nom, None)
            # Mise en charge au vérin des appuis précontraints (même règle que le 2D, voir
            # sout.noyau.phasage) : force F0 seule sur l'état précédent, puis ressort bloqué.
            a_verin = [nm for nm in poser if m.appuis[nm].precharge != 0.0]
            if a_verin:
                W = u[0::3]
                dico = dict(poses)
                for nm in a_verin:
                    dico[nm] = _points(nm, W, 0.0, m.appuis[nm].precharge)
                appuis_v, _ = _appuis(dico)
                K_ph = self._matrice(frozenset(dico))
                try:
                    u, _, _ = resoudre_general(K_ph, self.ddl_w, r, appuis_v, f_ext_prec, u0=u, y_rupture=m.y_rupture)
                except RuptureEquilibre as e:
                    sorties.append(PhasePseudo3D(ph.nom, False, f"Rupture à la mise en charge des appuis : {e}"))
                    break
                r.memoriser(u[0::3])
            W = u[0::3]
            for nom in poser:
                d = m.appuis[nom]
                poses[nom] = _points(nom, W, d.raideur, d.precharge)
            if self.sol_par_ligne:
                sols = [m2.etat_sol(etat, coupe=c) for c in self.coupes_lignes]
                sol3 = {c: (np.concatenate([x[c] for x in sols]) if isinstance(v, np.ndarray) else v) for c, v in sols[0].items()}
            else:
                sol = m2.etat_sol(etat)
                sol3 = {c: (np.tile(v, ns) if isinstance(v, np.ndarray) else v) for c, v in sol.items()}
            MoteurPhases.mettre_a_jour_ressorts(r, sol3, u[0::3][r.noeud], present_prec, sv_prec, self.largeur)
            u_am, u_av = m2.pressions_eau(etat)
            f_ligne = m2.force_eau_noeuds(u_am, u_av)
            f_ext = np.zeros_like(u)
            f_ext[0::3] = np.outer(self.ds, f_ligne).ravel()
            appuis, ss = _appuis(poses)
            noms = list(appuis.nom)
            K_ph = self._matrice(frozenset(poses))
            try:
                u, it, nR = resoudre_general(K_ph, self.ddl_w, r, appuis, f_ext, u0=u, y_rupture=m.y_rupture)
            except RuptureEquilibre as e:
                sorties.append(PhasePseudo3D(ph.nom, False, f"Rupture : {e}"))
                break
            W = u[0::3]
            champs = self._efforts_phase(u, r, appuis, f_ext, u_am, u_av, K_ph)
            champs["liernes"] = self._efforts_liernes(u, poses)
            r.memoriser(W)
            sv_prec, present_prec = sol3["sv"], sol3["present"]
            f_ext_prec = f_ext
            eff, actif = appuis.efforts(W)
            groupes: dict[tuple[str, float, float | None], list] = {}   # un appui réel = ses nœuds porteurs
            for nm, (sp, s2), ef, ac in zip(noms, ss, eff, actif):
                g = groupes.setdefault((nm, sp, s2), [0.0, False])
                g[0] += float(ef); g[1] = g[1] or bool(ac)
            sorties.append(PhasePseudo3D(
                ph.nom, True, "",
                appuis=[{"nom": nm, "s": sp, "s2": s2, "effort": g[0], "actif": g[1],
                         "espacement": float(m.appuis[nm].infos.get("espacement", 1.0) or 1.0),
                         "angle": float(m.appuis[nm].infos.get("angle", 0.0) or 0.0)}
                        for (nm, sp, s2), g in groupes.items()],
                **champs))
        return ResultatPseudo3D(self.s, self.z, sorties, self.avertissements,
                                sommets=[float(self.s[i]) for i in self.i_angles], fermee=self.aretes is not None,
                                longueur=self.longueur, appuis_repartis=self.largeur_appui is not None)


def chaine_principale(phases: list) -> list:
    """Phases de la branche menant à la dernière phase de la liste (le pseudo-3D est linéaire)."""
    noms = [p.nom for p in phases]
    chaine = []
    k = len(phases) - 1
    while k >= 0:
        chaine.append(phases[k])
        p = phases[k]
        k = noms.index(p.depuis) if (p.depuis is not None and p.depuis in noms[:k]) else k - 1
    return chaine[::-1]


def moteur_depuis_script(ex) -> MoteurPseudo3D:
    """Moteur pseudo-3D du script : fouille fermée sur le contour du bloc plan quand pseudo3d.longueur
    est absent, paroi droite de `longueur` sinon."""
    s = ex.script
    p = s.pseudo3d
    if p is None:
        raise ErreurModele("mode pseudo3d : bloc pseudo3d obligatoire (longueur pour une paroi droite, ou bloc plan)")
    contour = plan_appuis = None
    if p.longueur is None:
        if s.plan is None:
            raise ErreurModele("pseudo3d : donnez longueur (paroi droite) ou un bloc plan avec contour (fouille fermée)")
        contour = s.plan.contour
        plan_appuis = [a.model_dump() for a in s.plan.appuis] or None
    mo = MoteurPseudo3D(ex.modele, p.longueur, p.pas_horizontal, p.bords, p.angle, p.rigidite_horizontale,
                        p.largeur_appui, p.rapport_rigidite_horizontale, p.torsion,
                        s.paroi.longueur_panneau, s.paroi.origine_panneaux, contour, plan_appuis,
                        cotes_plan=s.plan.cotes if s.plan is not None else None)
    if p.longueur is not None and s.plan is not None:
        mo.avertissements.append(
            f"Pseudo-3D : paroi droite de {p.longueur:g} m ; pour la fouille fermée (parois en vis-à-vis reliées "
            "par les butons), supprimez pseudo3d.longueur.")
    return mo


def avertissements_simplifications(modele, res: ResultatPseudo3D, n_jeux: int = 1) -> list[str]:
    """Ce que le pseudo-3D ne fait pas (et que le 2D fait), dit explicitement."""
    out = []
    regime = (modele.hydraulique or {}).get("regime", "hydrostatique")
    if regime != "hydrostatique":
        out.append(f"Pseudo-3D : l'écoulement (hydraulique.regime = {regime}) n'est pas pris en compte, pressions d'eau hydrostatiques.")
    if len(chaine_principale(modele.phases)) < len(modele.phases):
        out.append("Pseudo-3D : seule la branche de phases menant à la dernière phase est calculée (variantes `depuis` ignorées).")
    if n_jeux > 1:
        out.append("Pseudo-3D : jeu d'eau principal seul (les autres jeux ne sont calculés qu'en 2D).")
    if res.phases and not res.complet:
        ph = next(p for p in res.phases if not p.ok)
        out.append(f"Pseudo-3D : calcul interrompu à la phase « {ph.nom} » ({ph.message}) ; phases suivantes non calculées, "
                   "vérifications structurelles [pseudo-3D] omises.")
    return out


def depuis_script(ex) -> ResultatPseudo3D:
    res = moteur_depuis_script(ex).calculer()
    res.avertissements.extend(avertissements_simplifications(ex.modele, res, len(ex.jeux)))
    return res


def _sous_echantillon(n: int, max_n: int) -> np.ndarray:
    return np.unique(np.linspace(0, n - 1, min(n, max_n)).round().astype(int))


def serialiser(res: ResultatPseudo3D, res2d=None) -> dict:
    js = _sous_echantillon(len(res.z), 90)
    phases2d = {p.nom: p for p in res2d.phases} if res2d is not None else {}

    def boucle(a: np.ndarray) -> np.ndarray:
        """Fouille fermée : le nœud s = périmètre est le nœud 0, répété pour l'affichage."""
        return np.vstack([a, a[:1]]) if res.fermee else a

    s_aff = np.concatenate([res.s, [res.longueur]]) if res.fermee else res.s
    phases = []
    for ph in res.phases:
        d = {"nom": ph.nom, "ok": ph.ok, "message": ph.message}
        if ph.ok:
            lignes = np.flatnonzero(np.abs(ph.reactions).sum(axis=1) > 0)
            d.update({
                "y_mm": (boucle(ph.W)[:, js] * 1e3).round(3).tolist(),
                "M": boucle(ph.Mz)[:, js].round(2).tolist(),
                "Ms": boucle(ph.Ms)[:, js].round(2).tolist(),
                "V": boucle(ph.V)[:, js].round(2).tolist(),
                "y_max_mm": float(np.abs(ph.W).max() * 1e3),
                "Mz_max": float(ph.Mz.max()), "Mz_min": float(ph.Mz.min()),
                "Ms_absmax": float(np.abs(ph.Ms).max()),
                "V_absmax": float(np.abs(ph.V_diag).max()),
                "Mzs_absmax": float(np.abs(ph.Mzs).max()),
                "appuis": ph.appuis,
                "reactions": {"s": res.s[lignes].round(3).tolist(),
                              "total_kN": ph.reactions[lignes].sum(axis=1).round(2).tolist()},
                "bilan": {k: round(v, 4) for k, v in ph.bilan.items()},
                "liernes": {nom: {"cote": li["cote"], "EI": li["EI"], "M": li["M"].round(2).tolist(),
                                  "V": li["V"].round(2).tolist(), "M_absmax": float(np.abs(li["M"]).max()),
                                  "V_absmax": float(np.abs(li["V"]).max())}
                            for nom, li in ph.liernes.items()},
            })
            p2 = phases2d.get(ph.nom)
            if p2 is not None and p2.ok:
                d["y_max_2d_mm"] = float(np.abs(p2.y).max() * 1e3)
        phases.append(d)
    return {"s": s_aff.round(4).tolist(), "z": res.z[js].round(4).tolist(), "phases": phases,
            "avertissements": res.avertissements, "sommets": [round(float(x), 4) for x in res.sommets],
            "fermee": res.fermee, "longueur": round(res.longueur, 4)}


def champ_pour_maquette(ex) -> dict:
    """Champ pseudo-3D au format attendu par la maquette (abscisse s le long du contour) ; réutilise le
    résultat déjà calculé par verifications.executer quand il existe."""
    res = getattr(ex, "pseudo3d", None)
    return serialiser(res if res is not None else depuis_script(ex))
