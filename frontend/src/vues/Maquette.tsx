import { useState } from 'react'
import { api } from '../lib/api'

/** Maquette 3D : générée par le serveur en un fichier HTML autonome (three.js intégré). */
export function Maquette({ texte }: { texte: string }) {
  const [html, setHtml] = useState<string | null>(null)
  const [erreur, setErreur] = useState<string | null>(null)
  const [enCours, setEnCours] = useState(false)

  const generer = async () => {
    setEnCours(true)
    setErreur(null)
    try {
      setHtml(await api.maquette(texte))
    } catch (e) {
      setErreur(String(e))
    } finally {
      setEnCours(false)
    }
  }

  const telecharger = () => {
    if (!html) return
    const url = URL.createObjectURL(new Blob([html], { type: 'text/html' }))
    const a = document.createElement('a')
    a.href = url
    a.download = 'maquette_retainwall.html'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="maquette">
      <div className="barre">
        <button onClick={() => void generer()} disabled={enCours}>{enCours ? 'Génération…' : 'Générer la maquette'}</button>
        <button className="secondaire" onClick={telecharger} disabled={!html}>Exporter le fichier HTML</button>
        <span className="note">Le script doit contenir un bloc « plan » (polygone de fouille, appuis en plan).</span>
      </div>
      {erreur && <div className="alerte rouge-fond">{erreur}</div>}
      {html && <iframe title="maquette 3D" srcDoc={html} className="cadre-3d" />}
    </div>
  )
}
