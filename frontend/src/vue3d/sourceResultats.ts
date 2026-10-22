// Source abstraite des résultats d'une coupe locale (« Couper ici »).
//
// - Mode 2D (projet à coupes ou coupe unique) : la coupe locale lit simplement les résultats de
//   la coupe de calcul du tronçon, et le dit.
// - Mode pseudo-3D : les courbes sont lues dans le champ de la plaque (déplacement et moment le
//   long de la verticale à l'abscisse s), le tranchant est dérivé numériquement du moment, les
//   pressions et l'eau viennent du calcul 2D d'accompagnement.
// Le pseudo-3D s'y branche par `sourceChamp` : toute fonction (s → courbes) convient, ce qui permet
// de tester l'extraction avec un champ analytique.
import type { AppuiPhase, PhaseRes, ProjetCoupes, Resultats } from '../lib/api'
import { indiceCoupePour, phaseCorrespondante, resultatsCoupe } from './coupes'
import type { Contour } from './geometrie'

export interface CourbesCoupe {
  /** Résultats « vus » à cette position (une phase par phase du calcul). */
  res: Resultats
  phase: number
  coupe: string | null
  /** Ce que l'utilisateur doit savoir sur l'origine des courbes. */
  origine: string
  mode: '2d' | 'pseudo3d'
}

export interface SourceResultats {
  mode: '2d' | 'pseudo3d'
  /** Courbes à la position (arête k, abscisse locale sl) pour la phase affichée ; null si rien n'est calculé. */
  coupeLocale(k: number, sl: number, phase: number): CourbesCoupe | null
}

/** Champ 3D : courbes le long de la verticale à l'abscisse développée s, pour chaque phase. */
export interface ChampPlaque {
  z: number[]
  /** y (mm) et M (kN·m/m) aux cotes z pour la phase i ; null si la phase n'est pas calculée. */
  courbes(s: number, phase: number): { y_mm: number[]; M: number[] } | null
}

// ------------------------------------------------------------------ mode 2D
export function source2D(projet: ProjetCoupes | null, premiers: Resultats, active: number): SourceResultats {
  return {
    mode: '2d',
    coupeLocale(k, sl, phase) {
      if (!projet || projet.unique || projet.coupes.length <= 1) {
        return { res: premiers, phase, coupe: projet?.coupes[0]?.nom ?? null, mode: '2d',
          origine: 'mode 2D : résultats du calcul, identiques sur tout le linéaire' }
      }
      const i = indiceCoupePour(projet, k, sl)
      if (i < 0) return null
      const res = resultatsCoupe(projet, premiers, i)
      return { res, phase: phaseCorrespondante(projet, active, phase, i), coupe: projet.coupes[i].nom, mode: '2d',
        origine: `mode 2D : résultats de la coupe de calcul du tronçon (${projet.coupes[i].nom})` }
    },
  }
}

// ------------------------------------------------------------------ mode pseudo-3D (champ)
/** Dérivée dM/dz par différences finies centrées (V = dM/dz, z vers le haut). */
export function deriver(z: number[], M: number[]): number[] {
  const n = z.length
  const V = new Array<number>(n)
  for (let i = 0; i < n; i++) {
    const a = Math.max(0, i - 1)
    const b = Math.min(n - 1, i + 1)
    const dz = z[b] - z[a]
    V[i] = dz === 0 ? 0 : (M[b] - M[a]) / dz
  }
  return V
}

/** Phase synthétique : courbes du champ à l'abscisse s, pressions et eau du 2D d'accompagnement. */
function phaseChamp(base: PhaseRes, champ: ChampPlaque, s: number, i: number, appuis: AppuiPhase[] | undefined): PhaseRes {
  const c = champ.courbes(s, i)
  if (!base.ok || !c) return { ...base, ok: false, message: base.ok ? 'position hors du champ pseudo-3D' : base.message }
  const z = champ.z
  const M = c.M
  const y_mm = c.y_mm
  const i_max = y_mm.reduce((k, v, j) => (Math.abs(v) > Math.abs(y_mm[k]) ? j : k), 0)
  return {
    ...base, z, y_mm, z_diag: z, M, V: deriver(z, M), appuis: appuis ?? base.appuis,
    synthese: { ...base.synthese!, y_max_mm: y_mm[i_max], z_y_max: z[i_max], y_tete_mm: y_mm[z.length - 1],
      M_max: Math.max(...M), M_min: Math.min(...M), V_absmax: Math.max(...deriver(z, M).map(Math.abs)) },
  }
}

