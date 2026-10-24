import { Component, type ErrorInfo, type ReactNode } from 'react'

/** Dernier filet : une exception dans un composant n'efface plus toute l'interface (écran blanc) ;
 *  le script reste dans le brouillon du navigateur, on affiche l'erreur et un bouton pour recharger. */
export class GardeErreur extends Component<{ children: ReactNode }, { erreur: Error | null }> {
  state = { erreur: null as Error | null }

  static getDerivedStateFromError(erreur: Error) {
    return { erreur }
  }

  componentDidCatch(erreur: Error, info: ErrorInfo) {
    console.error('RetainWall : erreur d’affichage', erreur, info.componentStack)
  }

  render() {
    if (!this.state.erreur) return this.props.children
    return (
      <div className="vide-centre bloque" style={{ height: '100vh', padding: 24 }}>
        <b>Erreur d'affichage</b>
        <span>Le script est conservé dans le navigateur. Recharger la page ; si l'erreur se reproduit, transmettre le message ci-dessous avec le script.</span>
        <pre className="mono" style={{ whiteSpace: 'pre-wrap', maxWidth: 720, textAlign: 'left' }}>{String(this.state.erreur.message || this.state.erreur)}</pre>
        <button className="btn" onClick={() => window.location.reload()}>Recharger l'interface</button>
      </div>
    )
  }
}
