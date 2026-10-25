import type * as THREE from 'three'
import { describe, expect, it } from 'vitest'
import { attenuationAngle, Contour, contourMaquette } from '../geometrie'
import { jeu, nouvelleScene } from './outils'

describe('coupe 2D infinie et contour ouvert', () => {
  it('un tronçon droit ouvert : une arête, terre et fouille de part et d’autre, rien d’inventé', () => {
    const geo = new Contour([[0, 0], [28, 0]], false, 19)
    expect(geo.ferme).toBe(false)
    expect(geo.aretes).toHaveLength(1)
    expect(geo.longueur).toBe(28)
    const ni = geo.aretes[0].ni
    // côté fouille : celui du polygone que fermerait la polyligne (même règle que le calcul) ; ici y < 0
    expect(ni[1]).toBe(-1)
    expect(geo.fouille).toHaveLength(4)
    expect(Math.min(...geo.fouille.map((p) => p[1]))).toBeCloseTo(-19, 9)         // bande assez large pour les butons
    expect(Math.max(...geo.terre.points.map((p) => p[1]))).toBeCloseTo(geo.marge, 9)
    expect(geo.terre.trou).toBeUndefined()
    expect(geo.dedans(10, -3)).toBe(true)
    expect(geo.dedans(10, 3)).toBe(false)
    // les bandes s'arrêtent aux bouts de l'écran : coupe nette, l'écran est supposé continuer
    expect(Math.min(...geo.fouille.map((p) => p[0]))).toBe(0)
    expect(Math.max(...geo.terre.points.map((p) => p[0]))).toBe(28)
  })

  it('une paroi en L ouverte : deux arêtes, fouille à l’intérieur de l’angle', () => {
    const geo = new Contour([[0, 40], [0, 0], [40, 0]], false)
    expect(geo.aretes).toHaveLength(2)
    expect(geo.dedans(10, 10)).toBe(true)
    expect(geo.dedans(-5, 10)).toBe(false)
  })

  it('la déformée n’est pas atténuée aux bouts libres, seulement aux angles', () => {
    expect(attenuationAngle(0, 20, 5, true, true)).toBe(1)
    expect(attenuationAngle(20, 20, 5, true, true)).toBe(1)
    expect(attenuationAngle(0, 20, 5)).toBe(0)
    expect(attenuationAngle(20, 20, 5, true, false)).toBe(0)
  })

  it('la maquette de l’exemple sans tracé en plan se charge en coupe ouverte, avec une seule face d’écran', () => {
    const res = jeu('exemple')
    expect(res.maquette!.ferme).toBe(false)
    const geo = contourMaquette(res.maquette)
    expect(geo.ferme).toBe(false)
    const { sc } = nouvelleScene()
    sc.charger(res)
    expect([...sc.elements.keys()].filter((id) => id.startsWith('paroi.cote.'))).toHaveLength(1)
    sc.phase(3)
    const terre = [...sc.elements.values()].find((e) => e.id.startsWith('terrain.couche') || e.id.startsWith('sol.'))
    expect(terre === undefined || (terre.objet as THREE.Object3D).visible !== undefined).toBe(true)
  })
})

describe('légende de la déformée d’une coupe infinie', () => {
  it('ne parle ni d’angle ni de zone hors modèle quand il n’y en a pas', async () => {
    const { noteDeformee } = await import('../legendes')
    const res = jeu('exemple')
    expect(noteDeformee(res)).toContain('écran supposé infini')
    expect(noteDeformee(res)).not.toContain('angles')
  })
})
