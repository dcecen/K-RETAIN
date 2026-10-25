// Schémas SVG des fiches de vérification : fonctions pures (données du schéma renvoyées par le serveur -> texte SVG),
// sans DOM ni three.js, réutilisées telles quelles par la note de calcul (HTML autonome : les couleurs ont un repli).
// Conventions : écran en x = 0, côté terre à gauche (x < 0), fouille à droite ; z vers le haut (m).
import { nb } from '../../lib/format'

export type Schema = { type: string } & Record<string, unknown>

/** Nombre d'une fiche affiché avec un nombre de décimales adapté à sa grandeur (texte rendu tel quel). */
export function valeurFiche(v: unknown): string {
  if (v === null || v === undefined) return '—'
  if (typeof v !== 'number') return String(v)
  const a = Math.abs(v)
  return nb(v, a >= 100 ? 0 : a >= 10 ? 1 : a >= 1 ? 2 : 3)
}

export const LARGEUR = 440
export const HAUTEUR = 260
const C = {
  texte: 'var(--texte, #1b2330)', doux: 'var(--texte-doux, #5a6475)', filet: 'var(--filet-fort, #c6cdd8)',
  terre: '#d8c9a3', terreTrait: '#8b6b3e', eau: '#3b8fd9', ecran: '#3d4a5c', accent: '#1f4e79', accentDoux: '#9bb7d6',
  rouge: '#a32018', vert: '#2e7d4f', orange: '#b8860b',
}
const POLICE = 'Segoe UI, Arial, sans-serif'

export const f = (v: number, d = 1) => (Number.isFinite(v) ? v.toLocaleString('fr-FR', { minimumFractionDigits: d, maximumFractionDigits: d }) : '—')
const num = (v: unknown, defaut = 0): number => (typeof v === 'number' && Number.isFinite(v) ? v : defaut)
const opt = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null)
const esc = (s: string) => s.replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' })[c]!)
const r1 = (v: number) => (Math.round(v * 10) / 10).toString()

function texte(x: number, y: number, s: string, o: { ancre?: 'start' | 'middle' | 'end'; taille?: number; couleur?: string; gras?: boolean } = {}): string {
  return `<text x="${r1(x)}" y="${r1(y)}" font-size="${o.taille ?? 11}" fill="${o.couleur ?? C.texte}" text-anchor="${o.ancre ?? 'start'}"${o.gras ? ' font-weight="600"' : ''} font-family="${POLICE}">${esc(s)}</text>`
}

function fleche(x1: number, y1: number, x2: number, y2: number, couleur: string, epaisseur = 1.6): string {
  const dx = x2 - x1, dy = y2 - y1
  const L = Math.hypot(dx, dy) || 1
  const ux = dx / L, uy = dy / L
  const t = 6
  const ax = x2 - ux * t, ay = y2 - uy * t
  return `<line x1="${r1(x1)}" y1="${r1(y1)}" x2="${r1(x2)}" y2="${r1(y2)}" stroke="${couleur}" stroke-width="${epaisseur}" />`
    + `<polygon points="${r1(x2)},${r1(y2)} ${r1(ax - uy * 3.5)},${r1(ay + ux * 3.5)} ${r1(ax + uy * 3.5)},${r1(ay - ux * 3.5)}" fill="${couleur}" />`
}

export interface Cadre { x: (m: number) => number; z: (m: number) => number; xmin: number; xmax: number; zmin: number; zmax: number; H: number }

/** Repère de la coupe : x (m, écran en 0, amont négatif) et z (m, vers le haut) -> pixels ; marges pour les cotes. */
export function cadre(xmin: number, xmax: number, zmin: number, zmax: number): Cadre {
  const m = { g: 46, d: 14, h: 16, b: 20 }
  const sx = (LARGEUR - m.g - m.d) / Math.max(xmax - xmin, 1e-9)
  const sz = (HAUTEUR - m.h - m.b) / Math.max(zmax - zmin, 1e-9)
  return { x: (v) => m.g + (v - xmin) * sx, z: (v) => HAUTEUR - m.b - (v - zmin) * sz, xmin, xmax, zmin, zmax, H: zmax - zmin }
}

interface Geo { tete: number; pied: number; terrain: number; fond: number; nappe_amont?: number | null; nappe_aval?: number | null }

