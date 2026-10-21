import type { ReactNode } from 'react'
import type { Resultats } from '../lib/api'
import { IconeCorbeille, IconeDepose, IconeEau, IconeExcavation, IconeInitial, IconePlus, IconePose, IconeRadier, IconeRemblai } from '../lib/icones'
import type { Modele } from '../lib/scriptDoc'
import { arbrePhases, cheminVers } from '../lib/phases'

const ICONES: Record<string, ReactNode> = {
  initial: <IconeInitial />, excavation: <IconeExcavation />, pose: <IconePose />, depose: <IconeDepose />,
  radier: <IconeRadier />, eau: <IconeEau />, remblai: <IconeRemblai />,
}

function resume(p: Modele): { type: string; texte: string }[] {
  const a: { type: string; texte: string }[] = []
  if (!p) return a
  if (typeof p.excaver === 'number') a.push({ type: 'excavation', texte: `excaver à ${p.excaver} m` })
  if (p.remblayer) a.push({ type: 'remblai', texte: 'remblai' })
  const l = (v: unknown) => (Array.isArray(v) ? v.join(', ') : v ? String(v) : '')
  if (p.poser) a.push({ type: 'pose', texte: `poser ${l(p.poser)}` })
  if (p.deposer) a.push({ type: 'depose', texte: `déposer ${l(p.deposer)}` })
  if (p.eau) a.push({ type: 'eau', texte: `nappe${p.eau.aval !== undefined ? ` aval ${p.eau.aval ?? 'aucune'}` : ''}${p.eau.amont !== undefined ? ` amont ${p.eau.amont ?? 'aucune'}` : ''}` })
  return a
}

/** Explorateur de phases façon Plaxis : lignes de branchement, insertion, variantes. */
export function ArbrePhases({ phases, res, actif, selection, onChoisir, onInserer, onBrancher, onSupprimer }: {
  phases: Modele[]
  res: Resultats | null
  actif: number                 // phase active des résultats (indice de résultat : 0 = état initial)
  selection: number | null      // phase sélectionnée pour l'édition (indice dans phases[])
  onChoisir: (index: number) => void
  onInserer: (apres: number) => void
  onBrancher: (depuis: number) => void
  onSupprimer: (index: number) => void
}) {
  const noeuds = arbrePhases(phases)
  const nLanes = Math.max(...noeuds.map((n) => n.lane)) + 1
  const RH = 34, LW = 18, X0 = 14
  const x = (lane: number) => X0 + lane * LW
  const y = (rang: number) => rang * RH + RH / 2
  const chemin = new Set(cheminVers(noeuds, actif - 1))
  return (
    <div className="arbre-phases" style={{ display: 'grid', gridTemplateColumns: `${X0 + nLanes * LW + 10}px 1fr` }}>
      <svg width={X0 + nLanes * LW + 10} height={noeuds.length * RH} style={{ display: 'block' }}>
        {noeuds.filter((n) => n.parent >= -1).map((n) => {
          const p = noeuds.find((q) => q.index === n.parent)!
          const enChemin = chemin.has(n.index) && chemin.has(p.index)
          const col = enChemin ? 'var(--accent)' : 'var(--filet-fort)'
          const pts = p.lane === n.lane
            ? `${x(p.lane)},${y(p.rang)} ${x(n.lane)},${y(n.rang)}`
            : `${x(p.lane)},${y(p.rang)} ${x(p.lane)},${y(p.rang) + RH * 0.45} ${x(n.lane)},${y(p.rang) + RH * 0.45} ${x(n.lane)},${y(n.rang)}`
          return <polyline key={n.index} points={pts} fill="none" stroke={col} strokeWidth={enChemin ? 2.5 : 1.5} strokeLinejoin="round" />
        })}
        {noeuds.map((n) => {
          const r = res?.phases[n.index + 1]
          const col = r ? (r.ok ? 'var(--vert)' : 'var(--rouge)') : 'var(--texte-faible)'
          const act = n.index + 1 === actif
          return (
            <g key={`n${n.index}`} style={{ cursor: 'pointer' }} onClick={() => onChoisir(n.index)}>
              <circle cx={x(n.lane)} cy={y(n.rang)} r={act ? 7 : 5.5} fill={act ? 'var(--accent)' : 'var(--panneau)'} stroke={col} strokeWidth={2} />
            </g>
          )
        })}
      </svg>
      <div>
        {noeuds.map((n) => {
          const p = n.index >= 0 ? phases[n.index] : null
          const r = res?.phases[n.index + 1]
          const sel = n.index === selection
          const act = n.index + 1 === actif
          return (
            <div key={n.index} className={`ligne-phase ${sel ? 'sel' : ''} ${act ? 'act' : ''}`} style={{ height: RH }} onClick={() => onChoisir(n.index)}>
              <span className="mono faible" style={{ width: 22 }}>{n.index >= 0 ? n.index + 1 : ''}</span>
              <span style={{ fontWeight: act || sel ? 600 : 400, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>{n.nom}</span>
              {n.index >= 0 && p?.depuis && <span className="pastille non_verifiable" title={`branche depuis « ${p.depuis} »`}>variante</span>}
              <span className="doux" style={{ display: 'flex', gap: 6, alignItems: 'center', fontSize: 11.5, minWidth: 0 }}>
                {(n.index < 0 ? [{ type: 'initial', texte: 'sol au repos' }] : resume(p)).map((a, k) => <span key={k} title={a.texte} style={{ display: 'inline-flex', alignItems: 'center', gap: 3 }}>{ICONES[a.type]}<span className="masquer-etroit">{a.texte}</span></span>)}
              </span>
              {r && !r.ok && <span className="pastille non_ok" title={r.message}>échec</span>}
              <span style={{ display: 'flex', gap: 2 }} onClick={(e) => e.stopPropagation()}>
                <button className="btn icone discret" title="Insérer une phase après celle-ci" onClick={() => onInserer(n.index)}><IconePlus taille={14} /></button>
                <button className="btn icone discret" title="Créer une variante (branche) à partir de cette phase" onClick={() => onBrancher(n.index)}>
                  <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M4 2v9a3 3 0 0 0 3 3h5" /><path d="M9 11l3 3-3 3" transform="translate(0 -3)" /><circle cx="4" cy="2" r="1.5" /></svg>
                </button>
                {n.index >= 0 && <button className="btn icone discret" title="Supprimer la phase" onClick={() => onSupprimer(n.index)}><IconeCorbeille taille={14} /></button>}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
