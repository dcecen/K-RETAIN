import type * as THREE from 'three'
import { describe, expect, it } from 'vitest'
import { definirVisible, etatInitial, versScene } from '../calques'
import { resolveur } from '../coupes'
import { FABRIQUES_CHANTIER } from '../elements'
import { Contour } from '../geometrie'
import { activeA, emprises, entreeYamlSurcharge, FABRIQUES_SURCHARGES, hauteurVisuelle } from '../surcharges'
import { jeuProjet, nouvelleScene } from './outils'

const TOUT = [...FABRIQUES_CHANTIER, ...FABRIQUES_SURCHARGES]

describe('surcharges dans la maquette', () => {
  it('une surcharge phasée est visible uniquement entre sa phase d’application et son retrait', () => {
    const { resultats, projet } = jeuProjet('coupes')
    const liste = resultats.maquette!.surcharges!
    const grue = liste.find((s) => s.nom === 'grue')!
    expect([grue.phase_debut, grue.phase_fin]).toEqual([2, 3])
    expect([activeA(grue, 0), activeA(grue, 1), activeA(grue, 2), activeA(grue, 3)]).toEqual([false, false, true, true])
    const { sc } = nouvelleScene(TOUT)
    sc.charger(resultats, { projet, resultatsPour: resolveur(projet, resultats, 0), cotes: { long_sud: 0, court_est: 1, long_nord: 2, court_ouest: 3 } })
    const i = liste.indexOf(grue)
    const el = sc.elements.get(`surcharges.volume.${i}`)!
    sc.phase(1)
    expect(el.objet.visible).toBe(false)
    sc.phase(2)
    expect(el.objet.visible).toBe(true)
    expect(sc.etiquettesCourantes.find((x) => x.id === `nom.surcharge.${i}`)!.texte).toContain('grue · 1')
    sc.phase(3)
    expect(el.objet.visible).toBe(true)
    // la surcharge de chantier (bande historique) existe dès le début, l'immeuble aussi
    const ch = sc.elements.get(`surcharges.volume.${liste.findIndex((s) => s.nom === 'chantier')}`)!
    sc.phase(0)
    expect(ch.objet.visible).toBe(true)
    const im = liste.find((s) => s.nom === 'immeuble')!
    expect(im.niveaux).toBe(6)
    const c0 = sc.fab.creations
    for (let k = 0; k < 8; k++) sc.phase(k % 4)
    expect(sc.fab.creations).toBe(c0)
  })

  it('la pression induite s’affiche au survol/sélection ou quand son calque est visible', () => {
    const { resultats, projet } = jeuProjet('coupes')
    const liste = resultats.maquette!.surcharges!
    const i = liste.findIndex((s) => s.nom === 'chantier')
    expect(Math.max(...liste[i].profil!.dsv)).toBeGreaterThan(0)
    const { sc } = nouvelleScene(TOUT)
    sc.charger(resultats, { projet, resultatsPour: resolveur(projet, resultats, 0) })
    sc.phase(3)
    const el = sc.elements.get(`surcharges.pression.${i}`)!
    expect(el.objet.visible).toBe(false)
    sc.selectionner(`surcharge:${i}`)
    sc.appliquerPhase()
    expect(el.objet.visible).toBe(true)
    expect(sc.etiquettesCourantes.find((x) => x.id === `dsv.${i}`)!.texte).toContain('Δσv max')
    sc.selectionner(null)
    sc.appliquerCalques(versScene(definirVisible(etatInitial(), 'surcharges.pressions', true)))
    expect(el.objet.visible).toBe(true)
    // le ruban part de la face terre de la paroi
    const pos = (el.objet as THREE.Mesh).geometry.attributes.position as THREE.BufferAttribute
    expect(pos.getZ(1)).toBeGreaterThanOrEqual(pos.getZ(0) - 1e-6)   // y projet décroissant = terre (côté 0, ni = +y)
  })

  it('emprises et hauteur visuelle selon le type', () => {
    const geo = new Contour([[0, 0], [30, 0], [30, 18], [0, 18]])
    const cotes = { long_sud: 0, court_est: 1, long_nord: 2, court_ouest: 3 }
    const base = { cote_ecran: 'amont', phase_debut: 0, phase_fin: 3 }
    const rect = emprises(geo, { nom: 'r', type: 'rectangulaire', q: 40, position: [38, 9], emprise: [10, 8], ...base }, cotes)
    expect(rect).toEqual([{ cx: 38, cy: 9, lx: 10, ly: 8, angle: 0 }])
    const bande = emprises(geo, { nom: 'b', type: 'bande', q: 90, distance: 3.5, largeur: 18, emprise: [4, 26], cotes_paroi: ['long_nord'], ...base }, cotes)
    expect(bande.length).toBe(1)
    expect(bande[0].cy).toBeCloseTo(18 + 3.5 + 9, 6)                  // derrière le côté nord (y = 18), vers la terre
    expect(bande[0].lx).toBeCloseTo(22, 6)
    const unif = emprises(geo, { nom: 'u', type: 'uniforme', q: 10, ...base }, cotes)
    expect(unif.length).toBe(4)                                          // tous les côtés
    expect(hauteurVisuelle({ nom: 'r', type: 'rectangulaire', q: 40, ...base }, 20)).toBeCloseTo(2, 6)
    expect(hauteurVisuelle({ nom: 'g', type: 'ponctuelle', q: 1200, emprise: [6, 6], ...base }, 20)).toBeCloseTo(1200 / 36 / 20, 6)
  })

  it('créer une surcharge depuis la 3D écrit une entrée YAML correcte', () => {
    const e = entreeYamlSurcharge('stock', 40, [20, -10], [30, -4], 2)
    expect(e).toEqual({ nom: 'stock', type: 'rectangulaire', q: 40, position: [25, -7], emprise: [10, 6], phase: 2 })
    const e2 = entreeYamlSurcharge('S', 10, [5, 5], [5.1, 5.2], null)
    expect(e2.emprise).toEqual([0.5, 0.5])                               // emprise minimale
    expect('phase' in e2).toBe(false)
  })
})
