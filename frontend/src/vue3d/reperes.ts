// Repères liés au panneau de résultats : curseur de cote sur la paroi (survol d'une courbe),
// marqueurs d'alerte sur les éléments dont une vérification dépasse 90 %.
import * as THREE from 'three'
import { nb } from '../lib/format'
import { demiEpaisseur, extremitesAppui, lambert } from './elements'
import { hacher, versThree } from './geometrie'
import { pointsAttention } from './navigation'
import type { Contexte, Element, Spec } from './scene'

function specRepereCote(ctx: Contexte): Spec[] {
  const geo = ctx.d.geo
  const p = ctx.d.m.paroi
  const id = 'annotations.repere'
  const cle = hacher(`${id}|${geo.cle()}|${demiEpaisseur(p)}`)
  return [{
    id, cle, creer: (cx) => {
      const mat = lambert(cx.fab, 0xe39a2b, { emissive: 0x553300 })
      const mesh = cx.fab.obj(new THREE.Mesh(cx.fab.geo(new THREE.BoxGeometry(1, 0.12, 1)), mat))
      const el: Element = { id, cle, noeud: 'annotations', calque: 'annotations.cotes', objet: mesh, visiblePhase: false }
      const placer = (k: Contexte) => {
        const r = k.scene.repereCote
        el.visiblePhase = !!r
        mesh.visible = el.visiblePhase && k.scene.calques.visible(el.calque)
        if (!r) return
        const a = geo.aretes[r.k] ?? geo.aretes[0]
        const o = demiEpaisseur(p) + 0.1
        versThree((a.A[0] + a.B[0]) / 2 + a.ni[0] * o, (a.A[1] + a.B[1]) / 2 + a.ni[1] * o, r.z, mesh.position)
        mesh.rotation.y = Math.atan2(-a.t[1], a.t[0])
        mesh.scale.set(a.L, 1, 0.25)
      }
      el.appliquerPhase = placer
      el.majCoupe = placer
      el.etiquettes = (k, o) => {
        const r = k.scene.repereCote
        if (!r) return
        const a = geo.aretes[r.k] ?? geo.aretes[0]
        o.push({ id: 'repere.cote', pos: versThree(a.A[0] + a.ni[0] * 0.5, a.A[1] + a.ni[1] * 0.5, r.z), texte: `z = ${nb(r.z, 2)} m`, calque: 'annotations.cotes', classe: 'valeur' })
      }
      return el
    },
  }]
}

function specAlertes(ctx: Contexte): Spec[] {
  const geo = ctx.d.geo
  const id = 'resultats.alertes'
  const cle = hacher(`${id}|${geo.cle()}`)
  return [{
    id, cle, creer: (cx) => {
      const groupe = cx.fab.obj(new THREE.Group())
      const el: Element = { id, cle, noeud: 'resultats', calque: 'resultats.alertes', objet: groupe, visiblePhase: true }
      let points = pointsAttention(cx.d.res, cx.d.m.assemblages)
      el.majDonnees = (k) => { points = pointsAttention(k.d.res, k.d.m.assemblages) }
      el.etiquettes = (k, o) => {
        const m = k.d.m
        const vus = new Set<string>()
        for (const pt of points) {
          if (vus.has(pt.selection)) continue
          vus.add(pt.selection)
          const [type, nom] = pt.selection.split(':')
          let pos: THREE.Vector3 | null = null
          const a0 = geo.aretes.reduce((x, y) => (y.L > x.L ? y : x), geo.aretes[0])
          if (type === 'appui' || type === 'lierne' || type === 'assemblage') {
            const nomAppui = type === 'assemblage' ? m.assemblages[nom]?.appui ?? '' : nom
            const a = m.appuis[nomAppui]
            const pa = m.plan_appuis.find((x) => x.appui === nomAppui)
            if (a && pa) {
              const e = extremitesAppui(a, pa, k.ph.terrain_aval)
              pos = e.de.clone().lerp(e.fin, type === 'lierne' ? 0.02 : type === 'assemblage' ? 0.08 : 0.5)
              pos.y += 0.6
            } else if (a) pos = versThree((a0.A[0] + a0.B[0]) / 2, (a0.A[1] + a0.B[1]) / 2, a.cote + 0.6)
          } else if (type === 'fond' || type === 'bouchon') {
            pos = versThree((geo.xmin + geo.xmax) / 2, (geo.ymin + geo.ymax) / 2, k.ph.terrain_aval + 0.4)
          } else {
            pos = versThree((a0.A[0] + a0.B[0]) / 2 + a0.ni[0] * 0.6, (a0.A[1] + a0.B[1]) / 2 + a0.ni[1] * 0.6, m.paroi.tete + 0.4)
          }
          if (!pos) continue
          const qui = type === 'paroi' ? 'paroi' : type === 'lierne' ? `lierne ${nom}` : type === 'fond' ? 'fond de fouille' : type === 'bouchon' ? 'bouchon' : nom
          o.push({ id: `alerte.${pt.selection}`, pos, texte: `${qui} : ${pt.taux !== null ? `taux ${nb(pt.taux * 100, 0)} %` : 'non vérifiable'}${pt.etat === 'non_ok' ? ', non vérifié' : ''}`,
            calque: 'resultats.alertes', classe: pt.etat === 'non_ok' || (pt.taux ?? 0) >= 1 ? 'alerte rouge' : 'alerte orange', selection: pt.selection })
        }
      }
      return el
    },
  }]
}

export const FABRIQUES_REPERES = [specRepereCote, specAlertes]
