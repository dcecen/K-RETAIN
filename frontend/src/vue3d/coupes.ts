// Coupes de calcul dans la maquette : rattachement de chaque tronçon de paroi à sa coupe,
// correspondance des phases entre coupes, plans verticaux nommés, zones d'application et
// diagrammes dessinés dans le plan de la coupe. Fonctions pures + fabriques d'objets.
import * as THREE from 'three'
import type { CoupeRes, ProjetCoupes, Resultats } from '../lib/api'
import { nb } from '../lib/format'
import { demiEpaisseur, lambert } from './elements'
import { hacher, interpBorne, versThree, type Contour } from './geometrie'
import { echelleAilette, geoRuban, profilValeur, remplirRuban, zGrille } from './resultats'
import { modeCalque, reglageCalque, type Contexte, type DonneesScene, type Element, type Spec } from './scene'

/** Teintes discrètes des coupes (une par coupe, cycliques). */
export const TEINTES_COUPES = [0x2f5d8a, 0xc0392b, 0x2e7d4f, 0xa86400, 0x6c3fa0, 0x0f8b8d, 0x8a5a2b, 0x4a4a8a]

export interface ResolutionCoupe {
  res: Resultats
  phase: number
  coupe: string | null
  indice: number
}

/** Résultats de la coupe i (la première coupe porte les résultats de la réponse). */
export function resultatsCoupe(projet: ProjetCoupes, premiers: Resultats, i: number): Resultats {
  return projet.coupes[i].resultats ?? premiers
}

/** Coupe qui s'applique au point (arête k, abscisse locale sl) ; −1 si aucune (tronçon orphelin). */
export function indiceCoupePour(projet: ProjetCoupes, k: number, sl: number): number {
  if (projet.unique) return 0
  for (let i = 0; i < projet.coupes.length; i++) {
    const z = projet.coupes[i].zone
    if (z.k === k && sl >= z.de - 1e-6 && sl <= z.a + 1e-6) return i
  }
  return -1
}

/** Phase de la coupe `cible` correspondant à la phase `phase` de la coupe `active` (même phase projet,
 *  sinon la dernière phase de la cible qui la précède dans le phasage projet). */
export function phaseCorrespondante(projet: ProjetCoupes, active: number, phase: number, cible: number): number {
  if (active === cible) return phase
  const ip = projet.coupes[active].correspondance[phase] ?? phase
  const corr = projet.coupes[cible].correspondance
  let best = 0
  for (let j = 0; j < corr.length; j++) if (corr[j] <= ip) best = j
  return best
}

/** Fonction de résolution à donner à la scène (DonneesScene.resultatsPour). */
export function resolveur(projet: ProjetCoupes, premiers: Resultats, active: number): DonneesScene['resultatsPour'] {
  if (projet.unique || projet.coupes.length <= 1) return undefined
  return (k, sl, phase) => {
    const i = indiceCoupePour(projet, k, sl)
    if (i < 0) return { res: premiers, phase, coupe: null }
    return { res: resultatsCoupe(projet, premiers, i), phase: phaseCorrespondante(projet, active, phase, i), coupe: projet.coupes[i].nom }
  }
}

/** Point d'intersection de la trace d'une coupe avec son tronçon (abscisse locale), sinon le milieu du tronçon. */
export function stationTrace(geo: Contour, c: CoupeRes): { sl: number; dir: [number, number] } {
  const a = geo.aretes[c.zone.k]
  const milieu = 0.5 * (c.zone.de + c.zone.a)
  if (!a || !c.trace || c.trace.length < 2) return { sl: milieu, dir: a ? a.ni : [0, 1] }
  const [P, Q] = c.trace
  const dx = Q[0] - P[0]
  const dy = Q[1] - P[1]
  const L = Math.hypot(dx, dy) || 1
  let dir: [number, number] = [dx / L, dy / L]
  if (dir[0] * a.ni[0] + dir[1] * a.ni[1] < 0) dir = [-dir[0], -dir[1]]     // orientée vers la fouille
  // intersection trace × arête
  const ex = a.B[0] - a.A[0]
  const ey = a.B[1] - a.A[1]
  const den = dx * ey - dy * ex
  if (Math.abs(den) < 1e-9) return { sl: milieu, dir }
  const wx = a.A[0] - P[0]
  const wy = a.A[1] - P[1]
  const u = (wx * dy - wy * dx) / den
  const sl = u * a.L
  return { sl: sl >= c.zone.de - 1e-6 && sl <= c.zone.a + 1e-6 ? sl : milieu, dir }
}

