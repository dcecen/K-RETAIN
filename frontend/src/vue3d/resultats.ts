// Projection des résultats du moteur sur la géométrie de la paroi (calque « Résultats »).
// Les valeurs viennent uniquement des résultats du calcul ; tout est mis en cache par phase.
//
// Conventions : déplacement y positif vers la fouille (mm) ; moment M positif quand la face
// côté fouille est tendue (kN·m/m) ; tranchant V = dM/dz (kN/m ; en pseudo-3D : statique des lignes verticales) ; pressions en kPa.
import * as THREE from 'three'
import type { Pressions, Resultats, Verif } from '../lib/api'
import { nb } from '../lib/format'
import { demiEpaisseur, lambert } from './elements'
export { tauxAppui } from './appuis'
import { attenuationAngle, hacher, interpBorne, versThree, type Arete } from './geometrie'
import { classeTaux, COULEURS_TAUX, couleurValeur, type NomPalette, type Seuils, SEUILS_DEFAUT } from './palettes'
import { modeCalque, reglageCalque, type Contexte, type Element, type Spec } from './scene'

export const NZ = 48          // lignes de la grille de paroi selon z
const COULEUR_NEUTRE = 0xb8c0cc
const COULEUR_POSITIF = 0xc7362c   // face fouille tendue (M > 0) : rouge
const COULEUR_NEGATIF = 0x2c5da8   // bleu
const COULEUR_EAU = 0x3b8fd9
const COULEUR_TERRE = 0x8b6b3e
const COULEUR_FOUILLE = 0x2e7d4f

// ------------------------------------------------------------------ accès aux résultats
/** Fonction z → valeur pour un point de paroi (abscisse développée s), d'après le profil 2D ou le champ pseudo-3D. */
export function profilValeur(res: Resultats, phase: number, quoi: 'y' | 'M' | 'V', s: number): ((z: number) => number) | null {
  const ph = res.phases[phase]
  if (!ph?.ok) return null
  const p3 = res.pseudo3d
  if (p3) {
    const q = p3.phases[phase]
    const champ = quoi === 'M' ? q?.M : quoi === 'V' ? q?.V : q?.y_mm
    if (q?.ok && champ) {
      const S = p3.s
      let i = 0
      while (i < S.length - 1 && S[i + 1] < s) i++
      const i1 = Math.min(i + 1, S.length - 1)
      const t = S[i1] === S[i] ? 0 : Math.min(Math.max((s - S[i]) / (S[i1] - S[i]), 0), 1)
      const a = champ[i]
      const b = champ[i1]
      return (z) => (1 - t) * interpBorne(p3.z, a, z) + t * interpBorne(p3.z, b, z)
    }
  }
  if (quoi === 'y') return (z) => interpBorne(ph.z!, ph.y_mm!, z)
  const zd = ph.z_diag!
  const v = quoi === 'M' ? ph.M! : ph.V!
  return (z) => interpBorne(zd, v, z)
}

/** Bornes d'une grandeur sur toutes les phases (échelle fixe) ou sur une phase. */
export function bornes(res: Resultats, quoi: 'y' | 'M' | 'V' | 'yabs', phase: number | null): { min: number; max: number } {
  let lo = Infinity
  let hi = -Infinity
  const phases = phase === null ? res.phases : [res.phases[phase]]
  for (const ph of phases) {
    if (!ph?.ok) continue
    const idx = res.phases.indexOf(ph)
    const p3 = res.pseudo3d?.phases[idx]
    const champ = quoi === 'M' ? p3?.M : quoi === 'V' ? p3?.V : p3?.y_mm
    const vals: number[] = p3?.ok && champ ? champ.flat() : quoi === 'M' ? ph.M! : quoi === 'V' ? ph.V! : ph.y_mm!
    for (const v of vals) {
      const u = quoi === 'yabs' ? Math.abs(v) : v
      if (u < lo) lo = u
      if (u > hi) hi = u
    }
  }
  if (!Number.isFinite(lo)) return { min: 0, max: 1 }
  if (quoi === 'yabs') lo = 0
  if (hi - lo < 1e-9) hi = lo + 1
  return { min: lo, max: hi }
}

/** Amplification « auto » : la flèche maximale de toutes les phases vaut `cible` m à l'écran. */
export function amplificationAuto(res: Resultats, cible = 2.0): number {
  const b = bornes(res, 'yabs', null)
  return b.max > 1e-6 ? (cible * 1000) / b.max : 1
}

export function amplification(ctx: Contexte): number {
  const r = reglageCalque<number | string>(ctx.scene.calques, 'resultats.deformee', 'amplification', 'auto')
  if (r === 'auto' || r === 0) return amplificationAuto(ctx.d.res)
  return Math.min(Math.max(Number(r) || 1, 1), 2000)
}

