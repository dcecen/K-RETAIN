import { useEffect, useState, type ReactNode } from 'react'
import type { Resultats } from '../lib/api'
import { cote } from '../lib/format'
import {
  IconeDepose, IconeEau, IconeExcavation, IconeInitial, IconeLecture, IconePause, IconePose, IconePrec, IconeRadier,
  IconeRemblai, IconeSuiv, IconeSurcharge,
} from '../lib/icones'

const ICONES: Record<string, ReactNode> = {
  initial: <IconeInitial />, excavation: <IconeExcavation />, pose: <IconePose />, depose: <IconeDepose />,
  radier: <IconeRadier />, eau: <IconeEau />, remblai: <IconeRemblai />, surcharge: <IconeSurcharge />,
}
const PRIORITE = ['radier', 'pose', 'depose', 'excavation', 'remblai', 'eau', 'surcharge', 'initial']

/** Frise des phases : une case par phase, lecture automatique, flèches du clavier. */
export function FrisePhases({ res, phase, onPhase }: { res: Resultats | null; phase: number; onPhase: (i: number) => void }) {
  const [lecture, setLecture] = useState(false)
  const n = res?.phases.length ?? 0

  useEffect(() => {
    if (!lecture || !n) return
    const t = window.setInterval(() => {
      onPhase(-1) // signal : phase suivante (gérée par le parent)
    }, 900)
    return () => window.clearInterval(t)
  }, [lecture, n, onPhase])

  useEffect(() => {
    if (lecture && phase >= n - 1) setLecture(false)
  }, [lecture, phase, n])

  if (!res) {
    return <div className="frise zone-frise"><span className="doux">Aucun calcul : la frise des phases s'affiche après le calcul.</span></div>
  }
  const ph = res.phases[Math.min(phase, n - 1)]
  const ancetres = new Set<number>()
  for (let k: number | null = phase; k !== null && k !== undefined; k = res.phases[k]?.parent ?? null) ancetres.add(k)
  const precedent = ph.parent ?? Math.max(0, phase - 1)
  const suivant = ph.enfants?.[0] ?? Math.min(n - 1, phase + 1)
  return (
    <div className="frise zone-frise">
      <button className="btn icone" onClick={() => onPhase(precedent)} title="Phase précédente dans la branche (flèche gauche)"><IconePrec /></button>
      <button className="btn icone" onClick={() => onPhase(suivant)} title="Phase suivante dans la branche (flèche droite)"><IconeSuiv /></button>
      <button className="btn icone" onClick={() => { if (!lecture && phase >= n - 1) onPhase(0); setLecture(!lecture) }}
        title={lecture ? 'Arrêter la lecture' : 'Lire les phases'}>{lecture ? <IconePause /> : <IconeLecture />}</button>
      <div className="cases" role="tablist" aria-label="Phases">
        {res.phases.map((p, i) => {
          const type = PRIORITE.find((t) => p.actions.some((a) => a.type === t)) ?? 'initial'
          return (
            <button key={i} role="tab" aria-selected={i === phase}
              className={`case-phase ${i === phase ? 'actif' : ''} ${p.ok ? '' : 'echec'} ${ancetres.has(i) ? 'ancetre' : ''} ${p.depuis ? 'branche' : ''}`}
              onClick={() => onPhase(i)}
              title={`Phase ${i + 1} : ${p.nom}${p.actions.length ? '\n' + p.actions.map((a) => a.texte).join('\n') : ''}${p.ok ? '' : '\n' + p.message}`}>
              {ICONES[type]}
              <span className="numero">{i + 1}</span>
            </button>
          )
        })}
      </div>
      <div className="infos">
        <span className="nom-phase">{phase + 1}. {ph.nom}</span>
        <span className="doux">fond <span className="mono">{cote(ph.terrain_aval)}</span></span>
        <span className="doux masquer-etroit">nappe aval <span className="mono">{cote(ph.eau_aval)}</span></span>
      </div>
    </div>
  )
}
