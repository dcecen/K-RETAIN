import { useMemo } from 'react'
import type { PhaseRes, Resultats } from '../lib/api'
import { Graphique } from './Graphique'

const DOMAINES = [
  [0, 0.21],
  [0.26, 0.47],
  [0.52, 0.73],
  [0.78, 1],
]

function cadre(titres: string[], res: Resultats, phase: PhaseRes | null) {
  const layout: Record<string, unknown> = {
    yaxis: { title: { text: 'cote z (m)' }, range: [res.paroi.pied - 0.5, res.paroi.tete + 0.5] },
    legend: { orientation: 'h', y: -0.12 },
    margin: { l: 60, r: 20, t: 80, b: 50 },
    annotations: titres.map((t, i) => ({
      text: `<b>${t}</b>`,
      x: (DOMAINES[i][0] + DOMAINES[i][1]) / 2,
      y: 1.0,
      yanchor: 'bottom',
      xref: 'paper',
      yref: 'paper',
      showarrow: false,
    })),
    shapes: [] as object[],
  }
  titres.forEach((_, i) => {
    const k = i === 0 ? '' : String(i + 1)
    layout[`xaxis${k}`] = { domain: DOMAINES[i], anchor: 'y', zeroline: true, zerolinecolor: '#888' }
  })
  if (phase) {
    const sh = layout.shapes as object[]
    for (const [z, coul] of [
      [phase.terrain_aval, '#7f4f24'],
      [phase.terrain_amont, '#b08850'],
    ] as const) {
      sh.push({ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: z, y1: z, line: { color: coul, width: 1, dash: 'dot' } })
    }
  }
  return layout
}

/** Diagrammes le long de la paroi pour la phase choisie. */
export function Diagrammes({ res, phase }: { res: Resultats; phase: PhaseRes }) {
  const { data, layout } = useMemo(() => {
    if (!phase.ok || !phase.z) return { data: [], layout: {} }
    const p = phase.pressions!
    const titres = ['y (mm)', 'M (kN·m/m)', 'V (kN/m)', 'p (kPa) amont ← → aval']
    const neg = (a: number[]) => a.map((v) => -v)
    const data = [
      { x: phase.y_mm, y: phase.z, xaxis: 'x', name: 'y (positif vers la fouille)', line: { color: '#d62728' }, hovertemplate: 'z %{y:.2f} m : %{x:.1f} mm<extra></extra>' },
      { x: phase.M, y: phase.z_diag, xaxis: 'x2', name: 'M (positif : face fouille tendue)', line: { color: '#1f77b4' }, fill: 'tozerox', hovertemplate: 'z %{y:.2f} m : %{x:.1f} kN·m/m<extra></extra>' },
      { x: phase.V, y: phase.z_diag, xaxis: 'x3', name: 'V = dM/dz', line: { color: '#9467bd' }, fill: 'tozerox', hovertemplate: 'z %{y:.2f} m : %{x:.1f} kN/m<extra></extra>' },
      { x: neg(p.amont.p), y: p.amont.z, xaxis: 'x4', name: 'pression amont mobilisée', line: { color: '#ff7f0e' } },
      { x: neg(p.amont.pa), y: p.amont.z, xaxis: 'x4', name: 'poussée limite amont', line: { color: '#ff7f0e', dash: 'dot', width: 1 } },
      { x: neg(p.amont.pp), y: p.amont.z, xaxis: 'x4', name: 'butée limite amont', line: { color: '#ff7f0e', dash: 'dash', width: 1 }, visible: 'legendonly' },
      { x: p.aval.p, y: p.aval.z, xaxis: 'x4', name: 'pression aval mobilisée', line: { color: '#2ca02c' } },
      { x: p.aval.pp, y: p.aval.z, xaxis: 'x4', name: 'butée limite aval', line: { color: '#2ca02c', dash: 'dash', width: 1 } },
      { x: p.aval.pa, y: p.aval.z, xaxis: 'x4', name: 'poussée limite aval', line: { color: '#2ca02c', dash: 'dot', width: 1 }, visible: 'legendonly' },
      { x: neg(phase.eau!.u_amont), y: phase.eau!.z, xaxis: 'x4', name: 'eau amont', line: { color: '#1f77b4', dash: 'dashdot', width: 1 } },
      { x: phase.eau!.u_aval, y: phase.eau!.z, xaxis: 'x4', name: 'eau aval', line: { color: '#17becf', dash: 'dashdot', width: 1 } },
    ].map((t) => ({ mode: 'lines', yaxis: 'y', ...t }))
    const layout = cadre(titres, res, phase)
    layout.title = { text: `Diagrammes — ${phase.nom}`, y: 0.98, yanchor: 'top' }
    return { data, layout }
  }, [res, phase])
  if (!phase.ok) return <p className="alerte">{phase.message}</p>
  return <Graphique data={data} layout={layout} hauteur={640} nom={`diagrammes_${phase.nom}`} />
}

/** Enveloppes toutes phases et phase dimensionnante. */
export function Enveloppes({ res }: { res: Resultats }) {
  const { data, layout } = useMemo(() => {
    const e = res.enveloppes
    if (!e.z) return { data: [], layout: {} }
    const enveloppe = (x1: number[], x2: number[], y: number[], axe: string, coul: string, nom: string) => [
      { x: x1, y, xaxis: axe, mode: 'lines', line: { color: coul, width: 1 }, name: `${nom} min`, showlegend: false },
      { x: x2, y, xaxis: axe, mode: 'lines', line: { color: coul, width: 1 }, fill: 'tonextx', name: `${nom} min / max` },
    ]
    const data = [
      ...enveloppe(e.y_min_mm!, e.y_max_mm!, e.z, 'x', '#d62728', 'y (mm)'),
      ...enveloppe(e.M_min!, e.M_max!, e.z_diag!, 'x2', '#1f77b4', 'M (kN·m/m)'),
      ...enveloppe(e.V_min!, e.V_max!, e.z_diag!, 'x3', '#9467bd', 'V (kN/m)'),
    ].map((t) => ({ yaxis: 'y', ...t }))
    const d = res.dimensionnant
    const layout = cadre(['y (mm)', 'M (kN·m/m)', 'V (kN/m)'], res, null)
    layout.title = {
      text: `Enveloppes toutes phases<br><sup>M+ max ${d.moment_positif?.valeur.toFixed(0)} (${d.moment_positif?.phase}) · M− min ${d.moment_negatif?.valeur.toFixed(0)} (${d.moment_negatif?.phase}) · y max ${d.deplacement?.valeur_mm.toFixed(1)} mm (${d.deplacement?.phase})</sup>`,
      y: 0.98,
      yanchor: 'top',
    }
    layout.margin = { l: 60, r: 20, t: 100, b: 50 }
    for (let i = 0; i < 3; i++) {
      const k = i === 0 ? '' : String(i + 1)
      ;(layout[`xaxis${k}`] as Record<string, unknown>).domain = [i * 0.345, i * 0.345 + 0.31]
    }
    ;(layout.annotations as { x: number }[]).forEach((a, i) => (a.x = i * 0.345 + 0.155))
    return { data, layout }
  }, [res])
  return <Graphique data={data} layout={layout} hauteur={600} nom="enveloppes" />
}
