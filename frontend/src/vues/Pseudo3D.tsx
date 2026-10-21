import { useMemo } from 'react'
import type { Resultats } from '../lib/api'
import { Graphique } from './Graphique'

const transposer = (g: number[][]) => g[0].map((_, j) => g.map((ligne) => ligne[j]))

/** Champs pseudo-3D de la phase : déplacement et moment vertical le long de la paroi développée. */
export function Pseudo3D({ res, phase }: { res: Resultats; phase: number }) {
  const p3d = res.pseudo3d!
  const ph = p3d.phases[Math.min(phase, p3d.phases.length - 1)]
  const { data, layout } = useMemo(() => {
    if (!ph.ok || !ph.y_mm) return { data: [], layout: {} }
    const carte = (g: number[][], axe: string, titre: string, echelle: string, barreX: number) => ({
      type: 'heatmap',
      x: p3d.s,
      y: p3d.z,
      z: transposer(g),
      xaxis: axe === '1' ? 'x' : 'x2',
      yaxis: 'y',
      colorscale: echelle,
      colorbar: { title: { text: titre }, x: barreX, len: 0.9 },
      hovertemplate: 's = %{x:.1f} m<br>z = %{y:.2f} m<br>%{z:.1f}<extra></extra>',
    })
    return {
      data: [
        carte(ph.y_mm, '1', 'y (mm)', 'RdBu', 0.45),
        carte(ph.M!, '2', 'M (kN·m/m)', 'Portland', 1.0),
      ],
      layout: {
        title: { text: `Pseudo-3D — ${ph.nom} : déplacement (positif vers la fouille) et moment vertical (positif face fouille tendue)`, font: { size: 13 } },
        xaxis: { domain: [0, 0.42], title: { text: 'abscisse le long de la paroi s (m)' } },
        xaxis2: { domain: [0.55, 0.97], title: { text: 'abscisse le long de la paroi s (m)' } },
        yaxis: { title: { text: 'cote z (m)' } },
      },
    }
  }, [p3d, ph])
  if (!ph.ok) return <div className="alerte rouge" style={{ margin: 12 }}>{ph.message}</div>
  return (
    <div style={{ padding: 12 }}>
      {p3d.avertissements.map((a, i) => (
        <div key={i} className="alerte orange">{a}</div>
      ))}
      <div className="chiffres" style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
        <div className="chiffre"><div className="lib">|y| max pseudo-3D</div><div className="val">{ph.y_max_mm?.toFixed(1)} mm</div><div className="sous">2D : {ph.y_max_2d_mm?.toFixed(1) ?? '—'} mm</div></div>
        <div className="chiffre"><div className="lib">Moment vertical</div><div className="val">{ph.Mz_max?.toFixed(0)} / {ph.Mz_min?.toFixed(0)}</div><div className="sous">kN·m/m</div></div>
        <div className="chiffre"><div className="lib">|Moment horizontal| max</div><div className="val">{ph.Ms_absmax?.toFixed(0)}</div><div className="sous">kN·m/m</div></div>
        <div className="chiffre"><div className="lib">Appuis ponctuels</div><div className="val">{ph.appuis?.length ?? 0}</div><div className="sous">effort max {Math.max(0, ...(ph.appuis ?? []).map((a) => a.effort)).toFixed(0)} kN</div></div>
      </div>
      <Graphique data={data} layout={layout} hauteur={560} nom={`pseudo3d_${ph.nom}`} />
    </div>
  )
}
