// Navigation depuis la maquette : analyse d'une sélection, fil d'Ariane, ancre d'URL partageable,
// points d'attention (vérifications ≥ 90 %), vérifications rattachées à un objet. Fonctions pures.
import type { ProjetCoupes, Resultats, Verif } from '../lib/api'
import { filtreAssemblage, FILTRE_LIERNE, verifsAppui } from './appuis'
import { SEUIL_ATTENTION } from '../lib/verifs'

export type TypeSelection = 'paroi' | 'appui' | 'lierne' | 'assemblage' | 'coupe' | 'coupe_locale' | 'fond' | 'bouchon' | 'couche' | 'surcharge' | 'terrain'

export interface SelectionAnalysee { type: TypeSelection; nom: string; k?: number; index?: number }

const TYPES: TypeSelection[] = ['paroi', 'appui', 'lierne', 'assemblage', 'coupe', 'coupe_locale', 'fond', 'bouchon', 'couche', 'surcharge', 'terrain']

/** « appui:B1 » -> { type: 'appui', nom: 'B1' } ; « paroi:2 » -> { type: 'paroi', k: 2 } ; null si inconnu. */
export function analyserSelection(id: string | null | undefined): SelectionAnalysee | null {
  if (!id) return null
  const [type, ...reste] = id.split(':')
  if (!TYPES.includes(type as TypeSelection)) return null
  const nom = reste.join(':')
  const out: SelectionAnalysee = { type: type as TypeSelection, nom }
  if (type === 'paroi') out.k = Number(nom) || 0
  if (type === 'couche' || type === 'surcharge') out.index = Number(nom) || 0
  return out
}

const HYDRO = /^(Fond de fouille|Boulance|Renard|Soulèvement|Gradient|Débit|Stabilité du fond)/
const PAROI = /^(Palplanches|Paroi moulée|Profilés de berlinoise|Blindage|Pieux)/

/** Vérifications rattachées à une sélection (toutes pour une coupe ou le vide). */
export function verifsPour(sel: SelectionAnalysee | null, res: Resultats, assemblages: Record<string, { appui: string | null }> = {}): Verif[] {
  const vs = res.verifications ?? []
  if (!sel || sel.type === 'coupe' || sel.type === 'coupe_locale') return vs
  switch (sel.type) {
    case 'paroi': return vs.filter((v) => PAROI.test(v.nom) || (v.categorie === 'geotechnique' && !HYDRO.test(v.nom)))
    case 'appui': return verifsAppui(vs, sel.nom, assemblages)
    case 'lierne': return verifsAppui(vs, sel.nom, assemblages, FILTRE_LIERNE)
    case 'assemblage': return vs.filter(filtreAssemblage(sel.nom))
    case 'fond': case 'bouchon': return vs.filter((v) => HYDRO.test(v.nom))
    default: return []
  }
}

export interface PointAttention { selection: string; libelle: string; taux: number | null; etat: Verif['etat']; phase: string | null }

/** Éléments dont une vérification dépasse le seuil (ou est non vérifiée), triés par taux décroissant. */
export function pointsAttention(res: Resultats, assemblages: Record<string, { appui: string | null }> = {}, seuil = SEUIL_ATTENTION): PointAttention[] {
  const noms = new Set(res.appuis.map((a) => a.nom))
  const out: PointAttention[] = []
  for (const v of res.verifications ?? []) {
    const grave = v.etat === 'non_ok' || (v.taux !== null && Number.isFinite(v.taux) && v.taux >= seuil)
    if (!grave) continue
    const tete = v.element.split(' ')[0]
    let selection: string
    if (assemblages[tete]) selection = `assemblage:${tete}`
    else if (noms.has(tete)) selection = v.nom.startsWith('Lierne') ? `lierne:${tete}` : `appui:${tete}`
    else if (HYDRO.test(v.nom)) selection = v.element.startsWith('bouchon') ? 'bouchon' : 'fond'
    else selection = 'paroi:0'
    out.push({ selection, libelle: `${v.nom} — ${v.element}`, taux: v.taux, etat: v.etat, phase: v.phase })
  }
  return out.sort((a, b) => (b.taux ?? -1) - (a.taux ?? -1))
}

export interface Miette { libelle: string; selection: string | null }

