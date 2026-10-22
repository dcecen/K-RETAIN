import { useEffect, useMemo, useRef, useState } from 'react'
import Plotly from 'plotly.js-dist-min'
import type { PhaseRes, Resultats } from '../lib/api'
import { enregistrerExport } from '../lib/exporter'
import { interp, nb } from '../lib/format'
import { COULEURS_SOL, couleurs, type Theme } from '../lib/theme'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Obj = any

// Domaines horizontaux des cinq panneaux (coupe, y, M, V, pressions)
const DOM = [[0, 0.27], [0.31, 0.45], [0.49, 0.64], [0.68, 0.81], [0.85, 1]] as const

function etendue(valeurs: number[], marge = 0.08): [number, number] {
  let lo = Math.min(0, ...valeurs)
  let hi = Math.max(0, ...valeurs)
  if (hi - lo < 1e-9) { lo -= 1; hi += 1 }
  const m = (hi - lo) * marge
  return [lo - m, hi + m]
}

/** Bornes fixes pour toutes les phases (les axes ne bougent pas d'une phase à l'autre). */
function bornes(res: Resultats) {
  const ok = res.phases.filter((p) => p.ok && p.z)
  const y = ok.flatMap((p) => p.y_mm!)
  const M = ok.flatMap((p) => p.M!)
  const V = ok.flatMap((p) => p.V!)
  const pmob = ok.flatMap((p) => [...p.pressions!.amont.p, ...p.pressions!.aval.p, ...p.eau!.u_amont, ...p.eau!.u_aval])
  const pmax = Math.max(1, ...pmob)
  const pa = ok.flatMap((p) => [...p.pressions!.amont.p, ...p.eau!.u_amont])
  const pv = ok.flatMap((p) => [...p.pressions!.aval.p, ...p.eau!.u_aval])
  const plafond = 1.8 * pmax
  return {
    y: etendue(y), M: etendue(M), V: etendue(V),
    p: [-Math.min(plafond, 1.25 * Math.max(1, ...pa)), Math.min(plafond, 1.25 * Math.max(1, ...pv))] as [number, number],
  }
}

function extreme(xs: number[], zs: number[], quoi: 'max' | 'min' | 'abs') {
  let k = 0
  for (let i = 1; i < xs.length; i++) {
    const v = xs[i], b = xs[k]
    if ((quoi === 'max' && v > b) || (quoi === 'min' && v < b) || (quoi === 'abs' && Math.abs(v) > Math.abs(b))) k = i
  }
  return { x: xs[k], z: zs[k] }
}

