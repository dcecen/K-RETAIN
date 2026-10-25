// Légendes des calques de résultats actifs (fonctions pures : description -> rendu par Legendes.tsx).
import type { Resultats } from '../lib/api'
import { nb } from '../lib/format'
import { reglageCalque, type EtatCalquesScene } from './scene'
import { maxEfforts, type ModeEffort } from './appuis'
import { amplificationAuto, bornes } from './resultats'
import { maxFleche } from './resultatsAppuis'
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

/** Longueur développée d'un contour fermé (m). */
function perimetreContour(contour: number[][] | undefined, ferme = true): number {
  if (!contour || contour.length < 2) return 0
  let L = 0
  for (let i = 0; i < (ferme ? contour.length : contour.length - 1); i++) {
    const a = contour[i]
    const b = contour[(i + 1) % contour.length]
    L += Math.hypot(b[0] - a[0], b[1] - a[1])
  }
  return L
}

/** Origine de la déformée affichée : champ pseudo-3D (avec, le cas échéant, la part du contour hors de la longueur
 *  modélisée, laissée en gris), ou profil 2D de la coupe de chaque tronçon, extrudé le long du tronçon. */
export function noteDeformee(res: Resultats): string {
  const p3 = res.pseudo3d
  const ferme = res.maquette?.ferme !== false
  if (!p3) {
    if (!ferme && (res.maquette?.contour.length ?? 0) <= 2) return 'profil 2D de la coupe, extrudé le long du tronçon (écran supposé infini, déformation plane)'
    return `profil 2D de la coupe de chaque tronçon, extrudé le long du tronçon et atténué aux angles${ferme ? '' : ' intérieurs'} (visuel)`
  }
  if (!p3.fermee && p3.s.length) {
    const L = p3.s[p3.s.length - 1]
    if (perimetreContour(res.maquette?.contour, ferme) > L + 1e-6) return `champ pseudo-3D (paroi droite de ${nb(L, 0)} m) ; au-delà : hors longueur modélisée, en gris`
  }
  return 'champ pseudo-3D'
}

