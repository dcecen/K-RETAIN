// Transition visuelle entre deux phases : interpolation des positions, échelles, visibilités et
// tableaux de sommets (déformée, couleurs) entre l'état de la phase courante et celui de la phase
// cible. Purement visuelle : les valeurs intermédiaires ne sont pas des résultats de calcul.
import * as THREE from 'three'
import type { SceneRetainWall } from './scene'

interface Instantane {
  position: Map<THREE.Object3D, THREE.Vector3>
  scale: Map<THREE.Object3D, THREE.Vector3>
  visible: Map<THREE.Object3D, boolean>
  attributs: Map<THREE.BufferAttribute, Float32Array>
}

const ATTRIBUTS = ['position', 'color']

function capturer(sc: SceneRetainWall): Instantane {
  const s: Instantane = { position: new Map(), scale: new Map(), visible: new Map(), attributs: new Map() }
  for (const el of sc.elements.values()) {
    el.objet.traverse((o) => {
      s.position.set(o, o.position.clone())
      s.scale.set(o, o.scale.clone())
      s.visible.set(o, o.visible)
      const g = (o as THREE.Mesh).geometry
      if (g && !(o as THREE.InstancedMesh).isInstancedMesh) {
        for (const nom of ATTRIBUTS) {
          const a = g.getAttribute(nom) as THREE.BufferAttribute | undefined
          if (a && a.array instanceof Float32Array) s.attributs.set(a, new Float32Array(a.array))
        }
      }
    })
  }
  return s
}

/** Interpole la scène entre deux instantanés (t ∈ [0, 1]) ; la visibilité bascule à mi-course. */
export function interpoler(a: Instantane, b: Instantane, t: number) {
  const u = Math.min(Math.max(t, 0), 1)
  for (const [o, pb] of b.position) {
    const pa = a.position.get(o)
    if (pa) o.position.lerpVectors(pa, pb, u)
    const sa = a.scale.get(o)
    const sb = b.scale.get(o)
    if (sa && sb) o.scale.lerpVectors(sa, sb, u)
    const va = a.visible.get(o)
    const vb = b.visible.get(o)
    if (va !== undefined && vb !== undefined && va !== vb) o.visible = u < 0.5 ? va : vb
  }
  for (const [attr, arrB] of b.attributs) {
    const arrA = a.attributs.get(attr)
    if (!arrA || arrA.length !== arrB.length) continue
    const arr = attr.array as Float32Array
    for (let i = 0; i < arr.length; i++) arr[i] = arrA[i] + (arrB[i] - arrA[i]) * u
    attr.needsUpdate = true
  }
}

export interface Transition {
  /** Avance la transition au temps t (ms depuis le départ) ; renvoie vrai quand elle est terminée. */
  avancer(tMs: number): boolean
  annuler(): void
}

/** Prépare la transition de la phase courante vers `phase` : capture les deux états et rend la scène
 *  interpolable. La phase cible est appliquée à la fin (état exact). */
export function transition(sc: SceneRetainWall, phase: number, dureeMs: number): Transition | null {
  if (!sc.d || dureeMs <= 0 || phase === sc.phaseActive) return null
  const avant = capturer(sc)
  sc.phase(phase)
  const apres = capturer(sc)
  interpoler(avant, apres, 0)
  let fini = false
  return {
    avancer(tMs) {
      if (fini) return true
      const u = tMs / dureeMs
      if (u >= 1) { fini = true; sc.appliquerPhase(); return true }
      interpoler(avant, apres, u)
      sc.demanderRendu()
      return false
    },
    annuler() { if (!fini) { fini = true; sc.appliquerPhase() } },
  }
}
