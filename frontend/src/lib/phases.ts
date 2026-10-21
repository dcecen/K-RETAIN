// Arbre des phases (parent explicite `depuis` ou phase précédente), chemins et voies d'affichage.
import type { Modele } from './scriptDoc'

export interface NoeudPhase {
  index: number          // −1 = état initial, sinon indice dans phases[]
  nom: string
  parent: number         // index du parent (−1 = état initial ; −2 pour l'état initial lui-même)
  lane: number
  rang: number           // ligne d'affichage
}

/** Arbre des phases : parent explicite (`depuis`) ou phase précédente de la liste. */
export function arbrePhases(phases: Modele[]): NoeudPhase[] {
  const noms = phases.map((p) => String(p?.nom ?? ''))
  const noeuds: NoeudPhase[] = [{ index: -1, nom: 'État initial', parent: -2, lane: 0, rang: 0 }]
  const lanes: number[] = [0]
  const enfantsVus = new Map<number, number>()   // parent -> nombre d'enfants déjà placés
  let maxLane = 0
  phases.forEach((p, i) => {
    let parent = i - 1
    if (p?.depuis !== undefined && p?.depuis !== null) {
      const k = noms.slice(0, i).indexOf(String(p.depuis))
      if (k >= 0) parent = k
      else if (String(p.depuis) === 'État initial') parent = -1
    }
    const n = enfantsVus.get(parent) ?? 0
    enfantsVus.set(parent, n + 1)
    const lane = n === 0 ? lanes[parent + 1] : ++maxLane
    lanes.push(lane)
    noeuds.push({ index: i, nom: noms[i] || `Phase ${i + 1}`, parent, lane, rang: i + 1 })
  })
  return noeuds
}

/** Chemin de l'état initial à la phase d'indice i (indices de phases[], −1 = état initial). */
export function cheminVers(noeuds: NoeudPhase[], index: number): number[] {
  const out: number[] = []
  let k = index
  while (k >= -1) {
    out.push(k)
    const n = noeuds.find((x) => x.index === k)
    if (!n || n.parent < -1) break
    k = n.parent
  }
  return out.reverse()
}

