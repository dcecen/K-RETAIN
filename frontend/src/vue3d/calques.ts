// Gestion des calques de la vue 3D, à la manière d'un logiciel de CAO (fonctions pures).
// L'état n'est stocké que pour les calques « feuilles » ; l'état d'un groupe se déduit de ses enfants.
import type { EtatCalquesScene } from './scene'

export interface DefCalque {
  id: string
  nom: string
  enfants?: DefCalque[]
  /** Le plan de coupe s'applique à ce calque par défaut. */
  coupe?: boolean
  /** Visible par défaut. */
  visible?: boolean
  /** Modes d'affichage proposés (le premier est le mode par défaut). */
  modes?: { id: string; nom: string }[]
  /** Calques qui colorent la paroi : un seul actif à la fois (en mode couleur). */
  exclusif?: string
  /** Opacité par défaut. */
  opacite?: number
}

const MODES_COULEUR_AILETTES = [{ id: 'couleur', nom: 'Couleur' }, { id: 'ailettes', nom: 'Ailettes' }]

export const ARBRE_CALQUES: DefCalque[] = [
  { id: 'terrain', nom: 'Terrain', enfants: [
    { id: 'terrain.couches', nom: 'Couches de sol côté terre', coupe: true },
    { id: 'terrain.surface', nom: 'Terrain en pente, talus côté terre', coupe: true },
    { id: 'terrain.remblais', nom: 'Remblais', coupe: true },
  ] },
  { id: 'fouille', nom: 'Fouille', enfants: [
    { id: 'fouille.couches', nom: 'Couches de sol dans la fouille', coupe: true },
    { id: 'fouille.fond', nom: 'Fond de fouille', coupe: true },
    { id: 'fouille.bouchon', nom: 'Bouchon', coupe: true },
    { id: 'fouille.risbermes', nom: 'Risbermes, talus, gradins', coupe: true },
  ] },
  { id: 'eau', nom: 'Eau', enfants: [
    { id: 'eau.amont', nom: 'Nappe amont', coupe: true },
    { id: 'eau.aval', nom: 'Nappe aval', coupe: true },
    { id: 'eau.piezo', nom: 'Surface piézométrique', coupe: true },
    { id: 'eau.gradients', nom: 'Gradients de sortie' },
    { id: 'eau.equipotentielles', nom: 'Équipotentielles (plan de coupe)' },
  ] },
  { id: 'surcharges', nom: 'Surcharges', enfants: [
    { id: 'surcharges.volumes', nom: 'Surcharges (emprises et valeurs)' },
    { id: 'surcharges.pressions', nom: 'Pression induite sur la paroi', visible: false },
  ] },
  { id: 'environnement', nom: 'Environnement', enfants: [
    { id: 'environnement.batiments', nom: 'Bâtiments voisins', opacite: 0.6 },
    { id: 'environnement.voirie', nom: 'Voirie et réseaux' },
    { id: 'environnement.engins', nom: 'Grues et engins' },
  ] },
  { id: 'paroi', nom: 'Paroi', enfants: [
    { id: 'paroi.elements', nom: 'Paroi (panneaux, palplanches, pieux, profilés)' },
  ] },
  { id: 'appuis', nom: 'Appuis', enfants: [
    { id: 'appuis.butons', nom: 'Butons et bracons' },
    { id: 'appuis.liernes', nom: 'Liernes' },
    { id: 'appuis.tirants', nom: 'Tirants' },
    { id: 'appuis.dalles', nom: 'Dalles et radier' },
    { id: 'appuis.assemblages', nom: 'Assemblages' },
  ] },
  { id: 'resultats', nom: 'Résultats', enfants: [
    { id: 'resultats.deformee', nom: 'Déformée de la paroi', visible: false },
    { id: 'resultats.deplacement', nom: 'Déplacement (couleur)', visible: false, exclusif: 'couleur-paroi',
      modes: [{ id: 'absolu', nom: '|y|' }, { id: 'signe', nom: 'y signé' }] },
    { id: 'resultats.moment', nom: 'Moment fléchissant', visible: false, exclusif: 'couleur-paroi', modes: MODES_COULEUR_AILETTES },
    { id: 'resultats.tranchant', nom: 'Effort tranchant', visible: false, exclusif: 'couleur-paroi', modes: [{ id: 'ailettes', nom: 'Ailettes' }, { id: 'couleur', nom: 'Couleur' }] },
    { id: 'resultats.pressions', nom: 'Pressions des terres et de l\'eau', visible: false,
      modes: [{ id: 'deux', nom: 'Deux faces' }, { id: 'terre', nom: 'Face terre' }, { id: 'fouille', nom: 'Face fouille' }] },
    { id: 'resultats.efforts', nom: 'Efforts dans les appuis', visible: false, modes: [{ id: 'service', nom: 'Service' }, { id: 'elu', nom: 'ELU' }] },
    { id: 'resultats.fleches', nom: 'Flèche des butons et des liernes', visible: false,
      modes: [{ id: 'compression', nom: 'Avec compression' }, { id: 'poids_propre', nom: 'Poids propre seul' }] },
    { id: 'resultats.taux', nom: 'Taux de travail', visible: false, exclusif: 'couleur-paroi' },
    { id: 'resultats.enveloppes', nom: 'Enveloppes (toutes phases)', visible: false, modes: [{ id: 'deformee', nom: 'Déformée' }, { id: 'moment', nom: 'Moment' }] },
    { id: 'resultats.extremes', nom: 'Étiquettes d\'extrêmes', visible: false },
    { id: 'resultats.alertes', nom: 'Alertes (taux ≥ 90 %)' },
  ] },
  { id: 'coupes', nom: 'Coupes de calcul', enfants: [
    { id: 'coupes.plans', nom: 'Plans de coupe nommés' },
    { id: 'coupes.zones', nom: 'Zones d\'application', visible: false },
    { id: 'coupes.diagrammes', nom: 'Diagrammes dans le plan de coupe', visible: false,
      modes: [{ id: 'deplacement', nom: 'Déplacement' }, { id: 'moment', nom: 'Moment' }, { id: 'pressions', nom: 'Pressions' }] },
    { id: 'coupes.locale', nom: 'Coupe locale (« Couper ici »)' },
  ] },
  { id: 'annotations', nom: 'Annotations', enfants: [
    { id: 'annotations.noms', nom: 'Noms des appuis et objets' },
    { id: 'annotations.cotes', nom: 'Cotes et niveaux' },
  ] },
  { id: 'outils', nom: 'Outils', enfants: [
    { id: 'outils.grille', nom: 'Grille' },
    { id: 'outils.axes', nom: 'Axes et repère nord' },
    { id: 'outils.plan_coupe', nom: 'Plan de coupe' },
    { id: 'outils.mesure', nom: 'Mesures' },
  ] },
]