// ------------------------------------------------------------------ taux de travail de la paroi
const NOMS_PAROI = /^(Palplanches|Paroi moulée|Profilés de berlinoise|Blindage|Pieux)/
/** Taux de travail de la paroi : zone courante (au-dessus du fond) et fiche (mobilisation de la butée incluse). */
export function tauxParoi(verifs: Verif[] | undefined): { courant: number | null; fiche: number | null; verifiable: boolean } {
  const v = (verifs ?? []).filter((x) => NOMS_PAROI.test(x.nom))
  const butee = (verifs ?? []).filter((x) => x.nom.startsWith('Mobilisation de la butée'))
  const pire = (l: Verif[]) => {
    const t = l.map((x) => x.taux).filter((x): x is number => x !== null && Number.isFinite(x))
    return t.length ? Math.max(...t) : null
  }
  const c = pire(v)
  const f = pire([...v, ...butee])
  return { courant: c, fiche: f, verifiable: v.some((x) => x.etat !== 'non_verifiable') }
}

function seuils(ctx: Contexte): Seuils {
  const c = ctx.scene.calques
  return { orange: reglageCalque(c, 'resultats.taux', 'orange', SEUILS_DEFAUT.orange), rouge: reglageCalque(c, 'resultats.taux', 'rouge', SEUILS_DEFAUT.rouge) }
}

// ------------------------------------------------------------------ surface de résultats (déformée + couleurs)
export type ModeCouleur = 'aucun' | 'deplacement' | 'moment' | 'tranchant' | 'taux'

/** Calque de couleur actif sur la paroi (un seul à la fois, exclusivité gérée par calques.ts). */
export function modeCouleurActif(ctx: Contexte): ModeCouleur {
  const c = ctx.scene.calques
  if (c.visible('resultats.taux')) return 'taux'
  if (c.visible('resultats.deplacement')) return 'deplacement'
  if (c.visible('resultats.moment') && modeCalque(c, 'resultats.moment', 'couleur') === 'couleur') return 'moment'
  if (c.visible('resultats.tranchant') && modeCalque(c, 'resultats.tranchant', 'ailettes') === 'couleur') return 'tranchant'
  return 'aucun'
}

export interface EchelleCouleur { quoi: 'y' | 'yabs' | 'M' | 'V'; min: number; max: number; palette: NomPalette; fixe: boolean }

export function echelleCouleur(ctx: Contexte, mode: ModeCouleur): EchelleCouleur | null {
  const c = ctx.scene.calques
  const res = ctx.d.res
  if (mode === 'deplacement') {
    const signe = modeCalque(c, 'resultats.deplacement', 'absolu') === 'signe'
    const fixe = reglageCalque(c, 'resultats.deplacement', 'echelle', 'fixe') === 'fixe'
    const b = bornes(res, signe ? 'y' : 'yabs', fixe ? null : ctx.phase)
    return { quoi: signe ? 'y' : 'yabs', ...b, palette: reglageCalque(c, 'resultats.deplacement', 'palette', signe ? 'signe' : 'divergente') as NomPalette, fixe }
  }
  if (mode === 'moment' || mode === 'tranchant') {
    const id = mode === 'moment' ? 'resultats.moment' : 'resultats.tranchant'
    const fixe = reglageCalque(c, id, 'echelle', 'fixe') === 'fixe'
    const quoi = mode === 'moment' ? 'M' : 'V'
    const b = bornes(res, quoi, fixe ? null : ctx.phase)
    const m = Math.max(Math.abs(b.min), Math.abs(b.max))   // échelle symétrique : le zéro reste au centre de la palette
    return { quoi, min: -m, max: m, palette: reglageCalque(c, id, 'palette', 'signe') as NomPalette, fixe }
  }
  return null
}

interface Grille { ns: number; nz: number; s: Float32Array; z: Float32Array; sl: Float32Array }

function grilleArete(a: Arete, pied: number, tete: number): Grille {
  const ns = Math.max(2, Math.round(a.L / 1.0)) + 1
  const s = new Float32Array(ns)
  const sl = new Float32Array(ns)
  for (let i = 0; i < ns; i++) { sl[i] = (a.L * i) / (ns - 1); s[i] = a.s0 + sl[i] }
  const z = new Float32Array(NZ)
  for (let j = 0; j < NZ; j++) z[j] = pied + ((tete - pied) * j) / (NZ - 1)
  return { ns, nz: NZ, s, z, sl }
}

const _c = new THREE.Color()

