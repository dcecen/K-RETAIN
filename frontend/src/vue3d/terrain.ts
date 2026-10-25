// Géométrie du terrain dans la maquette : terrain en pente ou remblai localisé côté terre (volume
// au-dessus de la cote amont suivant le profil déclaré), risbermes, talus et gradins côté fouille
// (volumes phasés, texture de la couche concernée, cotes en étiquette), outil « Mesurer ».
import * as THREE from 'three'
import type { ObjetTerrainMaquette } from '../lib/api'
import { nb } from '../lib/format'
import { COULEURS_SOL, lambert } from './elements'
import { hacher, versThree, type Arete, type Contour, type Point2 } from './geometrie'
import type { Contexte, Element, Spec } from './scene'

/** Ligne (d -> z) d'un objet, prolongée jusqu'à la base aux deux bouts, en polygone fermé (d, z). */
export function polygoneObjet(profil: number[][], base: number): Point2[] {
  const pts = profil.map(([d, z]) => [d, Math.max(z, base)] as Point2)
  const d0 = pts[0][0]
  const dn = pts[pts.length - 1][0]
  return [[d0, base], ...pts, [dn, base]]
}

/** Côtés concernés par un objet (noms de plan.cotes ou « #k » ; vide = tous). */
export function aretesObjet(geo: Contour, o: { cotes_paroi?: string[] | null }, cotes: Record<string, number>): Arete[] {
  if (!o.cotes_paroi) return geo.aretes.filter((a) => a.L > 1e-6)
  const ks = new Set<number>()
  for (const c of o.cotes_paroi) {
    if (c.startsWith('#')) ks.add(Number(c.slice(1)))
    else if (cotes[c] !== undefined) ks.add(cotes[c])
  }
  return geo.aretes.filter((a) => ks.has(a.k) && a.L > 1e-6)
}

/** Volume obtenu en extrudant un polygone (d, z) de la section le long d'une arête : d mesuré depuis la paroi
 *  vers la fouille (sens = +1) ou vers la terre (sens = −1). */
export function geoExtrusion(poly: Point2[], a: Arete, sens: 1 | -1, de = 0, fin = a.L): THREE.BufferGeometry {
  const n = poly.length
  const pos = new Float32Array(3 * 2 * n)
  const v = new THREE.Vector3()
  for (let i = 0; i < n; i++) {
    const [d, z] = poly[i]
    for (const [j, s] of [[0, de], [1, fin]] as const) {
      versThree(a.A[0] + a.t[0] * s + a.ni[0] * d * sens, a.A[1] + a.t[1] * s + a.ni[1] * d * sens, z, v)
      pos.set([v.x, v.y, v.z], 3 * (2 * i + j))
    }
  }
  const idx: number[] = []
  // faces latérales (bandes entre points consécutifs du polygone)
  for (let i = 0; i < n; i++) {
    const i1 = (i + 1) % n
    idx.push(2 * i, 2 * i1, 2 * i1 + 1, 2 * i, 2 * i1 + 1, 2 * i + 1)
  }
  // bouchons (éventail depuis le premier point)
  for (let i = 1; i + 1 < n; i++) idx.push(0, 2 * (i + 1), 2 * i, 1, 2 * i + 1, 2 * (i + 1) + 1)
  const g = new THREE.BufferGeometry()
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3))
  g.setIndex(idx)
  g.computeVertexNormals()
  return g
}

/** Entrée YAML d'une risberme créée depuis la maquette : forme ancienne (fouille.risbermes, clé cote_paroi) ou bloc
 *  geometrie.fouille.objets (clé cotes, type, tronçon facultatif) selon la forme du script. */
