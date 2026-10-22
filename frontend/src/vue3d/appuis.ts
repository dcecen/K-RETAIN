// Résultats des appuis : taux de travail, échelle des efforts, couleurs et étiquettes (fonctions pures).
import * as THREE from 'three'
import type { AppuiPhase, Resultats, Verif } from '../lib/api'
import { nb } from '../lib/format'
import { classeTaux, COULEURS_TAUX, couleurValeur, SEUILS_DEFAUT, type Seuils } from './palettes'
import { modeCalque, reglageCalque, type Contexte, type EtatCalquesScene } from './scene'

/** Vérifications rattachées à un appui (élément « B1 », « B1 (HEB 400) ») et à ses assemblages (« A1 (…) · soudure »). */
export function verifsAppui(verifs: Verif[] | undefined, nom: string, assemblages: Record<string, { appui: string | null }> = {}, filtre?: (v: Verif) => boolean): Verif[] {
  const noms = new Set([nom, ...Object.entries(assemblages).filter(([, a]) => a.appui === nom).map(([k]) => k)])
  return (verifs ?? []).filter((v) => noms.has(v.element.split(' ')[0]) && (!filtre || filtre(v)))
}

/** Taux de travail le plus défavorable d'un appui et de ses assemblages (null si rien de vérifiable). */
export function tauxAppui(verifs: Verif[] | undefined, nom: string, assemblages: Record<string, { appui: string | null }> = {}, filtre?: (v: Verif) => boolean): number | null {
  const t = verifsAppui(verifs, nom, assemblages, filtre).map((v) => v.taux).filter((x): x is number => x !== null && Number.isFinite(x))
  return t.length ? Math.max(...t) : null
}

export const FILTRE_LIERNE = (v: Verif) => v.nom.startsWith('Lierne')
/** Vérifications de la barre elle-même (ni lierne, ni assemblage « A1 (…) »). */
export const FILTRE_BARRE = (v: Verif) => !v.nom.startsWith('Lierne') && !/·/.test(v.element)
export const filtreAssemblage = (nomAss: string) => (v: Verif) => v.element.split(' ')[0] === nomAss

export function seuilsTaux(c: EtatCalquesScene): Seuils {
  return { orange: reglageCalque(c, 'resultats.taux', 'orange', SEUILS_DEFAUT.orange), rouge: reglageCalque(c, 'resultats.taux', 'rouge', SEUILS_DEFAUT.rouge) }
}

export type ModeEffort = 'service' | 'elu'

/** Effort d'un appui à une phase selon le mode (par mètre et axial) ; null si l'ELU n'est pas disponible. */
export function effortAppui(a: AppuiPhase, mode: ModeEffort): { par_m: number; axial: number } | null {
  if (mode === 'elu') return a.effort_elu_kN_m != null && a.effort_elu_kN != null ? { par_m: a.effort_elu_kN_m, axial: a.effort_elu_kN } : null
  return { par_m: a.effort_kN_m, axial: a.effort_axial_kN }
}

/** Borne haute des efforts par mètre, toutes phases et tous appuis (échelle fixe). */
export function maxEfforts(res: Resultats, mode: ModeEffort): number {
  let m = 0
  for (const ph of res.phases) for (const a of ph.appuis ?? []) {
    const e = effortAppui(a, mode)
    if (e) m = Math.max(m, Math.abs(e.par_m))
  }
  return m || 1
}

const _c = new THREE.Color()

/** Couleur d'un appui pour la phase : taux de travail, effort, ou couleur de base. */
export function couleurAppui(ctx: Contexte, nom: string, base: number, filtre?: (v: Verif) => boolean): number {
  const c = ctx.scene.calques
  if (c.visible('resultats.taux')) {
    return COULEURS_TAUX[classeTaux(tauxAppui(ctx.d.res.verifications, nom, ctx.d.m.assemblages, filtre), seuilsTaux(c))]
  }
  if (c.visible('resultats.efforts')) {
    const mode = modeCalque(c, 'resultats.efforts', 'service') as ModeEffort
    const a = ctx.ph.appuis?.find((x) => x.nom === nom)
    const e = a ? effortAppui(a, mode) : null
    if (!e) return 0x9aa2ad
    return couleurValeur(Math.abs(e.par_m), 0, maxEfforts(ctx.d.res, mode), 'sequentielle', _c).getHex()
  }
  return base
}

/** Texte de l'étiquette d'effort d'un appui (« B1 · 141 kN/m · 847 kN »), null si le calque est inactif. */
export function etiquetteEffort(ctx: Contexte, nom: string): string | null {
  const c = ctx.scene.calques
  if (!c.visible('resultats.efforts') || !reglageCalque(c, 'resultats.efforts', 'etiquettes', true)) return null
  const mode = modeCalque(c, 'resultats.efforts', 'service') as ModeEffort
  const a = ctx.ph.appuis?.find((x) => x.nom === nom)
  if (!a) return null
  const e = effortAppui(a, mode)
  if (!e) return `${nom} · ELU non disponible (coefficient manquant)`
  return `${nom} · ${nb(e.par_m, 0)} kN/m · ${nb(e.axial, 0)} kN${mode === 'elu' ? ' (ELU)' : ''}`
}

/** Taux affiché d'un appui (« B1 · 77 % »), null si le calque est inactif. */
export function etiquetteTaux(ctx: Contexte, nom: string, filtre?: (v: Verif) => boolean): string | null {
  if (!ctx.scene.calques.visible('resultats.taux')) return null
  const t = tauxAppui(ctx.d.res.verifications, nom, ctx.d.m.assemblages, filtre)
  return t === null ? `${nom} · non vérifiable` : `${nom} · ${nb(t * 100, 0)} %`
}
