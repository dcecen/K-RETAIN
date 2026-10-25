import type * as THREE from 'three'
import { describe, expect, it } from 'vitest'
import { compter, indicePhase, jeu, jeuRectangle, nouvelleScene } from './outils'

describe('scène persistante', () => {
  it("construit l'arbre fixe avec des identifiants stables", () => {
    const { sc } = nouvelleScene()
    sc.charger(jeu('exemple'))
    for (const id of ['terrain', 'fouille', 'eau', 'surcharges', 'environnement', 'paroi', 'appuis', 'appuis.butons', 'resultats', 'coupes', 'annotations', 'outils'])
      expect(sc.scene.getObjectByName(id)?.userData.id).toBe(id)
    expect(sc.elements.has('paroi.cote.0')).toBe(true)
    expect(sc.elements.has('appui.B1')).toBe(true)
    expect(sc.elements.has('terrain.couche.1')).toBe(true)
  })

  it('reste stable en mémoire après 50 changements de phase et 10 recalculs', () => {
    for (const nom of ['exemple', 'ecoulement', 'berlinoise', 'p3d'] as const) {
      const { sc } = nouvelleScene()
      const res = jeu(nom)
      sc.charger(res)
      for (let i = 0; i < res.phases.length; i++) sc.phase(i)
      const avant = compter(sc)
      const creations = sc.fab.creations
      for (let k = 0; k < 50; k++) sc.phase((k * 3) % res.phases.length)
      for (let k = 0; k < 10; k++) { sc.charger(jeu(nom)); sc.phase(k % res.phases.length) }
      const apres = compter(sc)
      expect(apres.objets, nom).toBe(avant.objets)
      expect(apres.geometries, nom).toBe(avant.geometries)
      expect(apres.materiaux, nom).toBe(avant.materiaux)
      expect(sc.fab.creations, `${nom} : aucun objet créé`).toBe(creations)
      // tout ce qui est enregistré est atteignable (aucune ressource orpheline non libérée)
      expect(sc.fab.geometries.size).toBe(apres.geometries)
      expect(sc.fab.materiaux.size).toBe(apres.materiaux)
    }
  })

  it("change de phase en moins de 30 ms sans créer d'objet", () => {
    const { sc } = nouvelleScene()
    const res = jeu('ecoulement')
    sc.charger(res)
    for (let i = 0; i < res.phases.length; i++) sc.phase(i)
    const c0 = sc.fab.creations
    const t0 = performance.now()
    for (let k = 0; k < 50; k++) sc.phase(k % res.phases.length)
    const moyen = (performance.now() - t0) / 50
    expect(moyen).toBeLessThan(30)
    expect(sc.fab.creations).toBe(c0)
  })

  it("met à jour la vue en moins de 100 ms lors d'un recalcul de même géométrie, sans rien reconstruire", () => {
    const { sc } = nouvelleScene()
    sc.charger(jeu('exemple'))
    const t0 = performance.now()
    sc.charger(jeu('exemple'))
    expect(performance.now() - t0).toBeLessThan(100)
    expect(sc.derniersReconstruits).toEqual([])
  })

  it('ne reconstruit que les objets dont la géométrie a changé, et libère les anciens', () => {
    const { sc } = nouvelleScene()
    sc.charger(jeuRectangle('exemple'))
    const avant = compter(sc)
    const r = jeuRectangle('exemple')
    r.maquette!.paroi.pied = -16
    sc.charger(r)
    expect(sc.derniersReconstruits.every((id) => id.startsWith('paroi.cote.'))).toBe(true)
    expect(sc.derniersReconstruits.length).toBe(4)
    const apres = compter(sc)
    expect(apres.geometries).toBe(avant.geometries)
    expect(sc.fab.geometries.size).toBe(apres.geometries)
  })

  it('suit la phase : appuis posés, sol de la fouille, nappe aval', () => {
    const { sc } = nouvelleScene()
    const res = jeu('exemple')
    sc.charger(res)
    const buton = sc.elements.get('appui.B1')!
    sc.phase(indicePhase(res, 'Terrassement à -2,0'))
    expect(buton.objet.visible).toBe(false)
    sc.phase(indicePhase(res, 'Pose du buton B1'))
    expect(buton.objet.visible).toBe(true)
    sc.phase(indicePhase(res, 'Terrassement final et pompage'))
    const sable = sc.elements.get('fouille.couche.1')!.objet
    expect(sable.position.y + sable.scale.y).toBeCloseTo(-6.5, 6)
    const terre = sc.elements.get('terrain.couche.1')!.objet
    expect(terre.position.y + terre.scale.y).toBeCloseTo(-3, 6)
    expect(sc.elements.get('eau.aval')!.objet.visible).toBe(false)   // nappe aval sous le fond (−7,0 < −6,5)
    sc.phase(indicePhase(res, 'Variante sans pompage'))
    const aval = sc.elements.get('eau.aval')!.objet
    expect(aval.visible).toBe(true)                                     // nappe à −2,0 au-dessus du fond à −5,5
    expect(aval.position.y).toBeCloseTo(-5.5, 6)
    expect(aval.position.y + aval.scale.y).toBeCloseTo(-2, 6)
  })

  it('conserve la caméra et la sélection à travers phases et recalculs', () => {
    const { sc } = nouvelleScene()
    sc.charger(jeu('exemple'))
    sc.orbiter(120, -40)
    sc.zoomer(200)
    const pos = sc.camera.position.clone()
    sc.selectionner('appui:B1')
    sc.phase(1)
    sc.charger(jeu('exemple'))
    const r = jeu('exemple')
    r.maquette!.contour = [[0, 0], [30, 0], [30, 12], [0, 12]]
    sc.charger(r)
    expect(sc.camera.position.distanceTo(pos)).toBeLessThan(1e-9)
    expect(sc.selection).toBe('appui:B1')
  })

  it("recadre automatiquement après un changement de dimensions seulement si la caméra n'a pas été touchée", () => {
    const { sc } = nouvelleScene()
    sc.charger(jeu('exemple'))
    const r0 = sc.orbite.rayon
    const r = jeu('exemple')
    r.maquette!.contour = [[0, 0], [40, 0], [40, 12], [0, 12]]
    sc.charger(r)
    expect(sc.orbite.rayon).toBeGreaterThan(r0)
  })

  it('ne rend que sur événement', () => {
    const { sc, rendus } = nouvelleScene()
    sc.charger(jeu('exemple'))
    const n = rendus.n
    expect(n).toBeGreaterThan(0)
    sc.phase(2)
    expect(rendus.n).toBe(n + 1)
  })

  it('applique le plan de coupe au terrain mais pas à la paroi', () => {
    const { sc } = nouvelleScene()
    sc.charger(jeu('exemple'))
    sc.definirCoupe({ actif: true, axe: 'x', t: 0.5 })
    const terre = sc.elements.get('terrain.couche.0')!.objet as THREE.Mesh
    const paroi = sc.elements.get('paroi.cote.0')!.objet.children[0] as THREE.Mesh
    expect((terre.material as THREE.Material).clippingPlanes?.length).toBe(1)
    expect((paroi.material as THREE.Material).clippingPlanes?.length ?? 0).toBe(0)
    expect(sc.planCoupe.constant).toBeCloseTo(sc.valeurCoupe, 9)
  })

  it('sélectionne un appui par visée et ignore les calques verrouillés', () => {
    const { sc } = nouvelleScene()
    const res = jeu('exemple')
    sc.charger(res)
    sc.phase(indicePhase(res, 'Pose du buton B1'))
    // caméra au-dessus du premier buton, visée verticale
    const b = sc.elements.get('appui.B1')!.objet.children[0] as THREE.InstancedMesh
    const m = new (b.matrix.constructor as typeof THREE.Matrix4)()
    b.getMatrixAt(0, m)
    const p = { x: m.elements[12], y: m.elements[13], z: m.elements[14] }
    sc.orbite.cible.set(p.x, p.y, p.z)
    sc.orbite.phi = 0.01
    sc.orbite.rayon = 5
    sc.placerCamera()
    sc.camera.updateProjectionMatrix()
    expect(sc.viser(0, 0)?.selection).toBe('appui:B1')
    sc.appliquerCalques({ ...sc.calques, verrouille: (id) => id === 'appuis.butons' })
    expect(sc.viser(0, 0)?.selection).not.toBe('appui:B1')
  })
})
