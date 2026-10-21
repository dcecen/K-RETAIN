// Registre des ressources three.js de la vue : toute géométrie et tout matériau passent par ici,
// ce qui permet de les libérer (dispose) quand un objet est remplacé et de compter les fuites.
import * as THREE from 'three'

export class Fabrique {
  readonly geometries = new Set<THREE.BufferGeometry>()
  readonly materiaux = new Set<THREE.Material>()
  /** Nombre d'objets three créés depuis le début (géométries, matériaux, objets 3D). */
  creations = 0

  geo<T extends THREE.BufferGeometry>(g: T): T {
    this.geometries.add(g)
    this.creations++
    return g
  }

  mat<T extends THREE.Material>(m: T): T {
    this.materiaux.add(m)
    this.creations++
    return m
  }

  obj<T extends THREE.Object3D>(o: T): T {
    this.creations++
    return o
  }

  /** Retire l'objet de la scène et libère ses géométries et matériaux. */
  liberer(o: THREE.Object3D) {
    o.removeFromParent()
    o.traverse((x) => {
      const m = x as THREE.Mesh
      if (m.geometry && this.geometries.has(m.geometry)) {
        m.geometry.dispose()
        this.geometries.delete(m.geometry)
      }
      const mats = Array.isArray(m.material) ? m.material : m.material ? [m.material] : []
      for (const mat of mats) {
        if (this.materiaux.has(mat)) {
          mat.dispose()
          this.materiaux.delete(mat)
        }
      }
      if ((x as THREE.InstancedMesh).isInstancedMesh) (x as THREE.InstancedMesh).dispose()
    })
  }
}
