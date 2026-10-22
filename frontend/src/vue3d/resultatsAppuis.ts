// Résultats des appuis en 3D : déformée des butons (flèche de poids propre amplifiée par la
// compression), déformée des liernes entre butons, assemblages colorés par leur taux de travail.
// Les flèches viennent du module de vérification (serveur) : la vue ne calcule aucune formule.
import * as THREE from 'three'
import type { AppuiPhase, Resultats } from '../lib/api'
import { nb } from '../lib/format'
import { couleurAppui, filtreAssemblage, tauxAppui } from './appuis'
import { extremitesAppui, lambert } from './elements'
import { hacher, versThree } from './geometrie'
import { classeTaux, COULEURS_TAUX } from './palettes'
import { reglageCalque, type Contexte, type Element, type Spec } from './scene'
import { seuilsTaux } from './appuis'

const NSEG = 24     // stations le long d'une barre
const NRAD = 12     // points du contour d'un tube

/** Forme de la déformée d'une poutre sur deux appuis sous charge uniforme, normée (1 à mi-portée) :
 *  w/w_max = 16/5 · (ξ − 2ξ³ + ξ⁴). */
export function formeBiAppuyee(xi: number): number {
  return (16 / 5) * (xi - 2 * xi ** 3 + xi ** 4)
}
/** Forme bi-encastrée sous charge uniforme, normée : w/w_max = 16 ξ² (1 − ξ)². */
export function formeBiEncastree(xi: number): number {
  return 16 * xi * xi * (1 - xi) * (1 - xi)
}

/** Flèche maximale (mm) de tous les appuis, toutes phases (amplification « auto »). */
export function maxFleche(res: Resultats): number {
  let m = 0
  for (const ph of res.phases) for (const a of ph.appuis ?? []) {
    if (a.fleche_mm != null) m = Math.max(m, a.fleche_mm)
    if (a.fleche_lierne_mm != null) m = Math.max(m, a.fleche_lierne_mm)
  }
  return m
}

export function amplificationFleches(ctx: Contexte): number {
  const r = reglageCalque<number | string>(ctx.scene.calques, 'resultats.fleches', 'amplification', 'auto')
  if (r === 'auto' || r === 0) {
    const m = maxFleche(ctx.d.res)
    return m > 1e-6 ? (1.5 * 1000) / m : 1      // la flèche maximale fait 1,5 m à l'écran
  }
  return Math.min(Math.max(Number(r) || 1, 1), 2000)
}

/** Géométrie d'un ensemble de tubes segmentés (positions mises à jour en place). */
function geoTubes(nInst: number, nseg = NSEG, nrad = NRAD): THREE.BufferGeometry {
  const nPts = (nseg + 1) * nrad
  const g = new THREE.BufferGeometry()
  g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(3 * nInst * nPts), 3))
  const idx: number[] = []
  for (let i = 0; i < nInst; i++) {
    const o = i * nPts
    for (let s = 0; s < nseg; s++) for (let r = 0; r < nrad; r++) {
      const r1 = (r + 1) % nrad
      const a = o + s * nrad + r
      const b = o + s * nrad + r1
      const c = o + (s + 1) * nrad + r
      const d = o + (s + 1) * nrad + r1
      idx.push(a, c, d, a, d, b)
    }
  }
  g.setIndex(idx)
  return g
}

const _d = new THREE.Vector3()
const _u = new THREE.Vector3()
const _v = new THREE.Vector3()
const _p = new THREE.Vector3()
const UP = new THREE.Vector3(0, 1, 0)
const X = new THREE.Vector3(1, 0, 0)

/** Remplit le tube `inst` entre a et b : rayon r, décalage latéral `dir × w(ξ)`, raccourcissement symétrique `dl`. */
function remplirTube(pos: Float32Array, inst: number, a: THREE.Vector3, b: THREE.Vector3, r: number, dir: THREE.Vector3,
  w: (xi: number) => number, dl = 0, nseg = NSEG, nrad = NRAD, profil: 'rond' | 'carre' = 'rond') {
  _d.subVectors(b, a)
  const L = _d.length() || 1e-6
  _d.divideScalar(L)
  _u.crossVectors(_d, Math.abs(_d.y) > 0.9 ? X : UP).normalize()
  _v.crossVectors(_u, _d).normalize()
  const nPts = (nseg + 1) * nrad
  const o = inst * nPts
  for (let s = 0; s <= nseg; s++) {
    const xi = s / nseg
    const x = dl / 2 + xi * (L - dl)
    _p.copy(a).addScaledVector(_d, x).addScaledVector(dir, w(xi))
    for (let k = 0; k < nrad; k++) {
      const th = (2 * Math.PI * k) / nrad + (profil === 'carre' ? Math.PI / 4 : 0)
      const cu = Math.cos(th) * r
      const cv = Math.sin(th) * r
      const q = 3 * (o + s * nrad + k)
      pos[q] = _p.x + _u.x * cu + _v.x * cv
      pos[q + 1] = _p.y + _u.y * cu + _v.y * cv
      pos[q + 2] = _p.z + _u.z * cu + _v.z * cv
    }
  }
}