function projetDe(ctx: Contexte): ProjetCoupes | null {
  return ctx.d.projet ?? null
}

// ------------------------------------------------------------------ fabriques
function specsPlans(ctx: Contexte): Spec[] {
  const projet = projetDe(ctx)
  if (!projet || projet.unique) return []
  const geo = ctx.d.geo
  const p = ctx.d.m.paroi
  const zHaut = Math.max(p.tete, ...ctx.d.m.couches.map((c) => c.toit)) + 0.5
  const zBas = ctx.d.m.z_bas
  return projet.coupes.map((c, i) => {
    const id = `coupes.plan.${i}`
    const cle = hacher(`${id}|${c.nom}|${JSON.stringify(c.trace)}|${JSON.stringify(c.zone)}|${zHaut}|${zBas}`)
    return {
      id, cle, creer: (cx) => {
        const a = geo.aretes[c.zone.k]
        const st = stationTrace(geo, c)
        const [P, Q] = c.trace.length >= 2 ? c.trace : [[a.A[0] + a.t[0] * st.sl - a.ni[0] * 6, a.A[1] + a.t[1] * st.sl - a.ni[1] * 6], [a.A[0] + a.t[0] * st.sl + a.ni[0] * 6, a.A[1] + a.t[1] * st.sl + a.ni[1] * 6]]
        const L = Math.hypot(Q[0] - P[0], Q[1] - P[1]) || 1
        const teinte = TEINTES_COUPES[i % TEINTES_COUPES.length]
        const mat = cx.fab.mat(new THREE.MeshBasicMaterial({ color: teinte, transparent: true, opacity: 0.12, side: THREE.DoubleSide, depthWrite: false }))
        const mesh = cx.fab.obj(new THREE.Mesh(cx.fab.geo(new THREE.PlaneGeometry(1, 1)), mat))
        versThree((P[0] + Q[0]) / 2, (P[1] + Q[1]) / 2, (zHaut + zBas) / 2, mesh.position)
        mesh.rotation.y = Math.atan2(-(Q[1] - P[1]), Q[0] - P[0])
        mesh.scale.set(L, zHaut - zBas, 1)
        const bord = cx.fab.obj(new THREE.LineSegments(cx.fab.geo(new THREE.EdgesGeometry(mesh.geometry)), cx.fab.mat(new THREE.LineBasicMaterial({ color: teinte }))))
        mesh.add(bord)
        const el: Element = { id, cle, noeud: 'coupes', calque: 'coupes.plans', objet: mesh, selection: `coupe:${c.nom}`, visiblePhase: true }
        el.etiquettes = (_k, o) => {
          o.push({ id: `nom.coupe.${i}`, pos: versThree(a.A[0] + a.t[0] * st.sl, a.A[1] + a.t[1] * st.sl, p.tete + 0.8), texte: c.nom, calque: 'coupes.plans', classe: 'coupe', selection: `coupe:${c.nom}` })
        }
        el.surligner = (actif) => { mat.opacity = actif ? 0.3 : 0.12 }
        return el
      },
    }
  })
}

