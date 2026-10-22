import type * as THREE from 'three'
import { describe, expect, it } from 'vitest'
import { transition } from '../animation'
import { definirReglage, definirVisible, etatInitial, versScene } from '../calques'
import { FABRIQUES_COMPARAISON, phaseReference } from '../comparaison'
import { FABRIQUES_CHANTIER } from '../elements'
import { sceneExportable } from '../exports'
import { FABRIQUES_RESULTATS_PAROI, NZ } from '../resultats'
import { indicePhase, jeu, nouvelleScene } from './outils'

const TOUT = [...FABRIQUES_CHANTIER, ...FABRIQUES_RESULTATS_PAROI, ...FABRIQUES_COMPARAISON]

describe('animation, comparaison, exports', () => {
  it('la transition interpole le fond de fouille et la déformée, puis atteint exactement la phase cible', () => {
    const { sc } = nouvelleScene(TOUT)
    const res = jeu('exemple')
    sc.charger(res)
    sc.appliquerCalques(versScene(definirVisible(etatInitial(), 'resultats.deformee', true)))
    const i0 = indicePhase(res, 'Pose du buton B1')
    const i1 = indicePhase(res, 'Terrassement final et pompage')
    sc.phase(i0)
    const sable = sc.elements.get('fouille.couche.1')!.objet
    const haut0 = sable.position.y + sable.scale.y
    const surf = sc.elements.get('resultats.surface.0')!.objet.children[0] as THREE.Mesh
    const pos = surf.geometry.attributes.position as THREE.BufferAttribute
    const x0 = pos.getZ(Math.floor(pos.count / 2))
    const tr = transition(sc, i1, 400)!
    expect(tr).not.toBeNull()
    expect(tr.avancer(200)).toBe(false)
    const hautMi = sable.position.y + sable.scale.y
    expect(hautMi).toBeCloseTo((haut0 + -6.5) / 2, 6)              // mi-course : fond à mi-chemin entre −2 et −6,5
    const xMi = pos.getZ(Math.floor(pos.count / 2))
    expect(tr.avancer(400)).toBe(true)
    expect(sable.position.y + sable.scale.y).toBeCloseTo(-6.5, 6)
    const x1 = pos.getZ(Math.floor(pos.count / 2))
    expect(Math.abs(xMi - (x0 + x1) / 2)).toBeLessThan(1e-4)         // déformée interpolée à mi-course
    expect(sc.phaseActive).toBe(i1)
    // sans animation possible : même phase → null ; durée nulle → null
    expect(transition(sc, i1, 400)).toBeNull()
    expect(transition(sc, i0, 0)).toBeNull()
    const t2 = transition(sc, i0, 100)!
    t2.annuler()
    expect(sable.position.y + sable.scale.y).toBeCloseTo(haut0, 6)     // annulation : état exact de la phase cible
  })

  it('le fantôme de comparaison reproduit la déformée de la phase de référence', () => {
    const { sc } = nouvelleScene(TOUT)
    const res = jeu('exemple')
    sc.charger(res)
    const iRef = indicePhase(res, 'Terrassement final et pompage')
    let e = definirVisible(etatInitial(), 'resultats.deformee', true)
    e = definirVisible(e, 'resultats.comparaison', true)
    e = definirReglage(e, 'resultats.comparaison', 'phase', iRef + 1)
    sc.appliquerCalques(versScene(e))
    sc.phase(indicePhase(res, 'Pose du buton B1'))
    const fant = sc.elements.get('resultats.comparaison.0')!
    expect(fant.objet.visible).toBe(true)
    expect(sc.etiquettesCourantes.find((x) => x.id === 'comparaison')!.texte).toContain(`phase ${iRef + 1}`)
    const pf = (fant.objet as THREE.Mesh).geometry.attributes.position as THREE.BufferAttribute
    // la surface déformée à la phase de référence coïncide avec le fantôme
    sc.phase(iRef)
    const ps = (sc.elements.get('resultats.surface.0')!.objet.children[0] as THREE.Mesh).geometry.attributes.position as THREE.BufferAttribute
    const j = Math.floor(ps.count / NZ / 2) * NZ + Math.round(NZ * 0.6)
    expect(pf.getZ(j)).toBeCloseTo(ps.getZ(j), 4)
    expect(pf.getY(j)).toBeCloseTo(ps.getY(j), 4)
    sc.appliquerCalques(versScene(definirReglage(e, 'resultats.comparaison', 'phase', 0)))
    expect(fant.objet.visible).toBe(false)
    expect(phaseReference({ scene: sc, d: sc.d!, phase: 0, ph: res.phases[0], fab: sc.fab, plan: sc.planCoupe })).toBeNull()
  })

  it('la scène exportable ne contient que les maillages visibles, en coordonnées monde', () => {
    const { sc } = nouvelleScene(FABRIQUES_CHANTIER)
    const res = jeu('exemple')
    sc.charger(res)
    sc.phase(1)                                       // buton pas encore posé
    const g = sceneExportable(sc.scene)
    const noms = g.children.map((o) => o.name)
    expect(g.children.length).toBeGreaterThan(5)
    expect(noms.some((n) => n.startsWith('appui.B1'))).toBe(false)
    sc.phase(3)
    const g2 = sceneExportable(sc.scene)
    expect(g2.children.some((o) => o.name === 'appui.B1.corps')).toBe(true)     // buton posé : exporté
    expect(g2.children.every((o) => (o as THREE.Mesh).isMesh)).toBe(true)
    const buton = g2.children.find((o) => o.name === 'appui.B1.corps')!
    expect(buton.matrixAutoUpdate).toBe(false)
  })
})
