// Objets « chantier » de la scène : couches de sol, fond de fouille, nappes, paroi, appuis,
// hydraulique, outils. Chaque objet est construit une fois ; la phase ne change que des attributs.
import * as THREE from 'three'
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js'
import type { AppuiMaquette, PhaseRes } from '../lib/api'
import { nb } from '../lib/format'
import { couleurAppui, etiquetteEffort, etiquetteTaux, FILTRE_BARRE, FILTRE_LIERNE } from './appuis'
import type { Fabrique } from './fabrique'
import { hacher, versThree, type Contour, type Point2 } from './geometrie'
import type { Contexte, Element, Etiquette, NomNoeud, Spec } from './scene'

export const COULEURS_SOL = [0xe8d8b0, 0xd9c08c, 0xc9a96e, 0xb8925a, 0xd6c7a1, 0xa88a5c]
const EPS = 1e-3

// ------------------------------------------------------------------ outils de construction
export function lambert(fab: Fabrique, couleur: number, o: THREE.MeshLambertMaterialParameters = {}) {
  return fab.mat(new THREE.MeshLambertMaterial({ color: couleur, side: THREE.DoubleSide, ...o }))
}

function forme(points: Point2[], trou?: Point2[]) {
  const s = new THREE.Shape(points.map(([x, y]) => new THREE.Vector2(x, y)))
  if (trou) s.holes.push(new THREE.Path(trou.map(([x, y]) => new THREE.Vector2(x, y))))
  return s
}

/** Bloc vertical de hauteur unité (de y = 0 à y = 1 en repère three) : on règle ensuite position.y et scale.y. */
export function geoBlocUnitaire(fab: Fabrique, points: Point2[], trou?: Point2[]) {
  const g = new THREE.ExtrudeGeometry(forme(points, trou), { depth: 1, bevelEnabled: false })
  g.rotateX(-Math.PI / 2)
  return fab.geo(g)
}

/** Place un bloc unitaire entre deux cotes ; le masque si l'épaisseur est nulle. */
export function caler(o: THREE.Object3D, zBas: number, zHaut: number): boolean {
  const h = zHaut - zBas
  if (h < EPS) return false
  o.position.y = zBas
  o.scale.y = h
  return true
}

function base(id: string, cle: string, noeud: NomNoeud, calque: string, objet: THREE.Object3D, selection?: string): Element {
  objet.name = id
  return { id, cle, noeud, calque, objet, selection, visiblePhase: true }
}

const _m = new THREE.Matrix4()
const _q = new THREE.Quaternion()
const _s = new THREE.Vector3()
const _p = new THREE.Vector3()
const _a = new THREE.Vector3()
const _b = new THREE.Vector3()
const _d = new THREE.Vector3()
const Y = new THREE.Vector3(0, 1, 0)

/** Matrice d'un cylindre unitaire (rayon 1, hauteur 1, axe y) entre deux points three. */
export function matriceCylindre(a: THREE.Vector3, b: THREE.Vector3, r: number, out: THREE.Matrix4) {
  _p.subVectors(b, a)
  const L = _p.length()
  _q.setFromUnitVectors(Y, L > 0 ? _d.copy(_p).divideScalar(L) : Y)
  _s.set(r, Math.max(L, 1e-6), r)
  _p.copy(a).lerp(b, 0.5)
  return out.compose(_p, _q, _s)
}

/** Matrice d'une boîte unitaire orientée selon la tangente en plan t. */
export function matriceBoite(cx: number, cy: number, z0: number, z1: number, t: Point2, lt: number, ln: number, out: THREE.Matrix4) {
  versThree(cx, cy, (z0 + z1) / 2, _p)
  _q.setFromAxisAngle(Y, Math.atan2(t[1], t[0]))
  _s.set(Math.max(lt, 1e-6), Math.max(z1 - z0, 1e-6), Math.max(ln, 1e-6))
  return out.compose(_p, _q, _s)
}

function phaseActif(ph: PhaseRes, nom: string): boolean {
  return !!ph.ok && !!ph.appuis?.some((a) => a.nom === nom && a.actif)
}

// ------------------------------------------------------------------ sol et fouille
function couches(ctx: Contexte): { nom: string; toit: number; bas: number }[] {
  const c = ctx.d.m.couches
  return c.map((x, i) => ({ nom: x.nom, toit: x.toit, bas: i + 1 < c.length ? c[i + 1].toit : ctx.d.m.z_bas }))
}

