// Types et fonctions utilitaires des formulaires de saisie (sans composant).
import type { ErreurScript, Resultats } from '../../lib/api'
import type { Selection } from '../../lib/etat'
import { cheminErreur, type Chemin, type Modele } from '../../lib/scriptDoc'
import type { Actions } from '../../lib/useProjet'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type Schema = any

/** Champ dont l'aide est affichée dans le panneau droit (champ focalisé). */
export interface AideChampInfo { bloc: string; cle: string; chemin: Chemin; libelle?: string }

export interface Ctx {
  modele: Modele
  erreurs: ErreurScript[]
  schema: Schema
  references: Record<string, string[]>
  actions: Actions
  onAide?: (a: AideChampInfo | null) => void
  /** Texte YAML courant (conversion de la géométrie par le serveur). */
  texte?: string
}

export interface PropsSection {
  ctx: Ctx
  selection: Selection
  onSelection: (s: Selection) => void
  phaseActive: number
  onPhaseActive: (i: number) => void
  res: Resultats | null
}

/** Description d'un champ depuis le schéma JSON (unité et bornes dans la description). */
export function doc(schema: Schema, bloc: string, cle: string): string {
  const def = bloc === 'Script' ? schema?.properties?.[cle] : schema?.$defs?.[bloc]?.properties?.[cle]
  return def?.description ?? ''
}

export function enumDe(schema: Schema, bloc: string, cle: string): string[] {
  const def = schema?.$defs?.[bloc]?.properties?.[cle]
  const cand = def?.enum ?? def?.anyOf?.find((x: Schema) => x.enum)?.enum ?? []
  return cand.map(String)
}

export function erreurDe(ctx: Ctx, chemin: Chemin): string | null {
  const c = cheminErreur(chemin)
  return ctx.erreurs.find((e) => e.chemin === c)?.message ?? null
}

/** Nombre de clés renseignées parmi une liste (compteur du bloc avancé). */
export function renseignes(obj: Modele, cles: string[]): number {
  if (!obj || typeof obj !== 'object') return 0
  return cles.filter((k) => obj[k] !== undefined && obj[k] !== null && obj[k] !== '').length
}

/** Une erreur existe-t-elle sur l'une des clés avancées d'un objet (pour ouvrir le bloc d'office) ? */
export function erreurParmi(ctx: Ctx, base: Chemin, cles: string[]): boolean {
  return cles.some((k) => erreurDe(ctx, [...base, k]) !== null)
}
