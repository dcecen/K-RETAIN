// Types des réponses du serveur de calcul et appels HTTP.

import type { Schema as SchemaAssemblage, TypeAssemblage } from './assemblages'

export interface ErreurScript {
  ligne: number | null
  chemin: string
  message: string
  /** « erreur » bloque le calcul ; « avertissement » (mot-clé inconnu ignoré) ne l'empêche pas. */
  niveau?: 'erreur' | 'avertissement'
}

export interface Pressions {
  z: number[]
  p: number[]
  pa: number[]
  pp: number[]
  p0: number[]
}

export interface AppuiPhase {
  nom: string
  cote: number
  type: string
  effort_kN_m: number
  effort_axial_kN: number
  actif: boolean
  /** Effort de calcul (× gamma_effets ELU fondamental) ; null si le coefficient de norme manque. */
  effort_elu_kN?: number | null
  effort_elu_kN_m?: number | null
  /** Flèches issues du module de vérification (mm) ; null si l'élément n'est pas dans la base ou s'il est instable. */
  fleche_mm?: number | null
  fleche_poids_propre_mm?: number | null
  raccourcissement_mm?: number | null
  N_cr_kN?: number | null
  fleche_lierne_mm?: number | null
}

export interface DefAppui {
  nom: string
  cote: number
  type: string
  angle: number
  element: string | null
  espacement: number
  precharge: number
  lierne: string | null
  longueur: number | null
  raideur: number
  unilateral: boolean
}

export interface Hydro {
  regime: string
  h_amont: number | null
  h_aval: number | null
  gradient_sortie_max: number
  gradient_sortie_moyen: number
  debit_m3_s_m: number
  debit_m3_h_m: number
  charge_base_prisme: number
  gradient_sortie_x: number[]
  gradient_sortie: number[]
  bouchon: { type: string; toit: number; base: number; k: number | null; epaisseur: number } | null
  charge_base_bouchon: number | null
  gradient_bouchon: number | null
  avertissements: string[]
  x?: number[]
  z?: number[]
  h?: (number | null)[][]
  equipotentielles?: { niveau: number; segments: number[][] }[]
  charge_fond?: { x: number[]; h: (number | null)[] }
  charge_mi_fiche?: { x: number[]; h: (number | null)[] }
}

export interface PhaseRes {
  nom: string
  ok: boolean
  message: string
  terrain_amont: number
  terrain_aval: number
  eau_amont: number | null
  eau_aval: number | null
  /** Fond de fouille par zone (geometrie.fouille.zones ; clé « defaut » = reste de la fouille). */
  fonds?: Record<string, number | null>
  z?: number[]
  y_mm?: number[]
  z_diag?: number[]
  M?: number[]
  V?: number[]
  pressions?: { amont: Pressions; aval: Pressions }
  /** Butée limite aval sans l'effet des risbermes/talus/gradins (présent seulement quand un objet agit). */
  pp_sans_terrain?: number[]
  eau?: { z: number[]; u_amont: number[]; u_aval: number[] }
  appuis?: AppuiPhase[]
  actions: { type: string; texte: string }[]
  parent: number | null
  enfants: number[]
  depuis: string | null
  iterations?: number
  hydro?: Hydro | null
  synthese?: {
    y_max_mm: number
    z_y_max: number
    y_tete_mm: number
    M_max: number
    M_min: number
    V_absmax: number
    butee_mobilisee: number | null
    /** Résultantes aval (kN/m) des pressions mobilisées et limites, valeurs caractéristiques. */
    Bm_kN_m?: number | null
    Bt_kN_m?: number | null
  }
}

/** Donnée d'une fiche de vérification : symbole, libellé, valeur (nombre ou texte), unité, origine
 *  (calcul | script | base matériaux | norme:<fichier>:<clé>). */
export interface DonneeVerif { symbole: string; libelle: string; valeur: number | string | null; unite: string; origine: string }

export interface Verif {
  nom: string
  categorie: 'geotechnique' | 'structure'
  element: string
  phase: string | null
  etat: 'ok' | 'attention' | 'non_ok' | 'non_verifiable'
  taux: number | null
  detail: string
  source: string
  manquants: string[]
  reperes: number[]
  /** Fiche détaillée (sout/verifs.py) : famille (sous-onglet), principe, données, étapes du calcul, schéma. */
  famille: string
  principe: string
  donnees: DonneeVerif[]
  etapes: string[]
  schema: ({ type: string } & Record<string, unknown>) | null
}