function specsSol(ctx: Contexte): Spec[] {
  const geo = ctx.d.geo
  const out: Spec[] = []
  couches(ctx).forEach((c, i) => {
    const cleT = hacher(`terre|${geo.cle()}|${c.toit}|${c.bas}|${geo.marge}`)
    out.push({
      id: `terrain.couche.${i}`, cle: cleT, creer: (cx) => {
        const fab = cx.fab
        const g = geoBlocUnitaire(fab, geo.exterieur(), geo.trigo)
        const mesh = fab.obj(new THREE.Mesh(g, lambert(fab, COULEURS_SOL[i % COULEURS_SOL.length], { transparent: true, opacity: 0.28, depthWrite: false })))
        mesh.add(fab.obj(new THREE.LineSegments(fab.geo(new THREE.EdgesGeometry(g, 30)),
          fab.mat(new THREE.LineBasicMaterial({ color: 0x8a7350, transparent: true, opacity: 0.5 })))))
        const el = base(`terrain.couche.${i}`, cleT, 'terrain', 'terrain.couches', mesh, `couche:${i}`)
        el.appliquerPhase = (k) => { el.visiblePhase = caler(mesh, c.bas, Math.min(c.toit, k.ph.terrain_amont)) }
        return el
      },
    })
    const cleF = hacher(`fouille|${geo.cle()}|${c.toit}|${c.bas}`)
    out.push({
      id: `fouille.couche.${i}`, cle: cleF, creer: (cx) => {
        const fab = cx.fab
        const g = geoBlocUnitaire(fab, geo.points)
        const mesh = fab.obj(new THREE.Mesh(g, lambert(fab, COULEURS_SOL[i % COULEURS_SOL.length], { transparent: true, opacity: 0.28, depthWrite: false })))
        mesh.add(fab.obj(new THREE.LineSegments(fab.geo(new THREE.EdgesGeometry(g, 30)),
          fab.mat(new THREE.LineBasicMaterial({ color: 0x8a7350, transparent: true, opacity: 0.5 })))))
        const el = base(`fouille.couche.${i}`, cleF, 'fouille', 'fouille.couches', mesh, `couche:${i}`)
        el.appliquerPhase = (k) => { el.visiblePhase = caler(mesh, c.bas, Math.min(c.toit, k.ph.terrain_aval)) }
        return el
      },
    })
  })
  const cleFond = hacher(`fond|${geo.cle()}`)
  const fondDefaut = (ph: { terrain_aval: number; fonds?: Record<string, number | null> }) => ph.fonds?.defaut ?? ph.terrain_aval
  out.push({
    id: 'fouille.fond', cle: cleFond, creer: (cx) => {
      const mesh = cx.fab.obj(new THREE.Mesh(geoBlocUnitaire(cx.fab, geo.points), lambert(cx.fab, 0x8b5a2b)))
      const el = base('fouille.fond', cleFond, 'fouille', 'fouille.fond', mesh, 'fond')
      el.appliquerPhase = (k) => { const f = fondDefaut(k.ph); el.visiblePhase = caler(mesh, f - 0.05, f) }
      el.etiquettes = (k, o) => {
        const a = geo.aretes[0]
        const f = fondDefaut(k.ph)
        o.push({ id: 'cote.fond', pos: versThree(a.A[0] + a.ni[0] * 1.5, a.A[1] + a.ni[1] * 1.5, f), texte: `fond ${nb(f, 2)} m`, calque: 'annotations.cotes' })
      }
      return el
    },
  })
  // zones de fond (geometrie.fouille.zones) : un fond par zone, à la cote de la zone pour la phase affichée
  for (const z of ctx.d.m.zones ?? []) {
    if (!z.polygone || z.polygone.length < 3) continue
    const pts = z.polygone.map((p) => [p[0], p[1]] as [number, number])
    const cleZ = hacher(`fond.zone|${z.nom}|${JSON.stringify(pts)}`)
    out.push({
      id: `fouille.fond.${z.nom}`, cle: cleZ, creer: (cx) => {
        const mesh = cx.fab.obj(new THREE.Mesh(geoBlocUnitaire(cx.fab, pts), lambert(cx.fab, 0x9c6a37)))
        const el = base(`fouille.fond.${z.nom}`, cleZ, 'fouille', 'fouille.fond', mesh, 'fond')
        el.appliquerPhase = (k) => { const f = k.ph.fonds?.[z.nom] ?? fondDefaut(k.ph); el.visiblePhase = caler(mesh, f - 0.05, f + 0.01) }
        el.etiquettes = (k, o) => {
          const f = k.ph.fonds?.[z.nom] ?? fondDefaut(k.ph)
          const cx0 = pts.reduce((s, p) => s + p[0], 0) / pts.length, cy0 = pts.reduce((s, p) => s + p[1], 0) / pts.length
          o.push({ id: `cote.fond.${z.nom}`, pos: versThree(cx0, cy0, f), texte: `fond ${z.nom} ${nb(f, 2)} m`, calque: 'annotations.cotes' })
        }
        return el
      },
    })
  }
  return out
}

// ------------------------------------------------------------------ eau
function specsEau(ctx: Contexte): Spec[] {
  const geo = ctx.d.geo
  const cle = hacher(`eau|${geo.cle()}|${geo.marge}`)
  const matEau = (fab: Fabrique, op: number) => lambert(fab, 0x3b8fd9, { transparent: true, opacity: op, depthWrite: false })
  return [
    {
      id: 'eau.amont', cle, creer: (cx) => {
        const mesh = cx.fab.obj(new THREE.Mesh(geoBlocUnitaire(cx.fab, geo.exterieur(), geo.trigo), matEau(cx.fab, 0.35)))
        const el = base('eau.amont', cle, 'eau', 'eau.amont', mesh)
        el.appliquerPhase = (k) => {
          const z = k.ph.eau_amont
          el.visiblePhase = z !== null && caler(mesh, z - 0.02, z)
        }
        el.etiquettes = (k, o) => {
          if (k.ph.eau_amont === null) return
          o.push({ id: 'cote.nappe', pos: versThree(geo.xmin - geo.marge * 0.5, geo.ymin - geo.marge * 0.5, k.ph.eau_amont), texte: `nappe amont ${nb(k.ph.eau_amont, 2)} m`, calque: 'annotations.cotes' })
        }
        return el
      },
    },
    {
      id: 'eau.sous_fouille', cle, creer: (cx) => {
        const mesh = cx.fab.obj(new THREE.Mesh(geoBlocUnitaire(cx.fab, geo.points), matEau(cx.fab, 0.35)))
        const el = base('eau.sous_fouille', cle, 'eau', 'eau.amont', mesh)
        el.appliquerPhase = (k) => {
          const z = k.ph.eau_amont
          el.visiblePhase = z !== null && z <= k.ph.terrain_aval && (k.ph.eau_aval === null || k.ph.eau_aval <= k.ph.terrain_aval) && caler(mesh, z - 0.02, z)
        }
        return el
      },
    },
    {
      id: 'eau.aval', cle, creer: (cx) => {
        const mesh = cx.fab.obj(new THREE.Mesh(geoBlocUnitaire(cx.fab, geo.points), matEau(cx.fab, 0.3)))
        const el = base('eau.aval', cle, 'eau', 'eau.aval', mesh)
        el.appliquerPhase = (k) => {
          const z = k.ph.eau_aval
          el.visiblePhase = z !== null && caler(mesh, k.ph.terrain_aval, z)
        }
        return el
      },
    },
  ]
}