function specsZones(ctx: Contexte): Spec[] {
  const projet = projetDe(ctx)
  if (!projet || projet.unique) return []
  const geo = ctx.d.geo
  const p = ctx.d.m.paroi
  const o = demiEpaisseur(p) + 0.06
  const out: Spec[] = []
  const bande = (cx: Contexte, k: number, de: number, a_: number, couleur: number, hachure: boolean) => {
    const ar = geo.aretes[k]
    const g = cx.fab.geo(new THREE.PlaneGeometry(1, 1))
    const mat = cx.fab.mat(hachure
      ? new THREE.MeshBasicMaterial({ color: couleur, wireframe: true, transparent: true, opacity: 0.6 })
      : new THREE.MeshBasicMaterial({ color: couleur, transparent: true, opacity: 0.35, side: THREE.DoubleSide, depthWrite: false }))
    const mesh = cx.fab.obj(new THREE.Mesh(hachure ? cx.fab.geo(new THREE.PlaneGeometry(1, 1, Math.max(2, Math.round((a_ - de) / 1.5)), 8)) : g, mat))
    const sm = 0.5 * (de + a_)
    versThree(ar.A[0] + ar.t[0] * sm + ar.ni[0] * o, ar.A[1] + ar.t[1] * sm + ar.ni[1] * o, (p.tete + p.pied) / 2, mesh.position)
    mesh.rotation.y = Math.atan2(-ar.t[1], ar.t[0])
    mesh.scale.set(a_ - de, p.tete - p.pied, 1)
    return mesh
  }
  projet.coupes.forEach((c, i) => {
    const id = `coupes.zone.${i}`
    const cle = hacher(`${id}|${JSON.stringify(c.zone)}|${p.tete}|${p.pied}|${o}`)
    out.push({
      id, cle, creer: (cx) => {
        const mesh = bande(cx, c.zone.k, c.zone.de, c.zone.a, TEINTES_COUPES[i % TEINTES_COUPES.length], false)
        const el: Element = { id, cle, noeud: 'coupes', calque: 'coupes.zones', objet: mesh, selection: `coupe:${c.nom}`, visiblePhase: true }
        el.etiquettes = (_k, out2) => {
          const ar = geo.aretes[c.zone.k]
          const sm = 0.5 * (c.zone.de + c.zone.a)
          out2.push({ id: `zone.${i}`, pos: versThree(ar.A[0] + ar.t[0] * sm + ar.ni[0] * o, ar.A[1] + ar.t[1] * sm + ar.ni[1] * o, p.pied + 0.3 * (p.tete - p.pied)),
            texte: `${c.nom} (${nb(c.zone.a - c.zone.de, 1)} m)`, calque: 'coupes.zones', classe: 'coupe', selection: `coupe:${c.nom}` })
        }
        return el
      },
    })
  })
  projet.orphelins.forEach((z, i) => {
    const id = `coupes.orphelin.${i}`
    const cle = hacher(`${id}|${JSON.stringify(z)}|${p.tete}|${p.pied}`)
    out.push({
      id, cle, creer: (cx) => {
        const mesh = bande(cx, z.k, z.de, z.a, 0x8a93a2, true)
        const el: Element = { id, cle, noeud: 'coupes', calque: 'coupes.zones', objet: mesh, visiblePhase: true }
        el.etiquettes = (_k, out2) => {
          const ar = geo.aretes[z.k]
          const sm = 0.5 * (z.de + z.a)
          out2.push({ id: `orphelin.${i}`, pos: versThree(ar.A[0] + ar.t[0] * sm + ar.ni[0] * o, ar.A[1] + ar.t[1] * sm + ar.ni[1] * o, p.pied + 0.3 * (p.tete - p.pied)),
            texte: 'sans coupe de calcul', calque: 'coupes.zones', classe: 'coupe' })
        }
        return el
      },
    })
  })
  return out
}