export interface EtatCalque {
  visible: boolean
  opacite: number
  verrou: boolean
  coupe: boolean
  mode?: string
  /** Réglages propres au calque (amplification, échelle, palette, seuils…). */
  reglages?: Record<string, number | string | boolean>
}

export interface EtatCalques {
  feuilles: Record<string, EtatCalque>
  /** État mémorisé avant une isolation (un second clic le restaure). */
  isolation?: { id: string; avant: Record<string, EtatCalque> } | null
}

// ------------------------------------------------------------------ parcours de l'arbre
const INDEX = new Map<string, DefCalque>()
const PARENT = new Map<string, string>()
;(function indexer(liste: DefCalque[], parent?: string) {
  for (const d of liste) {
    INDEX.set(d.id, d)
    if (parent) PARENT.set(d.id, parent)
    if (d.enfants) indexer(d.enfants, d.id)
  }
})(ARBRE_CALQUES)

export function definition(id: string): DefCalque | undefined {
  return INDEX.get(id)
}

/** Feuilles sous un calque (lui-même si c'est une feuille). */
export function feuillesDe(id: string): string[] {
  const d = INDEX.get(id)
  if (!d) return []
  if (!d.enfants) return [id]
  return d.enfants.flatMap((e) => feuillesDe(e.id))
}

export const FEUILLES: string[] = ARBRE_CALQUES.flatMap((d) => feuillesDe(d.id))