/** Résultats et phase à utiliser pour un point de paroi (coupe du tronçon en projet à coupes, sinon résultats affichés). */
export function sourcePour(ctx: Contexte, k: number, sl: number): { res: Resultats; phase: number; coupe: string | null } {
  return ctx.d.resultatsPour?.(k, sl, ctx.phase) ?? { res: ctx.d.res, phase: ctx.phase, coupe: null }
}

/** Décalage de la déformée (m) en chaque nœud de la grille pour une phase : y(z) × amplification × atténuation aux angles. */
function decalages(ctx: Contexte, a: Arete, g: Grille, phase: number, amp: number, enveloppe: 'max' | 'min' | null = null): Float32Array | null {
  const src = sourcePour(ctx, a.k, g.sl[Math.floor(g.ns / 2)])
  const res = src.res
  if (!enveloppe) phase = src.phase
  const out = new Float32Array(g.ns * g.nz)
  const p3 = !!res.pseudo3d
  const la = Math.min(0.25 * a.L, ctx.d.m.paroi.tete - ctx.d.m.paroi.pied)
  let f: ((z: number) => number) | null
  if (enveloppe) {
    const env = res.enveloppes
    if (!env.z) return null
    const v = enveloppe === 'max' ? env.y_max_mm! : env.y_min_mm!
    f = (z) => interpBorne(env.z!, v, z)
  } else f = profilValeur(res, phase, 'y', 0)
  if (!f) return null
  for (let i = 0; i < g.ns; i++) {
    const fi = p3 && !enveloppe ? profilValeur(res, phase, 'y', g.s[i])! : f
    const att = p3 ? 1 : attenuationAngle(g.sl[i], a.L, la)
    for (let j = 0; j < g.nz; j++) out[i * g.nz + j] = (fi(g.z[j]) / 1000) * amp * att
  }
  return out
}

function couleursGrille(ctx: Contexte, a: Arete, g: Grille, mode: ModeCouleur, ech: EchelleCouleur | null): Float32Array {
  const out = new Float32Array(3 * g.ns * g.nz)
  const src = sourcePour(ctx, a.k, g.sl[Math.floor(g.ns / 2)])
  const res = src.res
  const phase = src.phase
  if (mode === 'taux') {
    const t = tauxParoi(res.verifications)
    const s = seuils(ctx)
    const fond = ctx.ph.terrain_aval
    for (let i = 0; i < g.ns; i++) for (let j = 0; j < g.nz; j++) {
      const z = g.z[j]
      const taux = z < fond ? t.fiche : t.courant
      _c.setHex(COULEURS_TAUX[t.verifiable || (z < fond && taux !== null) ? classeTaux(taux, s) : 'gris'])
      out.set([_c.r, _c.g, _c.b], 3 * (i * g.nz + j))
    }
    return out
  }
  if (mode === 'aucun' || !ech) {
    _c.setHex(COULEUR_NEUTRE)
    for (let k = 0; k < g.ns * g.nz; k++) out.set([_c.r, _c.g, _c.b], 3 * k)
    return out
  }
  const quoi = ech.quoi === 'yabs' ? 'y' : ech.quoi
  for (let i = 0; i < g.ns; i++) {
    const f = profilValeur(res, phase, quoi, g.s[i])
    for (let j = 0; j < g.nz; j++) {
      let v = f ? f(g.z[j]) : 0
      if (ech.quoi === 'yabs') v = Math.abs(v)
      couleurValeur(v, ech.min, ech.max, ech.palette, _c)
      out.set([_c.r, _c.g, _c.b], 3 * (i * g.nz + j))
    }
  }
  return out
}

function geoGrille(g: Grille): THREE.BufferGeometry {
  const geo = new THREE.BufferGeometry()
  geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(3 * g.ns * g.nz), 3))
  geo.setAttribute('color', new THREE.BufferAttribute(new Float32Array(3 * g.ns * g.nz), 3))
  const idx: number[] = []
  for (let i = 0; i < g.ns - 1; i++) for (let j = 0; j < g.nz - 1; j++) {
    const q = i * g.nz + j
    idx.push(q, q + 1, q + g.nz + 1, q, q + g.nz + 1, q + g.nz)
  }
  geo.setIndex(idx)
  return geo
}

function positionsGrille(a: Arete, g: Grille, offset: number, dec: Float32Array | null, out: Float32Array) {
  const v = new THREE.Vector3()
  for (let i = 0; i < g.ns; i++) for (let j = 0; j < g.nz; j++) {
    const k = i * g.nz + j
    const o = offset + (dec ? dec[k] : 0)
    versThree(a.A[0] + a.t[0] * g.sl[i] + a.ni[0] * o, a.A[1] + a.t[1] * g.sl[i] + a.ni[1] * o, g.z[j], v)
    out[3 * k] = v.x; out[3 * k + 1] = v.y; out[3 * k + 2] = v.z
  }
}