/** Fond de coupe : sol côté terre jusqu'au terrain, sol côté fouille jusqu'au fond, nappes, écran et cotes. */
function fondCoupe(k: Cadre, g: Geo): string {
  const xg = k.x(k.xmin), xd = k.x(k.xmax), bas = k.z(k.zmin), x0 = k.x(0)
  const out: string[] = []
  out.push(`<rect x="${r1(xg)}" y="${r1(k.z(g.terrain))}" width="${r1(x0 - xg)}" height="${r1(bas - k.z(g.terrain))}" fill="${C.terre}" />`)
  out.push(`<rect x="${r1(x0)}" y="${r1(k.z(g.fond))}" width="${r1(xd - x0)}" height="${r1(bas - k.z(g.fond))}" fill="${C.terre}" />`)
  out.push(`<line x1="${r1(xg)}" y1="${r1(k.z(g.terrain))}" x2="${r1(x0)}" y2="${r1(k.z(g.terrain))}" stroke="${C.terreTrait}" stroke-width="1.2" />`)
  out.push(`<line x1="${r1(x0)}" y1="${r1(k.z(g.fond))}" x2="${r1(xd)}" y2="${r1(k.z(g.fond))}" stroke="${C.terreTrait}" stroke-width="1.2" />`)
  const na = opt(g.nappe_amont), nv = opt(g.nappe_aval)
  if (na !== null) {
    out.push(`<line x1="${r1(xg)}" y1="${r1(k.z(na))}" x2="${r1(x0)}" y2="${r1(k.z(na))}" stroke="${C.eau}" stroke-width="1.4" stroke-dasharray="6 3" />`)
    out.push(texte(xg + 3, k.z(na) - 3, `nappe ${f(na, 2)}`, { taille: 9.5, couleur: C.eau }))
  }
  if (nv !== null) {
    out.push(`<line x1="${r1(x0)}" y1="${r1(k.z(nv))}" x2="${r1(xd)}" y2="${r1(k.z(nv))}" stroke="${C.eau}" stroke-width="1.4" stroke-dasharray="6 3" />`)
    out.push(texte(xd - 3, k.z(nv) - 3, `nappe ${f(nv, 2)}`, { taille: 9.5, couleur: C.eau, ancre: 'end' }))
  }
  out.push(`<rect x="${r1(x0 - 3)}" y="${r1(k.z(g.tete))}" width="6" height="${r1(k.z(g.pied) - k.z(g.tete))}" fill="${C.ecran}" />`)
  out.push(texte(x0 + 7, k.z(g.tete) + 4, `tête ${f(g.tete, 2)} m`, { taille: 9.5, couleur: C.doux }))
  out.push(texte(x0 + 7, k.z(g.pied) + 11, `pied ${f(g.pied, 2)} m`, { taille: 9.5, couleur: C.doux }))
  out.push(texte(xd - 3, k.z(g.fond) - 3, `fond ${f(g.fond, 2)} m`, { taille: 9.5, couleur: C.doux, ancre: 'end' }))
  out.push(texte(xg + 3, k.z(g.terrain) - 3, `terrain ${f(g.terrain, 2)} m`, { taille: 9.5, couleur: C.doux }))
  return out.join('')
}

const enveloppe = (corps: string, titre: string) =>
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${LARGEUR} ${HAUTEUR}" width="${LARGEUR}" height="${HAUTEUR}" role="img" aria-label="${esc(titre)}" class="schema-verif">`
  + texte(6, 12, titre, { taille: 11, gras: true }) + corps + '</svg>'

