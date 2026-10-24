// Exports : image PNG de la vue active, note de calcul (HTML imprimable ou fichier), scripts.
import { api, type Resultats } from './api'
import { noteCalcul, type ContexteNote } from './note'
import type { Modele } from './scriptDoc'

/** Chaque vue qui sait produire une image s'enregistre ici quand elle est affichée. */
let exportateur: (() => void) | null = null
export function enregistrerExport(f: (() => void) | null) {
  exportateur = f
}
export function exportImagePossible(): boolean {
  return exportateur !== null
}
export function exporterImage() {
  exportateur?.()
}

export function telecharger(url: string, nom: string) {
  const a = document.createElement('a')
  a.href = url
  a.download = nom
  a.click()
}

export function telechargerTexte(texte: string, nom: string, type: string) {
  const url = URL.createObjectURL(new Blob([texte], { type }))
  telecharger(url, nom)
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

/** Référentiel (docs/normes) joint à la note ; null si le serveur ne répond pas (la note le signale). */
async function contexteNote(modele: Modele, version: string): Promise<ContexteNote> {
  const normes = await api.normes().then((d) => d.fichiers).catch(() => null)
  return { modele, normes, version }
}

const nomFichier = (res: Resultats) => `note_calcul_${(res.projet || 'projet').trim().replace(/[^\w-]+/g, '_')}.html`

/** Ouvre la note de calcul dans une fenêtre d'impression (enregistrement PDF par le navigateur). */
export async function imprimerNote(res: Resultats, modele: Modele, version: string) {
  const w = window.open('', '_blank')      // ouverte avant toute attente : sinon le navigateur la bloque
  if (!w) return
  const ctx = await contexteNote(modele, version)
  w.document.write(noteCalcul(res, ctx))
  w.document.close()
  w.focus()
  setTimeout(() => w.print(), 400)
}

/** Enregistre la note de calcul en fichier HTML autonome. */
export async function telechargerNote(res: Resultats, modele: Modele, version: string) {
  const ctx = await contexteNote(modele, version)
  telechargerTexte(noteCalcul(res, ctx), nomFichier(res), 'text/html;charset=utf-8')
}
