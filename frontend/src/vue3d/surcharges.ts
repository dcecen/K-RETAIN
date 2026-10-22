// Surcharges dans la maquette : volume translucide à l'emprise (hauteur ∝ valeur), flèches
// descendantes, bâtiment à niveaux, grue, ligne ; présentes entre leur phase d'application et
// leur retrait ; pression induite Δσv(z) au droit de la coupe (profil calculé par le serveur,
// module sol/terrain.py) en ailette sur la face terre.
import * as THREE from 'three'
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js'
import type { SurchargeMaquette } from '../lib/api'
import { nb } from '../lib/format'
import { demiEpaisseur, lambert } from './elements'
import { hacher, versThree, type Contour, type Point2 } from './geometrie'
import { geoRuban, remplirRuban, zGrille } from './resultats'
import { reglageCalque, type Contexte, type Element, type Spec } from './scene'

export const ECHELLE_DEFAUT = 20   // kPa par mètre de hauteur
const HAUTEUR_NIVEAU = 3.0

/** Hauteur visuelle (m) d'une surcharge : q / échelle, bornée. */
export function hauteurVisuelle(s: SurchargeMaquette, echelle: number): number {
  if (s.type === 'ponctuelle' && s.emprise) return Math.min(12, Math.max(0.5, s.q / (s.emprise[0] * s.emprise[1]) / echelle))
  if (s.type === 'ponctuelle' || s.type === 'lineaire' || s.type === 'lineique') return Math.min(12, Math.max(0.5, s.q / (10 * echelle)))
  return Math.min(12, Math.max(0.3, s.q / echelle))
}

/** La surcharge existe-t-elle à l'indice de phase k (0 = état initial, k = k-ième phase du script) ? */
export function activeA(s: SurchargeMaquette, k: number): boolean {
  return k >= s.phase_debut && k <= s.phase_fin
}

/** Entrée YAML d'une surcharge rectangulaire tracée dans la maquette (deux coins en plan). */
export function entreeYamlSurcharge(nom: string, q: number, p1: Point2, p2: Point2, phase?: number | null): Record<string, unknown> {
  const r2 = (v: number) => Math.round(v * 100) / 100
  const e: Record<string, unknown> = {
    nom, type: 'rectangulaire', q,
    position: [r2((p1[0] + p2[0]) / 2), r2((p1[1] + p2[1]) / 2)],
    emprise: [r2(Math.max(0.5, Math.abs(p2[0] - p1[0]))), r2(Math.max(0.5, Math.abs(p2[1] - p1[1])))],
  }
  if (phase) e.phase = phase
  return e
}

/** Côtés concernés par une surcharge relative à la paroi (noms de plan.cotes, « #k » pour un numéro). */
function aretesConcernees(geo: Contour, s: SurchargeMaquette, cotes: Record<string, number>): number[] {
  if (!s.cotes_paroi) return geo.aretes.filter((a) => a.L > 1e-6).map((a) => a.k)
  const ks = new Set<number>()
  for (const c of s.cotes_paroi) {
    if (c.startsWith('#')) ks.add(Number(c.slice(1)))
    else if (cotes[c] !== undefined) ks.add(cotes[c])
  }
  return [...ks]
}

function geoFlechesBas(fab: Contexte['fab']) {
  const tige = new THREE.CylinderGeometry(0.05, 0.05, 0.6, 6)
  tige.translate(0, 0.55, 0)
  const tete = new THREE.ConeGeometry(0.16, 0.3, 8)
  tete.rotateX(Math.PI)
  tete.translate(0, 0.15, 0)
  const g = mergeGeometries([tige, tete])!
  tige.dispose()
  tete.dispose()
  return fab.geo(g)
}

interface Boite { cx: number; cy: number; lx: number; ly: number; angle: number }

