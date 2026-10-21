import { useCallback, useEffect, useRef, useState } from 'react'
import { api, type Resultats } from '../lib/api'
import { enregistrerExport, telecharger, telechargerTexte } from '../lib/exporter'
import type { Theme } from '../lib/theme'
import type { EtatCoupe } from './scene'
import { Vue3D, type PoigneeVue3D } from './Vue3D'

/** Onglet « Maquette 3D » : vue persistante, outils de vue, plan de coupe, exports. */
export function Onglet3D({ res, texte, phase, theme, selection, onSelection }: {
  res: Resultats
  texte: string
  phase: number
  theme: Theme
  selection: string | null
  onSelection: (id: string | null) => void
}) {
  const poignee = useRef<PoigneeVue3D | null>(null)
  const [coupe, setCoupe] = useState<EtatCoupe>({ actif: false, axe: 'x', t: 0.5 })
  const [exportEnCours, setExportEnCours] = useState(false)

  const pret = useCallback((p: PoigneeVue3D | null) => { poignee.current = p }, [])

  useEffect(() => { poignee.current?.scene.definirCoupe(coupe) }, [coupe])

  useEffect(() => {
    enregistrerExport(() => {
      const p = poignee.current
      if (!p) return
      p.scene.rendreMaintenant()
      telecharger(p.canvas.toDataURL('image/png'), `maquette_phase${phase + 1}.png`)
    })
    return () => enregistrerExport(null)
  }, [phase])

  const exporterHtml = async () => {
    setExportEnCours(true)
    try { telechargerTexte(await api.maquette(texte), 'maquette_retainwall.html', 'text/html') }
    catch (e) { alert(String(e)) }
    finally { setExportEnCours(false) }
  }

  const vue = (n: 'iso' | 'face' | 'dessus' | 'coupe') => {
    poignee.current?.scene.vue(n)
    if (n === 'coupe') setCoupe({ actif: true, axe: 'x', t: 0.5 })
  }

  return (
    <div className="onglet-3d">
      <div className="barre-outils">
        <span className="doux">Vue :</span>
        <button className="btn" onClick={() => vue('iso')}>Iso</button>
        <button className="btn" onClick={() => vue('face')}>Face</button>
        <button className="btn" onClick={() => vue('dessus')}>Dessus</button>
        <button className="btn" onClick={() => vue('coupe')}>Coupe</button>
        <button className="btn" title="Recadrer sur la fouille" onClick={() => poignee.current?.scene.recadrer()}>Recadrer</button>
        <span className="separateur-v" />
        <label><input type="checkbox" checked={coupe.actif} onChange={(e) => setCoupe({ ...coupe, actif: e.target.checked })} /> plan de coupe</label>
        <select value={coupe.axe} disabled={!coupe.actif} onChange={(e) => setCoupe({ ...coupe, axe: e.target.value as 'x' | 'y' })} aria-label="Axe du plan de coupe">
          <option value="x">selon x</option>
          <option value="y">selon y</option>
        </select>
        <input type="range" min={0} max={1000} value={Math.round(coupe.t * 1000)} disabled={!coupe.actif} aria-label="Position du plan de coupe"
          onChange={(e) => setCoupe({ ...coupe, t: Number(e.target.value) / 1000 })} style={{ width: 140 }} />
        <span className="espace" />
        <button className="btn" disabled={exportEnCours} onClick={() => void exporterHtml()}>
          {exportEnCours ? 'Génération…' : 'Exporter le fichier HTML autonome'}
        </button>
      </div>
      <div className="onglet-3d-corps">
        <Vue3D res={res} phase={phase} theme={theme} selection={selection} onSelection={onSelection} onPret={pret}
          enfants={
            <div className="vue3d-note">
              {res.maquette?.plan_defaut && <div>Plan par défaut (rectangle 20 × 12 m) : ajoutez un bloc « plan » au script.</div>}
              <div>Glisser : tourner · clic droit ou Maj+glisser : déplacer · molette : zoom.</div>
              <div>Déplacement positif vers la fouille ; moment positif quand la face côté fouille est tendue.</div>
            </div>
          } />
      </div>
    </div>
  )
}
