// Formatage des nombres à la française (virgule décimale, espace fine pour les milliers).

const cache = new Map<number, Intl.NumberFormat>()

export function nb(v: number | null | undefined, decimales = 1): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return '—'
  let f = cache.get(decimales)
  if (!f) {
    f = new Intl.NumberFormat('fr-FR', { minimumFractionDigits: decimales, maximumFractionDigits: decimales })
    cache.set(decimales, f)
  }
  return f.format(v)
}

export function pourcent(v: number | null | undefined, decimales = 0): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return '—'
  return `${nb(v * 100, decimales)} %`
}

export function cote(v: number | null | undefined): string {
  return v === null || v === undefined ? 'aucune' : `${nb(v, 2)} m`
}

/** Interpolation linéaire y(x) sur des abscisses croissantes ; null hors domaine. */
export function interp(xs: number[], ys: number[], x: number): number | null {
  const n = xs.length
  if (!n || x < xs[0] - 1e-9 || x > xs[n - 1] + 1e-9) return null
  for (let i = 1; i < n; i++) {
    if (x <= xs[i]) {
      const t = xs[i] === xs[i - 1] ? 0 : (x - xs[i - 1]) / (xs[i] - xs[i - 1])
      return ys[i - 1] + t * (ys[i] - ys[i - 1])
    }
  }
  return ys[n - 1]
}


/** Nom du projet affiché : la clé `projet` doit être un texte ; pendant la frappe (ou si elle est écrite
 *  comme un bloc), on n'affiche jamais « [object Object] » : bloc avec `nom` → ce nom, sinon vide
 *  (la validation du script signale l'erreur). */
export function nomProjet(v: unknown): string {
  if (typeof v === 'string') return v
  if (typeof v === 'number') return String(v)
  if (v && typeof v === 'object' && !Array.isArray(v) && typeof (v as { nom?: unknown }).nom === 'string') return (v as { nom: string }).nom
  return ''
}

/** Unité des cotes affichée dans les en-têtes : « m NGF » par défaut, ou « m <système> » si le bloc
 *  `projet:` du script précise `systeme_cotes` (ex. « projet », « IGN69 »). */
export function uniteCote(modele: unknown): string {
  const p = modele && typeof modele === 'object' ? (modele as { projet?: unknown }).projet : null
  const s = p && typeof p === 'object' && !Array.isArray(p) ? (p as { systeme_cotes?: unknown }).systeme_cotes : null
  return typeof s === 'string' && s.trim() ? `m ${s.trim()}` : 'm NGF'
}
