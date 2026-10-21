import { useMemo } from 'react'
import type { PhaseRes, Resultats } from '../lib/api'
import { Graphique } from './Graphique'

const COULEURS_SOL = ['#e8d8b0', '#d9c08c', '#c9a96e', '#b8925a', '#d6c7a1', '#a88a5c', '#cbb68a']

/** Coupe de la phase : sol, nappes, paroi, appuis, fond de fouille, déformée amplifiée. */
export function Coupe({ res, phase }: { res: Resultats; phase: PhaseRes }) {
  const { data, layout } = useMemo(() => {
    const H = res.paroi.tete - res.paroi.pied
    const L = Math.max(8, 0.8 * H)
    const zBas = res.paroi.pied - 0.15 * H
    const formes: object[] = []
    const couches = res.couches
    couches.forEach((c, i) => {
      const bas = i + 1 < couches.length ? couches[i + 1].toit : zBas
      const coul = COULEURS_SOL[i % COULEURS_SOL.length]
      for (const [x0, x1, terrain] of [
        [-L, 0, phase.terrain_amont],
        [0, L, phase.terrain_aval],
      ] as const) {
        const haut = Math.min(c.toit, terrain)
        if (haut > bas) {
          formes.push({ type: 'rect', x0, x1, y0: bas, y1: haut, fillcolor: coul, line: { width: 0 }, layer: 'below' })
        }
      }
    })
    const traces: object[] = []
    // Noms des couches
    traces.push({
      x: couches.map(() => -L * 0.97),
      y: couches.map((c, i) => {
        const bas = i + 1 < couches.length ? couches[i + 1].toit : zBas
        return (Math.min(c.toit, phase.terrain_amont) + bas) / 2
      }),
      text: couches.map((c) => c.nom),
      mode: 'text',
      textposition: 'middle right',
      showlegend: false,
      hoverinfo: 'skip',
    })
    // Nappes
    if (phase.eau_amont !== null) {
      traces.push({ x: [-L, 0], y: [phase.eau_amont, phase.eau_amont], mode: 'lines', line: { color: '#1f77b4', width: 2, dash: 'dash' }, name: `nappe amont ${phase.eau_amont.toFixed(2)} m` })
    }
    if (phase.eau_aval !== null) {
      traces.push({ x: [0, L], y: [phase.eau_aval, phase.eau_aval], mode: 'lines', line: { color: '#17becf', width: 2, dash: 'dash' }, name: `nappe aval ${phase.eau_aval.toFixed(2)} m` })
      if (phase.eau_aval > phase.terrain_aval) {
        formes.push({ type: 'rect', x0: 0, x1: L, y0: phase.terrain_aval, y1: phase.eau_aval, fillcolor: 'rgba(23,190,207,0.25)', line: { width: 0 } })
      }
    }
    // Fond de fouille
    traces.push({ x: [0, L], y: [phase.terrain_aval, phase.terrain_aval], mode: 'lines', line: { color: '#7f4f24', width: 3 }, name: `fond de fouille ${phase.terrain_aval.toFixed(2)} m` })
    // Paroi
    traces.push({ x: [0, 0], y: [res.paroi.pied, res.paroi.tete], mode: 'lines', line: { color: '#333', width: 6 }, name: `paroi (${res.paroi.type ?? ''})` })
    // Déformée amplifiée
    if (phase.y_mm && phase.z) {
      const ymax = Math.max(...phase.y_mm.map(Math.abs), 1e-6)
      const facteur = (0.12 * L) / (ymax / 1000)
      traces.push({
        x: phase.y_mm.map((y) => (y / 1000) * facteur),
        y: phase.z,
        mode: 'lines',
        line: { color: '#d62728', width: 2 },
        name: `déformée ×${Math.round(facteur)} (y > 0 vers la fouille)`,
        customdata: phase.y_mm,
        hovertemplate: 'z = %{y:.2f} m<br>y = %{customdata:.1f} mm<extra></extra>',
      })
    }
    // Appuis posés
    const defs = Object.fromEntries(res.appuis.map((a) => [a.nom, a]))
    for (const a of phase.appuis ?? []) {
      const def = defs[a.nom] as { angle?: number } | undefined
      const ang = ((def?.angle ?? (a.type === 'tirant' ? 20 : 0)) * Math.PI) / 180
      const vers = a.type === 'tirant' ? -1 : 1
      const long = a.type === 'tirant' ? 0.6 * L : a.type === 'bracon' ? 0.5 * L : 0.95 * L
      traces.push({
        x: [0, vers * long * Math.cos(ang)],
        y: [a.cote, a.cote - long * Math.sin(Math.abs(ang)) * (a.type === 'buton' ? 0 : 1)],
        mode: 'lines+text',
        line: { color: a.actif ? '#2ca02c' : '#999', width: a.type === 'dalle' ? 8 : 4 },
        text: ['', `${a.nom} : ${a.effort_axial_kN.toFixed(0)} kN`],
        textposition: 'top center',
        name: `${a.nom} (${a.type})`,
      })
    }
    return {
      data: traces,
      layout: {
        title: { text: `Coupe — ${phase.nom}` },
        shapes: formes,
        xaxis: { title: { text: '← amont   distance (m)   aval →' }, range: [-L, L], zeroline: false },
        yaxis: { title: { text: 'cote z (m)' }, range: [zBas, res.paroi.tete + 0.1 * H], scaleanchor: 'x', scaleratio: 1 },
        legend: { orientation: 'h', y: -0.15 },
      },
    }
  }, [res, phase])
  return <Graphique data={data} layout={layout} hauteur={620} nom={`coupe_${phase.nom}`} />
}