function figure(res: Resultats, ph: PhaseRes, b: ReturnType<typeof bornes>, enveloppe: boolean) {
  const c = couleurs()
  const H = res.paroi.tete - res.paroi.pied
  const zBas = res.paroi.pied - 0.08 * H
  const zHaut = res.paroi.tete + 0.08 * H
  const L = Math.max(8, 0.7 * H)
  const traces: Obj[] = []
  const formes: Obj[] = [
    // 0 : réticule (déplacé au survol)
    { type: 'line', xref: 'paper', yref: 'y', x0: 0, x1: 1, y0: zHaut, y1: zHaut, line: { color: c.accent, width: 1, dash: 'dot' }, visible: false },
  ]
  const annotations: Obj[] = []
  const titre = (k: number, texte: string) => annotations.push({
    text: texte, xref: 'paper', yref: 'paper', x: (DOM[k][0] + DOM[k][1]) / 2, y: 1, yanchor: 'bottom',
    showarrow: false, font: { size: 11, color: c.doux },
  })

  // ---- coupe
  res.couches.forEach((ch, i) => {
    const bas = i + 1 < res.couches.length ? res.couches[i + 1].toit : zBas
    for (const [x0, x1, terrain] of [[-L, 0, ph.terrain_amont], [0, L, ph.terrain_aval]] as const) {
      const haut = Math.min(ch.toit, terrain)
      if (haut > bas) formes.push({ type: 'rect', xref: 'x', yref: 'y', x0, x1, y0: bas, y1: haut, line: { width: 0 }, fillcolor: COULEURS_SOL[i % COULEURS_SOL.length], opacity: 0.55, layer: 'below' })
    }
    annotations.push({ text: ch.nom, xref: 'x', yref: 'y', x: -L * 0.97, y: (Math.min(ch.toit, ph.terrain_amont) + bas) / 2, xanchor: 'left', showarrow: false, font: { size: 10, color: c.texte } })
  })
  // réseau d'écoulement (régime simplifié ou différences finies)
  const hy = ph.hydro
  if (hy?.h && hy.x && hy.z) {
    traces.push({
      type: 'contour', x: hy.x, y: hy.z, z: hy.h[0].map((_, j) => hy.h!.map((col) => col[j])), xaxis: 'x', yaxis: 'y',
      contours: { coloring: 'lines', showlabels: true, labelfont: { size: 9, color: c.accent }, start: Math.min(hy.h_amont ?? 0, hy.h_aval ?? 0), end: Math.max(hy.h_amont ?? 0, hy.h_aval ?? 0), size: Math.max(0.1, Math.abs((hy.h_amont ?? 0) - (hy.h_aval ?? 0)) / 10) },
      line: { color: c.accent, width: 1 }, showscale: false, hoverinfo: 'skip', connectgaps: false, opacity: 0.8,
    })
  }
  if (hy?.bouchon) {
    const b = hy.bouchon
    formes.push({ type: 'rect', xref: 'x', yref: 'y', x0: 0, x1: L, y0: b.base, y1: Math.min(b.toit, ph.terrain_aval), line: { color: c.doux, width: 1 }, fillcolor: c.faible, opacity: 0.35, layer: 'below' })
    annotations.push({ text: `bouchon ${b.type}`, xref: 'x', yref: 'y', x: L * 0.5, y: (b.base + Math.min(b.toit, ph.terrain_aval)) / 2, showarrow: false, font: { size: 10, color: c.texte } })
  }
  if (hy && hy.gradient_sortie.length && hy.gradient_sortie_max > 0) {
    const ic = (res.couches.length ? 1 : 1) // i_c affiché via la couleur : rouge au-delà de 0,9·i_c (i_c ≈ γ'/γw ≈ 1)
    hy.gradient_sortie_x.forEach((x, k) => {
      if (x > L || k % Math.max(1, Math.round(hy.gradient_sortie_x.length / 12))) return
      const i = hy.gradient_sortie[k]
      const lg = 0.12 * H * Math.min(1.5, i / ic)
      const coul = i >= 0.9 * ic ? c.rouge : i >= 0.5 * ic ? c.orange : c.accent
      annotations.push({ x, y: ph.terrain_aval + lg, ax: x, ay: ph.terrain_aval, xref: 'x', yref: 'y', axref: 'x', ayref: 'y', showarrow: true, arrowhead: 2, arrowwidth: 1.5, arrowcolor: coul, text: '' })
    })
    annotations.push({ text: `i sortie max ${nb(hy.gradient_sortie_max, 2)}`, xref: 'x', yref: 'y', x: L * 0.97, y: ph.terrain_aval + 0.2 * H, xanchor: 'right', showarrow: false, font: { size: 10, color: hy.gradient_sortie_max >= 0.9 * ic ? c.rouge : c.doux } })
  }
  if (ph.eau_aval !== null && ph.eau_aval > ph.terrain_aval) {
    formes.push({ type: 'rect', xref: 'x', yref: 'y', x0: 0, x1: L, y0: ph.terrain_aval, y1: ph.eau_aval, line: { width: 0 }, fillcolor: c.accent, opacity: 0.15, layer: 'below' })
  }
  for (const [x0, x1, z] of [[-L, 0, ph.eau_amont], [0, L, ph.eau_aval]] as const) {
    if (z !== null) traces.push({ x: [x0, x1], y: [z, z], xaxis: 'x', yaxis: 'y', mode: 'lines', line: { color: c.accent, width: 1.5, dash: 'dash' }, hoverinfo: 'none' })
  }
  traces.push({ x: [0, L], y: [ph.terrain_aval, ph.terrain_aval], xaxis: 'x', yaxis: 'y', mode: 'lines', line: { color: c.texte, width: 2 }, hoverinfo: 'none' })
  traces.push({ x: [0, 0], y: [res.paroi.pied, res.paroi.tete], xaxis: 'x', yaxis: 'y', mode: 'lines', line: { color: c.texte, width: 5 }, hoverinfo: 'none' })
  if (ph.ok && ph.z) {
    const ymax = Math.max(...ph.y_mm!.map(Math.abs), 1e-6)
    const f = (0.25 * L) / ymax
    traces.push({ x: ph.y_mm!.map((y) => y * f), y: ph.z, xaxis: 'x', yaxis: 'y', mode: 'lines', line: { color: c.rouge, width: 1.5 }, hoverinfo: 'none' })
    annotations.push({ text: `déformée ×${nb(f * 1000, 0)}`, xref: 'x', yref: 'y', x: L * 0.97, y: zBas + 0.03 * H, xanchor: 'right', showarrow: false, font: { size: 10, color: c.rouge } })
  }
  for (const a of ph.appuis ?? []) {
    const def = res.appuis.find((d) => d.nom === a.nom)
    const ang = ((def?.angle ?? 0) * Math.PI) / 180
    const sens = a.type === 'tirant' ? -1 : 1
    const lg = a.type === 'tirant' ? 0.6 * L : a.type === 'dalle' ? L : 0.9 * L
    const dz = a.type === 'buton' || a.type === 'dalle' ? 0 : -lg * Math.sin(Math.abs(ang))
    traces.push({ x: [0, sens * lg * Math.cos(ang)], y: [a.cote, a.cote + dz], xaxis: 'x', yaxis: 'y', mode: 'lines',
      line: { color: a.actif ? c.vert : c.faible, width: a.type === 'dalle' ? 6 : 3 }, hoverinfo: 'none' })
    annotations.push({ text: `${a.nom} ${nb(a.effort_axial_kN, 0)} kN`, xref: 'x', yref: 'y', x: sens * lg * 0.55, y: a.cote + dz / 2,
      yanchor: 'bottom', showarrow: false, font: { size: 10, color: c.texte } })
  }

  // ---- diagrammes
  if (ph.ok && ph.z) {
    const p = ph.pressions!
    const neg = (v: number[]) => v.map((x) => -x)
    if (enveloppe && res.enveloppes.z) {
      const e = res.enveloppes
      const env = (x1: number[], x2: number[], y: number[], ax: string) => {
        traces.push({ x: x1, y, xaxis: ax, yaxis: 'y', mode: 'lines', line: { width: 0 }, hoverinfo: 'none', showlegend: false })
        traces.push({ x: x2, y, xaxis: ax, yaxis: 'y', mode: 'lines', line: { width: 0 }, fill: 'tonextx', fillcolor: 'rgba(128,140,160,0.22)', hoverinfo: 'none' })
      }
      env(e.y_min_mm!, e.y_max_mm!, e.z!, 'x2')
      env(e.M_min!, e.M_max!, e.z_diag!, 'x3')
      env(e.V_min!, e.V_max!, e.z_diag!, 'x4')
    }
    traces.push({ x: ph.y_mm, y: ph.z, xaxis: 'x2', yaxis: 'y', mode: 'lines', line: { color: c.rouge, width: 2 }, hoverinfo: 'none' })
    traces.push({ x: ph.M, y: ph.z_diag, xaxis: 'x3', yaxis: 'y', mode: 'lines', line: { color: c.accent, width: 1.5 }, fill: 'tozerox', fillcolor: 'rgba(80,130,190,0.18)', hoverinfo: 'none' })
    traces.push({ x: ph.V, y: ph.z_diag, xaxis: 'x4', yaxis: 'y', mode: 'lines', line: { color: '#8a6bb8', width: 1.5 }, fill: 'tozerox', fillcolor: 'rgba(138,107,184,0.16)', hoverinfo: 'none' })
    traces.push({ x: neg(p.amont.pa), y: p.amont.z, xaxis: 'x5', yaxis: 'y', mode: 'lines', line: { color: c.orange, width: 1, dash: 'dot' }, hoverinfo: 'none' })
    traces.push({ x: p.aval.pp, y: p.aval.z, xaxis: 'x5', yaxis: 'y', mode: 'lines', line: { color: c.vert, width: 1, dash: 'dash' }, hoverinfo: 'none' })
    traces.push({ x: neg(ph.eau!.u_amont), y: ph.eau!.z, xaxis: 'x5', yaxis: 'y', mode: 'lines', line: { color: c.accent, width: 1, dash: 'dashdot' }, hoverinfo: 'none' })
    traces.push({ x: ph.eau!.u_aval, y: ph.eau!.z, xaxis: 'x5', yaxis: 'y', mode: 'lines', line: { color: c.accent, width: 1, dash: 'dashdot' }, hoverinfo: 'none' })
    traces.push({ x: neg(p.amont.p), y: p.amont.z, xaxis: 'x5', yaxis: 'y', mode: 'lines', line: { color: c.orange, width: 2 }, hoverinfo: 'none' })
    traces.push({ x: p.aval.p, y: p.aval.z, xaxis: 'x5', yaxis: 'y', mode: 'lines', line: { color: c.vert, width: 2 }, hoverinfo: 'none' })

    // extrêmes annotés
    const marque = (ax: string, pt: { x: number; z: number }, texte: string, couleur: string) => {
      traces.push({ x: [pt.x], y: [pt.z], xaxis: ax, yaxis: 'y', mode: 'markers', marker: { size: 6, color: couleur }, hoverinfo: 'none' })
      annotations.push({ text: texte, xref: ax, yref: 'y', x: pt.x, y: pt.z, ax: pt.x >= 0 ? -28 : 28, ay: -16, arrowwidth: 1, arrowcolor: couleur, arrowhead: 0, font: { size: 10.5, color: couleur }, bgcolor: c.fond })
    }
    marque('x2', extreme(ph.y_mm!, ph.z, 'abs'), `${nb(extreme(ph.y_mm!, ph.z, 'abs').x)} mm`, c.rouge)
    const mmax = extreme(ph.M!, ph.z_diag!, 'max'), mmin = extreme(ph.M!, ph.z_diag!, 'min')
    if (mmax.x > 0.5) marque('x3', mmax, nb(mmax.x, 0), c.accent)
    if (mmin.x < -0.5) marque('x3', mmin, nb(mmin.x, 0), c.accent)
    const vabs = extreme(ph.V!, ph.z_diag!, 'abs')
    marque('x4', vabs, nb(vabs.x, 0), '#8a6bb8')
  }

  // fonds et niveaux sur tous les diagrammes
  formes.push({ type: 'line', xref: 'paper', yref: 'y', x0: DOM[1][0], x1: 1, y0: ph.terrain_aval, y1: ph.terrain_aval, line: { color: c.filetFort, width: 1, dash: 'dot' } })

  titre(0, 'Coupe')
  titre(1, 'Déplacement (mm)')
  titre(2, 'Moment (kN·m/m)')
  titre(3, 'Tranchant (kN/m)')
  titre(4, 'Pressions (kPa)')

  const axe = (k: number, range: [number, number]) => ({
    domain: DOM[k], anchor: 'y', range, zeroline: k > 0, zerolinecolor: c.filetFort, zerolinewidth: 1,
    gridcolor: c.filet, linecolor: c.filetFort, tickfont: { size: 10, color: c.doux }, showline: true, fixedrange: true,
    showticklabels: true, ticks: 'outside', ticklen: 3, tickcolor: c.filetFort,
  })
  const layout: Obj = {
    paper_bgcolor: c.fond, plot_bgcolor: c.fond, font: { family: 'IBM Plex Sans, sans-serif', size: 11, color: c.texte },
    margin: { l: 52, r: 10, t: 26, b: 34 }, showlegend: false, hovermode: 'y', dragmode: false,
    yaxis: { range: [zBas, zHaut], title: { text: 'cote (m)', font: { size: 11, color: c.doux } }, gridcolor: c.filet, zeroline: false,
      linecolor: c.filetFort, showline: true, tickfont: { size: 10, color: c.doux }, ticks: 'outside', ticklen: 3, tickcolor: c.filetFort },
    xaxis: { ...axe(0, [-L, L]), showgrid: false, zeroline: false, showticklabels: false, ticks: '' },
    xaxis2: axe(1, b.y), xaxis3: axe(2, b.M), xaxis4: axe(3, b.V), xaxis5: axe(4, b.p),
    shapes: formes, annotations,
  }
  return { traces, layout }
}

