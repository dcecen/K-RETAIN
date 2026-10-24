// Thème clair (par défaut) ou sombre (option) : attribut data-theme sur <html>, préférence mémorisée si possible.
// Le thème ne suit pas le réglage du système : un logiciel de calcul s'ouvre sur fond clair.

export type Theme = 'clair' | 'sombre'
const CLE = 'retainwall.theme.choix'   // mémorisé seulement quand l'utilisateur change de thème

export function themeInitial(): Theme {
  try {
    const t = localStorage.getItem(CLE)
    if (t === 'clair' || t === 'sombre') return t
  } catch {
    /* stockage indisponible */
  }
  return 'clair'
}

export function appliquerTheme(t: Theme) {
  document.documentElement.dataset.theme = t
}

/** Thème choisi explicitement par l'utilisateur (bouton de la barre de titre) : mémorisé. */
export function choisirTheme(t: Theme) {
  try {
    localStorage.setItem(CLE, t)
  } catch {
    /* stockage indisponible */
  }
}

/** Couleurs lues dans les jetons CSS, pour les graphiques Plotly. */
export function couleurs() {
  const cs = getComputedStyle(document.documentElement)
  const v = (n: string) => cs.getPropertyValue(n).trim()
  return {
    fond: v('--panneau'),
    fond2: v('--panneau-2'),
    texte: v('--texte'),
    doux: v('--texte-doux'),
    faible: v('--texte-faible'),
    filet: v('--filet'),
    filetFort: v('--filet-fort'),
    accent: v('--accent'),
    vert: v('--vert'),
    orange: v('--orange'),
    rouge: v('--rouge'),
  }
}

/** Teintes terre désaturées pour les couches de sol (lisibles dans les deux thèmes). */
export const COULEURS_SOL = ['#c8b48c', '#b39b74', '#9f8a69', '#8b7a61', '#bcaa8c', '#a59276', '#958670', '#c2b49b']
