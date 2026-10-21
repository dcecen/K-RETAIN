import { useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import { enregistrerExport, telecharger, telechargerTexte } from '../lib/exporter'
import type { Theme } from '../lib/theme'

/** Maquette 3D : HTML autonome généré par le serveur, piloté par messages (phase, thème, sélection, image). */
export function Maquette3D({ texte, version, phase, theme, selection, onPhase, onSelection }: {
  texte: string
  version: number
  phase: number
  theme: Theme
  selection: string | null
  onPhase: (i: number) => void
  onSelection: (nom: string | null) => void
}) {
  const [html, setHtml] = useState<string | null>(null)
  const [erreur, setErreur] = useState<string | null>(null)
  const [enCours, setEnCours] = useState(false)
  const cadre = useRef<HTMLIFrameElement>(null)
  const pret = useRef(false)

  // Génération à chaque nouveau calcul
  useEffect(() => {
    let actif = true
    setEnCours(true)
    setErreur(null)
    pret.current = false
    api.maquette(texte).then((h) => { if (actif) setHtml(h) }).catch((e) => { if (actif) setErreur(String(e)) })
      .finally(() => { if (actif) setEnCours(false) })
    return () => { actif = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [version])

  const envoyer = (m: object) => cadre.current?.contentWindow?.postMessage({ source: 'retainwall', ...m }, '*')
  useEffect(() => { envoyer({ type: 'phase', index: phase }) }, [phase, html])
  useEffect(() => { envoyer({ type: 'theme', sombre: theme === 'sombre' }) }, [theme, html])
  useEffect(() => { envoyer({ type: 'selection', appui: selection }) }, [selection, html])

  useEffect(() => {
    const recevoir = (e: MessageEvent) => {
      const m = e.data || {}
      if (m.source !== 'retainwall-3d') return
      if (m.type === 'phase') onPhase(m.index)
      else if (m.type === 'selection') onSelection(m.appui ?? null)
      else if (m.type === 'image') telecharger(m.url, `maquette_phase${phase + 1}.png`)
    }
    window.addEventListener('message', recevoir)
    return () => window.removeEventListener('message', recevoir)
  }, [onPhase, onSelection, phase])

  useEffect(() => {
    enregistrerExport(() => envoyer({ type: 'image' }))
    return () => enregistrerExport(null)
  }, [])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="barre-outils">
        <span className="doux">Maquette 3D {enCours ? '— génération…' : ''}</span>
        <span className="espace" />
        <button className="btn" disabled={!html} onClick={() => html && telechargerTexte(html, 'maquette_retainwall.html', 'text/html')}>
          Exporter le fichier HTML autonome
        </button>
      </div>
      <div style={{ flex: 1, position: 'relative', minHeight: 0 }}>
        {erreur && <div className="alerte rouge" style={{ margin: 12 }}>{erreur}</div>}
        {html && (
          <iframe ref={cadre} title="Maquette 3D" className="cadre-3d" srcDoc={html}
            onLoad={() => { pret.current = true; envoyer({ type: 'theme', sombre: theme === 'sombre' }); envoyer({ type: 'phase', index: phase }); envoyer({ type: 'selection', appui: selection }) }} />
        )}
      </div>
    </div>
  )
}
