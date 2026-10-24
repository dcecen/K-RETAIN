import type { ReactNode } from 'react'
import { IconePanneauG } from '../lib/icones'

/** Grille plein écran : barre de titre, navigation, centre, panneau droit, frise. Les zones absentes (panneau,
 *  frise) libèrent leur place ; sous 1 100 px le panneau droit devient un tiroir, sous 768 px la navigation aussi. */
export function Disposition({ titre, nav, centre, insp, frise, navRepliee, tiroirNav, tiroirInsp, onRouvrirNav, onFermerTiroirs }: {
  titre: ReactNode
  nav: ReactNode
  centre: ReactNode
  insp: ReactNode | null
  frise: ReactNode | null
  navRepliee: boolean
  tiroirNav: boolean
  tiroirInsp: boolean
  onRouvrirNav: () => void
  onFermerTiroirs: () => void
}) {
  const classes = ['appli', navRepliee ? 'sans-nav' : '', insp ? '' : 'sans-insp', frise ? '' : 'sans-frise',
    tiroirNav ? 'nav-ouvert' : '', tiroirInsp ? 'insp-ouvert' : ''].join(' ')
  return (
    <div className={classes}>
      {titre}
      <div className="zone-nav">{nav}</div>
      <main className="zone-centre">
        {navRepliee && <button className="btn icone discret btn-rouvrir-nav" title="Afficher la navigation" onClick={onRouvrirNav}><IconePanneauG taille={14} /></button>}
        {centre}
      </main>
      <div className="zone-insp">{insp}</div>
      {frise}
      {(tiroirNav || tiroirInsp) && <div className="voile-tiroir" onClick={onFermerTiroirs} aria-hidden="true" />}
    </div>
  )
}