// ------------------------------------------------------------------ schémas par type
function butee(s: Schema): string {
  const z = s.z as number[], p = s.p as number[], pp = s.pp as number[]
  const fond = num(s.fond), pied = num(s.pied, Math.min(...z))
  const D = Math.max(fond - pied, 1)
  const tete = num(s.tete, fond + 0.9 * D), terrain = num(s.terrain_amont, tete)
  const H = Math.max(Math.max(tete, terrain) - pied, D)
  const k = cadre(-0.6 * H, 1.4 * H, pied - 0.12 * H, Math.max(tete, terrain) + 0.1 * H)
  const geo: Geo = { tete, pied, terrain, fond, nappe_amont: opt(s.nappe_amont), nappe_aval: opt(s.nappe_aval) }
  const ech = (0.9 * H) / Math.max(...pp, 1e-9)            // pression maximale limite = 0,9 H à l'écran
  const pts = (v: number[]) => z.map((zz, i) => `${r1(k.x(v[i] * ech))},${r1(k.z(zz))}`)
  const corps = fondCoupe(k, geo)
    + `<polygon points="${r1(k.x(0))},${r1(k.z(z[0]))} ${pts(p).join(' ')} ${r1(k.x(0))},${r1(k.z(z[z.length - 1]))}" fill="${C.accent}" fill-opacity="0.45" stroke="${C.accent}" stroke-width="1" />`
    + `<polyline points="${pts(pp).join(' ')}" fill="none" stroke="${C.rouge}" stroke-width="1.6" stroke-dasharray="5 3" />`
    + texte(k.x(0.35 * H), k.z(fond) + 14, 'Bm : pressions mobilisées (plein)', { taille: 10, couleur: C.accent })
    + texte(k.x(0.35 * H), k.z(fond) + 27, 'Bt : pressions limites (pointillé)', { taille: 10, couleur: C.rouge })
  return enveloppe(corps, `Butée sous le fond de fouille, phase « ${String(s.phase ?? '')} »`)
}

function kranz(s: Schema): string {
  const B = s.B as number[], A = s.A as number[]
  const tete = num(s.tete), pied = num(s.pied), terrain = num(s.terrain_amont, tete), fond = num(s.fond, tete)
  const xA = A[0], zA = A[1], zB = B[1]
  const H = Math.max(tete - pied, 1)
  const k = cadre(Math.min(xA * 1.25, -0.5 * H), 0.5 * H, pied - 0.1 * H, Math.max(tete, terrain) + 0.12 * H)
  const geo: Geo = { tete, pied, terrain, fond, nappe_amont: opt(s.nappe_amont) }
  const cote = num(s.cote_tirant), ang = (num(s.angle) * Math.PI) / 180
  const Ll = num(s.longueur_libre), Ls = num(s.longueur_scellee)
  const dir = [-Math.cos(ang), -Math.sin(ang)]
  const P1 = [0, cote], Pl = [dir[0] * Ll, cote + dir[1] * Ll], Ps = [dir[0] * (Ll + Ls), cote + dir[1] * (Ll + Ls)]
  const fo = s.forces as Record<string, number>
  const gx = (xA + 0) / 2 + xA / 4, gz = (terrain + zB + zA + terrain) / 4
  const corps = fondCoupe(k, geo)
    + `<polygon points="${r1(k.x(0))},${r1(k.z(terrain))} ${r1(k.x(0))},${r1(k.z(zB))} ${r1(k.x(xA))},${r1(k.z(zA))} ${r1(k.x(xA))},${r1(k.z(terrain))}" fill="${C.accentDoux}" fill-opacity="0.55" stroke="${C.accent}" stroke-width="1.2" />`
    + `<line x1="${r1(k.x(P1[0]))}" y1="${r1(k.z(P1[1]))}" x2="${r1(k.x(Pl[0]))}" y2="${r1(k.z(Pl[1]))}" stroke="${C.ecran}" stroke-width="1.5" />`
    + `<line x1="${r1(k.x(Pl[0]))}" y1="${r1(k.z(Pl[1]))}" x2="${r1(k.x(Ps[0]))}" y2="${r1(k.z(Ps[1]))}" stroke="${C.ecran}" stroke-width="5" stroke-linecap="round" />`
    + `<circle cx="${r1(k.x(xA))}" cy="${r1(k.z(zA))}" r="3.5" fill="${C.rouge}" />` + texte(k.x(xA) - 6, k.z(zA) - 6, 'A', { gras: true, ancre: 'end' })
    + `<circle cx="${r1(k.x(0))}" cy="${r1(k.z(zB))}" r="3.5" fill="${C.rouge}" />` + texte(k.x(0) + 8, k.z(zB) + 4, 'B', { gras: true })
    + fleche(k.x(gx), k.z(gz) - 10, k.x(gx), k.z(gz) + 22, C.texte) + texte(k.x(gx) + 5, k.z(gz) + 12, `W = ${f(fo.W, 0)} kN/m`, { taille: 10 })
    + fleche(k.x(xA) - 36, k.z((terrain + zA) / 2), k.x(xA) - 4, k.z((terrain + zA) / 2), C.accent) + texte(k.x(xA) - 38, k.z((terrain + zA) / 2) - 5, `P1 = ${f(fo.P1, 0)}`, { taille: 10, ancre: 'end', couleur: C.accent })
    + fleche(k.x(Pl[0]), k.z(Pl[1]) - 16, k.x(P1[0]) - 8, k.z(P1[1]) - 16, C.vert) + texte(k.x(Pl[0]) + 4, k.z(Pl[1]) - 20, `T = ${f(fo.T, 0)} kN/m (T_max ${f(fo.T_max, 0)})`, { taille: 10, couleur: C.vert })
    + texte(k.x(xA / 2) - 10, k.z((zA + zB) / 2) + 16, `R = ${f(fo.R, 0)} kN/m (sur BA)`, { taille: 10, couleur: C.orange })
  return enveloppe(corps, `Massif d'ancrage O-B-A-A', phase « ${String(s.phase ?? '')} »`)
}