// ------------------------------------------------------------------ paroi
/** Demi-épaisseur visuelle de la paroi (décalage des liernes). */
export function demiEpaisseur(p: { type: string; epaisseur: number; diametre: number; h: number }): number {
  return p.type === 'paroi_moulee' ? p.epaisseur / 2 : p.type.startsWith('pieux') ? p.diametre / 2 : p.h / 2
}

function specsParoi(ctx: Contexte): Spec[] {
  const p = ctx.d.m.paroi
  const geo = ctx.d.geo
  const H = p.tete - p.pied
  const out: Spec[] = []
  for (const a of geo.aretes) {
    if (a.L < 1e-6) continue
    const id = `paroi.cote.${a.k}`
    const cle = hacher(`${id}|${JSON.stringify(p)}|${a.A}|${a.B}|${geo.sens}`)
    out.push({
      id, cle, creer: (cx) => {
        const fab = cx.fab
        const acier = p.type === 'palplanche' || p.type === 'berlinoise'
        const mat = lambert(fab, acier ? 0x6d7b8a : 0xa0a0a0)
        const groupe = fab.obj(new THREE.Group())
        const pt = (s: number, o = 0): Point2 => [a.A[0] + a.t[0] * s + a.ni[0] * o, a.A[1] + a.t[1] * s + a.ni[1] * o]
        let blindage: THREE.InstancedMesh | null = null
        const baies: { s: number; L: number }[] = []
        if (p.type === 'palplanche') {
          const pas = Math.max(p.b, 0.3)
          const amp = p.h
          const nb_ = Math.max(1, Math.round(a.L / pas))
          const pts: Point2[] = []
          for (let i = 0; i <= 2 * nb_; i++) pts.push(pt((i * a.L) / (2 * nb_), ((i % 2 ? 1 : -1) * amp) / 2))
          const segZ = 2
          const pos: number[] = []
          const idx: number[] = []
          for (let j = 0; j <= segZ; j++) {
            const z = p.pied + (H * j) / segZ
            for (const [x, y] of pts) { versThree(x, y, z, _a); pos.push(_a.x, _a.y, _a.z) }
          }
          const m = pts.length
          for (let j = 0; j < segZ; j++) for (let i = 0; i < m - 1; i++) {
            const q = j * m + i
            idx.push(q, q + 1, q + m + 1, q, q + m + 1, q + m)
          }
          const g = new THREE.BufferGeometry()
          g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3))
          g.setIndex(idx)
          g.computeVertexNormals()
          groupe.add(fab.obj(new THREE.Mesh(fab.geo(g), mat)))
        } else if (p.type === 'paroi_moulee') {
          const n = Math.max(1, Math.ceil(a.L / 5))
          const lp = a.L / n
          const im = fab.obj(new THREE.InstancedMesh(fab.geo(new THREE.BoxGeometry(1, 1, 1)), mat, n))
          for (let i = 0; i < n; i++) {
            const [x, y] = pt((i + 0.5) * lp)
            im.setMatrixAt(i, matriceBoite(x, y, p.pied, p.tete, a.t, lp - 0.03, p.epaisseur, _m))
          }
          groupe.add(im)
        } else if (p.type.startsWith('pieux')) {
          const n = Math.max(1, Math.floor(a.L / p.entraxe))
          const im = fab.obj(new THREE.InstancedMesh(fab.geo(new THREE.CylinderGeometry(1, 1, 1, 16)), mat, n))
          for (let i = 0; i < n; i++) {
            const [x, y] = pt(((i + 0.5) * a.L) / n)
            im.setMatrixAt(i, matriceCylindre(versThree(x, y, p.pied, _a), versThree(x, y, p.tete, _b), p.diametre / 2, _m))
          }
          groupe.add(im)
        } else if (p.type === 'berlinoise') {
          const n = Math.max(1, Math.floor(a.L / p.entraxe))
          const ailes = fab.obj(new THREE.InstancedMesh(fab.geo(new THREE.BoxGeometry(1, 1, 1)), mat, 2 * (n + 1)))
          const ames = fab.obj(new THREE.InstancedMesh(fab.geo(new THREE.BoxGeometry(1, 1, 1)), mat, n + 1))
          let k = 0
          for (let i = 0; i <= n; i++) {
            const s = (i * a.L) / n
            for (const o of [-p.h / 2 + p.tf / 2, p.h / 2 - p.tf / 2]) {
              const [x, y] = pt(s, o)
              ailes.setMatrixAt(k++, matriceBoite(x, y, p.pied, p.tete, a.t, p.b, p.tf, _m))
            }
            const [x, y] = pt(s)
            ames.setMatrixAt(i, matriceBoite(x, y, p.pied, p.tete, a.t, p.tw, p.h - 2 * p.tf, _m))
            if (i < n) baies.push({ s: s + a.L / n / 2, L: a.L / n - p.b })
          }
          groupe.add(ailes, ames)
          if (p.blindage) {
            blindage = fab.obj(new THREE.InstancedMesh(fab.geo(new THREE.BoxGeometry(1, 1, 1)), lambert(fab, 0xb07a43), Math.max(1, baies.length)))
            groupe.add(blindage)
          }
        }
        const el = base(id, cle, 'paroi', 'paroi.elements', groupe, `paroi:${a.k}`)
        if (blindage) {
          const bl = blindage
          el.appliquerPhase = (k) => {
            const z0 = k.ph.terrain_aval
            const z1 = Math.min(p.tete, k.ph.terrain_amont)
            bl.visible = z1 - z0 > EPS
            if (!bl.visible) return
            baies.forEach((b, i) => {
              const [x, y] = pt(b.s, -p.h / 2 + p.tf + (p.blindage ?? 0) / 2)
              bl.setMatrixAt(i, matriceBoite(x, y, z0, z1, a.t, b.L, p.blindage ?? 0.05, _m))
            })
            bl.instanceMatrix.needsUpdate = true
          }
        }
        el.surligner = (actif) => { mat.emissive.setHex(actif ? 0x443300 : 0x000000) }
        return el
      },
    })
  }
  return out
}