/** Ancêtres d'un calque, du plus proche au plus lointain. */
export function ancetres(id: string): string[] {
  const out: string[] = []
  let p = PARENT.get(id)
  while (p) { out.push(p); p = PARENT.get(p) }
  return out
}

/** Feuille porteuse d'un identifiant de calque utilisé par la scène (préfixe le plus long connu). */
function feuillePour(id: string): string | null {
  if (INDEX.has(id) && !INDEX.get(id)!.enfants) return id
  let k = id
  while (k.includes('.')) {
    k = k.slice(0, k.lastIndexOf('.'))
    if (INDEX.has(k) && !INDEX.get(k)!.enfants) return k
  }
  return null
}

// ------------------------------------------------------------------ état
function etatDefaut(d: DefCalque): EtatCalque {
  return { visible: d.visible ?? true, opacite: d.opacite ?? 1, verrou: false, coupe: !!d.coupe, ...(d.modes ? { mode: d.modes[0].id } : {}) }
}

export function etatInitial(): EtatCalques {
  const feuilles: Record<string, EtatCalque> = {}
  for (const id of FEUILLES) feuilles[id] = etatDefaut(INDEX.get(id)!)
  return { feuilles, isolation: null }
}

/** Complète un état chargé (stockage, préréglage, ancienne version) avec les calques manquants. */
export function normaliser(e: Partial<EtatCalques> | null | undefined): EtatCalques {
  const base = etatInitial()
  if (!e?.feuilles) return base
  for (const id of FEUILLES) if (e.feuilles[id]) base.feuilles[id] = { ...base.feuilles[id], ...e.feuilles[id] }
  base.isolation = e.isolation ?? null
  return base
}

function copier(f: Record<string, EtatCalque>): Record<string, EtatCalque> {
  const out: Record<string, EtatCalque> = {}
  for (const [k, v] of Object.entries(f)) out[k] = { ...v, ...(v.reglages ? { reglages: { ...v.reglages } } : {}) }
  return out
}

/** Visibilité d'un groupe ou d'une feuille : vrai, faux ou « partiel » (état intermédiaire de la case). */
export function visibiliteGroupe(e: EtatCalques, id: string): boolean | 'partiel' {
  const fs = feuillesDe(id)
  const n = fs.filter((f) => e.feuilles[f]?.visible).length
  return n === 0 ? false : n === fs.length ? true : 'partiel'
}

/** Modes couleur actifs en conflit (calques qui colorent la paroi). */
function enCouleur(e: EtatCalques, id: string): boolean {
  const m = e.feuilles[id]?.mode
  return m === undefined || m === 'couleur' || m === 'absolu' || m === 'signe'
}

function appliquerExclusivite(e: EtatCalques, id: string) {
  const d = INDEX.get(id)
  if (!d?.exclusif || !e.feuilles[id].visible || !enCouleur(e, id)) return
  for (const f of FEUILLES) {
    if (f === id) continue
    const df = INDEX.get(f)!
    if (df.exclusif === d.exclusif && e.feuilles[f].visible && enCouleur(e, f)) e.feuilles[f].visible = false
  }
}

/** Coche ou décoche un calque ; un groupe propage à toutes ses feuilles. */
export function definirVisible(e: EtatCalques, id: string, visible: boolean): EtatCalques {
  const out: EtatCalques = { feuilles: copier(e.feuilles), isolation: e.isolation ?? null }
  const fs = feuillesDe(id)
  for (const f of fs) out.feuilles[f].visible = visible
  if (fs.length === 1) appliquerExclusivite(out, fs[0])
  else if (visible) {
    // un groupe coché n'active qu'un seul calque coloré par groupe d'exclusivité
    const vus = new Set<string>()
    for (const f of fs) {
      const ex = INDEX.get(f)!.exclusif
      if (!ex || !enCouleur(out, f)) continue
      if (vus.has(ex)) out.feuilles[f].visible = false
      vus.add(ex)
    }
  }
  return out
}

function modifierFeuilles(e: EtatCalques, id: string, f: (x: EtatCalque) => void): EtatCalques {
  const out: EtatCalques = { feuilles: copier(e.feuilles), isolation: e.isolation ?? null }
  for (const k of feuillesDe(id)) f(out.feuilles[k])
  return out
}