function appuiPhase(ctx: Contexte, nom: string): AppuiPhase | undefined {
  return ctx.ph.appuis?.find((x) => x.nom === nom && x.actif)
}

// ------------------------------------------------------------------ butons et bracons déformés
function specsFlechesBarres(ctx: Contexte): Spec[] {
  const out: Spec[] = []
  const groupes = new Map<string, { de: number[]; a: number[] }[]>()
  for (const pa of ctx.d.m.plan_appuis) groupes.set(pa.appui, [...(groupes.get(pa.appui) ?? []), pa])
  const GRAVITE = new THREE.Vector3(0, -1, 0)
  for (const [nom, a] of Object.entries(ctx.d.m.appuis)) {
    if (a.type !== 'buton' && a.type !== 'bracon') continue
    const pos = groupes.get(nom) ?? []
    if (!pos.length) continue
    const id = `resultats.fleche.${nom}`
    const cle = hacher(`${id}|${JSON.stringify(a)}|${JSON.stringify(pos)}`)
    out.push({
      id, cle, creer: (cx) => {
        const g = cx.fab.geo(geoTubes(pos.length))
        const mat = lambert(cx.fab, 0x2ca02c)
        const mesh = cx.fab.obj(new THREE.Mesh(g, mat))
        mesh.frustumCulled = false
        const el: Element = { id, cle, noeud: 'resultats', calque: 'resultats.fleches', objet: mesh, selection: `appui:${nom}`, visiblePhase: true }
        let info: { f_mm: number; amp: number; mode: string } | null = null
        el.appliquerPhase = (k) => {
          const ap = appuiPhase(k, nom)
          const c = k.scene.calques
          const mode = c.mode?.('resultats.fleches') ?? 'compression'
          const f_mm = ap ? (mode === 'poids_propre' ? ap.fleche_poids_propre_mm : ap.fleche_mm) ?? null : null
          el.visiblePhase = !!ap && f_mm !== null
          info = null
          if (!ap || f_mm === null) return
          const amp = amplificationFleches(k)
          const dl = reglageCalque(c, 'resultats.fleches', 'raccourcissement', false) && ap.raccourcissement_mm != null ? (ap.raccourcissement_mm / 1000) * amp : 0
          const f = (f_mm / 1000) * amp
          const arr = g.attributes.position.array as Float32Array
          pos.forEach((pa, i) => {
            const e = extremitesAppui(a, pa, k.ph.terrain_aval)
            remplirTube(arr, i, e.de, e.fin, a.D / 2, GRAVITE, (xi) => f * formeBiAppuyee(xi), dl)
          })
          ;(g.attributes.position as THREE.BufferAttribute).needsUpdate = true
          g.computeVertexNormals()
          mat.color.setHex(couleurAppui(k, nom, 0x2ca02c))
          info = { f_mm, amp, mode }
          mesh.userData.fleche_mm = f_mm
          mesh.userData.fleche_affichee_m = f
        }
        el.etiquettes = (k, o) => {
          if (!info || !reglageCalque(k.scene.calques, 'resultats.fleches', 'etiquettes', true)) return
          const e = extremitesAppui(a, pos[0], k.ph.terrain_aval)
          const p = e.de.clone().lerp(e.fin, 0.5)
          p.y -= (info.f_mm / 1000) * info.amp
          const ap = appuiPhase(k, nom)
          const comp = info.mode === 'compression' && ap?.N_cr_kN ? ` (N/Ncr = ${nb(ap.effort_axial_kN / ap.N_cr_kN, 2)})` : ''
          o.push({ id: `fleche.${nom}`, pos: p, texte: `f = ${nb(info.f_mm, 1)} mm${comp}`, calque: 'resultats.fleches', classe: 'valeur', selection: `appui:${nom}` })
        }
        el.surligner = (actif) => { mat.emissive.setHex(actif ? 0x664400 : 0x000000) }
        return el
      },
    })
  }
  return out
}