export interface Dimensionnant {
  deplacement?: { valeur_mm: number; phase: string }
  moment_positif?: { valeur: number; phase: string }
  moment_negatif?: { valeur: number; phase: string }
  tranchant?: { valeur: number; phase: string }
  appuis?: Record<string, { effort_kN_m: number; effort_axial_kN: number; phase: string }>
}

/** Géométrie de la maquette 3D renvoyée avec le calcul (repère du plan : x, y en m ; cotes z en m). */
export interface AppuiMaquette {
  type: string
  cote: number
  angle: number
  element: string | null
  lierne: string | null
  longueur: number | null
  longueur_libre: number | null
  longueur_scellee: number | null
  epaisseur: number | null
  pied_bracon: number | null
  espacement: number
  D: number
}

/** Surcharge telle que la maquette la reçoit (bloc surcharges du script, phases et profil Δσv au droit de la coupe). */
export interface SurchargeMaquette {
  nom: string
  type: string
  q: number
  cote_ecran: string
  phase_debut: number          // 0 = dès l'état initial, k = k-ième phase du script
  phase_fin: number
  distance?: number
  largeur?: number | null
  cote?: number | null
  emprise?: number[] | null
  position?: number[] | null
  trace?: number[][] | null
  profondeur?: number
  cotes_paroi?: string[] | null
  niveaux?: number | null
  modele?: string | null
  profil?: { z: number[]; dsv: number[]; methode: string }
}

export interface ObjetTerrainMaquette {
  nom: string
  type: string                 // risberme, talus, gradins, pente, remblai
  face: 'amont' | 'aval'
  profil: number[][]           // [distance à la paroi, cote]
  base: number
  gamma: number
  methode: string
  phase_debut: number
  phase_fin: number
  cotes_paroi: string[] | null
  cote_equivalente: number | null
  /** Tronçon [de, a] le long des côtés concernés (m) ; absent = côté entier. */
  troncon?: number[] | null
}

/** Zone de terrain côté terre (geometrie.terrain.zones) : cote, pente ou profil sur des côtés / tronçons. */
export interface ZoneTerrainMaquette {
  nom: string
  cotes: string[] | null
  de: number | null
  a: number | null
  cote: number | null
  pente_beta: number | null
  profil: number[][] | null
  methode_pente: string
}

export interface TerrainMaquette {
  profil: number[][] | null
  pente_beta: number | null
  methode_pente: string
  cote_paroi: string | number | (string | number)[] | null
  remblai: { cote: number; materiau: string | null; phase: number | string } | null
  objets: ObjetTerrainMaquette[]
  zones_terrain?: ZoneTerrainMaquette[]
}

/** Zone de fond de fouille (geometrie.fouille.zones) avec son polygone en plan. */
export interface ZoneFondMaquette { nom: string; cotes: string[] | null; de: number | null; a: number | null; polygone: number[][] }

export interface Maquette {
  projet: string
  paroi: { type: string; tete: number; pied: number; epaisseur: number; diametre: number; entraxe: number
    profil: string | null; b: number; h: number; tf: number; tw: number; blindage: number | null }
  contour: number[][]
  plan_defaut: boolean
  couches: { nom: string; toit: number }[]
  z_bas: number
  appuis: Record<string, AppuiMaquette>
  plan_appuis: { appui: string; de: number[]; a: number[] }[]
  i_critique: (number | null)[]
  /** Géométrie normalisée : noms des côtés, contour fermé ou ouvert, zones de fond, longueur de plaque modélisée. */
  cotes?: Record<string, number>
  ferme?: boolean
  zones?: ZoneFondMaquette[]
  longueur_modele?: number | null
  assemblages: Record<string, { type: string; appui: string | null }>
  surcharges?: SurchargeMaquette[]
  terrain?: TerrainMaquette
  coupe_calcul?: { x: number; y: number; ni: number[]; t: number[]; k: number; s: number; cote: string | null; nom: string | null } | null
}

