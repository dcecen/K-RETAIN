import { useMemo } from 'react'
import { emprise, figures, nomVue, projeter, type Schema, type Vue } from '../lib/assemblages'

const COULEUR: Record<string, string> = { acier: '#7b8794', boulon: '#3b4653', beton: '#b8b0a2', bois: '#b07a43', sol: '#d8cdb4', soudure: '#c23' }

/** Dessin d'une vue d'assemblage au format plan d'exécution : coupes hachurées, cotes, symboles de soudure, repères, efforts. */
export function SchemaSvg({ schema, vue, params, reperes, hauteur = 420, compact = false, onRepere }: {
  schema: Schema
  vue: Vue
  params?: Set<string>          // paramètres survolés (surlignage des cotes et pièces)
  reperes?: Set<number>         // repères surlignés (clic sur une vérification)
  hauteur?: number
  compact?: boolean
  onRepere?: (r: number) => void
}) {
  const figs = useMemo(() => figures(schema, vue), [schema, vue])
  const box = useMemo(() => emprise(schema, vue), [schema, vue])
  const genre = nomVue(vue)
  const ech = Math.max(box.w / 900, box.h / hauteur, 0.2)   // unités (mm) par pixel
  const trait = 1.2 * ech
  const police = (compact ? 13 : 11) * ech
  const id = `h${Math.abs(Math.round(box.x + box.y + box.w))}`
  const actif = (s: { parametres: string[]; repere: number }) =>
    (params && s.parametres.some((p) => params.has(p))) || (reperes && reperes.has(s.repere))
  const repereDessine = new Set<number>()

  return (
    <svg viewBox={`${box.x} ${box.y} ${box.w} ${box.h}`} width="100%" height={hauteur} style={{ display: 'block', background: 'var(--panneau)' }}
      fontFamily="IBM Plex Mono, monospace" fontSize={police}>
      <defs>
        <pattern id={`${id}-acier`} patternUnits="userSpaceOnUse" width={6 * ech} height={6 * ech} patternTransform="rotate(45)">
          <line x1="0" y1="0" x2="0" y2={6 * ech} stroke="var(--texte)" strokeWidth={trait * 0.7} />
        </pattern>
        <pattern id={`${id}-beton`} patternUnits="userSpaceOnUse" width={14 * ech} height={14 * ech}>
          <circle cx={3 * ech} cy={4 * ech} r={1.1 * ech} fill="var(--texte-doux)" />
          <circle cx={10 * ech} cy={10 * ech} r={1.3 * ech} fill="var(--texte-doux)" />
          <line x1="0" y1={14 * ech} x2={14 * ech} y2="0" stroke="var(--texte-doux)" strokeWidth={trait * 0.5} />
        </pattern>
        <pattern id={`${id}-sol`} patternUnits="userSpaceOnUse" width={8 * ech} height={8 * ech} patternTransform="rotate(-45)">
          <line x1="0" y1="0" x2="0" y2={8 * ech} stroke="var(--texte-faible)" strokeWidth={trait * 0.5} strokeDasharray={`${2 * ech} ${2 * ech}`} />
        </pattern>
        <marker id={`${id}-fl`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth={6} markerHeight={6} orient="auto-start-reverse">
          <path d="M0 0 L10 5 L0 10 z" fill="var(--rouge)" />
        </marker>
        <marker id={`${id}-cote`} viewBox="0 0 10 10" refX="5" refY="5" markerWidth={5} markerHeight={5} orient="auto">
          <path d="M0 5 L10 0 L10 10 z" fill="var(--accent)" />
        </marker>
      </defs>
      {/* solides */}
      {figs.map((f, i) => {
        const s = f.solide
        const act = actif(s)
        const fill = f.coupe
          ? `url(#${id}-${s.materiau === 'beton' ? 'beton' : s.materiau === 'sol' ? 'sol' : 'acier'})`
          : s.materiau === 'beton' ? COULEUR.beton : s.materiau === 'sol' ? 'none' : s.materiau === 'boulon' ? COULEUR.boulon : 'var(--panneau-2)'
        const stroke = act ? 'var(--accent)' : s.materiau === 'sol' ? 'var(--texte-faible)' : 'var(--texte)'
        const sw = act ? trait * 2.2 : f.coupe ? trait * 1.6 : trait
        const props = { fill, stroke, strokeWidth: sw, opacity: s.materiau === 'beton' && !f.coupe ? 0.5 : 1,
          strokeDasharray: s.materiau === 'sol' ? `${4 * ech} ${3 * ech}` : undefined, style: { cursor: onRepere ? 'pointer' : undefined },
          onClick: () => onRepere?.(s.repere) }
        if (f.genre === 'cercle') return <circle key={i} cx={f.cx} cy={f.cy} r={f.r} {...props} />
        if (f.genre === 'poly') return <polygon key={i} points={f.pts.map((p) => `${p[0]},${p[1]}`).join(' ')} {...props} />
        return <rect key={i} x={f.x} y={f.y} width={f.w} height={f.h} {...props} />
      })}
      {/* surlignage des pièces actives : liseré accent */}
      {figs.filter((f) => actif(f.solide)).map((f, i) =>
        f.genre === 'cercle' ? <circle key={`a${i}`} cx={f.cx} cy={f.cy} r={f.r} fill="var(--accent)" opacity={0.18} />
          : f.genre === 'poly' ? <polygon key={`a${i}`} points={f.pts.map((p) => `${p[0]},${p[1]}`).join(' ')} fill="var(--accent)" opacity={0.18} />
            : <rect key={`a${i}`} x={f.x} y={f.y} width={f.w} height={f.h} fill="var(--accent)" opacity={0.18} />)}
      {/* soudures : symbole ISO 2553 (ligne de repère, flèche, triangle = angle, demi-V = pénétration) */}
      {!compact && schema.soudures.map((w, i) => {
        const a = projeter(w.p1, vue.plan), b = projeter(w.p2, vue.plan)
        if (Math.abs(a.X - b.X) < 1e-6 && Math.abs(a.Y - b.Y) < 1e-6 && vue.plan !== 'xz') return null
        const mx = (a.X + b.X) / 2, my = (a.Y + b.Y) / 2
        const L = 55 * ech, act = (params && w.parametre && params.has(w.parametre)) || (reperes && w.reperes.some((r) => reperes.has(r)))
        const col = act ? 'var(--accent)' : 'var(--rouge)'
        return (
          <g key={`w${i}`} stroke={col} fill="none" strokeWidth={trait}>
            <line x1={a.X} y1={a.Y} x2={b.X} y2={b.Y} strokeWidth={trait * 2.5} opacity={0.6} />
            <line x1={mx} y1={my} x2={mx + L} y2={my - L} />
            <line x1={mx + L} y1={my - L} x2={mx + L + 2.2 * L} y2={my - L} />
            {w.type === 'angle'
              ? <path d={`M${mx + L + 0.5 * L} ${my - L} l0 ${-0.55 * L} l${0.55 * L} ${0.55 * L} z`} fill={col} />
              : <path d={`M${mx + L + 0.5 * L} ${my - L} l${0.55 * L} ${-0.6 * L} l0 ${0.6 * L} z`} />}
            {w.contour && <circle cx={mx + L} cy={my - L} r={0.25 * L} />}
            <text x={mx + L + 1.25 * L} y={my - L - 0.12 * L} fill={col} stroke="none" fontSize={police * 1.05}>a{w.a}</text>
          </g>
        )
      })}
      {/* repères de nomenclature */}
      {!compact && figs.map((f, i) => {
        const s = f.solide
        if (s.masque || repereDessine.has(s.repere) || f.coupe === false && figs.some((g) => g.solide.repere === s.repere && g.coupe)) return null
        repereDessine.add(s.repere)
        const c = f.genre === 'cercle' ? [f.cx, f.cy] : f.genre === 'poly' ? [f.pts.reduce((t, p) => t + p[0], 0) / f.pts.length, f.pts.reduce((t, p) => t + p[1], 0) / f.pts.length] : [f.x + f.w / 2, f.y + f.h / 2]
        const r = 11 * ech
        const act = actif(s)
        return (
          <g key={`r${i}`} style={{ cursor: 'pointer' }} onClick={() => onRepere?.(s.repere)}>
            <circle cx={c[0]} cy={c[1]} r={r} fill={act ? 'var(--accent)' : 'var(--panneau)'} stroke="var(--texte)" strokeWidth={trait} />
            <text x={c[0]} y={c[1] + police * 0.38} textAnchor="middle" fontSize={police * 1.1} fontWeight={600} fill={act ? 'var(--accent-texte)' : 'var(--texte)'}>{s.repere}</text>
          </g>
        )
      })}
      {/* cotes */}
      {!compact && schema.cotes.filter((c) => c.vue === genre).map((c, i) => {
        const a = projeter(c.p1, vue.plan), b = projeter(c.p2, vue.plan)
        const horiz = Math.abs(b.Y - a.Y) <= Math.abs(b.X - a.X)
        const d = c.decalage
        const act = params && c.parametre && params.has(c.parametre)
        const col = act ? 'var(--accent)' : 'var(--texte-doux)'
        const [ax, ay, bx, by] = horiz ? [a.X, a.Y + d, b.X, b.Y + d] : [a.X + d, a.Y, b.X + d, b.Y]
        return (
          <g key={`c${i}`} stroke={col} strokeWidth={act ? trait * 1.8 : trait * 0.8} fill="none">
            <line x1={a.X} y1={a.Y} x2={ax} y2={ay} opacity={0.6} />
            <line x1={b.X} y1={b.Y} x2={bx} y2={by} opacity={0.6} />
            <line x1={ax} y1={ay} x2={bx} y2={by} markerStart={`url(#${id}-cote)`} markerEnd={`url(#${id}-cote)`} />
            <text x={(ax + bx) / 2 + (horiz ? 0 : 6 * ech)} y={(ay + by) / 2 - (horiz ? 5 * ech : 0)} textAnchor={horiz ? 'middle' : 'start'} fill={col}
              stroke="none" fontSize={police * (act ? 1.15 : 1)} fontWeight={act ? 600 : 400} transform={horiz ? undefined : `rotate(-90 ${(ax + bx) / 2 + 6 * ech} ${(ay + by) / 2})`}>{c.texte}</text>
          </g>
        )
      })}
      {/* efforts */}
      {schema.efforts.map((e, i) => {
        const p = projeter(e.point, vue.plan)
        const d = projeter([e.point[0] + e.direction[0], e.point[1] + e.direction[1], e.point[2] + e.direction[2]], vue.plan)
        const dx = d.X - p.X, dy = d.Y - p.Y
        const n = Math.hypot(dx, dy)
        if (n < 1e-6) return null
        const L = (compact ? 90 : 140) * ech
        return (
          <g key={`e${i}`}>
            <line x1={p.X} y1={p.Y} x2={p.X + (dx / n) * L} y2={p.Y + (dy / n) * L} stroke="var(--rouge)" strokeWidth={trait * 2} markerEnd={`url(#${id}-fl)`} />
            {!compact && e.texte && <text x={p.X + 8 * ech} y={p.Y - 8 * ech} fill="var(--rouge)" fontSize={police * 1.15} fontWeight={600}>{e.texte}</text>}
          </g>
        )
      })}
      {!compact && <text x={box.x + 12 * ech} y={box.y + 20 * ech} fontSize={police * 1.25} fontWeight={600} fill="var(--texte)" fontFamily="IBM Plex Sans, sans-serif">{vue.nom}</text>}
      {!compact && vue.coupe && (() => {
        // trace du plan de coupe sur les autres vues : indiqué par la légende A-A (le plan est perpendiculaire à cette vue)
        return <text x={box.x + 12 * ech} y={box.y + 36 * ech} fontSize={police} fill="var(--texte-doux)" fontFamily="IBM Plex Sans, sans-serif">plan de coupe {vue.coupe.axe} = {vue.coupe.pos.toFixed(0)} mm, hachures = pièces coupées</text>
      })()}
    </svg>
  )
}