function fondDeFouille(s: Schema): string {
  const fond = num(s.fond), pied = num(s.pied), terrain = num(s.terrain_amont, fond + 1)
  const na = num(s.nappe_amont, terrain), nv = num(s.nappe_aval, fond)
  const tete = Math.max(terrain, na)
  const H = Math.max(tete - pied, 1)
  const k = cadre(-0.9 * H, 0.9 * H, pied - 0.12 * H, tete + 0.12 * H)
  const geo: Geo = { tete, pied, terrain, fond, nappe_amont: na, nappe_aval: nv }
  const xg = k.x(-0.08 * H), xd = k.x(0.08 * H)
  const corps = fondCoupe(k, geo)
    + fleche(xg, k.z(Math.min(na, terrain)) + 4, xg, k.z(pied) - 6, C.eau, 2) + fleche(xd, k.z(pied) - 2, xd, k.z(Math.min(fond, nv)) + 4, C.eau, 2)
    + texte(xg - 8, k.z((Math.min(na, terrain) + pied) / 2), `L_amont = ${f(num(s.L_amont), 2)} m`, { taille: 10, ancre: 'end', couleur: C.eau })
    + texte(xd + 8, k.z((fond + pied) / 2), `L_aval = ${f(num(s.L_aval), 2)} m`, { taille: 10, couleur: C.eau })
    + texte(k.x(0.3 * H), k.z(tete) + 14, `Δh = ${f(num(s.dh), 2)} m, dont ${f(num(s.dh_aval), 2)} m côté fouille`, { taille: 10 })
  return enveloppe(corps, `Cheminement de l'eau autour de l'écran, phase « ${String(s.phase ?? '')} »`)
}

function cercle(s: Schema): string {
  const xc = num(s.xc), zc = num(s.zc), R = num(s.R, 1)
  const tete = num(s.tete), pied = num(s.pied), terrain = num(s.z_amont, tete), fond = num(s.z_aval, tete - 1)
  const largeur = num(s.largeur, 2 * (tete - pied))
  const H = Math.max(tete - pied, 1)
  const xmin = Math.min(xc - R, -H) - 0.1 * H, xmax = Math.max(largeur, xc + R) + 0.1 * H
  const zmin = Math.min(pied, zc - R) - 0.1 * H, zmax = Math.max(terrain, zc) + 0.1 * H
  const k = cadre(xmin, xmax, zmin, zmax)
  const geo: Geo = { tete, pied, terrain, fond, nappe_amont: opt(s.nappe_amont), nappe_aval: opt(s.nappe_aval) }
  const rx = k.x(xc + R) - k.x(xc), ry = k.z(zc) - k.z(zc + R)
  const cd = s.cercle_calcul as number[] | null | undefined
  const corps = fondCoupe(k, geo)
    + `<rect x="${r1(k.x(largeur))}" y="${r1(k.z(fond))}" width="${r1(k.x(k.xmax) - k.x(largeur))}" height="${r1(k.z(k.zmin) - k.z(fond))}" fill="${C.terre}" />`
    + `<ellipse cx="${r1(k.x(xc))}" cy="${r1(k.z(zc))}" rx="${r1(rx)}" ry="${r1(ry)}" fill="none" stroke="${C.rouge}" stroke-width="1.8" stroke-dasharray="7 4" />`
    + (cd ? `<ellipse cx="${r1(k.x(cd[0]))}" cy="${r1(k.z(cd[1]))}" rx="${r1(k.x(cd[0] + cd[2]) - k.x(cd[0]))}" ry="${r1(k.z(cd[1]) - k.z(cd[1] + cd[2]))}" fill="none" stroke="${C.orange}" stroke-width="1.2" stroke-dasharray="3 3" />` : '')
    + `<line x1="${r1(k.x(xc) - 5)}" y1="${r1(k.z(zc))}" x2="${r1(k.x(xc) + 5)}" y2="${r1(k.z(zc))}" stroke="${C.rouge}" /><line x1="${r1(k.x(xc))}" y1="${r1(k.z(zc) - 5)}" x2="${r1(k.x(xc))}" y2="${r1(k.z(zc) + 5)}" stroke="${C.rouge}" />`
    + texte(k.x(xc) + 7, k.z(zc) - 6, `centre (${f(xc, 1)} ; ${f(zc, 1)}), R = ${f(R, 1)} m, F = ${f(num(s.F), 2)}`, { taille: 10, couleur: C.rouge })
    + (cd ? texte(k.x(xc) + 7, k.z(zc) + 12, 'cercle pondéré (orange)', { taille: 9.5, couleur: C.orange }) : '')
  return enveloppe(corps, `Cercle de glissement critique (Bishop), phase « ${String(s.phase ?? '')} »`)
}

