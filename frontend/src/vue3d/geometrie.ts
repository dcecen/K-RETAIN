// Géométrie en plan de la fouille, fonctions pures (aucun objet three.js créé ici, sauf `versThree`).
// Repère du projet : x, y en plan (m), z cote vers le haut (m). Repère three : (x, z, −y).
import * as THREE from 'three'

export type Point2 = [number, number]

/** Position three d'un point du projet (écrit dans `out` pour éviter les allocations). */
export function versThree(x: number, y: number, z: number, out = new THREE.Vector3()): THREE.Vector3 {
  return out.set(x, z, -y)
}

/** Interpolation linéaire y(x) sur des abscisses croissantes, bornée aux extrémités. */
export function interpBorne(xs: ArrayLike<number>, ys: ArrayLike<number>, x: number): number {
  const n = xs.length
  if (!n) return 0
  if (x <= xs[0]) return ys[0]
  if (x >= xs[n - 1]) return ys[n - 1]
  let lo = 0
  let hi = n - 1
  while (hi - lo > 1) {
    const m = (lo + hi) >> 1
    if (xs[m] <= x) lo = m
    else hi = m
  }
  const d = xs[hi] - xs[lo]
  const t = d === 0 ? 0 : (x - xs[lo]) / d
  return ys[lo] + t * (ys[hi] - ys[lo])
}

export interface Arete {
  k: number
  A: Point2
  B: Point2
  L: number
  t: Point2          // tangente unitaire
  ni: Point2         // normale unitaire vers l'intérieur de la fouille
  s0: number         // abscisse développée du sommet A
}

/** Contour de la fouille : polygone fermé (enceinte), ou polyligne ouverte (paroi droite ou en L, coupe 2D
 *  infinie). Ouvert : pas d'arête de fermeture ; le côté fouille est celui du polygone que fermerait la polyligne
 *  (même règle que le calcul, sout.plan.geometrie.aretes) ; terre et fouille sont deux bandes de part et d'autre de
 *  l'écran, coupées net aux deux bouts (l'écran est supposé se prolonger au-delà). */
export class Contour {
  readonly points: Point2[]
  readonly n: number
  readonly sens: 1 | -1
  readonly aretes: Arete[]
  readonly ferme: boolean
  readonly xmin: number
  readonly xmax: number
  readonly ymin: number
  readonly ymax: number
  readonly taille: number
  readonly marge: number
  readonly longueur: number
  /** Zone de terre modélisée (polygone et trou éventuel) et zone de la fouille, en plan. */
  readonly terre: { points: Point2[]; trou?: Point2[] }
  readonly fouille: Point2[]

