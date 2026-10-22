import { useMemo, useState } from 'react'
import { nb } from '../lib/format'
import { IconeFermer } from '../lib/icones'
import type { Theme } from '../lib/theme'
import { CoupeDiagrammes } from '../vues/CoupeDiagrammes'
import type { PositionCoupeLocale } from './coupeLocale'
import type { Contour } from './geometrie'
import type { SourceResultats } from './sourceResultats'

/** Panneau « Couper ici » : courbes à la position de la coupe locale, réglage de la position, épinglage. */
export function PanneauCoupeLocale({ geo, source, position, phase, theme, cotes, onPosition, onEpingler, onFermer }: {
  geo: Contour
  source: SourceResultats
  position: PositionCoupeLocale
  phase: number
  theme: Theme
  cotes: Record<string, number>
  onPosition: (p: PositionCoupeLocale) => void
  onEpingler: (nom: string) => void
  onFermer: () => void
}) {
  const [nom, setNom] = useState('')
  const courbes = useMemo(() => source.coupeLocale(position.k, position.sl, phase), [source, position, phase])
  const a = geo.aretes[position.k]
  const nomCote = Object.entries(cotes).find(([, v]) => v === position.k)?.[0]
  return (
    <aside className="panneau-coupe-locale" aria-label="Coupe locale">
      <div className="panneau-entete">
        Couper ici <span className="raccourci">C</span>
        <span className="espace" />
        <button className="btn icone discret" title="Fermer" onClick={onFermer}><IconeFermer taille={14} /></button>
      </div>
      <div className="position">
        <label>Côté
          <select value={position.k} onChange={(e) => onPosition({ k: Number(e.target.value), sl: Math.min(position.sl, geo.aretes[Number(e.target.value)].L) })} aria-label="Côté de la coupe locale">
            {geo.aretes.filter((x) => x.L > 1e-6).map((x) => <option key={x.k} value={x.k}>{Object.entries(cotes).find(([, v]) => v === x.k)?.[0] ?? `côté ${x.k}`} ({nb(x.L, 1)} m)</option>)}
          </select>
        </label>
        <label>Abscisse
          <input type="number" min={0} max={a.L} step={0.5} value={Number(position.sl.toFixed(2))} onChange={(e) => onPosition({ k: position.k, sl: Math.min(Math.max(Number(e.target.value) || 0, 0), a.L) })} aria-label="Abscisse de la coupe locale (m)" /> m
        </label>
        <input type="range" min={0} max={a.L} step={0.1} value={position.sl} onChange={(e) => onPosition({ k: position.k, sl: Number(e.target.value) })} aria-label="Glisser la coupe le long de la paroi" />
      </div>
      <div className="origine doux">
        {courbes ? courbes.origine : 'Aucune coupe de calcul ne couvre ce tronçon : rien à afficher.'}
        {courbes?.coupe && <> · <b>{courbes.coupe}</b></>}
      </div>
      <div className="courbes">
        {courbes && <CoupeDiagrammes res={courbes.res} phase={courbes.phase} theme={theme} />}
      </div>
      <div className="pied">
        <input value={nom} onChange={(e) => setNom(e.target.value)} placeholder={`Nom de la coupe (ex. C4 — ${nomCote ?? `côté ${position.k}`}, s = ${nb(position.sl, 1)} m)`} aria-label="Nom de la coupe à épingler" />
        <button className="btn" disabled={!nom.trim()} title="Ajoute cette coupe aux coupes de calcul du script (bloc coupes)" onClick={() => { onEpingler(nom.trim()); setNom('') }}>Épingler et ajouter au script</button>
      </div>
    </aside>
  )
}