export function entreeYamlRisberme(nom: string, cote: string | number, creteZ: number, largeur: number, pente: number, piedZ: number, phases: [number, number],
  forme: 'ancienne' | 'geometrie' = 'ancienne', troncon?: [number, number] | null): Record<string, unknown> {
  if (forme === 'geometrie') {
    return { nom, type: 'risberme', cotes: [cote], ...(troncon ? { de: troncon[0], a: troncon[1] } : {}), phases, cote_crete: creteZ, largeur_crete: largeur, pente, cote_pied: piedZ }
  }
  return { nom, cote_paroi: cote, phases, cote_crete: creteZ, largeur_crete: largeur, pente, cote_pied: piedZ }
}

/** Tronçon [de, fin] (abscisses locales, m) sur lequel un objet s'étend le long d'une arête. */
export function tronconObjet(o: { troncon?: number[] | null }, a: Arete): [number, number] {
  const t = o.troncon
  if (!t || t.length < 2) return [0, a.L]
  const de = Math.max(0, Math.min(t[0] ?? 0, a.L))
  const fin = Math.max(de, Math.min(Number.isFinite(t[1]) ? t[1] : a.L, a.L))
  return [de, fin]
}

function couleurCouche(ctx: Contexte, z: number): number {
  const c = ctx.d.m.couches
  let i = c.length - 1
  for (let k = 0; k < c.length; k++) if (z <= c[k].toit + 1e-9) i = k
  return COULEURS_SOL[Math.max(0, i) % COULEURS_SOL.length]
}

function specsObjets(ctx: Contexte): Spec[] {
  const t = ctx.d.m.terrain
  if (!t) return []
  const geo = ctx.d.geo
  const cotes = ctx.d.cotes ?? {}
  const out: Spec[] = []
  const objets: ObjetTerrainMaquette[] = [...t.objets]
  const z0 = ctx.d.res.phases[0]?.terrain_amont ?? ctx.d.m.paroi.tete
  const L = geo.marge
  const coin = (nom: string, beta: number, base: number, cotes_paroi: string[] | null, troncon: number[] | null): ObjetTerrainMaquette => ({
    nom, type: 'pente', face: 'amont', base, gamma: 0, methode: 'coulomb_beta', phase_debut: 0, phase_fin: 999,
    profil: [[0, base], [L, base + L * Math.tan((beta * Math.PI) / 180)]], cotes_paroi, cote_equivalente: null, troncon })
  // terrain en pente uniforme (β) sans profil : volume en coin derrière la paroi (forme ancienne, ou zones du bloc geometrie)
  if (t.pente_beta && !t.profil && !(t.zones_terrain?.length)) {
    objets.push(coin(`Terrain en pente β = ${nb(t.pente_beta, 1)}°`, t.pente_beta, z0, t.cote_paroi == null ? null : [String(t.cote_paroi)], null))
  }
  for (const z of t.zones_terrain ?? []) {
    if (z.pente_beta && !z.profil) objets.push(coin(`${z.nom} : pente β = ${nb(z.pente_beta, 1)}°`, z.pente_beta, z.cote ?? z0, z.cotes, z.de == null && z.a == null ? null : [z.de ?? 0, z.a ?? Infinity]))
  }
  objets.forEach((o, i) => {
    const aretes = aretesObjet(geo, o, cotes)
    if (!aretes.length) return
    const poly = polygoneObjet(o.profil, o.base)
    const id = `terrain.objet.${i}`
    const cle = hacher(`${id}|${JSON.stringify(o)}|${aretes.map((a) => a.k).join(',')}|${geo.cle()}`)
    out.push({
      id, cle, creer: (cx) => {
        const sens: 1 | -1 = o.face === 'aval' ? 1 : -1
        const zMid = 0.5 * (o.base + Math.max(...o.profil.map((p) => p[1])))
        const mat = lambert(cx.fab, couleurCouche(cx, zMid), { transparent: true, opacity: o.face === 'aval' ? 0.75 : 0.45 })
        const matBord = cx.fab.mat(new THREE.LineBasicMaterial({ color: 0x8a7350 }))
        const groupe = cx.fab.obj(new THREE.Group())
        for (const a of aretes) {
          const [de, fin] = tronconObjet(o, a)                 // l'objet ne couvre que son tronçon
          if (fin - de < 1e-6) continue
          const g = cx.fab.geo(geoExtrusion(poly, a, sens, de, fin))
          const m = cx.fab.obj(new THREE.Mesh(g, mat))
          m.add(cx.fab.obj(new THREE.LineSegments(cx.fab.geo(new THREE.EdgesGeometry(g, 20)), matBord)))
          groupe.add(m)
        }
        const calque = o.face === 'aval' ? 'fouille.risbermes' : o.type === 'remblai' ? 'terrain.remblais' : 'terrain.surface'
        const el: Element = { id, cle, noeud: o.face === 'aval' ? 'fouille' : 'terrain', calque, objet: groupe, selection: `terrain:${o.nom}`, visiblePhase: true }
        el.appliquerPhase = (k) => { el.visiblePhase = k.phase >= o.phase_debut && k.phase <= o.phase_fin }
        el.etiquettes = (_k, out2) => {
          const a = aretes[0]
          const [de, fin] = tronconObjet(o, a)
          const sm = 0.5 * (de + fin)
          const dCrete = o.profil[0][0]
          const zCrete = Math.max(...o.profil.map((p) => p[1]))
          const dFin = o.profil[o.profil.length - 1][0]
          const etendue = o.troncon ? ` · de ${nb(de, 1)} à ${nb(fin, 1)} m` : ''
          out2.push({ id: `nom.terrain.${i}`, pos: versThree(a.A[0] + a.t[0] * sm + a.ni[0] * (dCrete + 1) * sens, a.A[1] + a.t[1] * sm + a.ni[1] * (dCrete + 1) * sens, zCrete + 0.5),
            texte: `${o.nom} · crête ${nb(zCrete, 2)} m · pied ${nb(o.base, 2)} m · ${nb(dFin, 1)} m${etendue}`, calque, selection: `terrain:${o.nom}` })
        }
        el.surligner = (actif) => { mat.emissive.setHex(actif ? 0x443300 : 0x000000) }
        return el
      },
    })
  })
  return out
}