export function definirOpacite(e: EtatCalques, id: string, opacite: number): EtatCalques {
  const o = Math.min(Math.max(opacite, 0), 1)
  return modifierFeuilles(e, id, (x) => { x.opacite = o })
}

export function definirVerrou(e: EtatCalques, id: string, verrou: boolean): EtatCalques {
  return modifierFeuilles(e, id, (x) => { x.verrou = verrou })
}

export function definirCoupe(e: EtatCalques, id: string, coupe: boolean): EtatCalques {
  return modifierFeuilles(e, id, (x) => { x.coupe = coupe })
}

export function definirMode(e: EtatCalques, id: string, mode: string): EtatCalques {
  const out = modifierFeuilles(e, id, (x) => { x.mode = mode })
  for (const f of feuillesDe(id)) appliquerExclusivite(out, f)
  return out
}

export function definirReglage(e: EtatCalques, id: string, cle: string, valeur: number | string | boolean): EtatCalques {
  return modifierFeuilles(e, id, (x) => { x.reglages = { ...(x.reglages ?? {}), [cle]: valeur } })
}

/** Isole un calque (seules ses feuilles restent visibles) ; un second appel sur le même calque restaure l'état exact d'avant. */
export function basculerIsolation(e: EtatCalques, id: string): EtatCalques {
  if (e.isolation && e.isolation.id === id) return { feuilles: copier(e.isolation.avant), isolation: null }
  const avant = e.isolation ? e.isolation.avant : e.feuilles
  const garder = new Set(feuillesDe(id))
  const feuilles = copier(e.feuilles)
  for (const f of FEUILLES) feuilles[f].visible = garder.has(f) ? (garder.size === 1 ? true : e.feuilles[f].visible || !feuillesDe(id).some((g) => e.feuilles[g].visible)) : false
  return { feuilles, isolation: { id, avant: copier(avant) } }
}

// ------------------------------------------------------------------ recherche
const sansAccents = (s: string) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()

/** Calques dont le nom contient le texte (sans tenir compte des accents), avec leurs ancêtres. */
export function rechercher(texte: string): Set<string> | null {
  const t = sansAccents(texte.trim())
  if (!t) return null
  const out = new Set<string>()
  for (const [id, d] of INDEX) {
    if (sansAccents(d.nom).includes(t) || id.includes(t)) {
      out.add(id)
      for (const a of ancetres(id)) out.add(a)
      for (const f of feuillesDe(id)) out.add(f)
    }
  }
  return out
}

// ------------------------------------------------------------------ préréglages
export interface Prereglage {
  id: string
  nom: string
  description: string
  livre?: boolean
  etat?: EtatCalques
}

/** Construit un état où seules les feuilles des calques listés sont visibles. */
function seulement(ids: string[], reglages: (e: EtatCalques) => void = () => {}): EtatCalques {
  const e = etatInitial()
  const garder = new Set(ids.flatMap(feuillesDe))
  for (const f of FEUILLES) e.feuilles[f].visible = garder.has(f)
  reglages(e)
  return e
}

