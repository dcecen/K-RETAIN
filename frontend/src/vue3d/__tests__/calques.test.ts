import { describe, expect, it } from 'vitest'
import {
  basculerIsolation, definirMode, definirOpacite, definirVerrou, definirVisible, enregistrerPrereglage, etatInitial,
  etatPrereglage, exporterJson, feuillesDe, importerJson, normaliser, PREREGLAGES_LIVRES, rechercher, versScene, visibiliteGroupe,
} from '../calques'
import { jeu, nouvelleScene } from './outils'

describe('calques', () => {
  it('masquer un groupe masque ses enfants ; un groupe partiellement visible est en état intermédiaire', () => {
    let e = etatInitial()
    e = definirVisible(e, 'eau', false)
    for (const f of feuillesDe('eau')) expect(e.feuilles[f].visible).toBe(false)
    expect(visibiliteGroupe(e, 'eau')).toBe(false)
    e = definirVisible(e, 'eau.aval', true)
    expect(visibiliteGroupe(e, 'eau')).toBe('partiel')
    e = definirVisible(e, 'eau', true)
    expect(visibiliteGroupe(e, 'eau')).toBe(true)
  })

  it('isoler puis annuler restaure exactement l\'état précédent', () => {
    let e = etatInitial()
    e = definirVisible(e, 'eau.aval', false)
    e = definirOpacite(e, 'paroi', 0.3)
    e = definirVerrou(e, 'terrain', true)
    const avant = JSON.stringify(e.feuilles)
    e = basculerIsolation(e, 'appuis')
    expect(e.isolation?.id).toBe('appuis')
    for (const f of feuillesDe('appuis')) expect(e.feuilles[f].visible).toBe(true)
    expect(e.feuilles['paroi.elements'].visible).toBe(false)
    expect(e.feuilles['terrain.couches'].visible).toBe(false)
    e = basculerIsolation(e, 'appuis')
    expect(e.isolation).toBeNull()
    expect(JSON.stringify(e.feuilles)).toBe(avant)
  })

  it('isoler un autre calque pendant une isolation garde l\'état d\'origine comme référence', () => {
    let e = definirVisible(etatInitial(), 'eau.aval', false)
    const avant = JSON.stringify(e.feuilles)
    e = basculerIsolation(e, 'appuis')
    e = basculerIsolation(e, 'paroi')
    expect(e.feuilles['appuis.butons'].visible).toBe(false)
    expect(e.feuilles['paroi.elements'].visible).toBe(true)
    e = basculerIsolation(e, 'paroi')
    expect(JSON.stringify(e.feuilles)).toBe(avant)
  })

  it('un seul calque colore la paroi à la fois', () => {
    let e = definirVisible(etatInitial(), 'resultats.deplacement', true)
    e = definirVisible(e, 'resultats.moment', true)
    expect(e.feuilles['resultats.deplacement'].visible).toBe(false)
    expect(e.feuilles['resultats.moment'].visible).toBe(true)
    e = definirMode(e, 'resultats.moment', 'ailettes')
    e = definirVisible(e, 'resultats.deplacement', true)
    expect(e.feuilles['resultats.moment'].visible).toBe(true)   // ailettes et couleur se combinent
  })

  it('un préréglage enregistré se recharge à l\'identique et survit à l\'export JSON', () => {
    let e = etatInitial()
    e = definirVisible(e, 'terrain', false)
    e = definirOpacite(e, 'paroi.elements', 0.42)
    e = definirMode(e, 'resultats.moment', 'ailettes')
    const perso = enregistrerPrereglage([], 'Ma vue', e)
    expect(perso[0].id).toBe('perso.ma_vue')
    const relu = etatPrereglage('perso.ma_vue', perso)!
    expect(relu.feuilles).toEqual(e.feuilles)
    const json = exporterJson(e, perso)
    const imp = importerJson(json)
    expect(imp.etat.feuilles).toEqual(e.feuilles)
    expect(etatPrereglage('perso.ma_vue', imp.prereglages)!.feuilles).toEqual(e.feuilles)
    expect(() => importerJson('{"a":1}')).toThrow()
  })

  it('les préréglages livrés existent et sont cohérents', () => {
    expect(PREREGLAGES_LIVRES.map((p) => p.id)).toEqual(['chantier', 'structure', 'resultats_paroi', 'resultats_appuis', 'coupes', 'hydraulique', 'presentation'])
    const s = etatPrereglage('structure')!
    expect(s.feuilles['paroi.elements'].visible).toBe(true)
    expect(s.feuilles['terrain.couches'].visible).toBe(false)
    const p = etatPrereglage('presentation')!
    expect(p.feuilles['outils.grille'].visible).toBe(false)
    expect(p.feuilles['annotations.noms'].visible).toBe(false)
    expect(etatPrereglage('inconnu')).toBeNull()
  })

  it('complète un état incomplet avec les calques par défaut', () => {
    const e = normaliser({ feuilles: { 'eau.amont': { visible: false, opacite: 1, verrou: false, coupe: true } } })
    expect(e.feuilles['eau.amont'].visible).toBe(false)
    expect(e.feuilles['paroi.elements'].visible).toBe(true)
    expect(e.feuilles['resultats.deformee'].visible).toBe(false)
  })

  it('recherche par nom sans accents et renvoie les ancêtres', () => {
    const r = rechercher('piezo')!
    expect(r.has('eau.piezo')).toBe(true)
    expect(r.has('eau')).toBe(true)
    expect(r.has('paroi')).toBe(false)
    expect(rechercher('  ')).toBeNull()
  })

  it('l\'état des calques survit à un recalcul et à un changement de phase dans la scène', () => {
    const { sc } = nouvelleScene()
    sc.charger(jeu('exemple'))
    const e = definirOpacite(definirVisible(etatInitial(), 'terrain', false), 'paroi', 0.5)
    sc.appliquerCalques(versScene(e))
    sc.phase(3)
    sc.charger(jeu('exemple'))
    expect(sc.elements.get('terrain.couche.0')!.objet.visible).toBe(false)
    const paroi = sc.elements.get('paroi.cote.0')!.objet.children[0] as import('three').Mesh
    expect((paroi.material as import('three').Material).opacity).toBeCloseTo(0.5, 6)
    expect((paroi.material as import('three').Material).transparent).toBe(true)
    sc.appliquerCalques(versScene(definirOpacite(e, 'paroi', 1)))
    expect((paroi.material as import('three').Material).transparent).toBe(false)
  })

  it('un calque masqué ne recalcule pas ses attributs de phase (calcul paresseux)', () => {
    const { sc } = nouvelleScene()
    sc.charger(jeu('ecoulement'))
    sc.appliquerCalques(versScene(definirVisible(etatInitial(), 'eau.piezo', false)))
    sc.phase(5)
    expect(sc.elementsEnAttente).toContain('eau.piezo')
    sc.appliquerCalques(versScene(etatInitial()))
    expect(sc.elementsEnAttente).not.toContain('eau.piezo')
    expect(sc.elements.get('eau.piezo')!.objet.visible).toBe(true)
  })
})
