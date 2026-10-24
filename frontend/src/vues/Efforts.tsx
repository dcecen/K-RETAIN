import { useMemo, useState } from 'react'
import type { Resultats } from '../lib/api'
import { nb } from '../lib/format'

type Tri = { cle: string; sens: 1 | -1 }

/** Tableau phases × appuis, phase active surlignée, tri par colonne. */
export function Efforts({ res, phase, onPhase, onAppui }: {
  res: Resultats
  phase: number
  onPhase: (i: number) => void
  onAppui: (nom: string) => void
}) {
  const [unite, setUnite] = useState<'kN/m' | 'kN'>('kN/m')
  const [tri, setTri] = useState<Tri>({ cle: 'phase', sens: 1 })
  const noms = res.appuis.map((a) => a.nom)
  const val = (i: number, nom: string) => {
    const a = res.phases[i].appuis?.find((x) => x.nom === nom)
    return a ? (unite === 'kN' ? a.effort_axial_kN : a.effort_kN_m) : null
  }
  const ordre = useMemo(() => {
    const idx = res.phases.map((_, i) => i)
    if (tri.cle === 'phase') return tri.sens === 1 ? idx : idx.reverse()
    if (tri.cle === 'fond') return idx.sort((a, b) => tri.sens * (res.phases[a].terrain_aval - res.phases[b].terrain_aval))
    return idx.sort((a, b) => tri.sens * ((val(a, tri.cle) ?? -Infinity) - (val(b, tri.cle) ?? -Infinity)))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [res, tri, unite])
  const trier = (cle: string) => setTri(tri.cle === cle ? { cle, sens: tri.sens === 1 ? -1 : 1 } : { cle, sens: cle === 'phase' ? 1 : -1 })
  const fleche = (cle: string) => (tri.cle === cle ? (tri.sens === 1 ? ' ▲' : ' ▼') : '')

  if (!noms.length) return <div className="vide-centre">Aucun appui défini dans ce modèle.</div>
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="barre-outils">
        <span className="doux">Efforts dans les appuis</span>
        <span className="espace" />
        <div className="puces-choix" role="radiogroup" aria-label="Unité">
          <button className={`puce-choix ${unite === 'kN/m' ? 'actif' : ''}`} onClick={() => setUnite('kN/m')}>kN par mètre d'écran</button>
          <button className={`puce-choix ${unite === 'kN' ? 'actif' : ''}`} onClick={() => setUnite('kN')}>kN par appui (effort axial)</button>
        </div>
      </div>
      <div style={{ flex: 1, overflow: 'auto' }}>
        <table className="tableau">
          <thead>
            <tr>
              <th className="triable" onClick={() => trier('phase')}>Phase{fleche('phase')}</th>
              <th className="triable num" onClick={() => trier('fond')}>Fond<span className="unite">m</span>{fleche('fond')}</th>
              {res.appuis.map((a) => (
                <th key={a.nom} className="triable num" onClick={() => trier(a.nom)} title={`${a.type}, cote ${nb(a.cote, 2)} m${a.element ? ', ' + a.element : ''}`}>
                  <span style={{ cursor: 'pointer' }} onClick={(e) => { e.stopPropagation(); onAppui(a.nom) }}>{a.nom}</span>
                  <span className="unite">{unite}</span>{fleche(a.nom)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ordre.map((i) => {
              const p = res.phases[i]
              return (
                <tr key={i} className={`cliquable ${i === phase ? 'actif' : ''}`} onClick={() => onPhase(i)}>
                  <td>{i + 1}. {p.nom}</td>
                  <td className="num">{nb(p.terrain_aval, 2)}</td>
                  {noms.map((n) => {
                    const v = val(i, n)
                    const a = p.appuis?.find((x) => x.nom === n)
                    return (
                      <td key={n} className={`num ${a && !a.actif ? 'inactif' : ''}`} title={a && !a.actif ? 'Appui décollé' : undefined}>
                        {v === null ? '' : nb(v, unite === 'kN' ? 0 : 1)}
                      </td>
                    )
                  })}
                </tr>
              )
            })}
          </tbody>
          <tfoot>
            <tr>
              <td style={{ fontWeight: 600 }}>Maximum</td><td />
              {noms.map((n) => {
                const d = res.dimensionnant.appuis?.[n]
                return <td key={n} className="num" style={{ fontWeight: 600 }} title={d?.phase}>{d ? nb(unite === 'kN' ? d.effort_axial_kN : d.effort_kN_m, unite === 'kN' ? 0 : 1) : ''}</td>
              })}
            </tr>
          </tfoot>
        </table>
        <p className="note" style={{ padding: '8px 12px' }}>Effort positif : l'appui retient l'écran (buton comprimé, tirant tendu). Grisé : appui décollé. Clic sur une ligne : phase active ; clic sur un nom d'appui : détail de l'appui.</p>
      </div>
    </div>
  )
}