function profil(s: Schema): string {
  const z = s.z as number[], y = s.y_mm as number[]
  const tete = num(s.tete, Math.max(...z)), pied = num(s.pied, Math.min(...z))
  const H = Math.max(tete - pied, 1)
  const lim = opt(s.limite_mm)
  const ymax = Math.max(...y.map(Math.abs), lim ?? 0, 1e-9)
  const ech = (0.7 * H) / ymax
  const k = cadre(-0.9 * H, 0.9 * H, pied - 0.1 * H, tete + 0.12 * H)
  const geo: Geo = { tete, pied, terrain: tete, fond: tete }
  const pts = z.map((zz, i) => `${r1(k.x(y[i] * ech))},${r1(k.z(zz))}`).join(' ')
  const corps = `<rect x="${r1(k.x(0) - 3)}" y="${r1(k.z(tete))}" width="6" height="${r1(k.z(pied) - k.z(tete))}" fill="${C.ecran}" fill-opacity="0.35" />`
    + texte(k.x(0) + 7, k.z(geo.tete) + 4, `tête ${f(tete, 2)} m`, { taille: 9.5, couleur: C.doux }) + texte(k.x(0) + 7, k.z(pied) + 11, `pied ${f(pied, 2)} m`, { taille: 9.5, couleur: C.doux })
    + `<polyline points="${pts}" fill="none" stroke="${C.accent}" stroke-width="2" />`
    + (lim !== null ? `<line x1="${r1(k.x(lim * ech))}" y1="${r1(k.z(tete))}" x2="${r1(k.x(lim * ech))}" y2="${r1(k.z(pied))}" stroke="${C.rouge}" stroke-dasharray="5 3" />`
      + `<line x1="${r1(k.x(-lim * ech))}" y1="${r1(k.z(tete))}" x2="${r1(k.x(-lim * ech))}" y2="${r1(k.z(pied))}" stroke="${C.rouge}" stroke-dasharray="5 3" />`
      + texte(k.x(lim * ech) + 4, k.z(tete) + 14, `admissible ${f(lim, 0)} mm`, { taille: 10, couleur: C.rouge }) : '')
    + texte(k.x(0.2 * H), k.z(pied) + 11, `déplacement (mm, positif vers la fouille) ; |y| max = ${f(ymax, 1)} mm`, { taille: 10, couleur: C.accent, ancre: 'middle' })
  return enveloppe(corps, `Déplacement ${String(s.quoi ?? '')} de l'écran, phase « ${String(s.phase ?? '')} »`)
}

