// Types partagés de l'état de l'interface.

/** Vues de l'application : une seule navigation (colonne gauche) en trois groupes.
 *  Données (étapes de saisie), Résultats (après calcul), Outils (script, assemblages, base, aide). */
export type Vue =
  | 'projet' | 'sol' | 'ecran' | 'eau' | 'surcharges' | 'appuis' | 'phases' | 'verifs_demandees'
  | 'synthese' | 'diagrammes' | 'efforts' | 'verifications' | '3d' | 'hypotheses' | 'pseudo3d'
  | 'script' | 'assemblages' | 'materiaux' | 'aide'

/** Vues de saisie (formulaires) : sous-ensemble des vues. */
export type Section = 'projet' | 'sol' | 'ecran' | 'eau' | 'surcharges' | 'appuis' | 'phases' | 'verifs_demandees'

export type Selection =
  | { type: 'couche'; index: number }
  | { type: 'appui'; nom: string }
  | { type: 'phase'; index: number }
  | null

export interface EtatCalcul {
  genre: 'aucun' | 'calcul' | 'ok' | 'modifie' | 'erreur' | 'rupture'
  texte: string
  ligne?: number | null
}