function specsSurface(ctx: Contexte): Spec[] {
  const geo = ctx.d.geo
  const p = ctx.d.m.paroi
  const out: Spec[] = []
  const offset = demiEpaisseur(p) + 0.03
  const calquesSurface = ['resultats.deformee', 'resultats.deplacement', 'resultats.moment', 'resultats.tranchant', 'resultats.taux']
  for (const a of geo.aretes) {
    if (a.L < 1e-6) continue
    const id = `resultats.surface.${a.k}`
    const cle = hacher(`${id}|${a.A}|${a.B}|${p.pied}|${p.tete}|${offset}|${NZ}`)
    out.push({
      id, cle, creer: (cx) => {
        const g = grilleArete(a, p.pied, p.tete)
        const bg = cx.fab.geo(geoGrille(g))
        const mat = cx.fab.mat(new THREE.MeshLambertMaterial({ vertexColors: true, side: THREE.DoubleSide, transparent: true, opacity: 0.95 }))
        const mesh = cx.fab.obj(new THREE.Mesh(bg, mat))
        // paroi initiale en fantôme (option de la déformée)
        const bgF = cx.fab.geo(geoGrille(g))
        const matF = cx.fab.mat(new THREE.MeshBasicMaterial({ color: 0x8a97a8, transparent: true, opacity: 0.18, side: THREE.DoubleSide, depthWrite: false, wireframe: true }))
        const fantome = cx.fab.obj(new THREE.Mesh(bgF, matF))
        positionsGrille(a, g, offset, null, bgF.attributes.position.array as Float32Array)
        ;(bgF.attributes.position as THREE.BufferAttribute).needsUpdate = true
        const groupe = cx.fab.obj(new THREE.Group())
        groupe.add(mesh, fantome)
        const cacheDec = new Map<string, Float32Array | null>()
        const cacheCoul = new Map<string, Float32Array>()
        const el: Element = { id, cle, noeud: 'resultats', calque: 'resultats.deformee', calques: calquesSurface, objet: groupe, selection: `paroi:${a.k}`, visiblePhase: true }
        el.appliquerPhase = (k) => {
          const c = k.scene.calques
          const deformee = c.visible('resultats.deformee')
          const amp = deformee ? amplification(k) : 0
          const srcK = sourcePour(k, a.k, a.L / 2)
          const cleD = `${k.phase}|${amp}|${srcK.coupe ?? ''}|${srcK.phase}`
          if (!cacheDec.has(cleD)) cacheDec.set(cleD, deformee ? decalages(k, a, g, k.phase, amp) : null)
          const dec = cacheDec.get(cleD) ?? null
          const pa = bg.attributes.position as THREE.BufferAttribute
          positionsGrille(a, g, offset, dec, pa.array as Float32Array)
          pa.needsUpdate = true
          bg.computeVertexNormals()
          bg.computeBoundingSphere()
          const mode = modeCouleurActif(k)
          const ech = echelleCouleur(k, mode)
          const cleC = `${k.phase}|${srcK.coupe ?? ''}|${srcK.phase}|${mode}|${ech ? `${ech.quoi}|${ech.min}|${ech.max}|${ech.palette}` : ''}|${mode === 'taux' ? JSON.stringify(seuils(k)) + k.ph.terrain_aval : ''}`
          if (!cacheCoul.has(cleC)) cacheCoul.set(cleC, couleursGrille(k, a, g, mode, ech))
          const ca = bg.attributes.color as THREE.BufferAttribute
          ;(ca.array as Float32Array).set(cacheCoul.get(cleC)!)
          ca.needsUpdate = true
          fantome.visible = deformee && reglageCalque(c, 'resultats.deformee', 'fantome', true)
          el.visiblePhase = !!k.ph.ok
        }
        el.majDonnees = () => { cacheDec.clear(); cacheCoul.clear() }
        el.surligner = (actif) => { mat.emissive.setHex(actif ? 0x332200 : 0x000000) }
        return el
      },
    })
  }
  return out
}

// ------------------------------------------------------------------ ailettes (diagrammes perpendiculaires à la paroi)
export interface Ailette { quoi: 'M' | 'V' | 'p_terre' | 'p_fouille'; k: number; sl: number }

/** Stations des ailettes le long de chaque arête (une tous les ~8 m, au moins une par côté). */
export function stationsAilettes(aretes: Arete[]): { k: number; sl: number }[] {
  const out: { k: number; sl: number }[] = []
  for (const a of aretes) {
    if (a.L < 1e-6) continue
    const n = Math.max(1, Math.round(a.L / 8))
    for (let i = 0; i < n; i++) out.push({ k: a.k, sl: ((i + 0.5) * a.L) / n })
  }
  return out
}

