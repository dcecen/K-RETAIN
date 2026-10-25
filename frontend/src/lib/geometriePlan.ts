// Géométrie en plan pour la vue « Géométrie » : fonctions pures sur le script courant (bloc geometrie ou forme
// ancienne plan / fouille / terrain), sans three.js. Mêmes conventions que sout.plan.geometrie : arêtes orientées,
// normale intérieure vers la fouille, abscisse développée le long du contour.
import type { Modele } from './scriptDoc'

export type Point2 = [number, number]

export interface AreteP { k: number; A: Point2; B: Point2; L: number; t: Point2; ni: Point2; s0: number; nom: string | null }

export interface EtendueP { cotes: string[] | null; de: number | null; a: number | null }

export interface ObjetP { nom: string; type: string; etendue: EtendueP; largeur: number; phases: unknown[] }
export interface ZoneFondP { nom: string; etendue: EtendueP; largeur: number | null; emprise: Point2[] | null }
export interface ZoneTerrainP { nom: string; etendue: EtendueP; cote: number | null; pente_beta: number | null }
export interface PositionP { surcharge: string; etendue: EtendueP; position: Point2 | null; emprise: Point2 | null; trace: [Point2, Point2] | null; type: string }

/** Géométrie du script telle que la vue la dessine (forme normalisée ou ancienne). */
export interface GeometrieP {
  contour: Point2[]
  ferme: boolean
  cotes: Record<string, number>
  appuis: { appui: string; de: Point2; a: Point2 }[]
  objets: ObjetP[]
  zonesFond: ZoneFondP[]
  zonesTerrain: ZoneTerrainP[]
  positions: PositionP[]
  ancienne: boolean
  anciens: string[]
}

const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null)
const paire = (v: unknown): Point2 | null => (Array.isArray(v) && v.length >= 2 && num(v[0]) !== null && num(v[1]) !== null ? [Number(v[0]), Number(v[1])] : null)

function aireSignee(c: Point2[]): number {
  let a = 0
  for (let i = 0; i < c.length; i++) { const p = c[i], q = c[(i + 1) % c.length]; a += p[0] * q[1] - q[0] * p[1] }
  return a / 2
}

/** Arêtes orientées d'un contour (fermé ou polyligne ouverte), avec le nom du côté s'il existe. */
export function aretesContour(contour: Point2[], ferme = true, cotes: Record<string, number> = {}): AreteP[] {
  const n = contour.length
  if (n < 2) return []
  const sens = aireSignee(contour) > 0 ? 1 : -1
  const noms = new Map<number, string>(Object.entries(cotes).map(([nom, k]) => [Number(k), nom]))
  const out: AreteP[] = []
  let s0 = 0
  for (let k = 0; k < (ferme ? n : n - 1); k++) {
    const A = contour[k], B = contour[(k + 1) % n]
    const L = Math.hypot(B[0] - A[0], B[1] - A[1])
    const t: Point2 = L > 0 ? [(B[0] - A[0]) / L, (B[1] - A[1]) / L] : [1, 0]
    out.push({ k, A, B, L, t, ni: [-t[1] * sens, t[0] * sens], s0, nom: noms.get(k) ?? null })
    s0 += L
  }
  return out
}

/** Côtés d'un objet : noms du bloc cotes ou numéros d'arête (texte « #k » ou entier) ; null = tous. */
export function lireCotes(v: unknown): string[] | null {
  if (v === undefined || v === null || v === 'toutes') return null
  const l = Array.isArray(v) ? v : [v]
  const out = l.map((c) => (typeof c === 'number' ? `#${c}` : String(c)))
  return out.length ? out : null
}

function etendue(o: Modele): EtendueP {
  return { cotes: lireCotes(o?.cotes ?? o?.cote_paroi), de: num(o?.de), a: num(o?.a) }
}

/** L'étendue concerne-t-elle l'arête k ? */
export function etendueConcerne(e: EtendueP, a: AreteP): boolean {
  if (!e.cotes) return true
  return e.cotes.includes(`#${a.k}`) || (a.nom !== null && e.cotes.includes(a.nom))
}

