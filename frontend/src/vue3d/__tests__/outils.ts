// Outils communs des tests de la vue 3D (sans WebGL).
import * as THREE from 'three'
import type { ProjetCoupes, Resultats } from '../../lib/api'
import { FABRIQUES_CHANTIER } from '../elements'
import { SceneRetainWall, type FabriqueSpecs } from '../scene'
import berlinoise from './donnees/berlinoise_tirants.json'
import ecoulement from './donnees/fouille_ecoulement.json'
import exemple from './donnees/fouille_exemple.json'
import p3d from './donnees/pseudo3d_angle.json'
import coupes from './donnees/fouille_coupes.json'
import zones from './donnees/geometrie_fouille_zones.json'

const JEUX: Record<string, unknown> = { exemple, ecoulement, p3d, berlinoise, coupes, zones }
export type NomJeu = 'exemple' | 'ecoulement' | 'p3d' | 'berlinoise' | 'coupes' | 'zones'

/** Copie profonde d'un jeu de résultats figé (chaque recalcul produit un nouvel objet). */
export function jeu(nom: NomJeu): Resultats {
  return structuredClone((JEUX[nom] as { resultats: Resultats }).resultats)
}

/** Jeu figé dessiné sur un contour rectangulaire fermé 20 × 12 m explicite. Depuis le 25/10/2026, un script sans
 *  tracé en plan (fouille_exemple) est dessiné en coupe infinie ouverte ; les tests écrits pour un contour fermé à
 *  quatre côtés lui donnent ce rectangle comme le ferait un bloc geometrie (donnée d'entrée, pas valeur attendue). */
export function jeuRectangle(nom: NomJeu): Resultats {
  const r = jeu(nom)
  r.maquette!.contour = [[0, 0], [20, 0], [20, 12], [0, 12]]
  r.maquette!.ferme = true
  r.maquette!.plan_defaut = false
  return r
}

/** Réponse complète du calcul (résultats de la première coupe + projet à coupes). */
export function jeuProjet(nom: NomJeu): { resultats: Resultats; projet: ProjetCoupes } {
  return structuredClone(JEUX[nom] as { resultats: Resultats; projet: ProjetCoupes })
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
