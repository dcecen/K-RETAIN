// Icônes SVG inline, trait de 1,5 px, grille 16 × 16.
import type { ReactNode } from 'react'

function Svg({ children, taille = 16 }: { children: ReactNode; taille?: number }) {
  return (
    <svg width={taille} height={taille} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.5}
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {children}
    </svg>
  )
}

type P = { taille?: number }

export const IconeLogo = (p: P) => (
  <Svg {...p}><path d="M3 2v12" /><path d="M3 5h10" /><path d="M3 9h7" /><path d="M6 14h7" strokeDasharray="1.5 1.5" /></Svg>
)
export const IconeProjet = (p: P) => <Svg {...p}><path d="M2.5 4.5h4l1.5 1.5h5.5v7h-11z" /></Svg>
export const IconeSol = (p: P) => <Svg {...p}><path d="M2 5h12M2 8.5h12M2 12h12" /></Svg>
export const IconeParoi = (p: P) => <Svg {...p}><rect x="6.5" y="2" width="3" height="12" /><path d="M2 6h4.5M9.5 9h4.5" /></Svg>
export const IconeEau = (p: P) => <Svg {...p}><path d="M8 2.5c2.5 3 4 5 4 7a4 4 0 0 1-8 0c0-2 1.5-4 4-7z" /></Svg>
export const IconeSurcharge = (p: P) => <Svg {...p}><path d="M2 13h12" /><path d="M4 4v6M8 4v6M12 4v6" /><path d="M3 8.5l1 1.5 1-1.5M7 8.5l1 1.5 1-1.5M11 8.5l1 1.5 1-1.5" /></Svg>
export const IconeAppui = (p: P) => <Svg {...p}><path d="M2 8h12" /><path d="M2 5.5v5M14 5.5v5" /></Svg>
export const IconePhases = (p: P) => <Svg {...p}><rect x="2" y="3" width="3" height="10" /><rect x="6.5" y="3" width="3" height="10" /><rect x="11" y="3" width="3" height="10" /></Svg>
export const IconeVerif = (p: P) => <Svg {...p}><path d="M3 8.5l3 3 7-7" /></Svg>
export const IconeScript = (p: P) => <Svg {...p}><path d="M5.5 4.5L2 8l3.5 3.5M10.5 4.5L14 8l-3.5 3.5" /></Svg>
export const IconeCoupe = (p: P) => <Svg {...p}><path d="M2 14V2M2 14h12" /><path d="M5 12c2-6 4-6 8-9" /></Svg>
export const IconeCube = (p: P) => <Svg {...p}><path d="M8 2l5.5 3v6L8 14l-5.5-3V5z" /><path d="M2.5 5L8 8l5.5-3M8 8v6" /></Svg>
export const IconeTableau = (p: P) => <Svg {...p}><rect x="2" y="3" width="12" height="10" /><path d="M2 6.5h12M6 3v10" /></Svg>
export const IconeBase = (p: P) => <Svg {...p}><ellipse cx="8" cy="4" rx="5" ry="2" /><path d="M3 4v8c0 1.1 2.2 2 5 2s5-.9 5-2V4" /><path d="M3 8c0 1.1 2.2 2 5 2s5-.9 5-2" /></Svg>
export const IconePlaque = (p: P) => <Svg {...p}><path d="M2 11l4-7h8l-4 7z" /><path d="M5 9h6" /></Svg>
export const IconeCalcul = (p: P) => <Svg {...p}><path d="M4.5 3l8 5-8 5z" /></Svg>
export const IconeExport = (p: P) => <Svg {...p}><path d="M8 10V2.5M5 5.5l3-3 3 3" /><path d="M3 9.5V13h10V9.5" /></Svg>
export const IconeSoleil = (p: P) => <Svg {...p}><circle cx="8" cy="8" r="2.75" /><path d="M8 1.5v1.5M8 13v1.5M1.5 8H3M13 8h1.5M3.4 3.4l1 1M11.6 11.6l1 1M3.4 12.6l1-1M11.6 4.4l1-1" /></Svg>
export const IconeLune = (p: P) => <Svg {...p}><path d="M13 9.5A5.5 5.5 0 0 1 6.5 3a5.5 5.5 0 1 0 6.5 6.5z" /></Svg>
export const IconeFichier = (p: P) => <Svg {...p}><path d="M4 2h5.5L12 4.5V14H4z" /><path d="M9.5 2v2.5H12" /></Svg>
export const IconeChevronD = (p: P) => <Svg {...p}><path d="M6 4l4 4-4 4" /></Svg>
export const IconeChevronB = (p: P) => <Svg {...p}><path d="M4 6l4 4 4-4" /></Svg>
export const IconePrec = (p: P) => <Svg {...p}><path d="M10 4L6 8l4 4" /></Svg>
export const IconeSuiv = (p: P) => <Svg {...p}><path d="M6 4l4 4-4 4" /></Svg>
export const IconeLecture = (p: P) => <Svg {...p}><path d="M5 3.5l7 4.5-7 4.5z" /></Svg>
export const IconePause = (p: P) => <Svg {...p}><path d="M5.5 3.5v9M10.5 3.5v9" /></Svg>
export const IconePanneauG = (p: P) => <Svg {...p}><rect x="2" y="3" width="12" height="10" /><path d="M6 3v10" /></Svg>
export const IconePanneauD = (p: P) => <Svg {...p}><rect x="2" y="3" width="12" height="10" /><path d="M10 3v10" /></Svg>
export const IconeAlerte = (p: P) => <Svg {...p}><path d="M8 2.5l6 11H2z" /><path d="M8 6.5v3.5M8 11.8v.2" /></Svg>
export const IconeInfo = (p: P) => <Svg {...p}><circle cx="8" cy="8" r="6" /><path d="M8 7.5v4M8 5v.2" /></Svg>
export const IconeFermer = (p: P) => <Svg {...p}><path d="M4 4l8 8M12 4l-8 8" /></Svg>
export const IconePlus = (p: P) => <Svg {...p}><path d="M8 3v10M3 8h10" /></Svg>
export const IconeMonter = (p: P) => <Svg {...p}><path d="M8 13V3M4 7l4-4 4 4" /></Svg>
export const IconeDescendre = (p: P) => <Svg {...p}><path d="M8 3v10M4 9l4 4 4-4" /></Svg>
export const IconeCorbeille = (p: P) => <Svg {...p}><path d="M3 4.5h10M6 4.5V3h4v1.5M4.5 4.5l.7 9h5.6l.7-9" /></Svg>
export const IconeMenu = (p: P) => <Svg {...p}><path d="M2.5 4.5h11M2.5 8h11M2.5 11.5h11" /></Svg>