/** Tronçon [de, fin] d'une étendue sur une arête (m). */
export function tronconSur(e: EtendueP, a: AreteP): [number, number] {
  const de = Math.max(0, Math.min(e.de ?? 0, a.L))
  const fin = Math.max(de, Math.min(e.a ?? a.L, a.L))
  return [de, fin]
}

function largeurObjet(o: Modele): number {
  if (o?.type === 'gradins' && Array.isArray(o.marches)) return o.marches.reduce((s: number, m: unknown) => s + (Array.isArray(m) ? Number(m[1]) || 0 : 0), 0)
  const crete = num(o?.cote_crete), pied = num(o?.cote_pied)
  const largeur = num(o?.largeur_crete) ?? num(o?.largeur_banquette) ?? 0
  const pente = num(o?.pente) ?? 1.5
  return largeur + (crete !== null && pied !== null ? Math.max(0, crete - pied) * pente : 0)
}

/** Lecture de la géométrie du script : bloc geometrie, sinon forme ancienne (plan, fouille, terrain, surcharges). */
export function lireGeometrie(modele: Modele): GeometrieP {
  const m = modele ?? {}
  const g = m.geometrie
  const anciens: string[] = []
  if (m.plan) anciens.push('plan')
  for (const k of ['risbermes', 'talus', 'gradins']) if (Array.isArray(m.fouille?.[k]) && m.fouille[k].length) anciens.push(`fouille.${k}`)
  for (const k of ['pente_beta', 'profil', 'cote_paroi']) if (m.terrain?.[k] !== undefined && m.terrain?.[k] !== null) anciens.push(`terrain.${k}`)
  const surcharges: Modele[] = Array.isArray(m.surcharges) ? m.surcharges : []
  const nomS = (s: Modele, i: number) => String(s?.nom ?? `S${i + 1}`)
  const typeS = (nom: string) => String(surcharges.find((s, i) => nomS(s, i) === nom)?.type ?? 'bande')
  if (g && typeof g === 'object') {
    const o = g.ouvrages ?? {}
    const contour = (Array.isArray(o.contour) ? o.contour : []).map(paire).filter((p: Point2 | null): p is Point2 => p !== null)
    const f = g.fouille ?? {}
    const objets: ObjetP[] = (Array.isArray(f.objets) ? f.objets : []).map((ob: Modele, i: number) => ({
      nom: String(ob?.nom ?? `${String(ob?.type ?? 'risberme')[0].toUpperCase()}${String(ob?.type ?? 'risberme').slice(1)}${i + 1}`),
      type: String(ob?.type ?? 'risberme'), etendue: etendue(ob), largeur: largeurObjet(ob), phases: Array.isArray(ob?.phases) ? ob.phases : [],
    }))
    const zonesFond: ZoneFondP[] = (Array.isArray(f.zones) ? f.zones : []).map((z: Modele) => ({
      nom: String(z?.nom ?? ''), etendue: etendue(z), largeur: num(z?.largeur),
      emprise: Array.isArray(z?.emprise) ? z.emprise.map(paire).filter((p: Point2 | null): p is Point2 => p !== null) : null,
    }))
    const t = g.terrain ?? {}
    const zonesTerrain: ZoneTerrainP[] = (Array.isArray(t.zones) ? t.zones : []).map((z: Modele, i: number) => ({
      nom: String(z?.nom ?? `terrain${i + 1}`), etendue: etendue(z), cote: num(z?.cote), pente_beta: num(z?.pente_beta) }))
    const positions: PositionP[] = (Array.isArray(g.surcharges) ? g.surcharges : []).map((p: Modele) => ({
      surcharge: String(p?.surcharge ?? ''), etendue: etendue(p), position: paire(p?.position), emprise: paire(p?.emprise),
      trace: p?.trace && paire(p.trace.de) && paire(p.trace.a) ? [paire(p.trace.de)!, paire(p.trace.a)!] : null, type: typeS(String(p?.surcharge ?? '')) }))
    return { contour, ferme: o.ferme !== false, cotes: o.cotes && typeof o.cotes === 'object' ? o.cotes : {},
      appuis: (Array.isArray(o.appuis) ? o.appuis : []).filter((a: Modele) => paire(a?.de) && paire(a?.a)).map((a: Modele) => ({ appui: String(a.appui), de: paire(a.de)!, a: paire(a.a)! })),
      objets, zonesFond, zonesTerrain, positions, ancienne: false, anciens }
  }
  const plan = m.plan ?? {}
  const contour = (Array.isArray(plan.contour) ? plan.contour : []).map(paire).filter((p: Point2 | null): p is Point2 => p !== null)
  const objets: ObjetP[] = []
  for (const [type, cle, defaut] of [['risberme', 'risbermes', 'Risberme'], ['talus', 'talus', 'Talus'], ['gradins', 'gradins', 'Gradins']] as const) {
    const liste: Modele[] = Array.isArray(m.fouille?.[cle]) ? m.fouille[cle] : []
    liste.forEach((ob, i) => objets.push({ nom: String(ob?.nom ?? `${defaut}${i + 1}`), type, etendue: { cotes: lireCotes(ob?.cote_paroi), de: null, a: null }, largeur: largeurObjet(ob), phases: Array.isArray(ob?.phases) ? ob.phases : [] }))
  }
  const zonesTerrain: ZoneTerrainP[] = m.terrain && (m.terrain.pente_beta !== undefined || m.terrain.profil !== undefined)
    ? [{ nom: 'terrain', etendue: { cotes: lireCotes(m.terrain.cote_paroi), de: null, a: null }, cote: null, pente_beta: num(m.terrain.pente_beta) }] : []
  const positions: PositionP[] = []
  surcharges.forEach((s, i) => {
    if (s?.cote_paroi === undefined && s?.emprise === undefined && s?.position === undefined && s?.trace === undefined) return
    const emp = s.emprise
    positions.push({ surcharge: nomS(s, i), type: String(s.type ?? 'bande'),
      etendue: { cotes: lireCotes(s.cote_paroi), de: emp && !Array.isArray(emp) ? num(emp.de) : null, a: emp && !Array.isArray(emp) ? num(emp.a) : null },
      position: paire(s.position), emprise: Array.isArray(emp) ? paire(emp) : null,
      trace: s.trace && paire(s.trace.de) && paire(s.trace.a) ? [paire(s.trace.de)!, paire(s.trace.a)!] : null })
  })
  return { contour, ferme: true, cotes: plan.cotes && typeof plan.cotes === 'object' ? plan.cotes : {},
    appuis: (Array.isArray(plan.appuis) ? plan.appuis : []).filter((a: Modele) => paire(a?.de) && paire(a?.a)).map((a: Modele) => ({ appui: String(a.appui), de: paire(a.de)!, a: paire(a.a)! })),
    objets, zonesFond: [], zonesTerrain, positions, ancienne: anciens.length > 0, anciens }
}