/** Échelle des ailettes : la valeur maximale (toutes phases) occupe `longueur` m. */
export function echelleAilette(res: Resultats, quoi: 'M' | 'V', H: number): number {
  const b = bornes(res, quoi, null)
  const m = Math.max(Math.abs(b.min), Math.abs(b.max), 1e-9)
  return (0.3 * H) / m
}

export function geoRuban(nz: number): THREE.BufferGeometry {
  const g = new THREE.BufferGeometry()
  g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(3 * 2 * nz), 3))
  g.setAttribute('color', new THREE.BufferAttribute(new Float32Array(3 * 2 * nz), 3))
  const idx: number[] = []
  for (let j = 0; j < nz - 1; j++) idx.push(2 * j, 2 * j + 1, 2 * j + 3, 2 * j, 2 * j + 3, 2 * j + 2)
  g.setIndex(idx)
  return g
}

/** Remplit un ruban : base sur la paroi, extrémité décalée de `val(z) × echelle` selon ±ni ; couleur par signe ou fixe. */
export function remplirRuban(g: THREE.BufferGeometry, a: Pick<Arete, 'A' | 't' | 'ni'>, sl: number, z: Float32Array, offset: number, sens: 1 | -1, val: (z: number) => number,
  echelle: number, couleur: (v: number) => number) {
  const pos = g.attributes.position.array as Float32Array
  const col = g.attributes.color.array as Float32Array
  const v = new THREE.Vector3()
  for (let j = 0; j < z.length; j++) {
    const x0 = a.A[0] + a.t[0] * sl
    const y0 = a.A[1] + a.t[1] * sl
    versThree(x0 + a.ni[0] * offset * sens, y0 + a.ni[1] * offset * sens, z[j], v)
    pos.set([v.x, v.y, v.z], 6 * j)
    const w = val(z[j])
    const d = offset * sens + w * echelle * sens
    versThree(x0 + a.ni[0] * d, y0 + a.ni[1] * d, z[j], v)
    pos.set([v.x, v.y, v.z], 6 * j + 3)
    _c.setHex(couleur(w))
    col.set([_c.r, _c.g, _c.b], 6 * j)
    col.set([_c.r, _c.g, _c.b], 6 * j + 3)
  }
  ;(g.attributes.position as THREE.BufferAttribute).needsUpdate = true
  ;(g.attributes.color as THREE.BufferAttribute).needsUpdate = true
  g.computeVertexNormals()
  g.computeBoundingSphere()
}

export function zGrille(pied: number, tete: number, n = 2 * NZ): Float32Array {
  const z = new Float32Array(n)
  for (let j = 0; j < n; j++) z[j] = pied + ((tete - pied) * j) / (n - 1)
  return z
}