// ------------------------------------------------------------------ appuis
function groupesAppuis(ctx: Contexte): Map<string, { de: number[]; a: number[] }[]> {
  const g = new Map<string, { de: number[]; a: number[] }[]>()
  for (const pa of ctx.d.m.plan_appuis) {
    if (!g.has(pa.appui)) g.set(pa.appui, [])
    g.get(pa.appui)!.push(pa)
  }
  return g
}

/** Extrémités three d'un appui en plan (buton, bracon, tirant : partie libre et scellement). */
export function extremitesAppui(a: AppuiMaquette, pa: { de: number[]; a: number[] }, fond: number): { de: THREE.Vector3; fin: THREE.Vector3; milieuLibre?: THREE.Vector3; finScelle?: THREE.Vector3 } {
  const de = versThree(pa.de[0], pa.de[1], a.cote)
  if (a.type === 'buton') return { de, fin: versThree(pa.a[0], pa.a[1], a.cote) }
  if (a.type === 'bracon') return { de, fin: versThree(pa.a[0], pa.a[1], a.pied_bracon ?? fond) }
  const Ll = a.longueur_libre || 8
  const Ls = a.longueur_scellee || 6
  const i = ((a.angle || 0) * Math.PI) / 180
  const dx = pa.a[0] - pa.de[0]
  const dy = pa.a[1] - pa.de[1]
  const Lh = Math.hypot(dx, dy) || 1
  const pnt = (L: number) => versThree(pa.de[0] + (dx / Lh) * L * Math.cos(i), pa.de[1] + (dy / Lh) * L * Math.cos(i), a.cote - L * Math.sin(i))
  return { de, fin: pnt(Ll + Ls), milieuLibre: pnt(Ll), finScelle: pnt(Ll + Ls) }
}