function specsDiagrammes(ctx: Contexte): Spec[] {
  const projet = projetDe(ctx)
  if (!projet || projet.unique) return []
  const geo = ctx.d.geo
  const p = ctx.d.m.paroi
  const H = p.tete - p.pied
  const offset = demiEpaisseur(p) + 0.05
  return projet.coupes.map((c, i) => {
    const id = `coupes.diagramme.${i}`
    const cle = hacher(`${id}|${JSON.stringify(c.trace)}|${JSON.stringify(c.zone)}|${p.pied}|${p.tete}`)
    return {
      id, cle, creer: (cx) => {
        const z = zGrille(p.pied, p.tete)
        const g1 = cx.fab.geo(geoRuban(z.length))
        const g2 = cx.fab.geo(geoRuban(z.length))
        const mat = cx.fab.mat(new THREE.MeshLambertMaterial({ vertexColors: true, side: THREE.DoubleSide, transparent: true, opacity: 0.85 }))
        const groupe = cx.fab.obj(new THREE.Group())
        groupe.add(cx.fab.obj(new THREE.Mesh(g1, mat)), cx.fab.obj(new THREE.Mesh(g2, mat)))
        const el: Element = { id, cle, noeud: 'coupes', calque: 'coupes.diagrammes', objet: groupe, selection: `coupe:${c.nom}`, visiblePhase: true }
        const teinte = TEINTES_COUPES[i % TEINTES_COUPES.length]
        let texte = ''
        el.appliquerPhase = (k) => {
          const r = k.d.resultatsPour?.(c.zone.k, 0.5 * (c.zone.de + c.zone.a), k.phase)
          const res = r?.res ?? k.d.res
          const phase = r?.phase ?? k.phase
          const ph = res.phases[phase]
          el.visiblePhase = !!ph?.ok
          if (!ph?.ok) return
          const st = stationTrace(geo, c)
          const ar = { ...geo.aretes[c.zone.k], ni: st.dir }
          const mode = modeCalque(k.scene.calques, 'coupes.diagrammes', 'deplacement')
          const facteur = reglageCalque(k.scene.calques, 'coupes.diagrammes', 'echelle_ailettes', 1)
          groupe.children[1].visible = mode === 'pressions'
          if (mode === 'pressions') {
            const pr = ph.pressions!
            let m = 1
            for (const q of res.phases) if (q.ok && q.pressions) m = Math.max(m, ...q.pressions.amont.p, ...q.pressions.aval.p)
            const ech = ((0.3 * H) / m) * facteur
            remplirRuban(g1, ar, st.sl, z, offset, -1, (zz) => (zz <= ph.terrain_amont ? interpBorne(pr.amont.z, pr.amont.p, zz) : 0), ech, () => 0x8b6b3e)
            remplirRuban(g2, ar, st.sl, z, offset, 1, (zz) => (zz <= ph.terrain_aval ? interpBorne(pr.aval.z, pr.aval.p, zz) : 0), ech, () => 0x2e7d4f)
            texte = `${c.nom} · pressions (kPa) · ${ph.nom}`
          } else {
            const quoi = mode === 'moment' ? 'M' : 'y'
            const f = profilValeur(res, phase, quoi, 0)!
            const ech = (quoi === 'M' ? echelleAilette(res, 'M', H) : (0.3 * H) / Math.max(1e-6, ...res.phases.filter((q) => q.ok).flatMap((q) => q.y_mm!.map(Math.abs)))) * facteur
            remplirRuban(g1, ar, st.sl, z, offset, 1, f, ech, (v) => (quoi === 'M' ? (v >= 0 ? 0xc7362c : 0x2c5da8) : teinte))
            let ext = 0
            for (const zz of z) if (Math.abs(f(zz)) > Math.abs(ext)) ext = f(zz)
            texte = `${c.nom} · ${quoi === 'M' ? `M max = ${nb(ext, 0)} kN·m/m` : `y max = ${nb(ext, 1)} mm`} · ${ph.nom}`
          }
        }
        el.etiquettes = (_k, o) => {
          if (!texte) return
          const ar = geo.aretes[c.zone.k]
          const st = stationTrace(geo, c)
          o.push({ id: `diag.${i}`, pos: versThree(ar.A[0] + ar.t[0] * st.sl + st.dir[0] * (0.3 * H), ar.A[1] + ar.t[1] * st.sl + st.dir[1] * (0.3 * H), p.tete),
            texte, calque: 'coupes.diagrammes', classe: 'valeur', selection: `coupe:${c.nom}` })
        }
        return el
      },
    }
  })
}

export const FABRIQUES_COUPES = [specsPlans, specsZones, specsDiagrammes]

export { lambert }