function specsAilettes(ctx: Contexte): Spec[] {
  const geo = ctx.d.geo
  const p = ctx.d.m.paroi
  const H = p.tete - p.pied
  const offset = demiEpaisseur(p) + 0.05
  const stations = stationsAilettes(geo.aretes)
  const out: Spec[] = []
  const signe = (v: number) => (v >= 0 ? COULEUR_POSITIF : COULEUR_NEGATIF)
  for (const quoi of ['M', 'V'] as const) {
    const calque = quoi === 'M' ? 'resultats.moment' : 'resultats.tranchant'
    stations.forEach((st, i) => {
      const id = `resultats.ailette.${quoi}.${i}`
      const a = geo.aretes[st.k]
      const cle = hacher(`${id}|${a.A}|${a.B}|${st.sl}|${p.pied}|${p.tete}`)
      out.push({
        id, cle, creer: (cx) => {
          const z = zGrille(p.pied, p.tete)
          const g = cx.fab.geo(geoRuban(z.length))
          const mesh = cx.fab.obj(new THREE.Mesh(g, cx.fab.mat(new THREE.MeshLambertMaterial({ vertexColors: true, side: THREE.DoubleSide, transparent: true, opacity: 0.85 }))))
          const el: Element = { id, cle, noeud: 'resultats', calque, objet: mesh, visiblePhase: true }
          let ech = echelleAilette(cx.d.res, quoi, H)
          let extreme = { v: 0, z: 0 }
          el.appliquerPhase = (k) => {
            const c = k.scene.calques
            const mode = modeCalque(c, calque, quoi === 'M' ? 'couleur' : 'ailettes')
            el.visiblePhase = !!k.ph.ok && mode === 'ailettes'
            if (!el.visiblePhase) return
            const src = sourcePour(k, a.k, st.sl)
            const f = profilValeur(src.res, src.phase, quoi, a.s0 + st.sl)
            if (!f) { el.visiblePhase = false; return }
            const facteur = reglageCalque(c, calque, 'echelle_ailettes', 1)
            remplirRuban(g, a, st.sl, z, offset, 1, f, ech * facteur, signe)
            extreme = { v: 0, z: p.tete }
            for (const zz of z) { const v = f(zz); if (Math.abs(v) > Math.abs(extreme.v)) extreme = { v, z: zz } }
          }
          el.majDonnees = () => { ech = echelleAilette(cx.d.res, quoi, H) }
          el.etiquettes = (k, o) => {
            if (i % Math.max(1, Math.round(stations.length / 4)) !== 0 && stations.length > 4) return
            const d = offset + extreme.v * ech * reglageCalque(k.scene.calques, calque, 'echelle_ailettes', 1)
            o.push({ id: `${id}.max`, pos: versThree(a.A[0] + a.t[0] * st.sl + a.ni[0] * d, a.A[1] + a.t[1] * st.sl + a.ni[1] * d, extreme.z),
              texte: `${quoi} = ${nb(extreme.v, quoi === 'M' ? 0 : 1)} ${quoi === 'M' ? 'kN·m/m' : 'kN/m'}`, calque, classe: 'valeur' })
          }
          return el
        },
      })
    })
  }
  // pressions des terres et de l'eau : rubans mobilisée + eau par face, limites en pointillé
  stations.forEach((st, i) => {
    const id = `resultats.pressions.${i}`
    const a = geo.aretes[st.k]
    const cle = hacher(`${id}|${a.A}|${a.B}|${st.sl}|${p.pied}|${p.tete}`)
    out.push({
      id, cle, creer: (cx) => {
        const z = zGrille(p.pied, p.tete)
        const groupe = cx.fab.obj(new THREE.Group())
        const rubans: Record<string, THREE.BufferGeometry> = {}
        const lignes: Record<string, THREE.BufferGeometry> = {}
        for (const face of ['terre', 'fouille']) {
          for (const nom of ['p', 'u']) {
            const g = cx.fab.geo(geoRuban(z.length))
            rubans[`${face}.${nom}`] = g
            groupe.add(cx.fab.obj(new THREE.Mesh(g, cx.fab.mat(new THREE.MeshLambertMaterial({ vertexColors: true, side: THREE.DoubleSide, transparent: true, opacity: nom === 'u' ? 0.5 : 0.8 })))))
          }
          for (const nom of ['pa', 'pp']) {
            const g = cx.fab.geo(new THREE.BufferGeometry())
            g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(3 * z.length), 3))
            lignes[`${face}.${nom}`] = g
            const l = cx.fab.obj(new THREE.Line(g, cx.fab.mat(new THREE.LineDashedMaterial({ color: nom === 'pa' ? 0x9a7b4f : 0x4f7b9a, dashSize: 0.3, gapSize: 0.2 }))))
            l.frustumCulled = false
            groupe.add(l)
          }
        }
        const el: Element = { id, cle, noeud: 'resultats', calque: 'resultats.pressions', objet: groupe, visiblePhase: true }
        let echP = 1
        let plafond = 1   // les limites (butée surtout) sont tronquées à 1,8 × la pression mobilisée maximale, comme sur la coupe 2D
        const calculerEchelle = (res: Resultats) => {
          let m = 1
          for (const ph of res.phases) if (ph.ok && ph.pressions) m = Math.max(m, ...ph.pressions.amont.p, ...ph.pressions.aval.p, ...ph.eau!.u_amont, ...ph.eau!.u_aval)
          echP = (0.3 * H) / m
          plafond = 1.8 * m
        }
        calculerEchelle(cx.d.res)
        el.appliquerPhase = (k) => {
          const src = sourcePour(k, a.k, st.sl)
          const ph = src.res.phases[src.phase] ?? k.ph
          el.visiblePhase = !!ph.ok && !!ph.pressions
          if (!el.visiblePhase) return
          const mode = modeCalque(k.scene.calques, 'resultats.pressions', 'deux')
          const facteur = reglageCalque(k.scene.calques, 'resultats.pressions', 'echelle_ailettes', 1) * echP
          const faces: Array<['terre' | 'fouille', Pressions, number[], 1 | -1]> = [
            ['terre', ph.pressions!.amont, ph.eau!.u_amont, -1], ['fouille', ph.pressions!.aval, ph.eau!.u_aval, 1]]
          for (const [face, pr, u, sens] of faces) {
            const vis = mode === 'deux' || mode === face
            for (const nom of ['p', 'u', 'pa', 'pp']) {
              const obj = groupe.children[Object.keys(rubans).concat(Object.keys(lignes)).indexOf(`${face}.${nom}`)]
              if (obj) obj.visible = vis
            }
            if (!vis) continue
            const fp = (zz: number) => (zz <= (face === 'terre' ? ph.terrain_amont : ph.terrain_aval) ? interpBorne(pr.z, pr.p, zz) : 0)
            const fu = (zz: number) => interpBorne(ph.eau!.z, u, zz)
            remplirRuban(rubans[`${face}.p`], a, st.sl, z, offset, sens, fp, facteur, () => (face === 'terre' ? COULEUR_TERRE : COULEUR_FOUILLE))
            // l'eau s'ajoute à la pression des terres (ruban posé sur le précédent)
            remplirRuban(rubans[`${face}.u`], a, st.sl, z, offset, sens, (zz) => fp(zz) + fu(zz), facteur, () => COULEUR_EAU)
            const posU = rubans[`${face}.u`].attributes.position.array as Float32Array
            const posP = rubans[`${face}.p`].attributes.position.array as Float32Array
            for (let j = 0; j < z.length; j++) posU.set(posP.subarray(6 * j + 3, 6 * j + 6), 6 * j)
            ;(rubans[`${face}.u`].attributes.position as THREE.BufferAttribute).needsUpdate = true
            for (const nom of ['pa', 'pp'] as const) {
              const g = lignes[`${face}.${nom}`]
              const arr = g.attributes.position.array as Float32Array
              const v = new THREE.Vector3()
              for (let j = 0; j < z.length; j++) {
                const lim = Math.min(plafond, z[j] <= (face === 'terre' ? ph.terrain_amont : ph.terrain_aval) ? interpBorne(pr.z, pr[nom], z[j]) : 0)
                const d = (offset + lim * facteur) * sens
                versThree(a.A[0] + a.t[0] * st.sl + a.ni[0] * d, a.A[1] + a.t[1] * st.sl + a.ni[1] * d, z[j], v)
                arr.set([v.x, v.y, v.z], 3 * j)
              }
              ;(g.attributes.position as THREE.BufferAttribute).needsUpdate = true
              const ligne = groupe.children.find((o) => (o as THREE.Line).geometry === g) as THREE.Line
              ligne.computeLineDistances()
            }
          }
        }
        el.majDonnees = () => calculerEchelle(cx.d.res)
        return el
      },
    })
  })
  return out
}