/** Paroi circulaire : anneau en plan (rayon, pression reprise) et profil de l'effort normal circonférentiel N_θ(z). */
function anneau(s: Schema): string {
  const z = s.z as number[], N = s.N as number[]
  const R = num(s.R), t = num(s.t)
  const tete = Math.max(...z), pied = Math.min(...z)
  const H = Math.max(tete - pied, 1)
  const Nmax = Math.max(...N.map(Math.abs), opt(s.N_Rd) ?? 0, 1e-9)
  // plan : cercle de rayon fixe à l'écran (le rayon réel est écrit), flèches de pression vers l'axe
  const cx = 95, cy = 125, rr = 58
  const fleches = Array.from({ length: 8 }, (_, i) => {
    const a = (i * Math.PI) / 4, x1 = cx + (rr + 24) * Math.cos(a), y1 = cy + (rr + 24) * Math.sin(a), x2 = cx + (rr + 6) * Math.cos(a), y2 = cy + (rr + 6) * Math.sin(a)
    return `<line x1="${r1(x1)}" y1="${r1(y1)}" x2="${r1(x2)}" y2="${r1(y2)}" stroke="${C.orange}" stroke-width="1.6" marker-end="url(#fl)" />`
  }).join('')
  const plan = `<defs><marker id="fl" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="${C.orange}" /></marker></defs>`
    + `<circle cx="${cx}" cy="${cy}" r="${rr}" fill="none" stroke="${C.ecran}" stroke-width="${Math.max(3, Math.min(14, (t / Math.max(R, 1e-9)) * rr * 4))}" stroke-opacity="0.6" />`
    + `<line x1="${cx}" y1="${cy}" x2="${cx + rr}" y2="${cy}" stroke="${C.doux}" stroke-dasharray="3 3" />`
    + texte(cx + rr / 2, cy - 6, `R = ${f(R, 2)} m`, { ancre: 'middle', taille: 10.5 })
    + texte(cx, cy + rr + 42, `anneau t = ${f(t, 3)} m, comprimé`, { ancre: 'middle', taille: 10, couleur: C.doux }) + fleches
  // profil N_θ(z) à droite
  const x0 = 225, larg = 175, y0 = 34, haut = 186
  const X = (v: number) => x0 + (v / Nmax) * larg
  const Y = (zz: number) => y0 + ((tete - zz) / H) * haut
  const pts = z.map((zz, i) => `${r1(X(N[i]))},${r1(Y(zz))}`).join(' ')
  const NRd = opt(s.N_Rd)
  const profilN = `<line x1="${x0}" y1="${y0}" x2="${x0}" y2="${y0 + haut}" stroke="${C.filet}" />`
    + `<polyline points="${pts}" fill="none" stroke="${C.accent}" stroke-width="2" />`
    + (NRd !== null ? `<line x1="${r1(X(NRd))}" y1="${y0}" x2="${r1(X(NRd))}" y2="${y0 + haut}" stroke="${C.rouge}" stroke-dasharray="5 3" />`
      + texte(X(NRd) - 4, y0 + 12, `N_Rd = ${f(NRd, 0)}`, { ancre: 'end', taille: 10, couleur: C.rouge }) : '')
    + texte(x0 + 4, y0 - 6, `tête ${f(tete, 2)} m`, { taille: 9.5, couleur: C.doux }) + texte(x0 + 4, y0 + haut + 14, `pied ${f(pied, 2)} m`, { taille: 9.5, couleur: C.doux })
    + texte(x0 + larg / 2, y0 + haut + 30, `N_θ (kN/m, compression > 0) ; max ${f(Math.max(...N), 0)} kN/m`, { ancre: 'middle', taille: 10, couleur: C.accent })
  return enveloppe(plan + profilN, `Anneau comprimé de la paroi circulaire, phase « ${String(s.phase ?? '')} »`)
}

function forcesVerticales(s: Schema): string {
  const m = num(s.montants), d = num(s.descendants)
  const vmax = Math.max(m, d, 1e-9)
  const ech = 150 / vmax
  const x0 = 120, y0 = 200
  const barre = (x: number, v: number, couleur: string, lib: string) =>
    `<rect x="${x}" y="${r1(y0 - v * ech)}" width="70" height="${r1(v * ech)}" fill="${couleur}" fill-opacity="0.7" />`
    + texte(x + 35, y0 - v * ech - 6, `${f(v, 0)} kN/m`, { ancre: 'middle', taille: 10.5, gras: true }) + texte(x + 35, y0 + 16, lib, { ancre: 'middle', taille: 10.5 })
  const corps = `<line x1="60" y1="${y0}" x2="${LARGEUR - 40}" y2="${y0}" stroke="${C.filet}" />`
    + barre(x0, d, C.accent, 'efforts descendants') + barre(x0 + 130, m, C.orange, 'efforts montants')
    + texte(x0 + 100, 40, `montants / descendants = ${f(d > 0 ? m / d : 0, 3)}`, { ancre: 'middle', taille: 10.5 })
  return enveloppe(corps, `Bilan des efforts verticaux, phase « ${String(s.phase ?? '')} »`)
}