// ------------------------------------------------------------------ liernes déformées entre butons
function specsFlechesLiernes(ctx: Contexte): Spec[] {
  const out: Spec[] = []
  const geo = ctx.d.geo
  const paroi = ctx.d.m.paroi
  const o = (paroi.type === 'paroi_moulee' ? paroi.epaisseur / 2 : paroi.type.startsWith('pieux') ? paroi.diametre / 2 : paroi.h / 2) + 0.2
  for (const [nom, a] of Object.entries(ctx.d.m.appuis)) {
    if (!a.lierne || a.type === 'dalle') continue
    // travées : entre butons consécutifs sur chaque arête (extrémités droites)
    const travees: { k: number; s0: number; s1: number; appuyee: boolean }[] = []
    for (const ar of geo.aretes) {
      if (ar.L < 1e-6) continue
      const st = ctx.d.m.plan_appuis.filter((pa) => pa.appui === nom).map((pa) => geo.projeter(pa.de[0], pa.de[1])).filter((p) => p.k === ar.k && p.d < 0.5).map((p) => p.sl).sort((x, y) => x - y)
      if (!st.length) { travees.push({ k: ar.k, s0: 0, s1: ar.L, appuyee: false }); continue }
      travees.push({ k: ar.k, s0: 0, s1: st[0], appuyee: false })
      for (let i = 0; i + 1 < st.length; i++) travees.push({ k: ar.k, s0: st[i], s1: st[i + 1], appuyee: true })
      travees.push({ k: ar.k, s0: st[st.length - 1], s1: ar.L, appuyee: false })
    }
    const id = `resultats.fleche_lierne.${nom}`
    const cle = hacher(`${id}|${geo.cle()}|${a.cote}|${o}|${JSON.stringify(travees)}`)
    out.push({
      id, cle, creer: (cx) => {
        const g = cx.fab.geo(geoTubes(travees.length, NSEG, 4))
        const mat = lambert(cx.fab, 0x34495e)
        const mesh = cx.fab.obj(new THREE.Mesh(g, mat))
        mesh.frustumCulled = false
        const el: Element = { id, cle, noeud: 'resultats', calque: 'resultats.fleches', objet: mesh, selection: `lierne:${nom}`, visiblePhase: true }
        let f_mm: number | null = null
        el.appliquerPhase = (k) => {
          const ap = appuiPhase(k, nom)
          f_mm = ap?.fleche_lierne_mm ?? null
          el.visiblePhase = f_mm !== null
          if (f_mm === null) return
          const amp = amplificationFleches(k)
          const f = (f_mm / 1000) * amp
          const arr = g.attributes.position.array as Float32Array
          const A = new THREE.Vector3()
          const B = new THREE.Vector3()
          const dir = new THREE.Vector3()
          travees.forEach((t, i) => {
            const ar = geo.aretes[t.k]
            versThree(ar.A[0] + ar.t[0] * t.s0 + ar.ni[0] * o, ar.A[1] + ar.t[1] * t.s0 + ar.ni[1] * o, a.cote, A)
            versThree(ar.A[0] + ar.t[0] * t.s1 + ar.ni[0] * o, ar.A[1] + ar.t[1] * t.s1 + ar.ni[1] * o, a.cote, B)
            dir.set(ar.ni[0], 0, -ar.ni[1])
            remplirTube(arr, i, A, B, 0.21, dir, (xi) => (t.appuyee ? f * formeBiEncastree(xi) : 0), 0, NSEG, 4, 'carre')
          })
          ;(g.attributes.position as THREE.BufferAttribute).needsUpdate = true
          g.computeVertexNormals()
          mat.color.setHex(couleurAppui(k, nom, 0x34495e, (v) => v.nom.startsWith('Lierne')))
          mesh.userData.fleche_mm = f_mm
          mesh.userData.fleche_affichee_m = f
        }
        el.etiquettes = (k, out2) => {
          if (f_mm === null || !reglageCalque(k.scene.calques, 'resultats.fleches', 'etiquettes', true)) return
          const t = travees.find((x) => x.appuyee) ?? travees[0]
          const ar = geo.aretes[t.k]
          const sm = (t.s0 + t.s1) / 2
          const d = o + (f_mm / 1000) * amplificationFleches(k)
          out2.push({ id: `fleche.lierne.${nom}`, pos: versThree(ar.A[0] + ar.t[0] * sm + ar.ni[0] * d, ar.A[1] + ar.t[1] * sm + ar.ni[1] * d, a.cote),
            texte: `lierne ${nom} : f ≈ ${nb(f_mm, 1)} mm (valeur approchée, travée bi-encastrée)`, calque: 'resultats.fleches', classe: 'valeur', selection: `lierne:${nom}` })
        }
        el.surligner = (actif) => { mat.emissive.setHex(actif ? 0x664400 : 0x000000) }
        return el
      },
    })
  }
  return out
}

