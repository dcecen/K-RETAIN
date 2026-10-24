// Saisie de nombres par l'utilisateur (boîtes de dialogue) : virgule ou point, « Annuler » annule vraiment.

/** Nombre demandé par une boîte de dialogue ; null si l'utilisateur annule ou si la valeur n'est pas un nombre
 *  (un message le lui dit : rien n'est écrit dans le script avec une valeur douteuse). */
export function demanderNombre(message: string, defaut: number | string): number | null {
  const r = window.prompt(message, typeof defaut === 'number' ? String(defaut) : defaut)
  if (r === null) return null
  const n = lireNombre(r)
  if (n === null) {
    window.alert(`Valeur « ${r} » non comprise : entrez un nombre (virgule ou point décimal).`)
    return null
  }
  return n
}

/** Texte → nombre (virgule acceptée) ; null si vide ou non numérique. */
export function lireNombre(texte: string): number | null {
  const t = texte.trim().replace(/\s/g, '').replace(',', '.')
  if (t === '') return null
  const n = Number(t)
  return Number.isFinite(n) ? n : null
}
