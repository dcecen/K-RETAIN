// Outils communs des tests de la vue 3D (sans WebGL).
import * as THREE from 'three'
import type { Resultats } from '../../lib/api'
import { FABRIQUES_CHANTIER } from '../elements'
import { SceneRetainWall, type FabriqueSpecs } from '../scene'
import berlinoise from './donnees/berlinoise_tirants.json'
import ecoulement from './donnees/fouille_ecoulement.json'
import exemple from './donnees/fouille_exemple.json'
import p3d from './donnees/pseudo3d_angle.json'

const JEUX: Record<string, unknown> = { exemple, ecoulement, p3d, berlinoise }
export type NomJeu = 'exemple' | 'ecoulement' | 'p3d' | 'berlinoise'

/** Copie profonde d'un jeu de résultats figé (chaque recalcul produit un nouvel objet). */
export function jeu(nom: NomJeu): Resultats {
  return structuredClone(JEUX[nom]) as Resultats
}

export function nouvelleScene(fabriques: FabriqueSpecs[] = FABRIQUES_CHANTIER) {
  const rendus = { n: 0 }
  const sc = new SceneRetainWall({ fabriques, rendu: { render: () => { rendus.n++ } } })
  return { sc, rendus }
}

/** Compte les objets de la scène, les géométries et les matériaux atteignables. */
export function compter(sc: SceneRetainWall) {
  let objets = 0
  const geos = new Set<THREE.BufferGeometry>()
  const mats = new Set<THREE.Material>()
  sc.scene.traverse((o) => {
    objets++
    const m = o as THREE.Mesh
    if (m.geometry) geos.add(m.geometry)
    const ms = Array.isArray(m.material) ? m.material : m.material ? [m.material] : []
    for (const x of ms) mats.add(x)
  })
  return { objets, geometries: geos.size, materiaux: mats.size, geos, mats }
}

export function indicePhase(res: Resultats, nom: string): number {
  const i = res.phases.findIndex((p) => p.nom === nom)
  if (i < 0) throw new Error(`phase ${nom} absente`)
  return i
}
