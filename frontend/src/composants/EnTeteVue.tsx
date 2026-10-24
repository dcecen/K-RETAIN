import type { ReactNode } from 'react'
import { IconePrec } from '../lib/icones'

/** En-tête commun des vues : titre, sous-titre, actions propres à la vue (à droite). */
export function EnTeteVue({ titre, sousTitre, retour, enfants }: {
  titre: string
  sousTitre?: string
  /** Lien de retour (vue ouverte depuis la maquette 3D). */
  retour?: { libelle: string; onClick: () => void } | null
  enfants?: ReactNode
}) {
  return (
    <header className="entete-vue">
      {retour && <button className="btn discret" onClick={retour.onClick} title={retour.libelle}><IconePrec taille={14} /> {retour.libelle}</button>}
      <div className="entete-vue-titres">
        <h1>{titre}</h1>
        {sousTitre && <span className="doux">{sousTitre}</span>}
      </div>
      <span className="espace" />
      {enfants}
    </header>
  )
}
