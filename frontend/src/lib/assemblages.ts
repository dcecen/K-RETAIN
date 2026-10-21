// Types et projections des schémas d'assemblage (géométrie partagée 2D / 3D).

export interface ParamDef {
  cle: string
  libelle: string
  unite: string
  defaut: number | string
  mini: number | null
  maxi: number | null
  choix: (number | string)[] | null
  genre: 'nombre' | 'entier' | 'choix' | 'profil' | 'tube' | 'acier' | 'beton'
}

export interface TypeAssemblage {
  cle: string
  nom: string
  famille: string
  description: string
  efforts: string[]
  parametres: ParamDef[]
}

export interface Solide {
  repere: number
  nom: string
  forme: 'boite' | 'cylindre' | 'prisme'
  materiau: string
  centre: number[]
  dims: number[]
  axe: 'x' | 'y' | 'z'
  points: number[][] | null
  parametres: string[]
  masque: boolean
}

export interface Soudure { p1: number[]; p2: number[]; a: number; type: string; contour: boolean; reperes: number[]; parametre: string | null }
export interface Cote { p1: number[]; p2: number[]; texte: string; vue: string; parametre: string | null; decalage: number }
export interface Effort { point: number[]; direction: number[]; valeur: number; texte: string }
export interface Vue { nom: string; plan: 'xz' | 'yz' | 'xy'; coupe: { axe: 'x' | 'y' | 'z'; pos: number } | null }

export interface Schema {
  type: string
  parametres: Record<string, number | string>
  solides: Solide[]
  soudures: Soudure[]
  cotes: Cote[]
  efforts: Effort[]
  vues: Vue[]
  notes: string[]
  nomenclature: { repere: number; nom: string; materiau: string; nombre: number }[]
  demo: boolean
}

const AXE: Record<string, number> = { x: 0, y: 1, z: 2 }

/** Boîte englobante [min, max] d'un solide. */
export function bbox(s: Solide): [number[], number[]] {
  const c = s.centre
  if (s.forme === 'boite') {
    const [lx, ly, lz] = s.dims
    return [[c[0] - lx / 2, c[1] - ly / 2, c[2] - lz / 2], [c[0] + lx / 2, c[1] + ly / 2, c[2] + lz / 2]]
  }
  if (s.forme === 'cylindre') {
    const [d, L] = s.dims
    const k = AXE[s.axe]
    const mn = [c[0] - d / 2, c[1] - d / 2, c[2] - d / 2], mx = [c[0] + d / 2, c[1] + d / 2, c[2] + d / 2]
    mn[k] = c[k] - L / 2; mx[k] = c[k] + L / 2
    return [mn, mx]
  }
  // prisme : points (u, v) dans le plan ⟂ axe, extrusion dims[0] centrée en centre[k]
  const k = AXE[s.axe]
  const [ku, kv] = autresAxes(s.axe)
  const pts = s.points ?? []
  const mn = [Infinity, Infinity, Infinity], mx = [-Infinity, -Infinity, -Infinity]
  for (const [u, v] of pts) { mn[ku] = Math.min(mn[ku], u); mx[ku] = Math.max(mx[ku], u); mn[kv] = Math.min(mn[kv], v); mx[kv] = Math.max(mx[kv], v) }
  mn[k] = c[k] - s.dims[0] / 2; mx[k] = c[k] + s.dims[0] / 2
  return [mn, mx]
}

export function autresAxes(axe: string): [number, number] {
  return axe === 'x' ? [1, 2] : axe === 'y' ? [0, 2] : [0, 1]
}

/** Projection d'un point 3D sur une vue : X vers la droite, Y vers le bas (écran), profondeur vers l'observateur. */
export function projeter(p: number[], plan: Vue['plan']): { X: number; Y: number; prof: number } {
  if (plan === 'xz') return { X: p[0], Y: -p[2], prof: -p[1] }       // observateur en −y
  if (plan === 'yz') return { X: p[1], Y: -p[2], prof: p[0] }        // observateur en +x (côté fouille)
  return { X: p[0], Y: -p[1], prof: p[2] }                           // dessus : observateur en +z
}