export interface Resultats {
  projet: string
  complet: boolean
  avertissements: string[]
  conventions: Record<string, string>
  paroi: { tete: number; pied: number; type?: string; [k: string]: unknown }
  couches: {
    nom: string; toit: number; kah?: number | null; kph?: number | null; k0?: number | null; kh?: number | null
    /** Méthodes et données telles qu'utilisées par le calcul (traçabilité). */
    methode_k?: string; methode_kh?: string; k0_source?: string
    phi?: number; c?: number; delta_a_sur_phi?: number; delta_p_sur_phi?: number
  }[]
  hydraulique?: Record<string, unknown> | null
  appuis: DefAppui[]
  phases: PhaseRes[]
  enveloppes: {
    z?: number[]
    y_min_mm?: number[]
    y_max_mm?: number[]
    z_diag?: number[]
    M_min?: number[]
    M_max?: number[]
    V_min?: number[]
    V_max?: number[]
  }
  dimensionnant: Dimensionnant
  maquette?: Maquette
  verifications?: Verif[]
  suggestions?: { appui: string; element: string | null; taux: number | null; message: string }[]
  pseudo3d?: {
    s: number[]
    z: number[]
    avertissements: string[]
    /** Abscisses des angles (sommets du contour ou angle de la paroi droite) et mode fouille fermée. */
    sommets?: number[]
    fermee?: boolean
    /** Longueur développée modélisée (m) : périmètre en fouille fermée, longueur de la paroi droite sinon. */
    longueur?: number
    phases: {
      nom: string
      ok: boolean
      message: string
      y_mm?: number[][]
      M?: number[][]
      /** Moment horizontal Ms (kN·m/m) et effort tranchant V (kN/m, statique de chaque ligne verticale). */
      Ms?: number[][]
      V?: number[][]
      y_max_mm?: number
      y_max_2d_mm?: number
      Mz_max?: number
      Mz_min?: number
      Ms_absmax?: number
      V_absmax?: number
      Mzs_absmax?: number
      /** Réactions des lignes pénalisées (bords, angle), kN par ligne ; bilan d'équilibre (kN, kN·m). */
      reactions?: { s: number[]; total_kN: number[] }
      bilan?: Record<string, number>
      /** Effort en kN par appui ponctuel ; espacement (m) et angle (°) pour revenir au kN/m et à l'effort axial ;
       *  s2 : abscisse de l'autre extrémité d'un buton reliant deux parois (fouille fermée). */
      appuis?: { nom: string; s: number; s2?: number | null; effort: number; actif: boolean; espacement?: number; angle?: number }[]
    }[]
  }
}

/** Script du menu Fichier : modèle, exemple de projet ou exemple élémentaire (exemples/elementaires/2d, 3d) ;
 *  pour les exemples élémentaires, titre (clé projet), résultat attendu et source lus dans l'en-tête. */
export interface Exemple { nom: string; texte: string; groupe?: string; titre?: string; attendu?: string; source?: string }

/** Coupe de calcul d'un projet 2D (voir backend/sout/script/coupes.py). */
export interface CoupeRes {
  nom: string
  zone: { k: number; de: number; a: number }      // arête du contour et tronçon (abscisses locales, m) ; k = −1 : coupe unique
  trace: number[][]
  empreinte: string
  herite: string[]
  local: string[]
  correspondance: number[]                        // indice projet de chaque phase de la coupe
  resultats?: Resultats                           // absent pour la première coupe (= resultats de la réponse)
  en_cache?: boolean
  automatique?: boolean                           // coupe créée par calcul.coupes_automatiques (une par côté du contour)
}

export interface SyntheseVerif {
  nom: string
  element: string
  categorie: string | null
  coupe: string
  taux: number | null
  etat: Verif['etat']
  phase: string | null
  detail: string
}

export interface ProjetCoupes {
  unique: boolean
  contour: number[][]
  orphelins: { k: number; de: number; a: number }[]
  avertissements: string[]
  coupes: CoupeRes[]
  phasage_projet: string[]
  synthese: { verifications: SyntheseVerif[]; chiffres: Record<string, unknown> }
}

export interface ReponseCalcul {
  ok: boolean
  erreurs: ErreurScript[]
  avertissements?: ErreurScript[]
  resultats?: Resultats
  projet?: ProjetCoupes
  coupe?: CoupeRes
}

/** Erreur renvoyée par le serveur de calcul (code HTTP et message en français du serveur). */
export class ErreurServeur extends Error {
  statut: number
  constructor(message: string, statut: number) {
    super(message)
    this.name = 'ErreurServeur'
    this.statut = statut
  }
}

