import { useMemo } from 'react'
import { nb } from '../lib/format'
import type { Resultats } from '../lib/api'
import { Graphique } from './Graphique'

const transposer = (g: number[][]) => g[0].map((_, j) => g.map((ligne) => ligne[j]))

/** Champs pseudo-3D de la phase : déplacement et moment vertical le long de la paroi développée. */
export function Pseudo3D({ res, phase }: { res: Resultats; phase: number }) {
  const p3d = res.pseudo3d!
  const ph = p3d.phases[Math.min(phase, p3d.phases.length - 1)]
  const { data, layout } = useMemo(() => {
    if (!ph.ok || !ph.y_mm) return { data: [], layout: {} }
    const carte = (g: number[][], xaxis: string, yaxis: string, titre: string, echelle: string, barreX: number, barreY: number) => ({
      type: 'heatmap',
      x: p3d.s,
      y: p3d.z,
      z: transposer(g),
      xaxis,
      yaxis,
      colorscale: echelle,
      colorbar: { title: { text: titre }, x: barreX, y: barreY, len: 0.42 },
      hovertemplate: 's = %{x:.1f} m<br>z = %{y:.2f} m<br>%{z:.1f}<extra></extra>',
    })
    const data = [carte(ph.y_mm, 'x', 'y', 'y (mm)', 'RdBu', 0.45, 0.78), carte(ph.M!, 'x2', 'y', 'Mz (kN·m/m)', 'Portland', 1.0, 0.78)]
    if (ph.Ms) data.push(carte(ph.Ms, 'x3', 'y2', 'Ms (kN·m/m)', 'Portland', 0.45, 0.22))
    if (ph.V) data.push(carte(ph.V, 'x4', 'y2', 'V (kN/m)', 'Picnic', 1.0, 0.22))
    const axeS = { title: { text: 'abscisse le long de la paroi s (m)' } }
    // angles de la fouille : traits verticaux sur chaque carte
    const sommets = (p3d.sommets ?? []).filter((x) => x > 1e-6 && x < p3d.s[p3d.s.length - 1] - 1e-6)
    const shapes = sommets.flatMap((x) => ['x', 'x2', 'x3', 'x4'].map((xr) => ({
      type: 'line', xref: xr, yref: xr === 'x3' || xr === 'x4' ? 'y2' : 'y', x0: x, x1: x,
      y0: p3d.z[0], y1: p3d.z[p3d.z.length - 1], line: { color: '#333', width: 1, dash: 'dot' },
    })))
    return {
      data,
      layout: {
        shapes,
        title: { text: `Pseudo-3D${p3d.fermee ? ' (fouille fermée, butons reliant les parois en vis-à-vis)' : ''} — ${ph.nom} : déplacement y (positif vers la fouille), moments vertical Mz et horizontal Ms (positifs face fouille tendue), tranchant V (statique des lignes verticales)`, font: { size: 13 } },
        xaxis: { domain: [0, 0.42], anchor: 'y', ...axeS },
        xaxis2: { domain: [0.55, 0.97], anchor: 'y', ...axeS },
        xaxis3: { domain: [0, 0.42], anchor: 'y2', ...axeS },
        xaxis4: { domain: [0.55, 0.97], anchor: 'y2', ...axeS },
        yaxis: { domain: [0.56, 1], title: { text: 'cote z (m)' } },
        yaxis2: { domain: [0, 0.44], title: { text: 'cote z (m)' } },
      },
    }
  }, [p3d, ph])
  if (!ph.ok) return <div className="alerte rouge" style={{ margin: 12 }}>{ph.message}</div>
  return (
    <div style={{ padding: 12 }}>
      {p3d.avertissements.map((a, i) => (
        <div key={i} className="alerte orange">{a}</div>
      ))}
      <table className="tableau" style={{ width: 'auto', marginBottom: 10 }}>
        <thead><tr><th>Grandeur</th><th className="num">Pseudo-3D</th><th className="num">2D</th><th>Unité</th></tr></thead>
        <tbody>
          <tr><td>|y| max</td><td className="num">{nb(ph.y_max_mm, 1)}</td><td className="num">{nb(ph.y_max_2d_mm, 1)}</td><td>mm</td></tr>
          <tr><td>Moment vertical Mz max / min</td><td className="num">{nb(ph.Mz_max, 0)} / {nb(ph.Mz_min, 0)}</td><td /><td>kN·m/m</td></tr>
          <tr><td>|Moment horizontal Ms| max</td><td className="num">{nb(ph.Ms_absmax, 0)}</td><td /><td>kN·m/m</td></tr>
          <tr><td>|Tranchant V| max</td><td className="num">{nb(ph.V_absmax, 0)}</td><td /><td>kN/m (au droit des appuis ponctuels : voir largeur_appui)</td></tr>
          <tr><td>{p3d.fermee ? 'Butons entre parois' : 'Appuis ponctuels'}</td><td className="num">{ph.appuis?.length ?? 0}</td><td /><td>effort max {nb((ph.appuis ?? []).reduce((m, a) => Math.max(m, a.effort), 0), 0)} kN{p3d.fermee ? ', angles à w = 0' : ''}</td></tr>
        </tbody>
      </table>
      <Graphique data={data} layout={layout} hauteur={ph.Ms || ph.V ? 900 : 560} nom={`pseudo3d_${ph.nom}`} />
    </div>
  )
}