const LIVRES: Record<string, { nom: string; description: string; etat: () => EtatCalques }> = {
  chantier: {
    nom: 'Chantier', description: 'Terrain avec talus et risbermes, eau, paroi, appuis, surcharges, environnement',
    etat: () => seulement(['terrain', 'fouille', 'eau.amont', 'eau.aval', 'surcharges.volumes', 'environnement', 'paroi', 'appuis', 'annotations', 'outils.grille', 'outils.axes', 'outils.plan_coupe', 'resultats.alertes', 'coupes.plans', 'coupes.locale']),
  },
  structure: {
    nom: 'Structure', description: 'Paroi, appuis et assemblages, sans terrain',
    etat: () => seulement(['paroi', 'appuis', 'annotations.noms', 'outils.axes', 'resultats.alertes']),
  },
  resultats_paroi: {
    nom: 'Résultats paroi', description: 'Paroi déformée colorée, enveloppes, étiquettes d\'extrêmes',
    etat: () => seulement(['paroi', 'resultats.deformee', 'resultats.deplacement', 'resultats.enveloppes', 'resultats.extremes', 'fouille.fond', 'outils.axes', 'annotations.cotes'],
      (e) => { e.feuilles['paroi.elements'].opacite = 0.15 }),
  },
  resultats_appuis: {
    nom: 'Résultats appuis', description: 'Appuis colorés par effort, flèche des butons, étiquettes',
    etat: () => seulement(['paroi', 'appuis', 'resultats.efforts', 'resultats.fleches', 'resultats.alertes', 'annotations.noms', 'outils.axes'],
      (e) => { e.feuilles['paroi.elements'].opacite = 0.25 }),
  },
  coupes: {
    nom: 'Coupes', description: 'Paroi en fantôme, plans de coupe nommés avec leurs diagrammes, zones d\'application',
    etat: () => seulement(['paroi', 'coupes', 'fouille.fond', 'outils.axes', 'annotations.cotes'],
      (e) => { e.feuilles['paroi.elements'].opacite = 0.2 }),
  },
  hydraulique: {
    nom: 'Hydraulique', description: 'Eau, bouchon, équipotentielles, gradients',
    etat: () => seulement(['eau', 'fouille.bouchon', 'fouille.fond', 'paroi', 'outils.plan_coupe', 'annotations.cotes'],
      (e) => { e.feuilles['paroi.elements'].opacite = 0.4 }),
  },
  presentation: {
    nom: 'Présentation', description: 'Tout ce qui est visuel, sans outils ni étiquettes techniques',
    etat: () => seulement(['terrain', 'fouille', 'eau.amont', 'eau.aval', 'surcharges.volumes', 'environnement', 'paroi', 'appuis']),
  },
}

export const PREREGLAGES_LIVRES: Prereglage[] = Object.entries(LIVRES).map(([id, p]) => ({ id, nom: p.nom, description: p.description, livre: true }))

export function etatPrereglage(id: string, perso: Prereglage[] = []): EtatCalques | null {
  if (LIVRES[id]) return LIVRES[id].etat()
  const p = perso.find((x) => x.id === id)
  return p?.etat ? normaliser(p.etat) : null
}

export function enregistrerPrereglage(perso: Prereglage[], nom: string, etat: EtatCalques): Prereglage[] {
  const id = `perso.${sansAccents(nom).replace(/[^a-z0-9]+/g, '_')}`
  const p: Prereglage = { id, nom, description: 'Préréglage enregistré', etat: { feuilles: copier(etat.feuilles), isolation: null } }
  return [...perso.filter((x) => x.id !== id), p]
}

export function exporterJson(etat: EtatCalques, perso: Prereglage[] = []): string {
  return JSON.stringify({ format: 'retainwall.calques', version: 1, etat: { feuilles: etat.feuilles }, prereglages: perso }, null, 1)
}

export function importerJson(texte: string): { etat: EtatCalques; prereglages: Prereglage[] } {
  const d = JSON.parse(texte)
  if (d?.format !== 'retainwall.calques') throw new Error('fichier de calques RetainWall attendu')
  return { etat: normaliser(d.etat), prereglages: Array.isArray(d.prereglages) ? d.prereglages : [] }
}

// ------------------------------------------------------------------ stockage local
const CLE_ETAT = 'retainwall.calques.etat'
const CLE_PERSO = 'retainwall.calques.prereglages'

export function lireStockage(): { etat: EtatCalques; perso: Prereglage[] } {
  try {
    const e = localStorage.getItem(CLE_ETAT)
    const p = localStorage.getItem(CLE_PERSO)
    return { etat: normaliser(e ? JSON.parse(e) : null), perso: p ? JSON.parse(p) : [] }
  } catch {
    return { etat: etatInitial(), perso: [] }
  }
}

export function ecrireStockage(etat: EtatCalques, perso: Prereglage[]) {
  try {
    localStorage.setItem(CLE_ETAT, JSON.stringify(etat))
    localStorage.setItem(CLE_PERSO, JSON.stringify(perso))
  } catch { /* stockage indisponible : l'état reste en mémoire */ }
}

