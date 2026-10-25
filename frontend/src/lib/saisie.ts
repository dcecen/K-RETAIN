// Lecture des nombres saisis par l'utilisateur : virgule ou point décimal.

/** Texte -> nombre (virgule acceptée) ; null si vide ou non numérique. */
export function lireNombre(texte: string): number | null {
  const t = texte.trim().replace(/\s/g, '').replace(',', '.')
  if (t === '') return null
  const n = Number(t)
  return Number.isFinite(n) ? n : null
}
