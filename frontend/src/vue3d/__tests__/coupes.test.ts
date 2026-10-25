import type * as THREE from 'three'
import { describe, expect, it } from 'vitest'
import { definirMode, definirVisible, etatInitial, versScene } from '../calques'
import { FABRIQUES_COUPES, indiceCoupePour, phaseCorrespondante, resolveur, stationTrace, TEINTES_COUPES } from '../coupes'
import { FABRIQUES_CHANTIER } from '../elements'
import { Contour } from '../geometrie'
import { FABRIQUES_RESULTATS_PAROI, NZ } from '../resultats'
import { jeuProjet, nouvelleScene } from './outils'

const TOUT = [...FABRIQUES_CHANTIER, ...FABRIQUES_RESULTATS_PAROI, ...FABRIQUES_COUPES]

describe('coupes de calcul dans la maquette', () => {
  it('rattache chaque tronçon de paroi à sa coupe ; un tronçon orphelin est signalé', () => {
    const { projet } = jeuProjet('coupes')
    expect(projet.unique).toBe(false)
    expect(projet.coupes.map((c) => c.nom.slice(0, 2))).toEqual(['C1', 'C2', 'C3'])
    expect(indiceCoupePour(projet, 0, 10)).toBe(0)
    expect(indiceCoupePour(projet, 2, 3)).toBe(1)
    expect(indiceCoupePour(projet, 1, 9)).toBe(2)
    expect(indiceCoupePour(projet, 3, 9)).toBe(-1)
    expect(projet.orphelins).toEqual([{ k: 3, de: 0, a: 18 }])
    expect(projet.avertissements.some((a) => a.includes('sans coupe'))).toBe(true)
  })

  it('fait correspondre les phases entre coupes par le phasage projet', () => {
    const { projet } = jeuProjet('coupes')
    expect(projet.phasage_projet).toEqual(['État initial', 'Terrassement à -2,0', 'Pose du buton B1', 'Terrassement final et pompage', 'Terrassement final sans pompage'])
    expect(projet.coupes[2].correspondance).toEqual([0, 1, 2, 4])
    expect(phaseCorrespondante(projet, 0, 3, 2)).toBe(2)      // C1 « final et pompage » → C3 : dernière phase précédente (pose)
    expect(phaseCorrespondante(projet, 2, 3, 0)).toBe(3)      // C3 « sans pompage » → C1 : dernière phase ≤ (final et pompage)
    expect(phaseCorrespondante(projet, 1, 2, 0)).toBe(2)      // même phase projet
  })

  it('trace : intersection avec le tronçon, orientée vers la fouille', () => {
    const { projet } = jeuProjet('coupes')
    const geo = new Contour(projet.contour)
    const c2 = stationTrace(geo, projet.coupes[1])
    expect(c2.sl).toBeCloseTo(15, 6)
    expect(c2.dir[1]).toBeCloseTo(-1, 6)
    const c1 = stationTrace(geo, projet.coupes[0])
    expect(c1.sl).toBeCloseTo(15, 6)                          // trace par défaut au milieu
  })

  it('chaque tronçon prend les résultats de sa propre coupe, sans interpolation', () => {
    const { resultats, projet } = jeuProjet('coupes')
    const { sc } = nouvelleScene(TOUT)
    sc.charger(resultats, { projet, resultatsPour: resolveur(projet, resultats, 0) })
    sc.appliquerCalques(versScene(definirVisible(etatInitial(), 'resultats.deplacement', true)))
    sc.phase(3)
    const col = (k: number) => (sc.elements.get(`resultats.surface.${k}`)!.objet.children[0] as THREE.Mesh).geometry.attributes.color as THREE.BufferAttribute
    const j = Math.round(((-1.0 - -14) / 14) * (NZ - 1))     // cote −1,0 m : C1 n'est pas en butée de palette
    const c0 = col(0)
    const c2 = col(2)
    const mid0 = Math.floor(c0.count / NZ / 2) * NZ + j
    const mid2 = Math.floor(c2.count / NZ / 2) * NZ + j
    // C2 (sol plus faible) se déplace plus : couleur différente de C1 à la même cote
    expect(Math.abs(c0.getX(mid0) - c2.getX(mid2)) + Math.abs(c0.getZ(mid0) - c2.getZ(mid2))).toBeGreaterThan(0.05)
    const r = sc.d!.resultatsPour!(2, 3, 3)
    expect(r.coupe!.startsWith('C2')).toBe(true)
    expect(r.res.dimensionnant.deplacement!.valeur_mm).toBeGreaterThan(resultats.dimensionnant.deplacement!.valeur_mm)
    expect(sc.d!.resultatsPour!(3, 1, 3).coupe).toBeNull()
  })

  it('plans nommés, zones colorées par coupe, orphelin hachuré, diagramme dans le plan de coupe', () => {
    const { resultats, projet } = jeuProjet('coupes')
    const { sc } = nouvelleScene(TOUT)
    sc.charger(resultats, { projet, resultatsPour: resolveur(projet, resultats, 0) })
    let e = definirVisible(etatInitial(), 'coupes.zones', true)
    e = definirVisible(e, 'coupes.diagrammes', true)
    sc.appliquerCalques(versScene(e))
    sc.phase(3)
    expect(sc.elements.has('coupes.plan.0') && sc.elements.has('coupes.plan.2')).toBe(true)
    expect(sc.etiquettesCourantes.find((x) => x.id === 'nom.coupe.1')!.texte.startsWith('C2')).toBe(true)
    const couleur = (i: number) => ((sc.elements.get(`coupes.zone.${i}`)!.objet as THREE.Mesh).material as THREE.MeshBasicMaterial).color.getHex()
    expect(couleur(0)).toBe(TEINTES_COUPES[0])
    expect(couleur(1)).toBe(TEINTES_COUPES[1])
    expect(couleur(0)).not.toBe(couleur(1))
    const orph = sc.elements.get('coupes.orphelin.0')!
    expect(((orph.objet as THREE.Mesh).material as THREE.MeshBasicMaterial).wireframe).toBe(true)
    expect(sc.etiquettesCourantes.some((x) => x.texte === 'sans coupe de calcul')).toBe(true)
    const diag = sc.elements.get('coupes.diagramme.1')!
    expect(diag.objet.visible).toBe(true)
    expect(sc.etiquettesCourantes.find((x) => x.id === 'diag.1')!.texte).toContain('y max')
    sc.appliquerCalques(versScene(definirMode(e, 'coupes.diagrammes', 'moment')))
    expect(sc.etiquettesCourantes.find((x) => x.id === 'diag.1')!.texte).toContain('M max')
    // changement de coupe active : rien n'est reconstruit
    const c0 = sc.fab.creations
    sc.charger(resultats, { projet, resultatsPour: resolveur(projet, resultats, 2) })
    expect(sc.fab.creations).toBe(c0)
  })

  it('une arête partagée par deux coupes : chaque tronçon prend sa coupe, colonne par colonne', () => {
    const { resultats, projet } = jeuProjet('coupes')
    // C1 sur la moitié ouest du côté sud (30 m), C2 (sol plus faible) sur la moitié est : même arête, deux coupes
    projet.coupes[0].zone = { k: 0, de: 0, a: 15 }
    projet.coupes[1].zone = { k: 0, de: 15, a: 30 }
    const { sc } = nouvelleScene(TOUT)
    sc.charger(resultats, { projet, resultatsPour: resolveur(projet, resultats, 0) })
    sc.appliquerCalques(versScene(definirVisible(etatInitial(), 'resultats.deplacement', true)))
    sc.phase(3)
    const col = (sc.elements.get('resultats.surface.0')!.objet.children[0] as THREE.Mesh).geometry.attributes.color as THREE.BufferAttribute
    const ns = col.count / NZ                                  // une colonne par mètre : sl = indice de colonne
    const j = Math.round(((-1.0 - -14) / 14) * (NZ - 1))
    const ouest = 2 * NZ + j                                   // sl = 2 m : tronçon de C1
    const est = (ns - 3) * NZ + j                              // sl = 28 m : tronçon de C2
    expect(Math.abs(col.getX(ouest) - col.getX(est)) + Math.abs(col.getZ(ouest) - col.getZ(est))).toBeGreaterThan(0.05)
    expect(col.getX(ouest)).toBeCloseTo(col.getX(5 * NZ + j), 6)      // deux colonnes du même tronçon : même couleur
    expect(col.getX(est)).toBeCloseTo(col.getX((ns - 6) * NZ + j), 6)
  })
})