/** Fil d'Ariane : Projet › Coupe C1 › Appuis › B2 › A1. */
export function filAriane(sel: SelectionAnalysee | null, projet: ProjetCoupes | null, coupeActive: number, assemblages: Record<string, { appui: string | null }> = {}, nomsSurcharges: string[] = []): Miette[] {
  const out: Miette[] = [{ libelle: 'Projet', selection: null }]
  const coupe = projet && !projet.unique ? projet.coupes[coupeActive] : null
  if (coupe) out.push({ libelle: coupe.nom.split(' — ')[0], selection: `coupe:${coupe.nom}` })
  if (!sel) return out
  switch (sel.type) {
    case 'paroi': out.push({ libelle: 'Écran', selection: `paroi:${sel.k ?? 0}` }); break
    case 'appui': out.push({ libelle: 'Appuis', selection: null }, { libelle: sel.nom, selection: `appui:${sel.nom}` }); break
    case 'lierne': out.push({ libelle: 'Appuis', selection: null }, { libelle: sel.nom, selection: `appui:${sel.nom}` }, { libelle: 'lierne', selection: `lierne:${sel.nom}` }); break
    case 'assemblage': {
      const a = assemblages[sel.nom]?.appui
      out.push({ libelle: 'Appuis', selection: null })
      if (a) out.push({ libelle: a, selection: `appui:${a}` })
      out.push({ libelle: sel.nom, selection: `assemblage:${sel.nom}` })
      break
    }
    case 'coupe': if (!coupe || coupe.nom !== sel.nom) out.push({ libelle: sel.nom.split(' — ')[0], selection: `coupe:${sel.nom}` }); break
    case 'coupe_locale': out.push({ libelle: 'Courbes en un point', selection: 'coupe_locale' }); break
    case 'fond': out.push({ libelle: 'Fond de fouille', selection: 'fond' }); break
    case 'bouchon': out.push({ libelle: 'Fond de fouille', selection: 'fond' }, { libelle: 'Bouchon', selection: 'bouchon' }); break
    case 'couche': out.push({ libelle: 'Sol', selection: null }, { libelle: `Couche ${(sel.index ?? 0) + 1}`, selection: `couche:${sel.index ?? 0}` }); break
    case 'surcharge': out.push({ libelle: 'Surcharges', selection: null }, { libelle: nomsSurcharges[sel.index ?? 0] ?? sel.nom, selection: `surcharge:${sel.nom}` }); break
    case 'terrain': out.push({ libelle: 'Terrain', selection: null }, { libelle: sel.nom, selection: `terrain:${sel.nom}` }); break
  }
  return out
}

/** En-tête du panneau : « B2 · coupe C1 · phase 8 ». */
export function titreFiltre(sel: SelectionAnalysee | null, coupeNom: string | null, phase: number): string {
  const objet = !sel ? 'Projet' : sel.type === 'paroi' ? `Écran (côté ${sel.k ?? 0})` : sel.type === 'couche' ? `Couche ${(sel.index ?? 0) + 1}`
    : sel.type === 'coupe' ? sel.nom.split(' — ')[0] : sel.type === 'coupe_locale' ? 'Courbes en un point' : sel.type === 'fond' ? 'Fond de fouille' : sel.type === 'bouchon' ? 'Bouchon'
    : sel.type === 'lierne' ? `Lierne de ${sel.nom}` : sel.type === 'surcharge' ? `Surcharge ${(sel.index ?? 0) + 1}` : sel.nom
  return [objet, coupeNom ? `coupe ${coupeNom.split(' — ')[0]}` : null, phase === 0 ? 'état initial' : `phase ${phase}`].filter(Boolean).join(' · ')
}

// ------------------------------------------------------------------ ancre d'URL
export interface EtatAncre { coupe: number; phase: number; selection: string | null; prereglage: string | null }

/** `#c1-p8-s_appui:B2-l_structure` (coupe et phase numérotées à partir de 1 dans l'ancre : format d'URL inchangé,
 *  indépendant de la numérotation affichée où l'état initial est la phase 0). */
export function encoderAncre(e: EtatAncre): string {
  const parts = [`c${e.coupe + 1}`, `p${e.phase + 1}`]
  if (e.selection) parts.push(`s_${encodeURIComponent(e.selection)}`)
  if (e.prereglage) parts.push(`l_${encodeURIComponent(e.prereglage)}`)
  return `#${parts.join('-')}`
}

export function decoderAncre(hash: string): EtatAncre | null {
  const h = hash.replace(/^#/, '')
  if (!/^c\d+-p\d+/.test(h)) return null
  const out: EtatAncre = { coupe: 0, phase: 0, selection: null, prereglage: null }
  for (const part of h.split('-')) {
    if (/^c\d+$/.test(part)) out.coupe = Math.max(0, Number(part.slice(1)) - 1)
    else if (/^p\d+$/.test(part)) out.phase = Math.max(0, Number(part.slice(1)) - 1)
    else if (part.startsWith('s_')) out.selection = decodeURIComponent(part.slice(2))
    else if (part.startsWith('l_')) out.prereglage = decodeURIComponent(part.slice(2))
  }
  return out
}