function specsAppuis(ctx: Contexte): Spec[] {
  const out: Spec[] = []
  const geo = ctx.d.geo
  const paroi = ctx.d.m.paroi
  const groupes = groupesAppuis(ctx)
  for (const [nom, a] of Object.entries(ctx.d.m.appuis)) {
    const pos = groupes.get(nom) ?? []
    if (a.type === 'buton' || a.type === 'bracon' || a.type === 'tirant') {
      if (!pos.length) continue
      const id = `appui.${nom}`
      const cle = hacher(`${id}|${JSON.stringify(a)}|${JSON.stringify(pos)}`)
      out.push({
        id, cle, creer: (cx) => {
          const fab = cx.fab
          const couleur = a.type === 'tirant' ? 0xc0392b : 0x2ca02c
          const mat = lambert(fab, couleur)
          const groupe = fab.obj(new THREE.Group())
          const geoCyl = () => fab.geo(new THREE.CylinderGeometry(1, 1, 1, 16))
          const corps = fab.obj(new THREE.InstancedMesh(geoCyl(), mat, pos.length))
          corps.name = `${id}.corps`
          groupe.add(corps)
          let scell: THREE.InstancedMesh | null = null
          if (a.type === 'tirant') {
            scell = fab.obj(new THREE.InstancedMesh(geoCyl(), mat, pos.length))
            groupe.add(scell)
          }
          const placer = (fond: number) => {
            pos.forEach((pa, i) => {
              const e = extremitesAppui(a, pa, fond)
              if (a.type === 'tirant') {
                corps.setMatrixAt(i, matriceCylindre(e.de, e.milieuLibre!, 0.05, _m))
                scell!.setMatrixAt(i, matriceCylindre(e.milieuLibre!, e.finScelle!, 0.12, _m))
              } else corps.setMatrixAt(i, matriceCylindre(e.de, e.fin, a.D / 2, _m))
            })
            corps.instanceMatrix.needsUpdate = true
            if (scell) scell.instanceMatrix.needsUpdate = true
            corps.computeBoundingSphere()
            scell?.computeBoundingSphere()
          }
          placer(ctx.ph.terrain_aval)
          const noeud: NomNoeud = a.type === 'tirant' ? 'appuis.tirants' : 'appuis.butons'
          const el = base(id, cle, noeud, a.type === 'tirant' ? 'appuis.tirants' : 'appuis.butons', groupe, `appui:${nom}`)
          let fondPlace = ctx.ph.terrain_aval
          el.calques = ['resultats.efforts', 'resultats.taux']
          el.appliquerPhase = (k) => {
            const ap = k.ph.appuis?.find((x) => x.nom === nom)
            const deformee = k.scene.calques.visible('resultats.fleches') && (ap?.fleche_mm != null || ap?.fleche_poids_propre_mm != null)
            el.visiblePhase = phaseActif(k.ph, nom) && k.scene.calques.visible(el.calque) && !deformee
            if (a.type === 'bracon' && a.pied_bracon === null && k.ph.terrain_aval !== fondPlace) {
              fondPlace = k.ph.terrain_aval
              placer(fondPlace)
            }
            mat.color.setHex(couleurAppui(k, nom, couleur, FILTRE_BARRE))
          }
          el.etiquettes = (k, o) => {
            const e = extremitesAppui(a, pos[0], k.ph.terrain_aval)
            o.push({ id: `nom.${nom}`, pos: e.de.clone().lerp(e.fin, 0.5), texte: `${nom}${a.element ? ` — ${a.element}` : ''}`, calque: 'annotations.noms', selection: `appui:${nom}` })
            const eff = etiquetteEffort(k, nom)
            if (eff) o.push({ id: `effort.${nom}`, pos: e.de.clone().lerp(e.fin, 0.35), texte: eff, calque: 'resultats.efforts', classe: 'valeur', selection: `appui:${nom}` })
            const tx = etiquetteTaux(k, nom, FILTRE_BARRE)
            if (tx) o.push({ id: `taux.${nom}`, pos: e.de.clone().lerp(e.fin, 0.65), texte: tx, calque: 'resultats.taux', classe: 'valeur', selection: `appui:${nom}` })
          }
          el.surligner = (actif) => { mat.emissive.setHex(actif ? 0x664400 : 0x000000) }
          return el
        },
      })
    }
    if (a.type === 'dalle') {
      const id = `appui.${nom}`
      const ep = a.epaisseur || 0.3
      const cle = hacher(`${id}|${geo.cle()}|${a.cote}|${ep}`)
      out.push({
        id, cle, creer: (cx) => {
          const mat = lambert(cx.fab, 0xbdbdbd)
          const mesh = cx.fab.obj(new THREE.Mesh(geoBlocUnitaire(cx.fab, geo.points), mat))
          caler(mesh, a.cote - ep / 2, a.cote + ep / 2)
          const el = base(id, cle, 'appuis.dalles', 'appuis.dalles', mesh, `appui:${nom}`)
          el.calques = ['resultats.efforts', 'resultats.taux']
          el.appliquerPhase = (k) => {
            el.visiblePhase = phaseActif(k.ph, nom) && k.scene.calques.visible(el.calque)
            mat.color.setHex(couleurAppui(k, nom, 0xbdbdbd))
          }
          el.etiquettes = (k, o) => {
            const cx = (geo.xmin + geo.xmax) / 2
            const cy = (geo.ymin + geo.ymax) / 2
            o.push({ id: `nom.${nom}`, pos: versThree(cx, cy, a.cote + 0.3), texte: `${nom} (dalle)`, calque: 'annotations.noms', selection: `appui:${nom}` })
            const eff = etiquetteEffort(k, nom)
            if (eff) o.push({ id: `effort.${nom}`, pos: versThree(cx, cy, a.cote + 0.9), texte: eff, calque: 'resultats.efforts', classe: 'valeur', selection: `appui:${nom}` })
          }
          el.surligner = (actif) => { mat.emissive.setHex(actif ? 0x664400 : 0x000000) }
          return el
        },
      })
    }
    if (a.lierne && a.type !== 'dalle') {
      const id = `appui.${nom}.lierne`
      const cle = hacher(`${id}|${geo.cle()}|${a.cote}|${a.lierne}|${demiEpaisseur(paroi)}`)
      out.push({
        id, cle, creer: (cx) => {
          const mat = lambert(cx.fab, 0x34495e)
          const aretes = geo.aretes.filter((x) => x.L > 1e-6)
          const im = cx.fab.obj(new THREE.InstancedMesh(cx.fab.geo(new THREE.BoxGeometry(1, 1, 1)), mat, aretes.length))
          const o = demiEpaisseur(paroi) + 0.2
          aretes.forEach((ar, i) => {
            const cxp = (ar.A[0] + ar.B[0]) / 2 + ar.ni[0] * o
            const cyp = (ar.A[1] + ar.B[1]) / 2 + ar.ni[1] * o
            im.setMatrixAt(i, matriceBoite(cxp, cyp, a.cote - 0.15, a.cote + 0.15, ar.t, ar.L, 0.3, _m))
          })
          im.computeBoundingSphere()
          const el = base(id, cle, 'appuis.butons', 'appuis.liernes', im, `lierne:${nom}`)
          el.calques = ['resultats.taux']
          el.appliquerPhase = (k) => {
            const c = k.scene.calques
            const deformee = c.visible('resultats.fleches') && k.ph.appuis?.find((x) => x.nom === nom)?.fleche_lierne_mm != null
            el.visiblePhase = phaseActif(k.ph, nom) && c.visible(el.calque) && !deformee
            mat.color.setHex(couleurAppui(k, nom, 0x34495e, FILTRE_LIERNE))
          }
          el.etiquettes = (k, out2) => {
            out2.push({ id: `nom.lierne.${nom}`, pos: versThree(geo.points[0][0], geo.points[0][1], a.cote + 0.4), texte: `lierne ${a.lierne}`, calque: 'annotations.noms', selection: `lierne:${nom}` })
            const tx = etiquetteTaux(k, nom, FILTRE_LIERNE)
            if (tx) out2.push({ id: `taux.lierne.${nom}`, pos: versThree(geo.points[0][0], geo.points[0][1], a.cote - 0.5), texte: `lierne ${tx}`, calque: 'resultats.taux', classe: 'valeur', selection: `lierne:${nom}` })
          }
          el.surligner = (actif) => { mat.emissive.setHex(actif ? 0x664400 : 0x000000) }
          return el
        },
      })
    }
  }
  return out
}