// ------------------------------------------------------------------ passage à la scène
export function versScene(e: EtatCalques): EtatCalquesScene & { mode(id: string): string | undefined; reglage<T extends number | string | boolean>(id: string, cle: string, defaut: T): T } {
  const f = (id: string) => {
    const k = feuillePour(id)
    return k ? e.feuilles[k] : undefined
  }
  return {
    visible: (id) => f(id)?.visible ?? true,
    opacite: (id) => f(id)?.opacite ?? 1,
    verrouille: (id) => f(id)?.verrou ?? false,
    coupe: (id) => f(id)?.coupe ?? false,
    mode: (id) => f(id)?.mode,
    reglage: <T extends number | string | boolean>(id: string, cle: string, defaut: T): T => (f(id)?.reglages?.[cle] as T | undefined) ?? defaut,
  }
}

// ------------------------------------------------------------------ réglages propres aux calques de résultats
export interface DefReglage {
  cle: string
  nom: string
  type: 'nombre' | 'choix' | 'bool'
  defaut: number | string | boolean
  min?: number
  max?: number
  pas?: number
  options?: { id: string; nom: string }[]
  /** « auto » accepté pour un nombre (valeur 0). */
  auto?: boolean
}

const CHOIX_ECHELLE = [{ id: 'fixe', nom: 'fixe (toutes phases)' }, { id: 'phase', nom: 'par phase' }]
const CHOIX_PALETTE = [{ id: 'divergente', nom: 'bleu → rouge' }, { id: 'sequentielle', nom: 'viridis' }, { id: 'signe', nom: 'signée' }]

export const REGLAGES: Record<string, DefReglage[]> = {
  'resultats.deformee': [
    { cle: 'amplification', nom: 'amplification ×', type: 'nombre', defaut: 'auto', min: 1, max: 2000, pas: 1, auto: true },
    { cle: 'fantome', nom: 'paroi initiale en fantôme', type: 'bool', defaut: true },
  ],
  'resultats.deplacement': [
    { cle: 'echelle', nom: 'échelle', type: 'choix', defaut: 'fixe', options: CHOIX_ECHELLE },
    { cle: 'palette', nom: 'palette', type: 'choix', defaut: 'divergente', options: CHOIX_PALETTE },
  ],
  'resultats.moment': [
    { cle: 'echelle', nom: 'échelle', type: 'choix', defaut: 'fixe', options: CHOIX_ECHELLE },
    { cle: 'echelle_ailettes', nom: 'taille des ailettes ×', type: 'nombre', defaut: 1, min: 0.1, max: 10, pas: 0.1 },
  ],
  'resultats.tranchant': [
    { cle: 'echelle', nom: 'échelle', type: 'choix', defaut: 'fixe', options: CHOIX_ECHELLE },
    { cle: 'echelle_ailettes', nom: 'taille des ailettes ×', type: 'nombre', defaut: 1, min: 0.1, max: 10, pas: 0.1 },
  ],
  'resultats.pressions': [{ cle: 'echelle_ailettes', nom: 'taille des ailettes ×', type: 'nombre', defaut: 1, min: 0.1, max: 10, pas: 0.1 }],
  'resultats.efforts': [{ cle: 'etiquettes', nom: 'étiquettes', type: 'bool', defaut: true }],
  'resultats.fleches': [
    { cle: 'amplification', nom: 'amplification ×', type: 'nombre', defaut: 'auto', min: 1, max: 2000, pas: 1, auto: true },
    { cle: 'etiquettes', nom: 'étiquettes', type: 'bool', defaut: true },
    { cle: 'raccourcissement', nom: 'raccourcissement axial', type: 'bool', defaut: false },
  ],
  'resultats.taux': [
    { cle: 'orange', nom: 'seuil orange', type: 'nombre', defaut: 0.9, min: 0.1, max: 2, pas: 0.05 },
    { cle: 'rouge', nom: 'seuil rouge', type: 'nombre', defaut: 1.0, min: 0.1, max: 2, pas: 0.05 },
  ],
  'coupes.zones': [{ cle: 'lisser', nom: 'lisser aux jonctions (visuel)', type: 'bool', defaut: false }],
  'surcharges.volumes': [{ cle: 'echelle', nom: 'hauteur : 1 m pour (kPa)', type: 'nombre', defaut: 20, min: 1, max: 500, pas: 5 }],
}
