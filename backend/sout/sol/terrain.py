"""Surcharges étendues et géométrie du terrain : contraintes verticales additionnelles
Δσv(z) au droit d'une coupe de calcul, à partir d'objets déclarés en plan.

Interface unique avec le moteur (`MoteurPhases._sigma_v`) : `delta_sigma_v_surcharges`
renvoie, pour une liste de surcharges (anciennes `Surcharge` de `sol.surcharges` ou
nouvelles `SurchargePlan`), la somme des Δσv aux cotes demandées, sur la face considérée.
Le moteur reste intact : il ajoute ce Δσv à σ'v avant d'appliquer Ka, K0 et Kp.

Sources (solutions élastiques du massif semi-infini, Poulos H.G. & Davis E.H. (1974),
*Elastic Solutions for Soil and Rock Mechanics*, Wiley) :
- charge ponctuelle Q : Boussinesq (1885), Δσz = 3·Q·z³ / (2·π·R⁵), R² = r² + z² (§ 2.1) ;
- rectangle uniformément chargé, contrainte sous un coin (Newmark 1935, § 3.3) :
  Δσz = q/(4π)·[ 2mn√(m²+n²+1)/(m²+n²+m²n²+1) · (m²+n²+2)/(m²+n²+1) + arctan( 2mn√(m²+n²+1)/(m²+n²+1−m²n²) ) ],
  m = B/z, n = L/z, avec +π dans l'arctangente quand m²n² > m²+n²+1 ; un point quelconque
  s'obtient par superposition (addition et soustraction) de rectangles ayant un coin au droit du point ;
- bande illimitée parallèle à l'écran et charge linéique : formules déjà présentes dans
  `sol.surcharges` (Boussinesq intégré, Flamant) ;
- charge linéique quelconque en plan : intégration numérique (Gauss-Legendre) de la solution
  de Boussinesq ponctuelle le long du segment.

Hypothèse de modélisation (commune à `sol.surcharges`) : la contrainte verticale du massif
semi-infini est transmise aux ressorts sans effet miroir de l'écran ; la présence de la
fouille n'est pas prise en compte dans la diffusion.

Méthode de la NF P 94-282 (annexe sur les surcharges) : non fournie dans docs/normes —
TODO-NORME, seule la diffusion élastique est disponible et elle est affichée.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .surcharges import Surcharge, delta_sigma_v

TYPES_PLAN = ("rectangulaire", "ponctuelle", "lineaire")
METHODE = "diffusion élastique (Boussinesq / Newmark), sans effet miroir de l'écran"


class ErreurTerrain(Exception):
    pass


@dataclass(frozen=True)
class CoupeCalcul:
    """Position d'une coupe de calcul en plan : point sur la paroi, normale vers la fouille,
    tangente, abscisse le long du côté, côté nommé."""
    x: float
    y: float
    ni: tuple[float, float]
    t: tuple[float, float]
    k: int = 0
    s: float = 0.0
    cote: str | None = None
    nom: str | None = None

    @staticmethod
    def depuis_dict(d: dict | None) -> CoupeCalcul | None:
        if not d:
            return None
        return CoupeCalcul(x=float(d["x"]), y=float(d["y"]), ni=(float(d["ni"][0]), float(d["ni"][1])),
                           t=(float(d["t"][0]), float(d["t"][1])), k=int(d.get("k", 0)), s=float(d.get("s", 0.0)),
                           cote=d.get("cote"), nom=d.get("nom"))


@dataclass(frozen=True)
class SurchargePlan:
    """Surcharge déclarée en plan ou par rapport à un côté de paroi (bloc `surcharges` du script)."""
    nom: str
    type: str                                  # uniforme, bande, rectangulaire, ponctuelle, lineaire, convoi
    q: float                                   # kPa (uniforme, bande, rectangulaire), kN (ponctuelle), kN/m (lineaire)
    distance: float = 0.0                      # bande : début depuis la paroi (m)
    largeur: float | None = None               # bande : largeur (m) ; uniforme : largeur de la zone chargée (vide = illimitée)
    emprise: tuple[float, float] | None = None  # rectangulaire/ponctuelle : [lx, ly] (m) ; bande : [de, a] le long du côté
    position: tuple[float, float] | None = None  # rectangulaire/ponctuelle : centre [x, y] (m)
    trace: tuple[tuple[float, float], tuple[float, float]] | None = None   # lineaire : segment [[x0, y0], [x1, y1]]
    profondeur: float = 0.0                    # cote d'application = terrain − profondeur (m)
    cote: float | None = None                  # cote d'application imposée (m)
    cote_ecran: str = "amont"
    cotes_paroi: tuple[str, ...] | None = None   # côtés concernés (noms de plan.cotes) ; None = tous
    modele: str | None = None                  # convoi : modèle routier (à fournir)
    phase_debut: int | None = None             # numéro de phase (1 = première phase) d'application
    phase_fin: int | None = None               # dernière phase où elle existe
    infos: dict = field(default_factory=dict)  # niveaux, nom affiché… (maquette)


# ---------------------------------------------------------------------------
# solutions élastiques
# ---------------------------------------------------------------------------
def boussinesq_ponctuelle(Q: float, r: np.ndarray, z: np.ndarray) -> np.ndarray:
    """Δσz sous une charge ponctuelle Q (kN) à la distance horizontale r et à la profondeur z > 0.
    Boussinesq (1885) : Δσz = 3·Q·z³ / (2·π·R⁵). Poulos & Davis (1974) § 2.1."""
    z = np.asarray(z, float)
    r = np.asarray(r, float)
    R2 = r * r + z * z
    out = np.zeros_like(z)
    ok = z > 1e-9
    out[ok] = 3.0 * Q * z[ok] ** 3 / (2.0 * math.pi * R2[ok] ** 2.5)
    return out


def newmark_coin(q: float, B: float, L: float, z: np.ndarray) -> np.ndarray:
    """Δσz sous le coin d'un rectangle B × L uniformément chargé (q), profondeur z > 0.
    Newmark (1935), Poulos & Davis (1974) § 3.3 (avec la correction de quadrant de l'arctangente)."""
    z = np.asarray(z, float)
    out = np.zeros_like(z)
    ok = z > 1e-9
    if B <= 0 or L <= 0 or not ok.any():
        return out
    m = B / z[ok]
    n = L / z[ok]
    m2, n2 = m * m, n * n
    rac = np.sqrt(m2 + n2 + 1.0)
    den1 = m2 + n2 + m2 * n2 + 1.0
    den2 = m2 + n2 + 1.0 - m2 * n2
    terme1 = 2.0 * m * n * rac / den1 * (m2 + n2 + 2.0) / (m2 + n2 + 1.0)
    atan = np.arctan2(2.0 * m * n * rac, den2)        # arctan avec +π quand den2 < 0
    out[ok] = q / (4.0 * math.pi) * (terme1 + atan)
    return out


def rectangle_quelconque(q: float, x0: float, x1: float, y0: float, y1: float, px: float, py: float, z: np.ndarray) -> np.ndarray:
    """Δσz au point (px, py) sous un rectangle [x0, x1] × [y0, y1] chargé de q, par superposition de
    rectangles ayant un coin au droit du point (signes selon la position du point)."""
    def coin(a: float, b: float) -> np.ndarray:
        # rectangle de côtés |a|, |b| avec un coin sous le point, signe = signe(a)·signe(b)
        if abs(a) < 1e-12 or abs(b) < 1e-12:
            return np.zeros_like(np.asarray(z, float))
        return math.copysign(1.0, a) * math.copysign(1.0, b) * newmark_coin(q, abs(a), abs(b), z)

    return coin(x1 - px, y1 - py) - coin(x0 - px, y1 - py) - coin(x1 - px, y0 - py) + coin(x0 - px, y0 - py)


_GAUSS = np.polynomial.legendre.leggauss(4)


def ligne_quelconque(Q: float, A: tuple[float, float], B: tuple[float, float], px: float, py: float, z: np.ndarray) -> np.ndarray:
    """Δσz au point (px, py) sous une charge linéique Q (kN/m) répartie sur le segment [A, B],
    par intégration de la solution ponctuelle de Boussinesq : le segment est réduit à la fenêtre
    utile autour du pied de la perpendiculaire (au-delà de 50·z la contribution est négligeable,
    décroissance en 1/R⁵) puis découpé en morceaux de longueur ≤ z_min/2 intégrés par Gauss-Legendre à 4 points."""
    z = np.asarray(z, float)
    out = np.zeros_like(z)
    L = math.dist(A, B)
    sous = z > 1e-9
    if L < 1e-9 or not sous.any():
        return out
    zs = z[sous]
    ux, uy = (B[0] - A[0]) / L, (B[1] - A[1]) / L
    t0 = ((px - A[0]) * ux + (py - A[1]) * uy) / L           # projection du point sur la droite (paramètre)
    W = 50.0 * float(zs.max()) / L
    ta, tb = max(0.0, t0 - W), min(1.0, t0 + W)
    if tb <= ta:
        return out
    n = int(min(4000, max(1, math.ceil((tb - ta) * L / (0.5 * max(float(zs.min()), 0.05))))))
    xi, w = _GAUSS
    acc = np.zeros_like(zs)
    dt = (tb - ta) / n
    for i in range(n):
        t_m = ta + (i + 0.5) * dt
        for u, wu in zip(xi, w):
            t = t_m + 0.5 * dt * u
            x = A[0] + t * (B[0] - A[0])
            y = A[1] + t * (B[1] - A[1])
            r = math.hypot(x - px, y - py)
            acc += wu * 0.5 * dt * L * boussinesq_ponctuelle(Q, np.full_like(zs, r), zs)
    out[sous] = acc
    return out


# ---------------------------------------------------------------------------
# rapport à la coupe
# ---------------------------------------------------------------------------
def _concerne(s: SurchargePlan, coupe: CoupeCalcul | None) -> bool:
    from ..plan.geometrie import cote_concerne
    return cote_concerne(s.cotes_paroi, coupe)


def delta_sigma_v_plan(s: SurchargePlan, z: np.ndarray, z_terrain: float, coupe: CoupeCalcul | None) -> np.ndarray:
    """Δσv (kPa) aux cotes z au droit de la coupe, pour une surcharge étendue."""
    z = np.asarray(z, float)
    z_app = z_terrain - s.profondeur if s.cote is None else s.cote
    prof = z_app - z
    out = np.zeros_like(z)
    sous = prof > 1e-9
    if not sous.any():
        return out
    h = prof[sous]
    if s.type == "convoi":
        raise ErreurTerrain(f"surcharge « {s.nom} » : modèle de convoi « {s.modele} » non disponible — "
                            "TODO-NORME : charges des convois à fournir dans docs/normes")
    if s.type in ("uniforme", "repartie"):
        if not _concerne(s, coupe):
            return out
        if s.largeur is None:
            out[sous] = s.q
        else:   # zone chargée de largeur finie à partir de la distance donnée : bande
            out[sous] = delta_sigma_v(Surcharge(s.nom, "bande", s.q, s.distance, s.largeur, z_app), z[sous], z_app)
        return out
    if s.type == "bande":
        if not _concerne(s, coupe) or not s.largeur:
            return out
        if s.emprise is None or coupe is None:
            out[sous] = delta_sigma_v(Surcharge(s.nom, "bande", s.q, s.distance, s.largeur, z_app), z[sous], z_app)
            return out
        # bande de longueur finie le long du côté : rectangle dans le repère (tangente, normale sortante)
        de, a = sorted(s.emprise)
        out[sous] = rectangle_quelconque(s.q, de, a, s.distance, s.distance + s.largeur, coupe.s, 0.0, h)
        return out
    if coupe is None:
        raise ErreurTerrain(f"surcharge « {s.nom} » ({s.type}) : position en plan impossible à rapporter à la coupe "
                            "(bloc plan et coupe de calcul nécessaires)")
    # repère local de la coupe : u le long de la paroi, v vers la terre (= −ni)
    def local(x: float, y: float) -> tuple[float, float]:
        dx, dy = x - coupe.x, y - coupe.y
        return dx * coupe.t[0] + dy * coupe.t[1], -(dx * coupe.ni[0] + dy * coupe.ni[1])

    if s.type == "rectangulaire" or (s.type == "ponctuelle" and s.emprise is not None):
        if s.position is None or s.emprise is None:
            raise ErreurTerrain(f"surcharge « {s.nom} » : position et emprise nécessaires")
        if len(s.emprise) < 2 or s.emprise[0] <= 0 or s.emprise[1] <= 0:
            raise ErreurTerrain(f"surcharge « {s.nom} » : emprise [lx, ly] strictement positive attendue, reçu {list(s.emprise)}")
        q = s.q if s.type == "rectangulaire" else s.q / (s.emprise[0] * s.emprise[1])
        # rectangle aligné sur le repère de la coupe (approximation si la fouille n'est pas rectangulaire)
        ux, vx = local(s.position[0], s.position[1])
        lx = abs(s.emprise[0] * coupe.t[0]) + abs(s.emprise[1] * coupe.t[1])
        ly = abs(s.emprise[0] * coupe.ni[0]) + abs(s.emprise[1] * coupe.ni[1])
        out[sous] = rectangle_quelconque(q, ux - lx / 2, ux + lx / 2, vx - ly / 2, vx + ly / 2, 0.0, 0.0, h)
        return out
    if s.type == "ponctuelle":
        if s.position is None:
            raise ErreurTerrain(f"surcharge « {s.nom} » : position nécessaire")
        r = math.hypot(s.position[0] - coupe.x, s.position[1] - coupe.y)
        out[sous] = boussinesq_ponctuelle(s.q, np.full_like(h, r), h)
        return out
    if s.type in ("lineaire", "lineique"):
        if s.trace is None:
            raise ErreurTerrain(f"surcharge « {s.nom} » : trace nécessaire")
        out[sous] = ligne_quelconque(s.q, s.trace[0], s.trace[1], coupe.x, coupe.y, h)
        return out
    raise ErreurTerrain(f"surcharge « {s.nom} » : type inconnu « {s.type} »")


def delta_sigma_v_surcharges(surcharges, face: str, z: np.ndarray, z_terrain: float, coupe: CoupeCalcul | None) -> np.ndarray:
    """Somme des Δσv de toutes les surcharges actives sur la face « amont » ou « aval » (interface unique du moteur)."""
    z = np.asarray(z, float)
    dsv = np.zeros_like(z)
    for s in surcharges:
        if s.cote_ecran != face:
            continue
        if isinstance(s, SurchargePlan):
            dsv += delta_sigma_v_plan(s, z, z_terrain, coupe)
        else:
            dsv += delta_sigma_v(s, z, z_terrain)
    return dsv


def profil_pour_affichage(s, z_terrain: float, z_pied: float, coupe: CoupeCalcul | None, n: int = 60) -> dict:
    """Δσv(z) d'une surcharge au droit de la coupe (maquette, panneau) ; valeurs nulles si non calculable."""
    z = np.linspace(z_pied, z_terrain, n)
    try:
        v = delta_sigma_v_surcharges([s], s.cote_ecran, z, z_terrain, coupe)
        note = METHODE
    except ErreurTerrain as e:
        v = np.zeros_like(z)
        note = str(e)
    return {"z": [round(float(x), 3) for x in z], "dsv": [round(float(x), 4) for x in v], "methode": note}


# ---------------------------------------------------------------------------
# géométrie du terrain : risbermes, talus, gradins côté fouille ; terrain en pente côté terre
# ---------------------------------------------------------------------------
METHODES_RISBERME = ("surcharge_equivalente", "fond_equivalent", "coin_de_rupture")
PREFIXE_TERRAIN = "~terrain:"


@dataclass(frozen=True)
class ObjetTerrain:
    """Volume de sol décrit par une ligne (distance à la paroi -> cote), sur une face de l'écran,
    présent entre deux phases. Côté fouille : risberme, talus, gradins (volume au-dessus de `base`,
    la cote du fond général). Côté terre : terrain en pente ou remblai localisé (volume au-dessus de
    la cote du terrain amont)."""
    nom: str
    type: str                                   # risberme, talus, gradins, pente
    face: str                                   # "aval" (fouille) ou "amont" (terre)
    profil: tuple[tuple[float, float], ...]     # ((d, z), ...) distances croissantes depuis la paroi
    base: float                                 # cote de référence (fond général ou terrain amont)
    gamma: float                                # kN/m³ du sol du volume (hors nappe)
    methode: str = "surcharge_equivalente"
    phase_debut: int | None = None              # 1 = première phase ; None = dès l'état initial
    phase_fin: int | None = None
    cotes_paroi: tuple[str, ...] | None = None
    cote_equivalente: float | None = None       # méthode fond_equivalent (valeur choisie par l'ingénieur)
    troncon: tuple[float, float] | None = None  # étendue [de, a] le long du côté (m) ; None = côté entier
    pas: float = 0.5                            # largeur des bandes équivalentes (m)

    def hauteur(self, d: float) -> float:
        """Épaisseur du volume au-dessus de la base à la distance d (interpolation sur la ligne)."""
        pts = self.profil
        if d <= pts[0][0]:
            z = pts[0][1]
        elif d >= pts[-1][0]:
            z = pts[-1][1]
        else:
            z = pts[-1][1]
            for (d0, z0), (d1, z1) in zip(pts, pts[1:]):
                if d0 <= d <= d1:
                    z = z0 if d1 == d0 else z0 + (z1 - z0) * (d - d0) / (d1 - d0)
                    break
        return max(0.0, z - self.base)

    @property
    def etendue(self) -> float:
        return self.profil[-1][0]


def profil_risberme(cote_crete: float, largeur_crete: float, pente: float, cote_pied: float) -> tuple[tuple[float, float], ...]:
    """Ligne d'une risberme ou d'un talus : crête horizontale contre la paroi puis descente à la pente
    donnée (horizontal / vertical) jusqu'au fond général."""
    if cote_pied > cote_crete:
        raise ErreurTerrain("risberme : la cote du pied doit être sous la cote de la crête")
    if pente <= 0:
        raise ErreurTerrain("risberme : la pente (horizontal/vertical) doit être > 0")
    d_fin = largeur_crete + pente * (cote_crete - cote_pied)
    return ((0.0, cote_crete), (largeur_crete, cote_crete), (d_fin, cote_pied), (d_fin + 1.0, cote_pied))


def profil_gradins(marches, cote_pied: float) -> tuple[tuple[float, float], ...]:
    """Ligne de gradins : marches [cote, largeur] depuis la paroi, puis le fond général."""
    pts: list[tuple[float, float]] = []
    d = 0.0
    for cote, largeur in marches:
        if cote < cote_pied - 1e-9:
            raise ErreurTerrain(f"gradins : marche à {cote} m sous le fond général {cote_pied} m")
        pts += [(d, cote), (d + largeur, cote)]
        d += largeur
    pts += [(d, cote_pied), (d + 1.0, cote_pied)]
    return tuple(pts)


def bandes_equivalentes(o: ObjetTerrain) -> list:
    """Méthode de la surcharge équivalente : le volume de sol est remplacé par son poids, appliqué
    à la cote de base sous forme de bandes verticales (largeur `pas`) diffusées par Boussinesq
    (`sol.surcharges.delta_sigma_v`, bande). Choix de modélisation RetainWall : les bandes
    conservent la forme du volume ; une surcharge uniforme unique serait plus grossière.
    Le poids volumique est pris hors nappe (volume supposé émergé).

    Objet sans restriction de côté ni de tronçon : bandes historiques (`Surcharge`), infinies le long
    de la paroi. Objet rattaché à des côtés ou à un tronçon : bandes `SurchargePlan` (type bande,
    `cotes_paroi`, `emprise` = tronçon) que `delta_sigma_v_plan` filtre et rapporte à chaque coupe ou
    ligne verticale du pseudo-3D ; sans tronçon, la bande reste infinie et la valeur est identique."""
    out = []
    n = max(1, int(math.ceil(o.etendue / o.pas)))
    w = o.etendue / n
    for i in range(n):
        d0 = i * w
        h = o.hauteur(d0 + w / 2)
        if h <= 1e-6:
            continue
        nom = f"{PREFIXE_TERRAIN}{o.nom}:{i}"
        if o.cotes_paroi is None and o.troncon is None:
            out.append(Surcharge(nom=nom, type="bande", q=o.gamma * h, distance=d0, largeur=w, cote=o.base, cote_ecran=o.face))
        else:
            out.append(SurchargePlan(nom=nom, type="bande", q=o.gamma * h, distance=d0, largeur=w, emprise=o.troncon,
                                     cote=o.base, cote_ecran=o.face, cotes_paroi=o.cotes_paroi))
    return out


def surcharges_terrain(objets, coupe: CoupeCalcul | None) -> list[tuple[ObjetTerrain, list]]:
    """Bandes équivalentes des objets concernant la coupe (les autres méthodes n'en produisent pas)."""
    from ..plan.geometrie import objet_concerne
    out = []
    for o in objets:
        if not objet_concerne(o.cotes_paroi, o.troncon, coupe):
            continue
        if o.methode == "coin_de_rupture":
            raise ErreurTerrain(f"{o.type} « {o.nom} » : méthode du coin de rupture non disponible — "
                                "TODO-NORME : publication à fournir dans docs/normes (surcharges_et_terrain.risberme_coin_de_rupture)")
        if o.methode == "fond_equivalent":
            out.append((o, []))
            continue
        out.append((o, bandes_equivalentes(o)))
    return out


def effet_butee(objets_actifs, kph_z: np.ndarray, z: np.ndarray, z_fond: float, coupe: CoupeCalcul | None) -> np.ndarray:
    """Supplément de butée limite dû aux bandes équivalentes des objets côté fouille : Kph(z) × Δσv(z).
    (Même relation que le moteur : pp = Kph·σ'v + terme de cohésion ; la cohésion ne change pas.)"""
    bandes = [b for o, bs in surcharges_terrain(objets_actifs, coupe) for b in bs if o.face == "aval"]
    if not bandes:
        return np.zeros_like(np.asarray(z, float))
    return np.asarray(kph_z, float) * delta_sigma_v_surcharges(bandes, "aval", z, z_fond, coupe)
