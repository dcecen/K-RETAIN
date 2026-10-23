import type * as THREE from 'three'
import { Color } from 'three'
import { describe, expect, it } from 'vitest'
import { effortAppui, maxEfforts, tauxAppui, FILTRE_BARRE, FILTRE_LIERNE } from '../appuis'
import { definirMode, definirReglage, definirVisible, etatInitial, versScene } from '../calques'
import { FABRIQUES_CHANTIER } from '../elements'
import { legendes } from '../legendes'
import { COULEURS_TAUX } from '../palettes'
import { FABRIQUES_RESULTATS_PAROI } from '../resultats'
import { amplificationFleches, FABRIQUES_RESULTATS_APPUIS, formeBiAppuyee, formeBiEncastree, maxFleche } from '../resultatsAppuis'
import { indicePhase, jeu, nouvelleScene } from './outils'

const TOUT = [...FABRIQUES_CHANTIER, ...FABRIQUES_RESULTATS_PAROI, ...FABRIQUES_RESULTATS_APPUIS]

describe('résultats des appuis en 3D', () => {
  it("l'étiquette de B1 affiche 142 kN/m et 853 kN (service) puis l'effort ELU", () => {
    const { sc } = nouvelleScene(TOUT)
    const res = jeu('exemple')
    sc.charger(res)
    let e = definirVisible(etatInitial(), 'resultats.efforts', true)
    sc.appliquerCalques(versScene(e))
    sc.phase(indicePhase(res, 'Terrassement final et pompage'))
    const et = sc.etiquettesCourantes.find((x) => x.id === 'effort.B1')!
    expect(et.texte).toContain('142 kN/m')
    expect(et.texte).toContain('853 kN')
    e = definirMode(e, 'resultats.efforts', 'elu')
    sc.appliquerCalques(versScene(e))
    const elu = sc.etiquettesCourantes.find((x) => x.id === 'effort.B1')!
    expect(elu.texte).toContain('1 152 kN')
    expect(elu.texte).toContain('ELU')
    const ap = res.phases[3].appuis!.find((a) => a.nom === 'B1')!
    expect(effortAppui(ap, 'elu')!.axial).toBeCloseTo(1.35 * 853.151, 0)
    expect(maxEfforts(res, 'service')).toBeCloseTo(142.19, 1)
    // couleur par effort : le buton n'a plus sa couleur de base
    const mat = (sc.elements.get('appui.B1')!.objet.children[0] as THREE.Mesh).material as THREE.MeshLambertMaterial
    expect(mat.color.getHex()).not.toBe(0x2ca02c)
  })

  it('la flèche affichée pour un buton correspond à la valeur du module de vérification à 1 % près', () => {
    const { sc } = nouvelleScene(TOUT)
    const res = jeu('ecoulement')
    sc.charger(res)
    sc.appliquerCalques(versScene(definirVisible(etatInitial(), 'resultats.fleches', true)))
    const i = res.phases.length - 1
    sc.phase(i)
    const ap = res.phases[i].appuis!.find((a) => a.nom === 'B1')!
    expect(ap.fleche_mm).toBeGreaterThan(0)
    const el = sc.elements.get('resultats.fleche.B1')!
    expect(el.objet.visible).toBe(true)
    expect(el.objet.userData.fleche_mm).toBeCloseTo(ap.fleche_mm!, 6)
    // géométrie : creux à mi-portée = flèche × amplification (moyenne des points du contour)
    const amp = amplificationFleches({ scene: sc, d: sc.d!, phase: i, ph: res.phases[i], fab: sc.fab, plan: sc.planCoupe })
    const pos = (el.objet as THREE.Mesh).geometry.attributes.position as THREE.BufferAttribute
    const nrad = 12
    const nseg = 24
    const yStation = (s: number) => { let y = 0; for (let k = 0; k < nrad; k++) y += pos.getY(s * nrad + k); return y / nrad }
    const creux = (yStation(0) + yStation(nseg)) / 2 - yStation(nseg / 2)
    expect(creux).toBeCloseTo((ap.fleche_mm! / 1000) * amp, 2)
    expect(Math.abs(creux - (ap.fleche_mm! / 1000) * amp) / creux).toBeLessThan(0.01)
    expect(amp * maxFleche(res)).toBeCloseTo(1500, 3)     // auto : 1,5 m à l'écran
    // B2 est instable (N ≥ Ncr) : pas de flèche affichée
    expect(sc.elements.get('resultats.fleche.B2')!.objet.visible).toBe(false)
    const et = sc.etiquettesCourantes.find((x) => x.id === 'fleche.B1')!
    expect(et.texte).toContain(`f = ${ap.fleche_mm!.toFixed(1).replace('.', ',')} mm`)
    // poids propre seul : flèche plus faible
    sc.appliquerCalques(versScene(definirMode(definirVisible(etatInitial(), 'resultats.fleches', true), 'resultats.fleches', 'poids_propre')))
    expect(el.objet.userData.fleche_mm).toBeCloseTo(ap.fleche_poids_propre_mm!, 6)
    expect(ap.fleche_poids_propre_mm!).toBeLessThan(ap.fleche_mm!)
  })

  it('la lierne déformée remplace la lierne droite entre les butons', () => {
    const { sc } = nouvelleScene(TOUT)
    const res = jeu('ecoulement')
    sc.charger(res)
    const i = res.phases.length - 1
    sc.phase(i)
    expect(sc.elements.get('appui.B1.lierne')!.objet.visible).toBe(true)
    sc.appliquerCalques(versScene(definirVisible(etatInitial(), 'resultats.fleches', true)))
    expect(sc.elements.get('appui.B1.lierne')!.objet.visible).toBe(false)
    const el = sc.elements.get('resultats.fleche_lierne.B1')!
    expect(el.objet.visible).toBe(true)
    expect(el.objet.userData.fleche_mm).toBeCloseTo(res.phases[i].appuis!.find((a) => a.nom === 'B1')!.fleche_lierne_mm!, 6)
    expect(sc.etiquettesCourantes.find((x) => x.id === 'fleche.lierne.B1')!.texte).toContain('approchée')
    expect(formeBiAppuyee(0.5)).toBeCloseTo(1, 9)
    expect(formeBiEncastree(0.5)).toBeCloseTo(1, 9)
    expect(formeBiAppuyee(0)).toBe(0)
  })

  it('colore butons, liernes et assemblages par leur taux de travail', () => {
    const res = jeu('ecoulement')
    expect(tauxAppui(res.verifications, 'B2', {}, FILTRE_BARRE)).toBeCloseTo(99, 6)
    expect(tauxAppui(res.verifications, 'B1', {}, FILTRE_LIERNE)).toBeCloseTo(0.654, 2)
    const { sc } = nouvelleScene(TOUT)
    sc.charger(res)
    sc.appliquerCalques(versScene(definirVisible(etatInitial(), 'resultats.taux', true)))
    sc.phase(res.phases.length - 1)
    const matB2 = (sc.elements.get('appui.B2')!.objet.children[0] as THREE.Mesh).material as THREE.MeshLambertMaterial
    expect(matB2.color.getHex()).toBe(COULEURS_TAUX.rouge)
    const matL1 = (sc.elements.get('appui.B1.lierne')!.objet as THREE.Mesh).material as THREE.MeshLambertMaterial
    expect(matL1.color.getHex()).toBe(COULEURS_TAUX.vert)
    expect(sc.etiquettesCourantes.find((x) => x.id === 'taux.B2')!.texte).toContain('9 900 %')
    // assemblages de l'exemple : A3 (âme sans raidisseur) à 139 % → rouge ; A1 → vert
    const ex = jeu('exemple')
    const { sc: s2 } = nouvelleScene(TOUT)
    s2.charger(ex)
    s2.appliquerCalques(versScene(definirVisible(etatInitial(), 'resultats.taux', true)))
    s2.phase(3)
    expect(s2.elements.has('appui.assemblage.A1')).toBe(true)
    const mA3 = (s2.elements.get('appui.assemblage.A3')!.objet as THREE.Mesh).material as THREE.MeshLambertMaterial
    const mA1 = (s2.elements.get('appui.assemblage.A1')!.objet as THREE.Mesh).material as THREE.MeshLambertMaterial
    expect(mA3.color.getHex()).toBe(COULEURS_TAUX.rouge)
    expect(mA1.color.getHex()).toBe(COULEURS_TAUX.vert)
    expect(s2.etiquettesCourantes.find((x) => x.id === 'nom.A3')!.texte).toContain('140 %')
    // seuils réglables
    s2.appliquerCalques(versScene(definirReglage(definirVisible(etatInitial(), 'resultats.taux', true), 'resultats.taux', 'orange', 0.5)))
    expect(mA1.color.getHex()).toBe(COULEURS_TAUX.orange)   // A1 : 61 % ≥ 50 %
    expect(new Color(COULEURS_TAUX.gris).getHex()).toBe(0x9aa2ad)
  })

  it('légendes des efforts et des flèches', () => {
    const res = jeu('exemple')
    let e = definirVisible(etatInitial(), 'resultats.efforts', true)
    e = definirVisible(e, 'resultats.fleches', true)
    const l = legendes(res, versScene(e), 3)
    const ef = l.find((x) => x.id === 'efforts')!
    expect(ef.type).toBe('continue')
    if (ef.type === 'continue') { expect(ef.unite).toBe('kN/m'); expect(ef.max).toBeCloseTo(142.19, 1) }
    expect(l.find((x) => x.id === 'fleches')!.titre).toContain('Flèche')
  })

  it('les calques d\'appuis restent stables en mémoire au fil des phases et recalculs', () => {
    const { sc } = nouvelleScene(TOUT)
    const res = jeu('ecoulement')
    sc.charger(res)
    let e = etatInitial()
    for (const id of ['resultats.efforts', 'resultats.fleches']) e = definirVisible(e, id, true)
    sc.appliquerCalques(versScene(e))
    for (let i = 0; i < res.phases.length; i++) sc.phase(i)
    const c0 = sc.fab.creations
    for (let k = 0; k < 20; k++) sc.phase(k % res.phases.length)
    sc.charger(jeu('ecoulement'))
    expect(sc.fab.creations).toBe(c0)
  })
})