// ------------------------------------------------------------------ enveloppes (fantôme)
function specsEnveloppes(ctx: Contexte): Spec[] {
  const geo = ctx.d.geo
  const p = ctx.d.m.paroi
  const H = p.tete - p.pied
  const offset = demiEpaisseur(p) + 0.03
  const out: Spec[] = []
  if (!ctx.d.res.enveloppes.z) return out
  for (const a of geo.aretes) {
    if (a.L < 1e-6) continue
    const id = `resultats.enveloppe.${a.k}`
    const cle = hacher(`${id}|${a.A}|${a.B}|${p.pied}|${p.tete}`)
    out.push({
      id, cle, creer: (cx) => {
        const g = grilleArete(a, p.pied, p.tete)
        const mat = cx.fab.mat(new THREE.MeshBasicMaterial({ color: 0x6b9ccc, transparent: true, opacity: 0.25, side: THREE.DoubleSide, depthWrite: false }))
        const gMax = cx.fab.geo(geoGrille(g))
        const gMin = cx.fab.geo(geoGrille(g))
        const groupe = cx.fab.obj(new THREE.Group())
        groupe.add(cx.fab.obj(new THREE.Mesh(gMax, mat)), cx.fab.obj(new THREE.Mesh(gMin, mat)))
        // moment : deux rubans fantômes (M_max, M_min) au milieu de l'arête
        const z = zGrille(p.pied, p.tete)
        const rMax = cx.fab.geo(geoRuban(z.length))
        const rMin = cx.fab.geo(geoRuban(z.length))
        const matR = cx.fab.mat(new THREE.MeshBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.3, side: THREE.DoubleSide, depthWrite: false }))
        groupe.add(cx.fab.obj(new THREE.Mesh(rMax, matR)), cx.fab.obj(new THREE.Mesh(rMin, matR)))
        const el: Element = { id, cle, noeud: 'resultats', calque: 'resultats.enveloppes', objet: groupe, visiblePhase: true }
        let fait = ''
        el.appliquerPhase = (k) => {
          const mode = modeCalque(k.scene.calques, 'resultats.enveloppes', 'deformee')
          const amp = amplification(k)
          const cleF = `${mode}|${amp}`
          groupe.children[0].visible = groupe.children[1].visible = mode === 'deformee'
          groupe.children[2].visible = groupe.children[3].visible = mode === 'moment'
          if (fait === cleF) return
          fait = cleF
          if (mode === 'deformee') {
            for (const [gg, env] of [[gMax, 'max'], [gMin, 'min']] as const) {
              positionsGrille(a, g, offset, decalages(k, a, g, 0, amp, env), gg.attributes.position.array as Float32Array)
              ;(gg.attributes.position as THREE.BufferAttribute).needsUpdate = true
              gg.computeBoundingSphere()
            }
          } else {
            const env = k.d.res.enveloppes
            const ech = echelleAilette(k.d.res, 'M', H) * reglageCalque(k.scene.calques, 'resultats.moment', 'echelle_ailettes', 1)
            remplirRuban(rMax, a, a.L / 2, z, offset, 1, (zz) => interpBorne(env.z_diag!, env.M_max!, zz), ech, () => COULEUR_POSITIF)
            remplirRuban(rMin, a, a.L / 2, z, offset, 1, (zz) => interpBorne(env.z_diag!, env.M_min!, zz), ech, () => COULEUR_NEGATIF)
          }
        }
        el.majDonnees = () => { fait = '' }
        return el
      },
    })
  }
  return out
}