// ------------------------------------------------------------------ hydraulique
function geoFleche(fab: Fabrique) {
  const tige = new THREE.CylinderGeometry(0.06, 0.06, 0.65, 8)
  tige.translate(0, 0.325, 0)
  const tete = new THREE.ConeGeometry(0.18, 0.35, 10)
  tete.translate(0, 0.825, 0)
  const g = mergeGeometries([tige, tete])!
  tige.dispose()
  tete.dispose()
  return fab.geo(g)
}

function couleurGradient(i: number, ic: number, out: THREE.Color) {
  const t = Math.min(1, i / (ic || 1))
  return out.setHSL((1 - t) * 0.33, 0.8, 0.45)   // vert -> rouge
}

function specsHydraulique(ctx: Contexte): Spec[] {
  const res = ctx.d.res
  const geo = ctx.d.geo
  const m = ctx.d.m
  const H = m.paroi.tete - m.paroi.pied
  const out: Spec[] = []
  const hydros = res.phases.map((p) => p.hydro ?? null)
  if (!hydros.some(Boolean)) return out

  // bouchon (actif à partir d'une phase)
  if (hydros.some((h) => h?.bouchon)) {
    const cle = hacher(`bouchon|${geo.cle()}`)
    out.push({
      id: 'fouille.bouchon', cle, creer: (cx) => {
        const mesh = cx.fab.obj(new THREE.Mesh(geoBlocUnitaire(cx.fab, geo.points), lambert(cx.fab, 0x7a9a7a, { transparent: true, opacity: 0.55 })))
        const el = base('fouille.bouchon', cle, 'fouille', 'fouille.bouchon', mesh, 'bouchon')
        el.appliquerPhase = (k) => {
          const b = k.ph.hydro?.bouchon
          el.visiblePhase = !!b && caler(mesh, b.base, Math.min(b.toit, k.ph.terrain_aval))
        }
        el.etiquettes = (k, o) => {
          const b = k.ph.hydro?.bouchon
          if (b) o.push({ id: 'nom.bouchon', pos: versThree((geo.xmin + geo.xmax) / 2, (geo.ymin + geo.ymax) / 2, Math.min(b.toit, k.ph.terrain_aval)), texte: `bouchon ${b.type} (${nb(Math.min(b.toit, k.ph.terrain_aval) - b.base, 1)} m)`, calque: 'annotations.noms', selection: 'bouchon' })
        }
        return el
      },
    })
  }

  // surface piézométrique à la cote du fond
  if (hydros.some((h) => h?.charge_fond?.h.some((v) => v !== null))) {
    const pas = Math.max(0.5, geo.taille / 40)
    const x0 = geo.xmin - geo.marge
    const y0 = geo.ymin - geo.marge
    const nx = Math.ceil((geo.xmax + geo.marge - x0) / pas)
    const ny = Math.ceil((geo.ymax + geo.marge - y0) / pas)
    const cle = hacher(`piezo|${geo.cle()}|${pas}`)
    out.push({
      id: 'eau.piezo', cle, creer: (cx) => {
        const n = (nx + 1) * (ny + 1)
        const ds = new Float32Array(n)
        const pos = new Float32Array(3 * n)
        for (let j = 0; j <= ny; j++) for (let i = 0; i <= nx; i++) {
          const k = j * (nx + 1) + i
          const x = x0 + i * pas
          const y = y0 + j * pas
          ds[k] = geo.distanceSignee(x, y)
          pos[3 * k] = x
          pos[3 * k + 2] = -y
        }
        const idx: number[] = []
        for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) {
          const a = j * (nx + 1) + i
          idx.push(a, a + 1, a + nx + 2, a, a + nx + 2, a + nx + 1)
        }
        const g = cx.fab.geo(new THREE.BufferGeometry())
        g.setAttribute('position', new THREE.BufferAttribute(pos, 3))
        g.setAttribute('color', new THREE.BufferAttribute(new Float32Array(3 * n), 3))
        g.setIndex(idx)
        const mesh = cx.fab.obj(new THREE.Mesh(g, cx.fab.mat(new THREE.MeshLambertMaterial({ vertexColors: true, side: THREE.DoubleSide, transparent: true, opacity: 0.55, depthWrite: false }))))
        const cache = new Map<number, { y: Float32Array; c: Float32Array; hmin: number; hmax: number } | null>()
        const col = new THREE.Color()
        const calculer = (k: Contexte) => {
          const cf = k.ph.hydro?.charge_fond
          if (!cf || !cf.h.some((v) => v !== null)) return null
          const xs = cf.x
          const hs = cf.h
          const hAt = (xl: number): number | null => {
            let q = 0
            while (q < xs.length - 1 && xs[q + 1] < xl) q++
            const q1 = Math.min(q + 1, xs.length - 1)
            const h0 = hs[q]
            const h1 = hs[q1]
            if (h0 === null && h1 === null) return null
            if (h0 === null) return h1
            if (h1 === null) return h0
            const t = q1 === q || xs[q1] === xs[q] ? 0 : (xl - xs[q]) / (xs[q1] - xs[q])
            return h0 + Math.max(0, Math.min(1, t)) * (h1 - h0)
          }
          const vals = new Float32Array(n)
          let hmin = Infinity
          let hmax = -Infinity
          for (let q = 0; q < n; q++) {
            const h = hAt(ds[q])
            vals[q] = h === null ? NaN : h
            if (h !== null) { hmin = Math.min(hmin, h); hmax = Math.max(hmax, h) }
          }
          const y = new Float32Array(n)
          const c = new Float32Array(3 * n)
          for (let q = 0; q < n; q++) {
            const h = vals[q]
            y[q] = Number.isNaN(h) ? hmin : h
            const t = hmax > hmin ? (Number.isNaN(h) ? 0 : (h - hmin) / (hmax - hmin)) : 0.5
            col.setHSL(0.6, 0.7, 0.35 + 0.4 * t)
            c[3 * q] = col.r; c[3 * q + 1] = col.g; c[3 * q + 2] = col.b
          }
          return { y, c, hmin, hmax }
        }
        const el = base('eau.piezo', cle, 'eau', 'eau.piezo', mesh)
        let courant: { hmin: number; hmax: number } | null = null
        el.appliquerPhase = (k) => {
          if (!cache.has(k.phase)) cache.set(k.phase, calculer(k))
          const v = cache.get(k.phase)!
          el.visiblePhase = !!v
          courant = v
          if (!v) return
          const pa = g.attributes.position as THREE.BufferAttribute
          const arr = pa.array as Float32Array
          for (let q = 0; q < n; q++) arr[3 * q + 1] = v.y[q]
          pa.needsUpdate = true
          const ca = g.attributes.color as THREE.BufferAttribute
          ;(ca.array as Float32Array).set(v.c)
          ca.needsUpdate = true
          g.computeVertexNormals()
          g.computeBoundingSphere()
        }
        el.majDonnees = () => cache.clear()
        el.etiquettes = (_k, o) => {
          if (courant) o.push({ id: 'cote.piezo', pos: versThree(geo.xmin - geo.marge * 0.6, geo.ymin - geo.marge * 0.6, courant.hmin), texte: `charge piézométrique à la cote du fond : ${nb(courant.hmin, 2)} à ${nb(courant.hmax, 2)} m`, calque: 'annotations.cotes' })
        }
        return el
      },
    })
  }

  // flèches de gradient de sortie (InstancedMesh, nombre maximal préparé une fois)
  const stations: { sp: number; k: number }[] = []
  for (const ar of geo.aretes) {
    if (ar.L < 1e-6) continue
    const n = Math.max(1, Math.round(ar.L / Math.max(2, geo.taille / 10)))
    for (let q = 0; q < n; q++) stations.push({ sp: ((q + 0.5) * ar.L) / n, k: ar.k })
  }
  const maxX = Math.max(0, ...hydros.map((h) => h?.gradient_sortie_x?.length ?? 0))
  if (maxX > 0) {
    const max = stations.length * maxX
    const cle = hacher(`gradients|${geo.cle()}|${max}`)
    out.push({
      id: 'eau.gradients', cle, creer: (cx) => {
        const im = cx.fab.obj(new THREE.InstancedMesh(geoFleche(cx.fab), cx.fab.mat(new THREE.MeshLambertMaterial({ color: 0xffffff })), Math.max(1, max)))
        im.setColorAt(0, new THREE.Color(1, 1, 1))
        const el = base('eau.gradients', cle, 'eau', 'eau.gradients', im)
        const col = new THREE.Color()
        let maxi: { i: number; ic: number } | null = null
        el.appliquerPhase = (k) => {
          const hy = k.ph.hydro
          const ic = ctx.d.m.i_critique[k.phase] ?? 1
          let c = 0
          maxi = null
          if (hy && hy.gradient_sortie && hy.gradient_sortie_max > 0) {
            maxi = { i: hy.gradient_sortie_max, ic }
            const xs = hy.gradient_sortie_x
            const gs = hy.gradient_sortie
            const pasA = Math.max(1, Math.round(xs.length / 8))
            for (const st of stations) {
              const ar = geo.aretes[st.k]
              for (let q = 0; q < xs.length; q += pasA) {
                if (xs[q] <= 0 || xs[q] > Math.min(ar.L, geo.taille) / 2) continue
                const i = gs[q]
                if (i <= 0.02 * ic) continue
                const lg = 0.12 * H * Math.min(1.5, i / ic)
                versThree(ar.A[0] + ar.t[0] * st.sp + ar.ni[0] * xs[q], ar.A[1] + ar.t[1] * st.sp + ar.ni[1] * xs[q], k.ph.terrain_aval, _p)
                _s.set(lg, lg, lg)
                _q.identity()
                im.setMatrixAt(c, _m.compose(_p, _q, _s))
                im.setColorAt(c, couleurGradient(i, ic, col))
                c++
              }
            }
          }
          im.count = c
          el.visiblePhase = c > 0
          im.instanceMatrix.needsUpdate = true
          if (im.instanceColor) im.instanceColor.needsUpdate = true
          im.computeBoundingSphere()
        }
        el.etiquettes = (k, o) => {
          if (maxi) o.push({ id: 'val.gradient', pos: versThree(geo.points[0][0], geo.points[0][1], k.ph.terrain_aval + 0.15 * H), texte: `gradient de sortie max ${nb(maxi.i, 2)} (i_c ≈ ${nb(maxi.ic, 2)})`, calque: 'annotations.cotes' })
        }
        return el
      },
    })
  }

  // équipotentielles sur le plan de coupe actif
  const maxSeg = Math.max(0, ...hydros.map((h) => (h?.equipotentielles ?? []).reduce((s, e) => s + e.segments.length, 0)))
  if (maxSeg > 0) {
    const max = maxSeg * geo.n
    const cle = hacher(`equipot|${geo.cle()}|${max}`)
    out.push({
      id: 'eau.equipotentielles', cle, creer: (cx) => {
        const g = cx.fab.geo(new THREE.BufferGeometry())
        const pos = new Float32Array(6 * max)
        g.setAttribute('position', new THREE.BufferAttribute(pos, 3))
        g.setDrawRange(0, 0)
        const ls = cx.fab.obj(new THREE.LineSegments(g, cx.fab.mat(new THREE.LineBasicMaterial({ color: 0x1f5fae }))))
        ls.frustumCulled = false
        const el = base('eau.equipotentielles', cle, 'eau', 'eau.equipotentielles', ls)
        const remplir = (k: Contexte) => {
          const hy = k.ph.hydro
          const sc = k.scene
          let c = 0
          if (hy?.equipotentielles?.length && sc.coupe.actif) {
            for (const { P, ni } of geo.intersections(sc.coupe.axe, sc.valeurCoupe)) {
              for (const eq of hy.equipotentielles) for (const [xa, za, xb, zb] of eq.segments) {
                if (Math.abs(xa) > geo.marge && Math.abs(xb) > geo.marge) continue
                if (c >= max) break
                versThree(P[0] + ni[0] * xa, P[1] + ni[1] * xa, za, _a)
                versThree(P[0] + ni[0] * xb, P[1] + ni[1] * xb, zb, _b)
                pos.set([_a.x, _a.y, _a.z, _b.x, _b.y, _b.z], 6 * c)
                c++
              }
            }
          }
          g.setDrawRange(0, 2 * c)
          ;(g.attributes.position as THREE.BufferAttribute).needsUpdate = true
          el.visiblePhase = c > 0
          ls.visible = el.visiblePhase && sc.calques.visible(el.calque)
        }
        el.appliquerPhase = remplir
        el.majCoupe = remplir
        return el
      },
    })
  }
  return out
}

