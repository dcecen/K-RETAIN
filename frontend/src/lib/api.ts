// Types des réponses du serveur de calcul et appels HTTP.

export interface ErreurScript {
  ligne: number | null
  chemin: string
  message: string
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

export interface PhaseRes {
  nom: string
  ok: boolean
  message: string
  terrain_amont: number
  terrain_aval: number
  eau_amont: number | null
  eau_aval: number | null
  z?: number[]
  y_mm?: number[]
  z_diag?: number[]
  M?: number[]
  V?: number[]
  pressions?: { amont: Pressions; aval: Pressions }
  eau?: { z: number[]; u_amont: number[]; u_aval: number[] }
  appuis?: AppuiPhase[]
  actions: { type: string; texte: string }[]
  synthese?: {
    y_max_mm: number
    z_y_max: number
    y_tete_mm: number
    M_max: number
    M_min: number
    V_absmax: number
    butee_mobilisee: number | null
  }
}

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
}

export interface Dimensionnant {
  deplacement?: { valeur_mm: number; phase: string }
  moment_positif?: { valeur: number; phase: string }
  moment_negatif?: { valeur: number; phase: string }
  tranchant?: { valeur: number; phase: string }
  appuis?: Record<string, { effort_kN_m: number; effort_axial_kN: number; phase: string }>
}

export interface Resultats {
  projet: string
  complet: boolean
  avertissements: string[]
  conventions: Record<string, string>
  paroi: { tete: number; pied: number; type?: string; [k: string]: unknown }
  couches: { nom: string; toit: number }[]
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
  verifications?: Verif[]
  suggestions?: { appui: string; element: string | null; taux: number | null; message: string }[]
  pseudo3d?: {
    s: number[]
    z: number[]
    avertissements: string[]
    phases: {
      nom: string
      ok: boolean
      message: string
      y_mm?: number[][]
      M?: number[][]
      y_max_mm?: number
      y_max_2d_mm?: number
      Mz_max?: number
      Mz_min?: number
      Ms_absmax?: number
      appuis?: { nom: string; s: number; effort: number; actif: boolean }[]
    }[]
  }
}

export interface ReponseCalcul {
  ok: boolean
  erreurs: ErreurScript[]
  resultats?: Resultats
}

async function post<T>(url: string, corps: unknown): Promise<T> {
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(corps),
  })
  if (!r.ok) throw new Error(`${url} : erreur ${r.status}`)
  return r.json() as Promise<T>
}

export const api = {
  calcul: (texte: string) => post<ReponseCalcul>('/api/calcul', { texte }),
  valider: (texte: string) => post<{ ok: boolean; erreurs: ErreurScript[] }>('/api/valider', { texte }),
  schema: () => fetch('/api/schema').then((r) => r.json()),
  exemples: () => fetch('/api/exemples').then((r) => r.json() as Promise<{ nom: string; texte: string }[]>),
  references: () =>
    fetch('/api/materiaux/references')
      .then((r) => (r.ok ? r.json() : {}))
      .catch(() => ({})) as Promise<Record<string, string[]>>,
  maquette: async (texte: string) => {
    const r = await fetch('/api/maquette', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ texte }),
    })
    if (!r.ok) {
      const d = await r.json().catch(() => ({}))
      throw new Error(d.detail ?? `erreur ${r.status}`)
    }
    return r.text()
  },
}