// ------------------------------------------------------------------ étiquettes d'extrêmes
export function extremes(res: Resultats): { id: string; texte: string; z: number; phase: string; appui?: string }[] {
  const d = res.dimensionnant
  const out: { id: string; texte: string; z: number; phase: string; appui?: string }[] = []
  if (d.deplacement) {
    const ph = res.phases.find((p) => p.nom === d.deplacement!.phase)
    out.push({ id: 'y', texte: `y max = ${nb(d.deplacement.valeur_mm, 1)} mm à ${nb(ph?.synthese?.z_y_max ?? 0, 2)} m`, z: ph?.synthese?.z_y_max ?? 0, phase: d.deplacement.phase })
  }
  for (const [cle, lab] of [['moment_positif', 'M max'], ['moment_negatif', 'M min']] as const) {
    const m = d[cle]
    if (!m) continue
    const ph = res.phases.find((p) => p.nom === m.phase)
    let z = 0
    if (ph?.M) { const i = cle === 'moment_positif' ? ph.M.indexOf(Math.max(...ph.M)) : ph.M.indexOf(Math.min(...ph.M)); z = ph.z_diag![i] ?? 0 }
    out.push({ id: cle, texte: `${lab} = ${nb(m.valeur, 0)} kN·m/m à ${nb(z, 2)} m`, z, phase: m.phase })
  }
  for (const [nom, a] of Object.entries(d.appuis ?? {})) {
    const def = res.appuis.find((x) => x.nom === nom)
    out.push({ id: `appui.${nom}`, texte: `${nom} max = ${nb(a.effort_kN_m, 0)} kN/m · ${nb(a.effort_axial_kN, 0)} kN`, z: def?.cote ?? 0, phase: a.phase, appui: nom })
  }
  return out
}

function specsExtremes(ctx: Contexte): Spec[] {
  const geo = ctx.d.geo
  const a = geo.aretes.reduce((m, x) => (x.L > m.L ? x : m), geo.aretes[0])
  const id = 'resultats.extremes'
  const cle = hacher(`${id}|${a.A}|${a.B}`)
  return [{
    id, cle, creer: (cx) => {
      const groupe = cx.fab.obj(new THREE.Group())
      const el: Element = { id, cle, noeud: 'resultats', calque: 'resultats.extremes', objet: groupe, visiblePhase: true }
      let liste = extremes(cx.d.res)
      el.majDonnees = (k) => { liste = extremes(k.d.res) }
      el.etiquettes = (_k, o) => {
        const d = demiEpaisseur(ctx.d.m.paroi) + 0.3
        liste.forEach((e, i) => {
          const sl = a.L * (0.3 + 0.1 * (i % 5))
          o.push({ id: `extreme.${e.id}`, pos: versThree(a.A[0] + a.t[0] * sl + a.ni[0] * d, a.A[1] + a.t[1] * sl + a.ni[1] * d, e.z),
            texte: `${e.texte} (${e.phase})`, calque: 'resultats.extremes', classe: 'extreme', selection: e.appui ? `appui:${e.appui}` : undefined })
        })
      }
      return el
    },
  }]
}

export const FABRIQUES_RESULTATS_PAROI = [specsSurface, specsAilettes, specsEnveloppes, specsExtremes]

export { lambert }
