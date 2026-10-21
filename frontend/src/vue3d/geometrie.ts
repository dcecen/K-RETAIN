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

/** Contour polygonal de la fouille. */
export class Contour {
  readonly points: Point2[]
  readonly n: number
  readonly sens: 1 | -1
  readonly aretes: Arete[]
  readonly xmin: number
  readonly xmax: number
  readonly ymin: number
  readonly ymax: number
  readonly taille: number
  readonly marge: number
  readonly longueur: number

  constructor(points: number[][]) {
    this.points = points.map((p) => [p[0], p[1]] as Point2)
    this.n = this.points.length
    const aire = this.points.reduce((s, [x0, y0], i) => {
      const [x1, y1] = this.points[(i + 1) % this.n]
      return s + x0 * y1 - x1 * y0
    }, 0) / 2
    this.sens = aire > 0 ? 1 : -1
    let s0 = 0
    this.aretes = []
    for (let k = 0; k < this.n; k++) {
      const A = this.points[k]
      const B = this.points[(k + 1) % this.n]
      const L = Math.hypot(B[0] - A[0], B[1] - A[1])
      const t: Point2 = L > 0 ? [(B[0] - A[0]) / L, (B[1] - A[1]) / L] : [1, 0]
      const ni: Point2 = [-t[1] * this.sens, t[0] * this.sens]
      this.aretes.push({ k, A, B, L, t, ni, s0 })
      s0 += L
    }
    this.longueur = s0
    const xs = this.points.map((p) => p[0])
    const ys = this.points.map((p) => p[1])
    this.xmin = Math.min(...xs)
    this.xmax = Math.max(...xs)
    this.ymin = Math.min(...ys)
    this.ymax = Math.max(...ys)
    this.taille = Math.max(this.xmax - this.xmin, this.ymax - this.ymin, 10)
    this.marge = Math.max(8, 0.5 * this.taille)
  }

  /** Contour orienté dans le sens trigonométrique (pour les trous des formes three). */
  get trigo(): Point2[] {
    return this.sens > 0 ? this.points : [...this.points].reverse()
  }

  /** Rectangle extérieur du terrain modélisé autour de la fouille. */
  exterieur(marge = this.marge): Point2[] {
    return [[this.xmin - marge, this.ymin - marge], [this.xmax + marge, this.ymin - marge],
      [this.xmax + marge, this.ymax + marge], [this.xmin - marge, this.ymax + marge]]
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
    const C = this.points
    for (let i = 0, j = this.n - 1; i < this.n; j = i++) {
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
    return this.points.map((p) => `${p[0].toFixed(3)},${p[1].toFixed(3)}`).join(';')
  }
}

/** Atténuation de la déformée près des angles (purement visuelle : l'angle est supposé fixe).
 *  Rampe en sinus sur une longueur `la` depuis chaque extrémité de l'arête. */
export function attenuationAngle(sl: number, L: number, la: number): number {
  if (la <= 0) return 1
  const d = Math.min(sl, L - sl)
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
