import type * as THREE from 'three'
import { Vector3 } from 'three'
import { describe, expect, it } from 'vitest'
import { resolveur } from '../coupes'
import { FABRIQUES_CHANTIER } from '../elements'
import { Contour } from '../geometrie'
import { aretesObjet, entreeYamlRisberme, FABRIQUES_TERRAIN, geoExtrusion, polygoneObjet } from '../terrain'
import { jeuProjet, nouvelleScene } from './outils'

const TOUT = [...FABRIQUES_CHANTIER, ...FABRIQUES_TERRAIN]
const COTES = { long_sud: 0, court_est: 1, long_nord: 2, court_ouest: 3 }

describe('géométrie du terrain dans la maquette', () => {
  it('une risberme déclarée sur une fenêtre de phases n’est visible que sur ces phases', () => {
    const { resultats, projet } = jeuProjet('coupes')
    const t = resultats.maquette!.terrain!
    expect(t.objets.map((o) => o.nom)).toEqual(['R1'])
    const r1 = t.objets[0]
    expect([r1.phase_debut, r1.phase_fin, r1.base, r1.methode]).toEqual([3, 3, -6.5, 'surcharge_equivalente'])
    const { sc } = nouvelleScene(TOUT)
    sc.charger(resultats, { projet, resultatsPour: resolveur(projet, resultats, 0), cotes: COTES })
    const el = sc.elements.get('terrain.objet.0')!
    sc.phase(2)
    expect(el.objet.visible).toBe(false)
    sc.phase(3)
    expect(el.objet.visible).toBe(true)
    expect(sc.etiquettesCourantes.find((x) => x.id === 'nom.terrain.0')!.texte).toContain('crête -4,00 m')
    expect(el.objet.children.length).toBe(1)                                   // un seul côté concerné (long_sud)
    // la butée limite de la coupe est modifiée sur cette phase seulement (calcul serveur)
    expect('pp_sans_terrain' in resultats.phases[3]).toBe(true)
    expect('pp_sans_terrain' in resultats.phases[2]).toBe(false)
    const ppAvec = resultats.phases[3].pressions!.aval.pp
    const ppSans = resultats.phases[3].pp_sans_terrain!
    expect(Math.max(...ppAvec)).toBeGreaterThan(Math.max(...ppSans))
    // les autres coupes (côté nord, est) ne portent pas la risberme
    expect('pp_sans_terrain' in projet.coupes[1].resultats!.phases[3]).toBe(false)
    const c0 = sc.fab.creations
    for (let k = 0; k < 6; k++) sc.phase(k % 4)
    expect(sc.fab.creations).toBe(c0)
  })

  it('polygone, extrusion et côtés concernés', () => {
    const poly = polygoneObjet([[0, -4], [2, -4], [5.75, -6.5], [6.75, -6.5]], -6.5)
    expect(poly[0]).toEqual([0, -6.5])
    expect(poly[poly.length - 1]).toEqual([6.75, -6.5])
    const geo = new Contour([[0, 0], [30, 0], [30, 18], [0, 18]])
    const g = geoExtrusion(poly, geo.aretes[0], 1)
    expect(g.attributes.position.count).toBe(2 * poly.length)
    expect(g.index!.count).toBeGreaterThan(0)
    // sommet de crête : sur la face fouille du côté sud (y = 0 → y croissant)
    const pos = g.attributes.position as THREE.BufferAttribute
    expect(pos.getY(2)).toBeCloseTo(-4, 6)
    expect(-pos.getZ(4)).toBeCloseTo(2, 6)
    expect(aretesObjet(geo, { cotes_paroi: ['long_nord', '#1'] }, COTES).map((a) => a.k)).toEqual([1, 2])
    expect(aretesObjet(geo, { cotes_paroi: null }, COTES).length).toBe(4)
  })

  it('l’outil Mesurer donne distance et dénivelée entre deux points', () => {
    const { resultats } = jeuProjet('coupes')
    const { sc } = nouvelleScene(TOUT)
    sc.charger(resultats)
    const el = sc.elements.get('outils.mesure')!
    expect(el.objet.visible).toBe(false)
    sc.definirMesure({ a: new Vector3(0, 0, 0), b: null })
    expect(el.objet.visible).toBe(false)
    sc.definirMesure({ a: new Vector3(0, 0, 0), b: new Vector3(3, -4, 0) })
    expect(el.objet.visible).toBe(true)
    const e = sc.etiquettesCourantes.find((x) => x.id === 'mesure')!
    expect(e.texte).toContain('5,00 m')
    expect(e.texte).toContain('dénivelée -4,00 m')
    sc.definirMesure(null)
    expect(el.objet.visible).toBe(false)
  })

  it('créer une risberme depuis la 3D écrit une entrée YAML correcte', () => {
    expect(entreeYamlRisberme('R2', 'long_nord', -3.5, 2, 1.5, -6.5, [3, 3])).toEqual({ nom: 'R2', cote_paroi: 'long_nord', phases: [3, 3], cote_crete: -3.5, largeur_crete: 2, pente: 1.5, cote_pied: -6.5 })
  })
})