export const MESSAGE_INJOIGNABLE = 'Serveur de calcul injoignable : vérifiez qu’il est lancé (fenêtre « Lancer RetainWall »).'

/** Message lisible d'une erreur quelconque, sans le préfixe technique « Error: ». */
export function messageErreur(e: unknown): string {
  if (e instanceof Error) return e.message || e.name
  return String(e)
}

/** Message d'une réponse en erreur : `erreurs[0].message` (réponses du calcul), `detail` texte ou liste (FastAPI). */
async function messageReponse(r: Response): Promise<string> {
  const d = (await r.json().catch(() => null)) as { erreurs?: { message?: string }[]; detail?: unknown } | null
  const m = d?.erreurs?.[0]?.message
  if (typeof m === 'string' && m) return m
  if (typeof d?.detail === 'string') return d.detail
  if (Array.isArray(d?.detail)) return d.detail.map((x) => (typeof x === 'string' ? x : (x as { msg?: string }).msg ?? JSON.stringify(x))).join(' ; ')
  return `erreur ${r.status} du serveur de calcul`
}

async function post<T>(url: string, corps: unknown): Promise<T> {
  let r: Response
  try {
    r = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(corps),
    })
  } catch {
    throw new Error(MESSAGE_INJOIGNABLE)
  }
  if (!r.ok) throw new ErreurServeur(await messageReponse(r), r.status)
  return r.json() as Promise<T>
}

/** Une valeur du référentiel docs/normes : clé pointée, valeur (null = TODO-NORME) et source. */
export interface EntreeNorme { cle: string; valeur: number | string | boolean | null; source: string }

export const api = {
  normes: () => fetch('/api/normes').then((r) => { if (!r.ok) throw new Error(`erreur ${r.status}`); return r.json() as Promise<{ dossier: string; fichiers: Record<string, EntreeNorme[]> }> }),
  calcul: (texte: string, coupe?: string) => post<ReponseCalcul>('/api/calcul', coupe === undefined ? { texte } : { texte, coupe }),
  coupesPreparer: (texte: string) => post<{ ok: boolean; erreurs: ErreurScript[]; unique: boolean; coupes: CoupeRes[]; avertissements: string[] }>('/api/coupes/preparer', { texte }),
  coupesSynthese: (texte: string) => post<{ ok: boolean; erreurs: ErreurScript[]; projet: ProjetCoupes }>('/api/coupes/synthese', { texte }),
  valider: (texte: string) => post<{ ok: boolean; erreurs: ErreurScript[]; avertissements?: ErreurScript[] }>('/api/valider', { texte }),
  schema: () => fetch('/api/schema').then((r) => r.json()),
  exemples: () => fetch('/api/exemples').then((r) => r.json() as Promise<Exemple[]>),
  references: () =>
    fetch('/api/materiaux/references')
      .then((r) => (r.ok ? r.json() : {}))
      .catch(() => ({})) as Promise<Record<string, string[]>>,
  rido: (texte: string, nom: string) => post<{ texte: string; rapport: string[] }>('/api/rido', { texte, nom }),
  /** Bloc geometrie équivalent à la forme ancienne du script (plan, fouille, pente de terrain) et chemins à retirer. */
  geometrieNormaliser: (texte: string) => post<{ bloc: Record<string, unknown>; anciens: string[] }>('/api/geometrie/normaliser', { texte }),
  assemblagesTypes: () => fetch('/api/assemblages/types').then((r) => { if (!r.ok) throw new Error(`erreur ${r.status}`); return r.json() }).then((ts) => { if (!Array.isArray(ts)) throw new Error('réponse inattendue'); return ts as TypeAssemblage[] }),
  assemblagesSchema: (corps: unknown) => post<SchemaAssemblage>('/api/assemblages/schema', corps),
  assemblagesVerifier: (corps: unknown) => post<Verif[]>('/api/assemblages/verifier', corps),
  maquette: async (texte: string) => {
    let r: Response
    try {
      r = await fetch('/api/maquette', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ texte }),
      })
    } catch {
      throw new Error(MESSAGE_INJOIGNABLE)
    }
    if (!r.ok) throw new ErreurServeur(await messageReponse(r), r.status)
    return r.text()
  },
}