/** Axe de profondeur d'un plan de vue et sens vers l'observateur. */
export function axeProfondeur(plan: Vue['plan']): { k: number; sens: 1 | -1 } {
  return plan === 'xz' ? { k: 1, sens: -1 } : plan === 'yz' ? { k: 0, sens: 1 } : { k: 2, sens: 1 }
}

export type Figure =
  | { genre: 'rect'; x: number; y: number; w: number; h: number; coupe: boolean; solide: Solide; prof: number }
  | { genre: 'cercle'; cx: number; cy: number; r: number; coupe: boolean; solide: Solide; prof: number }
  | { genre: 'poly'; pts: number[][]; coupe: boolean; solide: Solide; prof: number }

/** Figures 2D d'une vue : solides coupés (hachurés), solides vus, solides retirés (devant le plan de coupe). */
export function figures(schema: Schema, vue: Vue): Figure[] {
  const out: Figure[] = []
  const { k: kp, sens } = axeProfondeur(vue.plan)
  for (const s of schema.solides) {
    const [mn, mx] = bbox(s)
    let coupe = false
    if (vue.coupe) {
      const kc = AXE[vue.coupe.axe]
      const pos = vue.coupe.pos
      if (mn[kc] < pos && mx[kc] > pos) coupe = true
      else if (kc === kp) {
        // partie entre l'observateur et le plan : retirée
        const devant = sens === 1 ? mn[kc] >= pos : mx[kc] <= pos
        if (devant) continue
      }
    }
    const prof = sens * (sens === 1 ? mx[kp] : mn[kp])
    const a = projeter(mn, vue.plan), b = projeter(mx, vue.plan)
    const x = Math.min(a.X, b.X), y = Math.min(a.Y, b.Y), w = Math.abs(b.X - a.X), h = Math.abs(b.Y - a.Y)
    if (s.forme === 'cylindre' && AXE[s.axe] === kp) {
      out.push({ genre: 'cercle', cx: x + w / 2, cy: y + h / 2, r: s.dims[0] / 2, coupe, solide: s, prof })
    } else if (s.forme === 'prisme' && s.points && AXE[s.axe] === kp) {
      const [ku, kv] = autresAxes(s.axe)
      const pts = s.points.map(([u, v]) => { const p = [0, 0, 0]; p[ku] = u; p[kv] = v; p[AXE[s.axe]] = s.centre[AXE[s.axe]]; const q = projeter(p, vue.plan); return [q.X, q.Y] })
      out.push({ genre: 'poly', pts, coupe, solide: s, prof })
    } else {
      out.push({ genre: 'rect', x, y, w, h, coupe, solide: s, prof })
    }
  }
  // dessiner du plus lointain au plus proche ; les solides coupés en dernier
  out.sort((p, q) => (p.coupe === q.coupe ? p.prof - q.prof : p.coupe ? 1 : -1))
  return out
}

/** Emprise d'une vue (solides et cotes), en coordonnées écran. */
export function emprise(schema: Schema, vue: Vue): { x: number; y: number; w: number; h: number } {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity
  for (const s of schema.solides) {
    if (s.repere === 0 && s.materiau === 'beton') continue  // la paroi englobante ne dicte pas le cadrage
    const [mn, mx] = bbox(s)
    for (const p of [mn, mx]) { const q = projeter(p, vue.plan); x0 = Math.min(x0, q.X); x1 = Math.max(x1, q.X); y0 = Math.min(y0, q.Y); y1 = Math.max(y1, q.Y) }
  }
  for (const e of schema.efforts) { const q = projeter(e.point, vue.plan); x0 = Math.min(x0, q.X); x1 = Math.max(x1, q.X); y0 = Math.min(y0, q.Y); y1 = Math.max(y1, q.Y) }
  const m = 0.12 * Math.max(x1 - x0, y1 - y0) + 60
  return { x: x0 - m, y: y0 - m, w: x1 - x0 + 2 * m, h: y1 - y0 + 2 * m }
}

export function nomVue(v: Vue): 'elevation' | 'coupe' | 'dessus' {
  if (v.coupe) return 'coupe'
  return v.plan === 'xy' ? 'dessus' : 'elevation'
}