// ------------------------------------------------------------------ assemblages (cubes en tête des butons, colorés par taux)
function specsAssemblages(ctx: Contexte): Spec[] {
  const out: Spec[] = []
  const parAppui = new Map<string, string[]>()
  for (const [nomAss, ass] of Object.entries(ctx.d.m.assemblages)) if (ass.appui) parAppui.set(ass.appui, [...(parAppui.get(ass.appui) ?? []), nomAss])
  for (const [nom, liste] of parAppui) {
    const a = ctx.d.m.appuis[nom]
    const pos = ctx.d.m.plan_appuis.filter((pa) => pa.appui === nom)
    if (!a || !pos.length) continue
    liste.forEach((nomAss, j) => {
      const id = `appui.assemblage.${nomAss}`
      const cle = hacher(`${id}|${JSON.stringify(a)}|${JSON.stringify(pos)}|${j}`)
      out.push({
        id, cle, creer: (cx) => {
          const taille = Math.max(0.6, 1.3 * a.D)
          const mat = lambert(cx.fab, 0x7f8c8d)
          const im = cx.fab.obj(new THREE.InstancedMesh(cx.fab.geo(new THREE.BoxGeometry(taille, taille, taille)), mat, pos.length))
          const m = new THREE.Matrix4()
          const placer = (fond: number) => {
            pos.forEach((pa, i) => {
              const e = extremitesAppui(a, pa, fond)
              const p = e.de.clone().lerp(e.fin, Math.min(1, (taille * (0.6 + j)) / e.de.distanceTo(e.fin)))
              im.setMatrixAt(i, m.makeTranslation(p.x, p.y, p.z))
            })
            im.instanceMatrix.needsUpdate = true
            im.computeBoundingSphere()
          }
          placer(ctx.ph.terrain_aval)
          const el: Element = { id, cle, noeud: 'appuis', calque: 'appuis.assemblages', calques: ['resultats.taux'], objet: im, selection: `assemblage:${nomAss}`, visiblePhase: true }
          el.appliquerPhase = (k) => {
            el.visiblePhase = !!appuiPhase(k, nom) && k.scene.calques.visible('appuis.assemblages')
            const c = k.scene.calques
            mat.color.setHex(c.visible('resultats.taux') ? COULEURS_TAUX[classeTaux(tauxAppui(k.d.res.verifications, nom, k.d.m.assemblages, filtreAssemblage(nomAss)), seuilsTaux(c))] : 0x7f8c8d)
          }
          el.etiquettes = (k, o) => {
            const e = extremitesAppui(a, pos[0], k.ph.terrain_aval)
            const p = e.de.clone().lerp(e.fin, Math.min(1, (taille * (0.6 + j)) / e.de.distanceTo(e.fin)))
            p.y += taille
            const t = k.scene.calques.visible('resultats.taux') ? tauxAppui(k.d.res.verifications, nom, k.d.m.assemblages, filtreAssemblage(nomAss)) : null
            const ass = k.d.m.assemblages[nomAss]
            o.push({ id: `nom.${nomAss}`, pos: p, texte: `${nomAss} · ${ass.type}${t !== null ? ` · ${nb(t * 100, 0)} %` : ''}`, calque: 'annotations.noms', selection: `assemblage:${nomAss}` })
          }
          el.surligner = (actif) => { mat.emissive.setHex(actif ? 0x664400 : 0x000000) }
          return el
        },
      })
    })
  }
  return out
}

export const FABRIQUES_RESULTATS_APPUIS = [specsFlechesBarres, specsFlechesLiernes, specsAssemblages]