/** Boîtes en plan (centre, dimensions, orientation) représentant l'emprise d'une surcharge. */
export function emprises(geo: Contour, s: SurchargeMaquette, cotes: Record<string, number>): Boite[] {
  const out: Boite[] = []
  if (s.type === 'rectangulaire' || (s.type === 'ponctuelle' && s.emprise)) {
    if (s.position && s.emprise) out.push({ cx: s.position[0], cy: s.position[1], lx: s.emprise[0], ly: s.emprise[1], angle: 0 })
  } else if (s.type === 'ponctuelle') {
    if (s.position) out.push({ cx: s.position[0], cy: s.position[1], lx: 1, ly: 1, angle: 0 })
  } else if (s.type === 'lineaire' || s.type === 'lineique') {
    if (s.trace) {
      const [P, Q] = s.trace
      out.push({ cx: (P[0] + Q[0]) / 2, cy: (P[1] + Q[1]) / 2, lx: Math.max(0.5, Math.hypot(Q[0] - P[0], Q[1] - P[1])), ly: 0.6, angle: Math.atan2(Q[1] - P[1], Q[0] - P[0]) })
    } else {
      // linéique historique : parallèle à chaque côté, à la distance donnée
      for (const k of aretesConcernees(geo, s, cotes)) {
        const a = geo.aretes[k]
        const d = (s.distance ?? 0)
        out.push({ cx: (a.A[0] + a.B[0]) / 2 - a.ni[0] * d, cy: (a.A[1] + a.B[1]) / 2 - a.ni[1] * d, lx: a.L, ly: 0.6, angle: Math.atan2(a.t[1], a.t[0]) })
      }
    }
  } else {
    // uniforme / répartie / bande : zone derrière chaque côté concerné
    for (const k of aretesConcernees(geo, s, cotes)) {
      const a = geo.aretes[k]
      const d0 = s.type === 'bande' ? (s.distance ?? 0) : (s.largeur ? (s.distance ?? 0) : 0)
      const larg = s.largeur ?? geo.marge
      let de = 0
      let fin = a.L
      if (s.type === 'bande' && s.emprise) { de = Math.max(0, Math.min(s.emprise[0], s.emprise[1])); fin = Math.min(a.L, Math.max(s.emprise[0], s.emprise[1])) }
      const sm = 0.5 * (de + fin)
      const dm = d0 + larg / 2
      out.push({ cx: a.A[0] + a.t[0] * sm - a.ni[0] * dm, cy: a.A[1] + a.t[1] * sm - a.ni[1] * dm, lx: Math.max(0.5, fin - de), ly: larg, angle: Math.atan2(a.t[1], a.t[0]) })
    }
  }
  return out
}

