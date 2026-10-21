// Types partagés de l'état de l'interface.

export type Section = 'projet' | 'sol' | 'paroi' | 'eau' | 'surcharges' | 'appuis' | 'phases' | 'verifications'

export type Selection =
  | { type: 'couche'; index: number }
  | { type: 'appui'; nom: string }
  | { type: 'phase'; index: number }
  | null

export type Onglet = 'coupe' | '3d' | 'efforts' | 'verifications' | 'pseudo3d' | 'assemblages' | 'saisie' | 'script' | 'materiaux'

export interface EtatCalcul {
  genre: 'aucun' | 'calcul' | 'ok' | 'modifie' | 'erreur' | 'rupture'
  texte: string
  ligne?: number | null
}