/** Cadrage du dessin : boîte englobante du contour et des positions, élargie d'une marge. */
export function cadrage(g: GeometrieP, marge = 0.3): { xmin: number; xmax: number; ymin: number; ymax: number } {
  const pts: Point2[] = [...g.contour, ...g.positions.flatMap((p) => (p.position ? [p.position] : p.trace ? p.trace : []))]
  if (!pts.length) return { xmin: -1, xmax: 21, ymin: -1, ymax: 13 }
  let xmin = Math.min(...pts.map((p) => p[0])), xmax = Math.max(...pts.map((p) => p[0]))
  let ymin = Math.min(...pts.map((p) => p[1])), ymax = Math.max(...pts.map((p) => p[1]))
  const d = Math.max(xmax - xmin, ymax - ymin, 1) * marge
  xmin -= d; xmax += d; ymin -= d; ymax += d
  return { xmin, xmax, ymin, ymax }
}

/** Polygone (en plan) d'un objet ou d'une zone décrit par une étendue le long d'une arête, sur une largeur
 *  mesurée depuis la paroi (sens +1 vers la fouille, −1 vers la terre). */
export function bandeSur(a: AreteP, e: EtendueP, largeur: number, sens: 1 | -1): Point2[] {
  const [de, fin] = tronconSur(e, a)
  const P = (s: number, d: number): Point2 => [a.A[0] + a.t[0] * s + a.ni[0] * d * sens, a.A[1] + a.t[1] * s + a.ni[1] * d * sens]
  return [P(de, 0), P(fin, 0), P(fin, largeur), P(de, largeur)]
}