/** Légendes à afficher pour l'état des calques et la phase active. */
export function legendes(res: Resultats, c: EtatCalquesScene, phase: number, animation = false): Legende[] {
  const out: Legende[] = []
  const nomPhase = res.phases[phase]?.nom ?? ''
  const vis = (id: string) => c.visible(id)
  if (vis('resultats.deformee')) {
    const r = reglageCalque<number | string>(c, 'resultats.deformee', 'amplification', 'auto')
    const amp = r === 'auto' || r === 0 ? amplificationAuto(res) : Number(r)
    out.push({ type: 'discrete', id: 'deformee', titre: `Déformée × ${nb(amp, 0)}${r === 'auto' || r === 0 ? ' (auto : 2 m à l\'écran)' : ''}`, classes: [], phase: nomPhase,
      note: noteDeformee(res) })
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
    for (const [id, quoi, titre, unite] of [['resultats.moment', 'M', 'Moment (positif : face fouille tendue)', 'kN·m/m'], ['resultats.tranchant', 'V', 'Effort tranchant V = dM/dz (M > 0 : face fouille tendue)', 'kN/m']] as const) {
      if (!vis(id) || modeCalque(c, id, quoi === 'M' ? 'couleur' : 'ailettes') !== 'couleur') continue
      const fixe = reglageCalque(c, id, 'echelle', 'fixe') === 'fixe'
      const b = bornes(res, quoi, fixe ? null : phase)
      const m = Math.max(Math.abs(b.min), Math.abs(b.max))
      out.push({ type: 'continue', id: quoi, titre, unite, min: -m, max: m, degrade: degradeCss(reglageCalque(c, id, 'palette', 'signe') as NomPalette), phase: fixe ? 'toutes phases' : nomPhase })
    }
  }
  for (const [id, quoi, titre, unite] of [['resultats.moment', 'M', 'Moment en ailettes', 'kN·m/m'], ['resultats.tranchant', 'V', 'Tranchant en ailettes', 'kN/m']] as const) {
    if (vis(id) && modeCalque(c, id, quoi === 'M' ? 'couleur' : 'ailettes') === 'ailettes')
      out.push({ type: 'discrete', id: `${quoi}.ailettes`, titre: `${titre} (${unite})`, phase: nomPhase,
        classes: [{ couleur: '#c7362c', texte: quoi === 'M' ? 'M > 0 : face fouille tendue' : 'V > 0 (V = dM/dz)' }, { couleur: '#2c5da8', texte: quoi === 'M' ? 'M < 0 : face terre tendue' : 'V < 0' }] })
  }
  if (vis('resultats.pressions')) {
    out.push({ type: 'discrete', id: 'pressions', titre: 'Pressions (kPa)', phase: nomPhase, classes: [
      { couleur: '#8b6b3e', texte: 'terres mobilisées, face terre' }, { couleur: '#2e7d4f', texte: 'terres mobilisées, face fouille' },
      { couleur: '#3b8fd9', texte: 'eau' }, { couleur: '#9a7b4f', texte: 'limite de poussée (pointillé)' }, { couleur: '#4f7b9a', texte: 'limite de butée (pointillé)' }] })
  }
  if (vis('resultats.efforts')) {
    const mode = modeCalque(c, 'resultats.efforts', 'service') as ModeEffort
    out.push({ type: 'continue', id: 'efforts', titre: `Efforts d'appui (${mode === 'elu' ? 'ELU, × γ' : 'service'})`, unite: 'kN/m', min: 0, max: maxEfforts(res, mode),
      degrade: degradeCss('sequentielle'), phase: 'toutes phases' })
  }
  if (vis('resultats.fleches')) {
    const r = reglageCalque<number | string>(c, 'resultats.fleches', 'amplification', 'auto')
    const m = maxFleche(res)
    const amp = r === 'auto' || r === 0 ? (m > 1e-6 ? 1500 / m : 1) : Number(r)
    out.push({ type: 'discrete', id: 'fleches', titre: `Flèche des butons et liernes × ${nb(amp, 0)}${r === 'auto' || r === 0 ? ' (auto : 1,5 m à l\'écran)' : ''}`, classes: [], phase: nomPhase,
      note: modeCalque(c, 'resultats.fleches', 'compression') === 'compression' ? 'poids propre amplifié par 1/(1 − N/Ncr) ; liernes : valeur approchée' : 'poids propre seul ; liernes : valeur approchée' })
  }
  if (vis('surcharges.volumes') && res.maquette?.surcharges?.length) {
    out.push({ type: 'discrete', id: 'surcharges', titre: `Surcharges : 1 m de hauteur = ${nb(reglageCalque(c, 'surcharges.volumes', 'echelle', 20), 0)} kPa`, phase: nomPhase, classes: [],
      note: 'présentes de leur phase d\'application à leur retrait ; survol : pression induite' })
  }
  if (vis('resultats.comparaison')) {
    const r = Number(reglageCalque<number | string>(c, 'resultats.comparaison', 'phase', 0))
    if (r > 0 && res.phases[r - 1]) out.push({ type: 'discrete', id: 'comparaison', titre: `Comparaison : fantôme de la phase ${r} (${res.phases[r - 1].nom})`, phase: nomPhase, classes: [{ couleur: '#6c3fa0', texte: 'déformée de référence (filaire)' }] })
  }
  if (animation) out.push({ type: 'discrete', id: 'animation', titre: 'Lecture animée', phase: nomPhase, classes: [], note: 'interpolation purement visuelle entre deux phases, pas un résultat' })
  if (vis('resultats.enveloppes')) {
    out.push({ type: 'discrete', id: 'enveloppes', titre: `Enveloppe ${modeCalque(c, 'resultats.enveloppes', 'deformee') === 'moment' ? 'des moments' : 'de la déformée'} (toutes phases, fantôme)`, phase: 'toutes phases', classes: [] })
  }
  return out
}