// ------------------------------------------------------------------ outils
function specsOutils(ctx: Contexte): Spec[] {
  const geo = ctx.d.geo
  const zSol = Math.max(ctx.d.m.paroi.tete, ...ctx.d.m.couches.map((c) => c.toit))
  const cle = hacher(`outils|${geo.cle()}|${zSol}|${geo.marge}`)
  return [
    {
      id: 'outils.grille', cle, creer: (cx) => {
        const taille = Math.ceil(geo.taille + 2 * geo.marge)
        const grille = cx.fab.obj(new THREE.GridHelper(taille, Math.max(4, Math.round(taille / 2)), 0x8893a2, 0xc5ccd6))
        cx.fab.geo(grille.geometry)
        for (const m of Array.isArray(grille.material) ? grille.material : [grille.material]) {
          cx.fab.mat(m)
          m.transparent = true
          m.opacity = 0.35
        }
        grille.position.set((geo.xmin + geo.xmax) / 2, zSol + 0.01, -(geo.ymin + geo.ymax) / 2)
        return base('outils.grille', cle, 'outils', 'outils.grille', grille)
      },
    },
    {
      id: 'outils.axes', cle, creer: (cx) => {
        const ax = cx.fab.obj(new THREE.AxesHelper(3))
        cx.fab.geo(ax.geometry)
        for (const m of Array.isArray(ax.material) ? ax.material : [ax.material]) cx.fab.mat(m)
        ax.position.copy(versThree(geo.xmin - geo.marge + 1, geo.ymin - geo.marge + 1, zSol + 0.02))
        const el = base('outils.axes', cle, 'outils', 'outils.axes', ax)
        el.etiquettes = (_k, o) => {
          o.push({ id: 'axe.x', pos: versThree(geo.xmin - geo.marge + 4.3, geo.ymin - geo.marge + 1, zSol), texte: 'x', calque: 'outils.axes', classe: 'axe' })
          o.push({ id: 'axe.y', pos: versThree(geo.xmin - geo.marge + 1, geo.ymin - geo.marge + 4.3, zSol), texte: 'y (nord)', calque: 'outils.axes', classe: 'axe' })
        }
        return el
      },
    },
    {
      id: 'outils.plan_coupe', cle: hacher(`${cle}|plan|${ctx.d.m.z_bas}`), creer: (cx) => {
        const clePlan = hacher(`${cle}|plan|${ctx.d.m.z_bas}`)
        const H = zSol - ctx.d.m.z_bas
        const L = geo.taille + 2 * geo.marge
        const mesh = cx.fab.obj(new THREE.Mesh(cx.fab.geo(new THREE.PlaneGeometry(1, 1)),
          cx.fab.mat(new THREE.MeshBasicMaterial({ color: 0x2f5d8a, transparent: true, opacity: 0.08, side: THREE.DoubleSide, depthWrite: false }))))
        const el = base('outils.plan_coupe', clePlan, 'outils', 'outils.plan_coupe', mesh)
        const placer = (k: Contexte) => {
          const sc = k.scene
          el.visiblePhase = sc.coupe.actif
          mesh.visible = el.visiblePhase && sc.calques.visible(el.calque)
          const v = sc.valeurCoupe
          if (sc.coupe.axe === 'x') {
            mesh.position.set(v, (zSol + ctx.d.m.z_bas) / 2, -(geo.ymin + geo.ymax) / 2)
            mesh.rotation.set(0, Math.PI / 2, 0)
          } else {
            mesh.position.set((geo.xmin + geo.xmax) / 2, (zSol + ctx.d.m.z_bas) / 2, -v)
            mesh.rotation.set(0, 0, 0)
          }
          mesh.scale.set(L, H, 1)
        }
        el.appliquerPhase = placer
        el.majCoupe = placer
        return el
      },
    },
  ]
}

/** Toutes les familles d'objets « chantier ». */
export const FABRIQUES_CHANTIER = [specsSol, specsEau, specsParoi, specsAppuis, specsHydraulique, specsOutils]

export type { Contour, Etiquette }
