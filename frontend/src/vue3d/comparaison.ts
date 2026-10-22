// Mode comparaison : superposition en fantôme de la déformée d'une phase de référence.
import * as THREE from 'three'
import { nb } from '../lib/format'
import { demiEpaisseur } from './elements'
import { hacher, type Arete } from './geometrie'
import { amplification, NZ } from './resultats'
import { reglageCalque, type Contexte, type Element, type Spec } from './scene'
import { profilValeur, sourcePour } from './resultats'
import { attenuationAngle, versThree } from './geometrie'

/** Phase de référence du mode comparaison (réglage du calque), null si aucune. */
export function phaseReference(ctx: Contexte): number | null {
  const r = reglageCalque<number | string>(ctx.scene.calques, 'resultats.comparaison', 'phase', 0)
  const i = Number(r)
  if (!Number.isFinite(i) || i <= 0) return null
  return Math.min(i - 1, ctx.d.res.phases.length - 1)
}

function specsComparaison(ctx: Contexte): Spec[] {
  const geo = ctx.d.geo
  const p = ctx.d.m.paroi
  const offset = demiEpaisseur(p) + 0.03
  const out: Spec[] = []
  for (const a of geo.aretes) {
    if (a.L < 1e-6) continue
    const id = `resultats.comparaison.${a.k}`
    const cle = hacher(`${id}|${a.A}|${a.B}|${p.pied}|${p.tete}`)
    out.push({
      id, cle, creer: (cx) => {
        const ns = Math.max(2, Math.round(a.L / 1.0)) + 1
        const g = cx.fab.geo(new THREE.BufferGeometry())
        g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(3 * ns * NZ), 3))
        const idx: number[] = []
        for (let i = 0; i < ns - 1; i++) for (let j = 0; j < NZ - 1; j++) { const q = i * NZ + j; idx.push(q, q + 1, q + NZ + 1, q, q + NZ + 1, q + NZ) }
        g.setIndex(idx)
        const mat = cx.fab.mat(new THREE.MeshBasicMaterial({ color: 0x6c3fa0, wireframe: true, transparent: true, opacity: 0.45, depthWrite: false }))
        const mesh = cx.fab.obj(new THREE.Mesh(g, mat))
        const el: Element = { id, cle, noeud: 'resultats', calque: 'resultats.comparaison', objet: mesh, visiblePhase: true }
        let ref: number | null = null
        el.appliquerPhase = (k) => {
          ref = phaseReference(k)
          el.visiblePhase = ref !== null && !!k.d.res.phases[ref]?.ok
          if (ref === null || !el.visiblePhase) return
          const amp = amplification(k)
          const src = sourcePour(k, a.k, a.L / 2)
          const la = Math.min(0.25 * a.L, p.tete - p.pied)
          const arr = g.attributes.position.array as Float32Array
          const v = new THREE.Vector3()
          remplir(arr, a as Arete, ns, src.res, ref, amp, offset, la, !!k.d.res.pseudo3d, v)
          ;(g.attributes.position as THREE.BufferAttribute).needsUpdate = true
          g.computeBoundingSphere()
        }
        el.etiquettes = (k, o) => {
          if (ref === null || a.k !== 0) return
          o.push({ id: 'comparaison', pos: versThree(a.A[0] + a.t[0] * (a.L / 2) + a.ni[0] * 2.5, a.A[1] + a.t[1] * (a.L / 2) + a.ni[1] * 2.5, p.tete + 0.6),
            texte: `fantôme : phase ${ref + 1} (${k.d.res.phases[ref].nom}) × ${nb(amplification(k), 0)}`, calque: 'resultats.comparaison', classe: 'valeur' })
        }
        return el
      },
    })
  }
  return out
}

function remplir(arr: Float32Array, a: Arete, ns: number, res: Contexte['d']['res'], phase: number, amp: number, offset: number, la: number, p3d: boolean, v: THREE.Vector3) {
  const p = res.paroi
  for (let i = 0; i < ns; i++) {
    const sl = (a.L * i) / (ns - 1)
    const f = profilValeur(res, phase, 'y', a.s0 + sl)
    const att = p3d ? 1 : attenuationAngle(sl, a.L, la)
    for (let j = 0; j < NZ; j++) {
      const z = p.pied + ((p.tete - p.pied) * j) / (NZ - 1)
      const d = offset + (f ? (f(z) / 1000) * amp * att : 0)
      versThree(a.A[0] + a.t[0] * sl + a.ni[0] * d, a.A[1] + a.t[1] * sl + a.ni[1] * d, z, v)
      const q = 3 * (i * NZ + j)
      arr[q] = v.x; arr[q + 1] = v.y; arr[q + 2] = v.z
    }
  }
}

export const FABRIQUES_COMPARAISON = [specsComparaison]
