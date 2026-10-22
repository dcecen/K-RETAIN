// Outil « Couper ici » : plan vertical local que l'utilisateur place sur la paroi (clic, glissement
// ou abscisse saisie). Le panneau latéral lit les courbes par la source de résultats abstraite.
import * as THREE from 'three'
import { nb } from '../lib/format'
import { hacher, versThree, type Contour } from './geometrie'
import type { Contexte, Element, Spec } from './scene'

export interface PositionCoupeLocale { k: number; sl: number }

/** Position de coupe locale la plus proche d'un point three (projection sur le contour). */
export function positionDepuisPoint(geo: Contour, p: THREE.Vector3): PositionCoupeLocale {
  const r = geo.projeter(p.x, -p.z)
  return { k: r.k, sl: r.sl }
}

function specCoupeLocale(ctx: Contexte): Spec[] {
  const geo = ctx.d.geo
  const p = ctx.d.m.paroi
  const zHaut = Math.max(p.tete, ...ctx.d.m.couches.map((c) => c.toit)) + 0.5
  const zBas = ctx.d.m.z_bas
  const id = 'coupes.locale'
  const cle = hacher(`${id}|${geo.cle()}|${zHaut}|${zBas}`)
  return [{
    id, cle, creer: (cx) => {
      const L = Math.min(10, Math.max(5, 0.35 * geo.taille))
      const mat = cx.fab.mat(new THREE.MeshBasicMaterial({ color: 0xe39a2b, transparent: true, opacity: 0.18, side: THREE.DoubleSide, depthWrite: false }))
      const mesh = cx.fab.obj(new THREE.Mesh(cx.fab.geo(new THREE.PlaneGeometry(1, 1)), mat))
      mesh.add(cx.fab.obj(new THREE.LineSegments(cx.fab.geo(new THREE.EdgesGeometry(mesh.geometry)), cx.fab.mat(new THREE.LineBasicMaterial({ color: 0xe39a2b })))))
      const el: Element = { id, cle, noeud: 'coupes', calque: 'coupes.locale', objet: mesh, selection: 'coupe_locale', visiblePhase: false }
      const placer = (k: Contexte) => {
        const pos = k.scene.coupeLocale
        el.visiblePhase = !!pos
        mesh.visible = el.visiblePhase && k.scene.calques.visible(el.calque)
        if (!pos) return
        const a = geo.aretes[pos.k]
        const sl = Math.min(Math.max(pos.sl, 0), a.L)
        versThree(a.A[0] + a.t[0] * sl, a.A[1] + a.t[1] * sl, (zHaut + zBas) / 2, mesh.position)
        mesh.rotation.y = Math.atan2(-a.ni[1], a.ni[0])
        mesh.scale.set(2 * L, zHaut - zBas, 1)
      }
      el.appliquerPhase = placer
      el.majCoupe = placer
      el.etiquettes = (k, o) => {
        const pos = k.scene.coupeLocale
        if (!pos) return
        const a = geo.aretes[pos.k]
        o.push({ id: 'coupe.locale', pos: versThree(a.A[0] + a.t[0] * pos.sl, a.A[1] + a.t[1] * pos.sl, p.tete + 1.2), texte: `Couper ici · côté ${pos.k} · s = ${nb(pos.sl, 1)} m`, calque: 'coupes.locale', classe: 'coupe', selection: 'coupe_locale' })
      }
      return el
    },
  }]
}

export const FABRIQUES_COUPE_LOCALE = [specCoupeLocale]