function specsSurcharges(ctx: Contexte): Spec[] {
  const liste = ctx.d.m.surcharges ?? []
  const geo = ctx.d.geo
  const cotes = ctx.d.cotes ?? {}
  const out: Spec[] = []
  liste.forEach((s, i) => {
    const boites = emprises(geo, s, cotes)
    if (!boites.length) return
    const id = `surcharges.volume.${i}`
    const cle = hacher(`${id}|${JSON.stringify({ ...s, profil: undefined })}|${JSON.stringify(boites)}`)
    out.push({
      id, cle, creer: (cx) => {
        const fab = cx.fab
        const groupe = fab.obj(new THREE.Group())
        const teinte = s.type === 'ponctuelle' ? 0xd98c2b : s.niveaux ? 0xb0b7c3 : 0xd9a441
        const mat = lambert(fab, teinte, { transparent: true, opacity: 0.45, depthWrite: false })
        const matBord = fab.mat(new THREE.LineBasicMaterial({ color: 0x8a6a1e, transparent: true, opacity: 0.8 }))
        const geoBoite = fab.geo(new THREE.BoxGeometry(1, 1, 1))
        const geoBord = fab.geo(new THREE.EdgesGeometry(geoBoite))
        const corps: THREE.Mesh[] = []
        for (const b of boites) {
          const m = fab.obj(new THREE.Mesh(geoBoite, mat))
          m.add(fab.obj(new THREE.LineSegments(geoBord, matBord)))
          m.userData.boite = b
          groupe.add(m)
          corps.push(m)
        }
        // bâtiment : lignes de niveaux ; grue : fût et flèche
        let niveaux: THREE.LineSegments | null = null
        if (s.niveaux && s.niveaux > 1) {
          const g = fab.geo(new THREE.BufferGeometry())
          g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(3 * 8 * (s.niveaux - 1)), 3))
          niveaux = fab.obj(new THREE.LineSegments(g, matBord))
          groupe.add(niveaux)
        }
        let grue: THREE.Group | null = null
        if (s.type === 'ponctuelle' && s.emprise) {
          grue = fab.obj(new THREE.Group())
          const matG = lambert(fab, 0xe3a54a)
          const fut = fab.obj(new THREE.Mesh(fab.geo(new THREE.CylinderGeometry(0.4, 0.4, 1, 10)), matG))
          const fleche = fab.obj(new THREE.Mesh(fab.geo(new THREE.BoxGeometry(1, 0.5, 0.5)), matG))
          grue.add(fut, fleche)
          groupe.add(grue)
        }
        // flèches descendantes sur la face supérieure
        const nF = Math.min(16, Math.max(2, Math.round(boites.reduce((t, b) => t + b.lx * b.ly, 0) / 6)))
        const fleches = fab.obj(new THREE.InstancedMesh(geoFlechesBas(fab), lambert(fab, 0x7a4a0e), nF * boites.length))
        groupe.add(fleches)
        const m4 = new THREE.Matrix4()
        const el: Element = { id, cle, noeud: 'surcharges', calque: 'surcharges.volumes', objet: groupe, selection: `surcharge:${i}`, visiblePhase: true }
        let base = 0
        let haut = 0
        el.appliquerPhase = (k) => {
          el.visiblePhase = activeA(s, k.phase)
          if (!el.visiblePhase) return
          const ech = reglageCalque(k.scene.calques, 'surcharges.volumes', 'echelle', ECHELLE_DEFAUT)
          const zApp = s.cote ?? (k.ph.terrain_amont - (s.profondeur ?? 0))
          const h = s.niveaux ? s.niveaux * HAUTEUR_NIVEAU : hauteurVisuelle(s, ech)
          base = zApp
          haut = zApp + h
          let f = 0
          corps.forEach((m) => {
            const b = m.userData.boite as Boite
            versThree(b.cx, b.cy, zApp + h / 2, m.position)
            m.rotation.y = -b.angle
            m.scale.set(b.lx, h, b.ly)
            const nx = Math.max(1, Math.round(Math.sqrt(nF * (b.lx / (b.lx + b.ly)))))
            const ny = Math.max(1, Math.round(nF / nx))
            for (let ix = 0; ix < nx && f < fleches.count; ix++) for (let iy = 0; iy < ny && f < fleches.count; iy++) {
              const u = ((ix + 0.5) / nx - 0.5) * b.lx
              const v = ((iy + 0.5) / ny - 0.5) * b.ly
              const x = b.cx + u * Math.cos(b.angle) - v * Math.sin(b.angle)
              const y = b.cy + u * Math.sin(b.angle) + v * Math.cos(b.angle)
              const p = versThree(x, y, zApp + h)
              fleches.setMatrixAt(f++, m4.makeTranslation(p.x, p.y, p.z))
            }
          })
          for (let r = f; r < fleches.count; r++) fleches.setMatrixAt(r, m4.makeScale(0, 0, 0))
          fleches.instanceMatrix.needsUpdate = true
          fleches.computeBoundingSphere()
          if (niveaux) {
            const arr = niveaux.geometry.attributes.position.array as Float32Array
            const b = corps[0].userData.boite as Boite
            const c = [[-b.lx / 2, -b.ly / 2], [b.lx / 2, -b.ly / 2], [b.lx / 2, b.ly / 2], [-b.lx / 2, b.ly / 2]]
            let q = 0
            for (let n = 1; n < (s.niveaux ?? 1); n++) {
              const zN = zApp + n * HAUTEUR_NIVEAU
              for (let j = 0; j < 4; j++) {
                for (const [u, v] of [c[j], c[(j + 1) % 4]]) {
                  const p = versThree(b.cx + u * Math.cos(b.angle) - v * Math.sin(b.angle), b.cy + u * Math.sin(b.angle) + v * Math.cos(b.angle), zN)
                  arr[q++] = p.x; arr[q++] = p.y; arr[q++] = p.z
                }
              }
            }
            ;(niveaux.geometry.attributes.position as THREE.BufferAttribute).needsUpdate = true
          }
          if (grue && s.position) {
            const H = 18
            const fut = grue.children[0]
            const fl = grue.children[1]
            versThree(s.position[0], s.position[1], zApp + H / 2, fut.position)
            fut.scale.set(1, H, 1)
            versThree(s.position[0] + 9, s.position[1], zApp + H + 0.3, fl.position)
            fl.scale.set(22, 1, 1)
          }
        }
        el.etiquettes = (_k, o) => {
          const b = corps[0].userData.boite as Boite
          const unite = s.type === 'ponctuelle' ? 'kN' : s.type === 'lineaire' || s.type === 'lineique' ? 'kN/m' : 'kPa'
          o.push({ id: `nom.surcharge.${i}`, pos: versThree(b.cx, b.cy, haut + 0.8), texte: `${s.nom} · ${nb(s.q, 0)} ${unite}${s.niveaux ? ` · ${s.niveaux} niveaux` : ''}`, calque: 'surcharges.volumes', selection: `surcharge:${i}` })
          void base
        }
        el.surligner = (actif) => { mat.emissive.setHex(actif ? 0x553300 : 0x000000); mat.opacity = actif ? 0.65 : 0.45 }
        return el
      },
    })
  })
  // pression induite : ailette Δσv sur la face terre au droit de la coupe, visible si le calque l'est ou si la surcharge est sélectionnée
  const p = ctx.d.m.paroi
  const cc = ctx.d.m.coupe_calcul
  const station = cc ? { k: cc.k, sl: cc.s } : (() => { const a = geo.aretes.reduce((m, x) => (x.L > m.L ? x : m), geo.aretes[0]); return { k: a.k, sl: a.L / 2 } })()
  liste.forEach((s, i) => {
    const profil = s.profil
    if (!profil || !profil.dsv.some((v) => v > 0)) return
    const id = `surcharges.pression.${i}`
    const cle = hacher(`${id}|${JSON.stringify(profil)}|${station.k}|${station.sl}|${p.pied}|${p.tete}`)
    out.push({
      id, cle, creer: (cx) => {
        const z = zGrille(p.pied, p.tete)
        const g = cx.fab.geo(geoRuban(z.length))
        const mesh = cx.fab.obj(new THREE.Mesh(g, cx.fab.mat(new THREE.MeshLambertMaterial({ vertexColors: true, side: THREE.DoubleSide, transparent: true, opacity: 0.8 }))))
        mesh.frustumCulled = false
        const el: Element = { id, cle, noeud: 'surcharges', calque: 'surcharges.pressions', calques: ['surcharges.volumes'], objet: mesh, visiblePhase: true }
        const a = geo.aretes[station.k]
        const offset = demiEpaisseur(p) + 0.05
        const H = p.tete - p.pied
        const max = Math.max(...profil.dsv, 1e-6)
        let maxi = 0
        el.appliquerPhase = (k) => {
          const c = k.scene.calques
          el.visiblePhase = activeA(s, k.phase) && (c.visible('surcharges.pressions') || k.scene.selection === `surcharge:${i}`)
          if (!el.visiblePhase) return
          const f = (zz: number) => { const zs = profil.z; let j = 0; while (j < zs.length - 2 && zs[j + 1] < zz) j++; const t = (zz - zs[j]) / ((zs[j + 1] - zs[j]) || 1); return zz < zs[0] || zz > zs[zs.length - 1] ? 0 : profil.dsv[j] + Math.min(Math.max(t, 0), 1) * (profil.dsv[j + 1] - profil.dsv[j]) }
          remplirRuban(g, a, station.sl, z, offset, -1, f, (0.25 * H) / max, () => 0xc98a2b)
          maxi = max
        }
        el.etiquettes = (_k, o) => {
          const d = offset + 0.25 * H
          o.push({ id: `dsv.${i}`, pos: versThree(a.A[0] + a.t[0] * station.sl - a.ni[0] * d, a.A[1] + a.t[1] * station.sl - a.ni[1] * d, p.tete - 0.3 * H),
            texte: `${s.nom} : Δσv max ${nb(maxi, 1)} kPa (pression horizontale ≈ Ka × Δσv)`, calque: 'surcharges.volumes', classe: 'valeur', selection: `surcharge:${i}` })
        }
        return el
      },
    })
  })
  return out
}

export const FABRIQUES_SURCHARGES = [specsSurcharges]
