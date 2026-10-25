import { nb } from '../../lib/format'
import { aretesContour, bandeSur, cadrage, etendueConcerne, type GeometrieP, type Point2 } from '../../lib/geometriePlan'

const COULEURS = { contour: 'var(--accent)', fouille: 'var(--accent-doux)', objet: '#b98a4a', zone: '#7a9a7a', appui: '#2e7d4f', surcharge: '#a32018', terrain: '#c9b28a' }

/** Dessin du plan : contour et côtés nommés (longueur), appuis en plan, objets de terrain sur leur tronçon, zones de
 *  fond, zones de terrain, surcharges positionnées (rectangle, point, tracé, bande le long d'un côté). */
export function PlanSvg({ g, surbrillance }: { g: GeometrieP; surbrillance?: string | null }) {
  const aretes = aretesContour(g.contour, g.ferme, g.cotes)
  const c = cadrage(g)
  const W = 640, H = 420
  const ech = Math.min(W / (c.xmax - c.xmin), H / (c.ymax - c.ymin))
  const X = (x: number) => (x - c.xmin) * ech
  const Y = (y: number) => H - (y - c.ymin) * ech
  const pts = (p: Point2[]) => p.map(([x, y]) => `${X(x).toFixed(1)},${Y(y).toFixed(1)}`).join(' ')
  const classe = (nom: string) => (surbrillance && surbrillance === nom ? 'surbrille' : '')
  if (g.contour.length < 2) {
    return <div className="note" style={{ padding: 10 }}>Donnez au moins deux sommets au contour (bloc ouvrages) pour dessiner le plan.</div>
  }
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ maxWidth: W, display: 'block', background: 'var(--panneau)', border: '1px solid var(--filet)', borderRadius: 2 }} role="img" aria-label="Plan des ouvrages">
      {/* quadrillage de 5 m */}
      {Array.from({ length: Math.floor((c.xmax - c.xmin) / 5) + 1 }, (_, i) => Math.ceil(c.xmin / 5) * 5 + 5 * i).map((x) => (
        <line key={`vx${x}`} x1={X(x)} y1={0} x2={X(x)} y2={H} stroke="var(--filet)" strokeWidth={0.5} />))}
      {Array.from({ length: Math.floor((c.ymax - c.ymin) / 5) + 1 }, (_, i) => Math.ceil(c.ymin / 5) * 5 + 5 * i).map((y) => (
        <line key={`hy${y}`} x1={0} y1={Y(y)} x2={W} y2={Y(y)} stroke="var(--filet)" strokeWidth={0.5} />))}
      {g.ferme && g.contour.length >= 3 && <polygon points={pts(g.contour)} fill={COULEURS.fouille} fillOpacity={0.5} stroke="none" />}
      {/* zones de fond */}
      {g.zonesFond.map((z) => {
        const poly = z.emprise && z.emprise.length >= 3 ? z.emprise : aretes.filter((a) => etendueConcerne(z.etendue, a)).slice(0, 1).flatMap((a) => bandeSur(a, z.etendue, z.largeur ?? Math.min(a.L, 6), 1))
        return poly.length >= 3 ? <polygon key={`zf${z.nom}`} className={classe(`zone:${z.nom}`)} points={pts(poly)} fill={COULEURS.zone} fillOpacity={0.45} stroke={COULEURS.zone} strokeDasharray="4 3"><title>zone de fond {z.nom}</title></polygon> : null
      })}
      {/* zones de terrain (côté terre) */}
      {g.zonesTerrain.map((z) => aretes.filter((a) => etendueConcerne(z.etendue, a)).map((a) => (
        <polygon key={`zt${z.nom}${a.k}`} className={classe(`terrain:${z.nom}`)} points={pts(bandeSur(a, z.etendue, 4, -1))} fill={COULEURS.terrain} fillOpacity={0.5} stroke={COULEURS.terrain}>
          <title>terrain {z.nom}{z.pente_beta ? ` : β = ${nb(z.pente_beta, 1)}°` : ''}{z.cote !== null ? ` : cote ${nb(z.cote, 2)} m` : ''}</title></polygon>)))}
      {/* objets de terrain côté fouille, sur leur tronçon */}
      {g.objets.map((o) => aretes.filter((a) => etendueConcerne(o.etendue, a)).map((a) => (
        <polygon key={`ob${o.nom}${a.k}`} className={classe(`objet:${o.nom}`)} points={pts(bandeSur(a, o.etendue, Math.max(o.largeur, 0.5), 1))} fill={COULEURS.objet} fillOpacity={0.6} stroke={COULEURS.objet}>
          <title>{o.type} {o.nom} (phases {o.phases.join(' à ')})</title></polygon>)))}
      {/* surcharges positionnées */}
      {g.positions.map((p, i) => {
        if (p.position && p.emprise) {
          const [x, y] = p.position, [lx, ly] = p.emprise
          return <rect key={`s${i}`} className={classe(`surcharge:${p.surcharge}`)} x={X(x - lx / 2)} y={Y(y + ly / 2)} width={lx * ech} height={ly * ech} fill={COULEURS.surcharge} fillOpacity={0.25} stroke={COULEURS.surcharge}><title>{p.surcharge}</title></rect>
        }
        if (p.position) return <circle key={`s${i}`} className={classe(`surcharge:${p.surcharge}`)} cx={X(p.position[0])} cy={Y(p.position[1])} r={5} fill={COULEURS.surcharge}><title>{p.surcharge}</title></circle>
        if (p.trace) return <line key={`s${i}`} className={classe(`surcharge:${p.surcharge}`)} x1={X(p.trace[0][0])} y1={Y(p.trace[0][1])} x2={X(p.trace[1][0])} y2={Y(p.trace[1][1])} stroke={COULEURS.surcharge} strokeWidth={3}><title>{p.surcharge}</title></line>
        return aretes.filter((a) => etendueConcerne(p.etendue, a)).map((a) => (
          <polygon key={`s${i}${a.k}`} className={classe(`surcharge:${p.surcharge}`)} points={pts(bandeSur(a, p.etendue, 3, -1))} fill={COULEURS.surcharge} fillOpacity={0.2} stroke={COULEURS.surcharge} strokeDasharray="3 2"><title>{p.surcharge} (côté {a.nom ?? a.k})</title></polygon>))
      })}
      {/* appuis en plan */}
      {g.appuis.map((ap, i) => (
        <g key={`ap${i}`} className={classe(`appui:${ap.appui}`)}>
          <line x1={X(ap.de[0])} y1={Y(ap.de[1])} x2={X(ap.a[0])} y2={Y(ap.a[1])} stroke={COULEURS.appui} strokeWidth={2.5} />
          <text x={X((ap.de[0] + ap.a[0]) / 2) + 4} y={Y((ap.de[1] + ap.a[1]) / 2) - 4} fontSize={11} fill={COULEURS.appui}>{ap.appui}</text>
        </g>))}
      {/* contour et côtés */}
      {g.ferme && g.contour.length >= 3
        ? <polygon points={pts(g.contour)} fill="none" stroke={COULEURS.contour} strokeWidth={3} />
        : <polyline points={pts(g.contour)} fill="none" stroke={COULEURS.contour} strokeWidth={3} />}
      {aretes.map((a) => {
        // nom du côté à l'extérieur du contour (18 px le long de la normale sortante), longueur empilée au-dessus
        // ou au-dessous selon le sens, pour ne jamais se chevaucher sur les côtés verticaux
        const mx = (a.A[0] + a.B[0]) / 2, my = (a.A[1] + a.B[1]) / 2
        const ox = -a.ni[0], oy = -a.ni[1]
        const tx = X(mx) + ox * 18, ty = Y(my) - oy * 18 + 4
        const dy = oy > 0.5 ? -12 : 12
        return (
          <g key={`ar${a.k}`} className={classe(`cote:${a.k}`)}>
            <text x={tx} y={ty} fontSize={11.5} fontWeight={600} textAnchor="middle" fill="var(--texte)">{a.nom ?? `côté ${a.k}`}</text>
            <text x={tx} y={ty + dy} fontSize={10} textAnchor="middle" fill="var(--texte-doux)">{nb(a.L, 1)} m</text>
          </g>)
      })}
      {g.contour.map(([x, y], i) => (
        <g key={`pt${i}`}><circle cx={X(x)} cy={Y(y)} r={3.5} fill="var(--panneau)" stroke={COULEURS.contour} strokeWidth={1.5} />
          <text x={X(x) + 6} y={Y(y) - 6} fontSize={9.5} fill="var(--texte-faible)">{i} ({nb(x, 1)} ; {nb(y, 1)})</text></g>))}
      <text x={8} y={H - 8} fontSize={10} fill="var(--texte-faible)">x vers la droite, y vers le haut (m) ; côté fouille à l'intérieur du contour</text>
    </svg>
  )
}