/** Outil « Mesurer » : segment entre deux points cliqués, distance et dénivelée en étiquette. */
function specMesure(ctx: Contexte): Spec[] {
  const id = 'outils.mesure'
  const cle = hacher(`${id}|${ctx.d.geo.cle()}`)
  return [{
    id, cle, creer: (cx) => {
      const g = cx.fab.geo(new THREE.BufferGeometry())
      g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(6), 3))
      const ligne = cx.fab.obj(new THREE.Line(g, cx.fab.mat(new THREE.LineBasicMaterial({ color: 0xc0392b }))))
      ligne.frustumCulled = false
      const el: Element = { id, cle, noeud: 'outils', calque: 'outils.mesure', objet: ligne, visiblePhase: false }
      const placer = (k: Contexte) => {
        const m = k.scene.mesure
        el.visiblePhase = !!m && !!m.b
        ligne.visible = el.visiblePhase && k.scene.calques.visible(el.calque)
        if (!m?.b) return
        const arr = g.attributes.position.array as Float32Array
        arr.set([m.a.x, m.a.y, m.a.z, m.b.x, m.b.y, m.b.z])
        ;(g.attributes.position as THREE.BufferAttribute).needsUpdate = true
      }
      el.appliquerPhase = placer
      el.majCoupe = placer
      el.etiquettes = (k, o) => {
        const m = k.scene.mesure
        if (!m?.b) return
        const d = m.a.distanceTo(m.b)
        const dz = m.b.y - m.a.y
        const dh = Math.hypot(m.b.x - m.a.x, m.b.z - m.a.z)
        o.push({ id: 'mesure', pos: m.a.clone().lerp(m.b, 0.5), texte: `${nb(d, 2)} m · horizontal ${nb(dh, 2)} m · dénivelée ${nb(dz, 2)} m`, calque: 'outils.mesure', classe: 'valeur' })
      }
      return el
    },
  }]
}

export const FABRIQUES_TERRAIN = [specsObjets, specMesure]
