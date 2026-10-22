// Légendes des calques de résultats actifs (fonctions pures : description → rendu par Legendes.tsx).
import type { Resultats } from '../lib/api'
import { nb } from '../lib/format'
import { reglageCalque, type EtatCalquesScene } from './scene'
import { amplificationAuto, bornes } from './resultats'
import { COULEURS_TAUX, degradeCss, SEUILS_DEFAUT, type NomPalette } from './palettes'
import { modeCalque } from './scene'

export interface LegendeContinue {
  type: 'continue'
  id: string
  titre: string
  unite: string
  min: number
  max: number
  degrade: string
  phase: string
  note?: string
}
export interface LegendeDiscrete {
  type: 'discrete'
  id: string
  titre: string
  classes: { couleur: string; texte: string }[]
  phase: string
  note?: string
}
export type Legende = LegendeContinue | LegendeDiscrete

const hex = (c: number) => `#${c.toString(16).padStart(6, '0')}`

/** Légendes à afficher pour l'état des calques et la phase active. */
export function legendes(res: Resultats, c: EtatCalquesScene, phase: number): Legende[] {
  const out: Legende[] = []
  const nomPhase = res.phases[phase]?.nom ?? ''
  const vis = (id: string) => c.visible(id)
  if (vis('resultats.deformee')) {
    const r = reglageCalque<number | string>(c, 'resultats.deformee', 'amplification', 'auto')
    const amp = r === 'auto' || r === 0 ? amplificationAuto(res) : Number(r)
    out.push({ type: 'discrete', id: 'deformee', titre: `Déformée × ${nb(amp, 0)}${r === 'auto' || r === 0 ? ' (auto : 2 m à l\'écran)' : ''}`, classes: [], phase: nomPhase,
      note: res.pseudo3d ? 'champ pseudo-3D' : 'profil 2D extrudé, atténué aux angles (visuel)' })
  }
  if (vis('resultats.taux')) {
    const o = reglageCalque(c, 'resultats.taux', 'orange', SEUILS_DEFAUT.orange)
    const r = reglageCalque(c, 'resultats.taux', 'rouge', SEUILS_DEFAUT.rouge)
    out.push({ type: 'discrete', id: 'taux', titre: 'Taux de travail (toutes phases)', phase: nomPhase, classes: [
      { couleur: hex(COULEURS_TAUX.vert), texte: `< ${nb(o * 100, 0)} %` }, { couleur: hex(COULEURS_TAUX.orange), texte: `${nb(o * 100, 0)} à ${nb(r * 100, 0)} %` },
      { couleur: hex(COULEURS_TAUX.rouge), texte: `≥ ${nb(r * 100, 0)} %` }, { couleur: hex(COULEURS_TAUX.gris), texte: 'non vérifiable' }] })
  } else if (vis('resultats.deplacement')) {
    const signe = modeCalque(c, 'resultats.deplacement', 'absolu') === 'signe'
    const fixe = reglageCalque(c, 'resultats.deplacement', 'echelle', 'fixe') === 'fixe'
    const b = bornes(res, signe ? 'y' : 'yabs', fixe ? null : phase)
    out.push({ type: 'continue', id: 'deplacement', titre: signe ? 'Déplacement y (positif vers la fouille)' : 'Déplacement |y|', unite: 'mm', ...b,
      degrade: degradeCss(reglageCalque(c, 'resultats.deplacement', 'palette', signe ? 'signe' : 'divergente') as NomPalette), phase: fixe ? 'toutes phases' : nomPhase })
  } else {
    for (const [id, quoi, titre, unite] of [['resultats.moment', 'M', 'Moment (positif : face fouille tendue)', 'kN·m/m'], ['resultats.tranchant', 'V', 'Effort tranchant', 'kN/m']] as const) {
      if (!vis(id) || modeCalque(c, id, quoi === 'M' ? 'couleur' : 'ailettes') !== 'couleur') continue
      const fixe = reglageCalque(c, id, 'echelle', 'fixe') === 'fixe'
      const b = bornes(res, quoi, fixe ? null : phase)
      const m = Math.max(Math.abs(b.min), Math.abs(b.max))
      out.push({ type: 'continue', id: quoi, titre, unite, min: -m, max: m, degrade: degradeCss(reglageCalque(c, id, 'palette', 'signe') as NomPalette), phase: fixe ? 'toutes phases' : nomPhase })
    }
  }
  for (const [id, quoi, titre, unite] of [['resultats.moment', 'M', 'Moment en ailettes', 'kN·m/m'], ['resultats.tranchant', 'V', 'Tranchant en ailettes', 'kN/m']] as const) {
    if (vis(id) && modeCalque(c, id, quoi === 'M' ? 'couleur' : 'ailettes') === 'ailettes')
      out.push({ type: 'discrete', id: `${quoi}.ailettes`, titre: `${titre} (${unite})`, phase: nomPhase, classes: [{ couleur: '#c7362c', texte: 'positif' }, { couleur: '#2c5da8', texte: 'négatif' }] })
  }
  if (vis('resultats.pressions')) {
    out.push({ type: 'discrete', id: 'pressions', titre: 'Pressions (kPa)', phase: nomPhase, classes: [
      { couleur: '#8b6b3e', texte: 'terres mobilisées, face terre' }, { couleur: '#2e7d4f', texte: 'terres mobilisées, face fouille' },
      { couleur: '#3b8fd9', texte: 'eau' }, { couleur: '#9a7b4f', texte: 'limite de poussée (pointillé)' }, { couleur: '#4f7b9a', texte: 'limite de butée (pointillé)' }] })
  }
  if (vis('resultats.enveloppes')) {
    out.push({ type: 'discrete', id: 'enveloppes', titre: `Enveloppe ${modeCalque(c, 'resultats.enveloppes', 'deformee') === 'moment' ? 'des moments' : 'de la déformée'} (toutes phases, fantôme)`, phase: 'toutes phases', classes: [] })
  }
  return out
}