  constructor(points: number[][], ferme = true, largeurFouille = 0) {
    this.points = points.map((p) => [p[0], p[1]] as Point2)
    this.n = this.points.length
    this.ferme = ferme && this.n >= 3
    const aire = this.points.reduce((s, [x0, y0], i) => {
      const [x1, y1] = this.points[(i + 1) % this.n]
      return s + x0 * y1 - x1 * y0
    }, 0) / 2
    this.sens = aire > 0 ? 1 : -1
    let s0 = 0
    this.aretes = []
    for (let k = 0; k < (this.ferme ? this.n : Math.max(this.n - 1, 0)); k++) {
      const A = this.points[k]
      const B = this.points[(k + 1) % this.n]
      const L = Math.hypot(B[0] - A[0], B[1] - A[1])
      const t: Point2 = L > 0 ? [(B[0] - A[0]) / L, (B[1] - A[1]) / L] : [1, 0]
      const ni: Point2 = [-t[1] * this.sens, t[0] * this.sens]
      this.aretes.push({ k, A, B, L, t, ni, s0 })
      s0 += L
    }
    this.longueur = s0
    const boite = (pts: Point2[]) => {
      const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1])
      return [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)]
    }
    const [x0, x1, y0, y1] = boite(this.points)
    this.marge = Math.max(8, 0.5 * Math.max(x1 - x0, y1 - y0, 10))
    if (this.ferme) {
      this.terre = { points: this.exterieurDe(x0, x1, y0, y1, this.marge), trou: this.trigo }
      this.fouille = this.points
      ;[this.xmin, this.xmax, this.ymin, this.ymax] = [x0, x1, y0, y1]
    } else {
      // bandes de part et d'autre de l'écran : terre sur la marge, fouille assez large pour les butons dessinés
      this.terre = { points: [...this.points, ...this.decale(-this.marge).reverse()] }
      this.fouille = [...this.points, ...this.decale(Math.max(this.marge, largeurFouille)).reverse()]
      ;[this.xmin, this.xmax, this.ymin, this.ymax] = boite([...this.terre.points, ...this.fouille])
    }
    this.taille = Math.max(this.xmax - this.xmin, this.ymax - this.ymin, 10)
  }

  /** Polyligne décalée de w le long de la normale côté fouille (w < 0 : côté terre), coins en onglet. */
  private decale(w: number): Point2[] {
    const ar = this.aretes
    return this.points.map((P, i) => {
      const n1 = ar[Math.max(0, Math.min(i - 1, ar.length - 1))]?.ni ?? [0, 1]
      const n2 = ar[Math.min(i, ar.length - 1)]?.ni ?? n1
      const bx = n1[0] + n2[0], by = n1[1] + n2[1]
      const lb = Math.hypot(bx, by) || 1
      const f = w / Math.max(0.2, (bx * n2[0] + by * n2[1]) / lb)
      return [P[0] + (bx / lb) * f, P[1] + (by / lb) * f] as Point2
    })
  }

  private exterieurDe(x0: number, x1: number, y0: number, y1: number, marge: number): Point2[] {
    return [[x0 - marge, y0 - marge], [x1 + marge, y0 - marge], [x1 + marge, y1 + marge], [x0 - marge, y1 + marge]]
  }

  /** Contour orienté dans le sens trigonométrique (pour les trous des formes three). */
  get trigo(): Point2[] {
    return this.sens > 0 ? this.points : [...this.points].reverse()
  }

  /** Rectangle extérieur du terrain modélisé autour de la fouille (contour ouvert : boîte des deux bandes). */
  exterieur(marge = this.marge): Point2[] {
    if (!this.ferme) return this.exterieurDe(this.xmin, this.xmax, this.ymin, this.ymax, 0)
    return this.exterieurDe(this.xmin, this.xmax, this.ymin, this.ymax, marge)
  }

  /** Point du contour le plus proche : abscisse développée s, arête k, abscisse locale sl, distance d. */
  projeter(x: number, y: number): { s: number; k: number; sl: number; d: number } {
    let best = { s: 0, k: 0, sl: 0, d: Infinity }
    for (const a of this.aretes) {
      if (a.L <= 0) continue
      const sl = Math.min(Math.max((x - a.A[0]) * a.t[0] + (y - a.A[1]) * a.t[1], 0), a.L)
      const d = Math.hypot(a.A[0] + a.t[0] * sl - x, a.A[1] + a.t[1] * sl - y)
      if (d < best.d) best = { s: a.s0 + sl, k: a.k, sl, d }
    }
    return best
  }

  /** Point du contour à l'abscisse développée s (bornée). */
  point(s: number): { x: number; y: number; k: number; sl: number } {
    const sc = Math.min(Math.max(s, 0), this.longueur)
    for (const a of this.aretes) {
      if (sc <= a.s0 + a.L + 1e-9 || a.k === this.n - 1) {
        const sl = Math.min(Math.max(sc - a.s0, 0), a.L)
        return { x: a.A[0] + a.t[0] * sl, y: a.A[1] + a.t[1] * sl, k: a.k, sl }
      }
    }
    return { x: this.points[0][0], y: this.points[0][1], k: 0, sl: 0 }
  }

  dedans(x: number, y: number): boolean {
    let c = false
    const C = this.fouille
    const n = C.length
    for (let i = 0, j = n - 1; i < n; j = i++) {
      const [xi, yi] = C[i]
      const [xj, yj] = C[j]
      if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) c = !c
    }
    return c
  }

  /** Distance signée au contour : positive dans la fouille. */
  distanceSignee(x: number, y: number): number {
    const d = this.projeter(x, y).d
    return this.dedans(x, y) ? d : -d
  }

  /** Intersections d'une droite x = v (axe « x ») ou y = v (axe « y ») avec le contour. */
  intersections(axe: 'x' | 'y', v: number): { P: Point2; ni: Point2; k: number }[] {
    const out: { P: Point2; ni: Point2; k: number }[] = []
    for (const a of this.aretes) {
      const ua = axe === 'x' ? a.A[0] : a.A[1]
      const ub = axe === 'x' ? a.B[0] : a.B[1]
      if ((ua - v) * (ub - v) > 0 || ua === ub) continue
      const t = (v - ua) / (ub - ua)
      out.push({ P: [a.A[0] + t * (a.B[0] - a.A[0]), a.A[1] + t * (a.B[1] - a.A[1])], ni: a.ni, k: a.k })
    }
    return out
  }

  /** Empreinte de la géométrie en plan (clé de comparaison entre deux calculs). */
  cle(): string {
    return this.points.map((p) => `${p[0].toFixed(3)},${p[1].toFixed(3)}`).join(';') + (this.ferme ? '' : `|ouvert|${this.fouille.length}|${this.xmin.toFixed(2)},${this.ymin.toFixed(2)}`)
  }
}

/** Atténuation de la déformée près des angles (purement visuelle : l'angle est supposé fixe).
 *  Rampe en sinus sur une longueur `la` depuis chaque extrémité de l'arête ; une extrémité libre (bout coupé d'un
 *  contour ouvert, écran supposé se prolonger) n'est pas atténuée. */
export function attenuationAngle(sl: number, L: number, la: number, debutLibre = false, finLibre = false): number {
  if (la <= 0) return 1
  const d = Math.min(debutLibre ? Infinity : sl, finLibre ? Infinity : L - sl)
  if (d >= la) return 1
  return Math.sin((Math.PI / 2) * Math.max(d, 0) / la)
}

/** Hachage court et stable d'une chaîne (clés des objets de la scène). */
export function hacher(s: string): string {
  let h = 2166136261
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return (h >>> 0).toString(36)
}

/** Contour de la maquette renvoyée par le calcul : fermé ou ouvert selon `ferme` ; un contour ouvert garde une bande
 *  de fouille assez large pour dessiner les butons sur leur longueur (pas de paroi d'en face). */
export function contourMaquette(m: { contour: number[][]; ferme?: boolean; appuis?: Record<string, { type: string; longueur?: number | null }> } | null | undefined): Contour {
  if (!m) return new Contour([[0, 0], [20, 0], [20, 12], [0, 12]])
  const butons = Object.values(m.appuis ?? {}).filter((a) => a.type === 'buton').map((a) => a.longueur ?? 0)
  return new Contour(m.contour, m.ferme !== false, Math.max(0, ...butons) + 1)
}