// Icônes des actions de phase (frise)
export const IconeExcavation = (p: P) => <Svg {...p}><path d="M2 4h3v6h6V4h3" /><path d="M8 5.5v3M6.8 7.3L8 8.5l1.2-1.2" /></Svg>
export const IconePose = (p: P) => <Svg {...p}><path d="M2 3v10M14 3v10" /><path d="M2 7h12" /><path d="M8 9.5v3M6.5 11l1.5 1.5 1.5-1.5" strokeWidth={1.2} /></Svg>
export const IconeDepose = (p: P) => <Svg {...p}><path d="M2 3v10M14 3v10" /><path d="M2 7h4M10 7h4" strokeDasharray="1.5 1.5" /><path d="M6.5 9.5l3 3M9.5 9.5l-3 3" strokeWidth={1.2} /></Svg>
export const IconeRadier = (p: P) => <Svg {...p}><path d="M2 3v10M14 3v10" /><rect x="2" y="10" width="12" height="2.5" /></Svg>
export const IconeRemblai = (p: P) => <Svg {...p}><path d="M2 12h12" /><path d="M3 12l3-4 2 2 3-5 2 7" /></Svg>
export const IconeInitial = (p: P) => <Svg {...p}><path d="M2 6h12" /><path d="M2 9h12M2 12h12" strokeDasharray="1.5 1.5" /></Svg>
export const IconeOeil = (p: P) => <Svg {...p}><path d="M1.5 8s2.5-4.5 6.5-4.5S14.5 8 14.5 8 12 12.5 8 12.5 1.5 8 1.5 8z" /><circle cx="8" cy="8" r="2" /></Svg>
export const IconeOeilBarre = (p: P) => <Svg {...p}><path d="M1.5 8s2.5-4.5 6.5-4.5S14.5 8 14.5 8 12 12.5 8 12.5 1.5 8 1.5 8z" /><path d="M3 13L13 3" /></Svg>
export const IconeVerrou = (p: P) => <Svg {...p}><rect x="3.5" y="7" width="9" height="7" rx="1" /><path d="M5.5 7V5a2.5 2.5 0 0 1 5 0v2" /></Svg>
export const IconeVerrouOuvert = (p: P) => <Svg {...p}><rect x="3.5" y="7" width="9" height="7" rx="1" /><path d="M5.5 7V5a2.5 2.5 0 0 1 4.8-1" /></Svg>
export const IconeIsoler = (p: P) => <Svg {...p}><circle cx="8" cy="8" r="2.5" /><path d="M8 1.5v2M8 12.5v2M1.5 8h2M12.5 8h2" /></Svg>
export const IconeCalques = (p: P) => <Svg {...p}><path d="M8 2.5l6 3-6 3-6-3z" /><path d="M2 8.5l6 3 6-3M2 11l6 3 6-3" /></Svg>
export const IconeLoupe = (p: P) => <Svg {...p}><circle cx="7" cy="7" r="4.5" /><path d="M10.5 10.5L14 14" /></Svg>
export const IconeCiseaux = (p: P) => <Svg {...p}><circle cx="4" cy="4" r="2" /><circle cx="4" cy="12" r="2" /><path d="M5.5 5.5L14 12M5.5 10.5L14 4" /></Svg>