/** Valeurs à une cote donnée, pour le panneau de survol synchronisé. */
function valeursA(ph: PhaseRes, z: number) {
  if (!ph.ok || !ph.z) return null
  const asc = <T,>(xs: number[], ys: T[]) => {
    const idx = xs.map((_, i) => i).sort((a, b) => xs[a] - xs[b])
    return { x: idx.map((i) => xs[i]), y: idx.map((i) => ys[i] as unknown as number) }
  }
  const y = asc(ph.z, ph.y_mm!), M = asc(ph.z_diag!, ph.M!), V = asc(ph.z_diag!, ph.V!)
  const p = ph.pressions!
  return {
    y: interp(y.x, y.y, z), M: interp(M.x, M.y, z), V: interp(V.x, V.y, z),
    pam: interp(p.amont.z, p.amont.p, z), pav: interp(p.aval.z, p.aval.p, z),
  }
}

export function CoupeDiagrammes({ res, phase, theme, curseurZ, onSurvolZ }: {
  res: Resultats
  phase: number
  theme: Theme
  /** Cote imposée au réticule (survol d'une cote dans la maquette 3D). */
  curseurZ?: number | null
  /** Cote survolée sur les courbes (repère dans la maquette 3D). */
  onSurvolZ?: (z: number | null) => void
}) {
  const hote = useRef<HTMLDivElement>(null)
  const infos = useRef<HTMLDivElement>(null)
  const phaseRef = useRef<PhaseRes>(res.phases[phase])
  const survolRef = useRef(onSurvolZ)
  survolRef.current = onSurvolZ
  const [enveloppe, setEnveloppe] = useState(false)
  const b = useMemo(() => bornes(res), [res])
  const ph = res.phases[Math.min(phase, res.phases.length - 1)]
  phaseRef.current = ph

  useEffect(() => {
    const el = hote.current as Obj
    if (!el) return
    const { traces, layout } = figure(res, ph, b, enveloppe)
    void Plotly.react(el, traces, layout, { responsive: true, displayModeBar: false, doubleClick: 'reset', locale: 'fr' }).then(() => {
      if (el.__retainwall) return
      el.__retainwall = true
      el.on('plotly_hover', (e: Obj) => {
        const z = e?.points?.[0]?.y
        if (typeof z !== 'number') return
        survolRef.current?.(z)
        void Plotly.relayout(el, { 'shapes[0].y0': z, 'shapes[0].y1': z, 'shapes[0].visible': true })
        const v = valeursA(phaseRef.current, z)
        const boite = infos.current
        if (!boite) return
        boite.style.display = 'block'
        const l = (t: string, x: number | null | undefined, u: string, d = 1) => `<tr><td>${t}</td><td>${x === null || x === undefined ? '—' : nb(x, d)} ${u}</td></tr>`
        boite.innerHTML = `<div class="cote">z = ${nb(z, 2)} m</div><table>${
          v ? l('Déplacement', v.y, 'mm') + l('Moment', v.M, 'kN·m/m', 0) + l('Tranchant', v.V, 'kN/m', 0)
            + l('Pression amont', v.pam, 'kPa') + l('Pression aval', v.pav, 'kPa') : ''}</table>`
      })
      el.on('plotly_unhover', () => {
        survolRef.current?.(null)
        void Plotly.relayout(el, { 'shapes[0].visible': false })
        if (infos.current) infos.current.style.display = 'none'
      })
      // Maj + molette : zoom vertical centré sur le curseur
      el.addEventListener('wheel', (ev: WheelEvent) => {
        if (!ev.shiftKey) return
        ev.preventDefault()
        const ya = el._fullLayout?.yaxis
        if (!ya) return
        const r = el.getBoundingClientRect()
        const zc = ya.p2l(ev.clientY - r.top - ya._offset)
        const [a, bb] = ya.range as [number, number]
        const f = (ev.deltaY || ev.deltaX) > 0 ? 1.15 : 1 / 1.15
        void Plotly.relayout(el, { 'yaxis.range': [zc - (zc - a) * f, zc + (bb - zc) * f] })
      }, { passive: false })
    })
  }, [res, ph, b, enveloppe, theme])

  // réticule piloté depuis la maquette 3D
  useEffect(() => {
    const el = hote.current as Obj
    if (!el || !el._fullLayout) return
    if (curseurZ === null || curseurZ === undefined) void Plotly.relayout(el, { 'shapes[0].visible': false })
    else void Plotly.relayout(el, { 'shapes[0].y0': curseurZ, 'shapes[0].y1': curseurZ, 'shapes[0].visible': true })
  }, [curseurZ])

  useEffect(() => {
    enregistrerExport(() => {
      const el = hote.current
      if (el) void Plotly.downloadImage(el, { format: 'png', filename: `coupe_diagrammes_phase${phase + 1}`, scale: 2, width: 1600, height: 900 })
    })
    return () => enregistrerExport(null)
  }, [phase])

  useEffect(() => {
    const el = hote.current
    return () => { if (el) Plotly.purge(el) }
  }, [])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="barre-outils">
        <label><input type="checkbox" checked={enveloppe} onChange={(e) => setEnveloppe(e.target.checked)} /> Enveloppes toutes phases</label>
        <span className="espace" />
        <span className="legende-signes">y &gt; 0 vers la fouille · M &gt; 0 face fouille tendue · V = dM/dz · Maj+molette : zoom vertical, double-clic : rétablir</span>
      </div>
      <div style={{ flex: 1, position: 'relative', minHeight: 0 }}>
        {!ph.ok && <div className="alerte rouge" style={{ position: 'absolute', top: 8, left: 60, zIndex: 6 }}>{ph.message}</div>}
        <div ref={hote} className="figure-hote" />
        <div ref={infos} className="panneau-survol" />
      </div>
    </div>
  )
}