function barre(s: Schema): string {
  const L = num(s.L, 1), ang = (num(s.angle) * Math.PI) / 180
  const x1 = 70, x2 = LARGEUR - 70, y = 130
  const dy = Math.tan(ang) * (x2 - x1) * 0.25
  const corps = `<line x1="${x1}" y1="${r1(y + dy / 2)}" x2="${x2}" y2="${r1(y - dy / 2)}" stroke="${C.ecran}" stroke-width="8" stroke-linecap="round" />`
    + `<circle cx="${x1}" cy="${r1(y + dy / 2)}" r="5" fill="${C.texte}" /><circle cx="${x2}" cy="${r1(y - dy / 2)}" r="5" fill="${C.texte}" />`
    + fleche(x1 - 46, y + dy / 2, x1 - 10, y + dy / 2, C.rouge, 2) + fleche(x2 + 46, y - dy / 2, x2 + 10, y - dy / 2, C.rouge, 2)
    + texte(x1 - 46, y + dy / 2 - 10, `N_Ed = ${f(num(s.N_Ed), 0)} kN`, { taille: 10.5, couleur: C.rouge })
    + `<line x1="${x1}" y1="${y + 40}" x2="${x2}" y2="${y + 40}" stroke="${C.filet}" /><line x1="${x1}" y1="${y + 34}" x2="${x1}" y2="${y + 46}" stroke="${C.filet}" /><line x1="${x2}" y1="${y + 34}" x2="${x2}" y2="${y + 46}" stroke="${C.filet}" />`
    + texte((x1 + x2) / 2, y + 56, `L = ${f(L, 2)} m (bi-articulée), ${String(s.ref ?? '')}`, { ancre: 'middle', taille: 10.5 })
    + texte((x1 + x2) / 2, y + 84, `N_cr = ${f(num(s.N_cr), 0)} kN ; λ̄ = ${f(num(s.lambda), 3)} ; χ = ${f(num(s.chi), 3)} ; N_b,Rd = ${f(num(s.N_b_Rd), 0)} kN`, { ancre: 'middle', taille: 10.5 })
    + texte((x1 + x2) / 2, y + 102, `N_Ed / N_b,Rd = ${f(num(s.N_Ed) / Math.max(num(s.N_b_Rd), 1e-9), 3)}`, { ancre: 'middle', taille: 10.5, gras: true })
  return enveloppe(corps, 'Barre comprimée : flambement (EN 1993-1-1 § 6.3.1)')
}

function sectionBeton(s: Schema): string {
  const h = num(s.h, 0.5), d = num(s.d, h - 0.07)
  const ech = 160 / h
  const x = 150, y = 50, hp = h * ech
  const face = String(s.face ?? '')
  const As = opt(s.As), MR = opt(s.M_Rd)
  const corps = `<rect x="${x}" y="${y}" width="140" height="${r1(hp)}" fill="${C.terre}" stroke="${C.terreTrait}" />`
    + `<line x1="${x}" y1="${r1(y + d * ech)}" x2="${x + 140}" y2="${r1(y + d * ech)}" stroke="${C.rouge}" stroke-width="2" stroke-dasharray="2 4" />`
    + texte(x + 146, y + d * ech + 4, `As ${As !== null ? f(As, 1) + ' cm²/m' : 'non fourni'} (${face})`, { taille: 10, couleur: C.rouge })
    + texte(x + 146, y + 10, `As requis ${f(num(s.As_requis), 1)} cm²/m`, { taille: 10 })
    + `<line x1="${x - 18}" y1="${y}" x2="${x - 18}" y2="${r1(y + hp)}" stroke="${C.filet}" />` + texte(x - 24, y + hp / 2, `e = ${f(h, 2)} m`, { ancre: 'end', taille: 10 })
    + `<line x1="${x - 6}" y1="${y}" x2="${x - 6}" y2="${r1(y + d * ech)}" stroke="${C.filet}" />` + texte(x - 10, y + 14, `d = ${f(d, 3)} m`, { ancre: 'end', taille: 10 })
    + texte(x + 70, y + hp + 18, `M_Ed = ${f(num(s.M_Ed), 0)} kN·m/m${MR !== null ? ` ; M_Rd = ${f(MR, 0)} kN·m/m` : ''}`, { ancre: 'middle', taille: 10.5, gras: true })
  return enveloppe(corps, `Section de paroi moulée (1 m), ${face}`)
}

