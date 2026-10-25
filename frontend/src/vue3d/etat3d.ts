// État d'interface de la maquette 3D conservé par l'application (survit au changement de vue) :
// plan de coupe, panneau latéral ouvert, volet du panneau de résultats, position des courbes en un point.
import type { PositionCoupeLocale } from './coupeLocale'
import type { EtatCoupe } from './scene'

export type Panneau3D = 'resultats' | 'calques' | 'courbes' | null
export type Volet3D = 'courbes' | 'efforts' | 'verifications'

export interface EtatVue3D {
  coupe: EtatCoupe
  /** Un seul panneau latéral à la fois. */
  panneau: Panneau3D
  volet: Volet3D
  largeur: number
  positionLocale: PositionCoupeLocale | null
}

export const ETAT_3D_INITIAL: EtatVue3D = { coupe: { actif: false, axe: 'x', t: 0.5 }, panneau: null, volet: 'courbes', largeur: 420, positionLocale: null }