export function sourceChamp(res: Resultats, champ: ChampPlaque, geo: Contour, appuisAuDroit?: (s: number, phase: number) => AppuiPhase[] | undefined): SourceResultats {
  const cache = new Map<string, Resultats>()
  return {
    mode: 'pseudo3d',
    coupeLocale(k, sl, phase) {
      const a = geo.aretes[k]
      if (!a) return null
      const s = a.s0 + sl
      const cle = s.toFixed(3)
      let r = cache.get(cle)
      if (!r) {
        r = { ...res, pseudo3d: undefined, phases: res.phases.map((ph, i) => phaseChamp(ph, champ, s, i, appuisAuDroit?.(s, i))) }
        if (cache.size > 64) cache.clear()
        cache.set(cle, r)
      }
      return { res: r, phase, coupe: null, mode: 'pseudo3d',
        origine: `mode pseudo-3D : déplacement et moment lus dans le champ à s = ${s.toFixed(1)} m ; V dérivé de M ; pressions du calcul 2D` }
    },
  }
}

/** Champ lu dans les résultats pseudo-3D du serveur (interpolation linéaire en s). */
export function champPseudo3D(res: Resultats): ChampPlaque | null {
  const p3 = res.pseudo3d
  if (!p3) return null
  return {
    z: p3.z,
    courbes(s, phase) {
      const q = p3.phases[phase]
      if (!q?.ok || !q.y_mm || !q.M) return null
      const S = p3.s
      let i = 0
      while (i < S.length - 1 && S[i + 1] < s) i++
      const i1 = Math.min(i + 1, S.length - 1)
      const t = S[i1] === S[i] ? 0 : Math.min(Math.max((s - S[i]) / (S[i1] - S[i]), 0), 1)
      const mix = (A: number[], B: number[]) => A.map((v, j) => (1 - t) * v + t * B[j])
      return { y_mm: mix(q.y_mm[i], q.y_mm[i1]), M: mix(q.M[i], q.M[i1]) }
    },
  }
}

export function sourcePseudo3D(res: Resultats, geo: Contour): SourceResultats | null {
  const champ = champPseudo3D(res)
  if (!champ) return null
  const appuis = (s: number, phase: number): AppuiPhase[] | undefined => {
    const q = res.pseudo3d!.phases[phase]
    const base = res.phases[phase]?.appuis
    if (!q?.appuis || !base) return base
    // effort de l'appui le plus proche en s (par nom), sinon valeur 2D
    return base.map((a) => {
      const cands = q.appuis!.filter((x) => x.nom === a.nom)
      if (!cands.length) return a
      const prox = cands.reduce((m, x) => (Math.abs(x.s - s) < Math.abs(m.s - s) ? x : m))
      return { ...a, effort_kN_m: prox.effort, effort_axial_kN: a.effort_kN_m ? (a.effort_axial_kN * prox.effort) / a.effort_kN_m : a.effort_axial_kN, actif: prox.actif }
    })
  }
  return sourceChamp(res, champ, geo, appuis)
}

/** Source adaptée au projet : pseudo-3D si le champ existe, sinon 2D. */
export function sourcePourProjet(res: Resultats, projet: ProjetCoupes | null, premiers: Resultats, active: number, geo: Contour): SourceResultats {
  return (res.pseudo3d && sourcePseudo3D(res, geo)) || source2D(projet, premiers, active)
}

// ------------------------------------------------------------------ épinglage
/** Entrée YAML d'une coupe de calcul créée depuis une coupe locale épinglée. */
export function entreeYamlCoupe(nom: string, geo: Contour, k: number, sl: number, cotes: Record<string, number> = {}, longueurTrace?: number): Record<string, unknown> {
  const a = geo.aretes[k]
  const nomCote = Object.entries(cotes).find(([, v]) => v === k)?.[0]
  const L = longueurTrace ?? Math.min(8, Math.max(4, 0.3 * a.L))
  const r3 = (v: number) => Math.round(v * 1000) / 1000
  const px = a.A[0] + a.t[0] * sl
  const py = a.A[1] + a.t[1] * sl
  return {
    nom,
    zone: { paroi: nomCote ?? k },
    trace: { de: [r3(px - a.ni[0] * L), r3(py - a.ni[1] * L)], a: [r3(px + a.ni[0] * L), r3(py + a.ni[1] * L)] },
  }
}