function sectionAcier(s: Schema): string {
  const pts = [[150, 60], [200, 60], [230, 170], [280, 170]].map((p) => p.join(',')).join(' ')
  const VR = opt(s.V_Rd)
  const corps = `<polyline points="${pts}" fill="none" stroke="${C.ecran}" stroke-width="7" stroke-linejoin="round" />`
    + texte(215, 200, String(s.profil ?? ''), { ancre: 'middle', taille: 11, gras: true })
    + texte(215, 222, `M_Ed = ${f(num(s.M_Ed), 0)} / M_c,Rd = ${f(num(s.M_Rd), 0)} kN·m/m`, { ancre: 'middle', taille: 10.5 })
    + texte(215, 240, `V_Ed = ${f(num(s.V_Ed), 0)} / Vpl,Rd = ${VR !== null ? f(VR, 0) : '—'} kN/m ; W = ${f(num(s.W), 0)} cm³/m, fy = ${f(num(s.fy), 0)} MPa`, { ancre: 'middle', taille: 10 })
  return enveloppe(corps, 'Palplanche : flexion et cisaillement (EN 1993-5)')
}

function poutreContinue(s: Schema): string {
  const e = num(s.e, 1), q = num(s.q)
  const x1 = 60, x2 = LARGEUR - 60, y = 120
  const xm = (x1 + x2) / 2
  const appui = (x: number) => `<polygon points="${x},${y + 4} ${x - 7},${y + 18} ${x + 7},${y + 18}" fill="${C.texte}" />`
  const fleches = Array.from({ length: 11 }, (_, i) => x1 + ((x2 - x1) * i) / 10).map((x) => fleche(x, y - 34, x, y - 8, C.accent, 1.2)).join('')
  const corps = `<line x1="${x1}" y1="${y}" x2="${x2}" y2="${y}" stroke="${C.ecran}" stroke-width="5" />` + appui(x1) + appui(xm) + appui(x2) + fleches
    + texte(xm, y - 40, `q = ${f(q, 1)} kN/m (réaction de la paroi)`, { ancre: 'middle', taille: 10.5, couleur: C.accent })
    + texte((x1 + xm) / 2, y + 34, `e = ${f(e, 2)} m`, { ancre: 'middle', taille: 10 }) + texte((xm + x2) / 2, y + 34, `e = ${f(e, 2)} m`, { ancre: 'middle', taille: 10 })
    + `<path d="M ${x1} ${y + 60} Q ${(x1 + xm) / 2} ${y + 100} ${xm} ${y + 46} Q ${(xm + x2) / 2} ${y + 100} ${x2} ${y + 60}" fill="none" stroke="${C.rouge}" stroke-width="1.6" />`
    + texte(xm, y + 42, `M = ${s.pseudo3d ? '' : 'q·e²/8 = '}${f(num(s.My), 0)} kN·m`, { ancre: 'middle', taille: 10.5, couleur: C.rouge })
    + texte(xm, y + 118, `V = ${s.pseudo3d ? '' : '0,625·q·e = '}${f(num(s.V), 0)} kN${s.pseudo3d ? ' (plaque pseudo-3D)' : ''}, ${String(s.profil ?? '')}`, { ancre: 'middle', taille: 10.5 })
  return enveloppe(corps, 'Lierne en poutre continue sur les appuis')
}

const RENDUS: Record<string, (s: Schema) => string> = {
  butee, kranz, fond_de_fouille: fondDeFouille, cercle, profil, forces_verticales: forcesVerticales, barre,
  section_beton: sectionBeton, section_acier: sectionAcier, poutre_continue: poutreContinue, anneau,
}

/** Texte SVG du schéma d'une vérification ; null si le type est inconnu ou les données insuffisantes. */
export function schemaSvg(s: Schema | null | undefined): string | null {
  if (!s || typeof s.type !== 'string') return null
  const rendu = RENDUS[s.type]
  if (!rendu) return null
  try {
    return rendu(s)
  } catch {
    return null
  }
}

export const TYPES_SCHEMA = Object.keys(RENDUS)
