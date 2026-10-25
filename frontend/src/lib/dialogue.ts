// Dialogues de l'application (confirmer, informer, saisir) : remplacent window.confirm / alert / prompt.
// Le composant composants/Dialogue.tsx affiche la demande courante ; les demandes s'enchaînent une à une.
import { lireNombre } from './saisie'

export interface ChampDialogue {
  cle: string
  libelle: string
  defaut?: string | number
  type?: 'number' | 'text'
}

export type Valeurs = Record<string, string | number>

export type Demande =
  | { genre: 'confirmer'; titre?: string; texte: string; ok: string; resoudre: (v: boolean) => void }
  | { genre: 'informer'; titre?: string; texte: string; resoudre: () => void }
  | { genre: 'saisir'; titre: string; texte?: string; champs: ChampDialogue[]; ok: string; resoudre: (v: Valeurs | null) => void }

let courante: Demande | null = null
const attente: Demande[] = []
const abonnes = new Set<() => void>()

function publier() { abonnes.forEach((f) => f()) }
function suivante() {
  courante = attente.shift() ?? null
  publier()
}
function poser(d: Demande) {
  if (courante) attente.push(d)
  else { courante = d; publier() }
}

/** Abonnement du composant d'affichage (useSyncExternalStore). */
export function sAbonner(f: () => void): () => void {
  abonnes.add(f)
  return () => { abonnes.delete(f) }
}
export function demandeCourante(): Demande | null { return courante }

/** Clôt la demande courante avec sa réponse et passe à la suivante. */
export function repondre(valeur: unknown) {
  const d = courante
  if (!d) return
  if (d.genre === 'confirmer') d.resoudre(!!valeur)
  else if (d.genre === 'informer') d.resoudre()
  else d.resoudre((valeur as Valeurs | null) ?? null)
  suivante()
}

export function confirmer(texte: string, opts: { titre?: string; ok?: string } = {}): Promise<boolean> {
  return new Promise((resoudre) => poser({ genre: 'confirmer', titre: opts.titre, texte, ok: opts.ok ?? 'Confirmer', resoudre }))
}

export function informer(texte: string, titre?: string): Promise<void> {
  return new Promise((resoudre) => poser({ genre: 'informer', titre, texte, resoudre }))
}

/** Boîte de saisie à plusieurs champs ; les champs numériques acceptent la virgule. null si annulée. */
export function saisir(opts: { titre: string; texte?: string; champs: ChampDialogue[]; ok?: string }): Promise<Valeurs | null> {
  return new Promise((resoudre) => poser({ genre: 'saisir', titre: opts.titre, texte: opts.texte, champs: opts.champs, ok: opts.ok ?? 'Valider', resoudre }))
}

/** Lecture des valeurs brutes d'une boîte de saisie ; renvoie les erreurs (clé -> message) ou les valeurs typées. */
export function lireValeurs(champs: ChampDialogue[], brut: Record<string, string>): { valeurs: Valeurs; erreurs: Record<string, string> } {
  const valeurs: Valeurs = {}
  const erreurs: Record<string, string> = {}
  for (const c of champs) {
    const t = (brut[c.cle] ?? '').trim()
    if (c.type === 'number') {
      const n = lireNombre(t)
      if (n === null) erreurs[c.cle] = t === '' ? 'valeur requise' : `« ${t} » n'est pas un nombre`
      else valeurs[c.cle] = n
    } else valeurs[c.cle] = t
  }
  return { valeurs, erreurs }
}
