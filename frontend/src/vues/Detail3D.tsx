import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import { autresAxes, type Schema, type Solide } from '../lib/assemblages'
import type { Theme } from '../lib/theme'

const COULEUR: Record<string, number> = { acier: 0x8a97a8, boulon: 0x3b4653, beton: 0xb8b0a2, bois: 0xb07a43, sol: 0xd8cdb4 }
// repère de l'assemblage (x, y, z vers le haut) -> three (x, z, -y)
const P = (p: number[]) => new THREE.Vector3(p[0], p[2], -p[1])

function maillage(s: Solide): THREE.Mesh | null {
  const mat = new THREE.MeshLambertMaterial({ color: COULEUR[s.materiau] ?? 0x8a97a8, transparent: s.materiau === 'beton' || s.materiau === 'sol',
    opacity: s.materiau === 'beton' ? 0.35 : s.materiau === 'sol' ? 0.2 : 1 })
  let g: THREE.BufferGeometry
  if (s.forme === 'boite') {
    g = new THREE.BoxGeometry(s.dims[0], s.dims[2], s.dims[1])
  } else if (s.forme === 'cylindre') {
    g = new THREE.CylinderGeometry(s.dims[0] / 2, s.dims[0] / 2, s.dims[1], 24)
    if (s.axe === 'x') g.rotateZ(Math.PI / 2)
    else if (s.axe === 'y') g.rotateX(Math.PI / 2)
  } else {
    if (!s.points) return null
    const forme = new THREE.Shape(s.points.map(([u, v]) => new THREE.Vector2(u, v)))
    g = new THREE.ExtrudeGeometry(forme, { depth: s.dims[0], bevelEnabled: false })
    // le plan (u, v) du prisme est le plan ⟂ à son axe ; replacer les axes
    const [ku, kv] = autresAxes(s.axe)
    const k = s.axe === 'x' ? 0 : s.axe === 'y' ? 1 : 2
    g.translate(0, 0, -s.dims[0] / 2)
    const pos = g.attributes.position as THREE.BufferAttribute
    const arr = pos.array as Float32Array
    for (let i = 0; i < pos.count; i++) {
      const u = arr[3 * i], v = arr[3 * i + 1], w = arr[3 * i + 2]
      const p = [0, 0, 0]
      p[ku] = u; p[kv] = v; p[k] = w + s.centre[k]
      arr[3 * i] = p[0]; arr[3 * i + 1] = p[2]; arr[3 * i + 2] = -p[1]
    }
    pos.needsUpdate = true
    g.computeVertexNormals()
    const m = new THREE.Mesh(g, mat)
    m.userData.repere = s.repere
    return m
  }
  const m = new THREE.Mesh(g, mat)
  m.position.copy(P(s.centre))
  m.userData.repere = s.repere
  return m
}

/** Libère géométries et matériaux des objets d'un groupe avant de le vider (sinon fuite graphique à chaque recalcul). */
function viderGroupe(groupe: THREE.Group) {
  for (const o of groupe.children) {
    const m = o as THREE.Mesh | THREE.LineSegments
    m.geometry?.dispose()
    const mat = m.material as THREE.Material | THREE.Material[] | undefined
    if (Array.isArray(mat)) mat.forEach((x) => x.dispose())
    else mat?.dispose()
  }
  groupe.clear()
}

/** Vue de détail 3D construite à partir des mêmes solides que le schéma 2D. */
export function Detail3D({ schema, reperes, theme, hauteur = 420 }: { schema: Schema; reperes?: Set<number>; theme: Theme; hauteur?: number }) {
  const hote = useRef<HTMLDivElement>(null)
  const etat = useRef<{ scene: THREE.Scene; cam: THREE.PerspectiveCamera; rendu: THREE.WebGLRenderer; groupe: THREE.Group; theta: number; phi: number; r: number; cible: THREE.Vector3; rendre: () => void } | null>(null)

  useEffect(() => {
    const el = hote.current
    if (!el) return
    const rendu = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true })
    rendu.setPixelRatio(window.devicePixelRatio)
    rendu.setSize(el.clientWidth, hauteur)
    el.appendChild(rendu.domElement)
    const scene = new THREE.Scene()
    scene.add(new THREE.AmbientLight(0xffffff, 0.7))
    const lum = new THREE.DirectionalLight(0xffffff, 0.8)
    lum.position.set(1000, 1500, 800)
    scene.add(lum)
    const cam = new THREE.PerspectiveCamera(40, el.clientWidth / hauteur, 1, 50000)
    const groupe = new THREE.Group()
    scene.add(groupe)
    // rendu à la demande (après une interaction ou un nouveau schéma), pas de boucle continue
    const rendre = () => rendu.render(scene, cam)
    const st = { scene, cam, rendu, groupe, theta: -0.8, phi: 1.05, r: 2500, cible: new THREE.Vector3(), rendre }
    etat.current = st
    const placer = () => {
      cam.position.set(st.cible.x + st.r * Math.sin(st.phi) * Math.cos(st.theta), st.cible.y + st.r * Math.cos(st.phi), st.cible.z + st.r * Math.sin(st.phi) * Math.sin(st.theta))
      cam.lookAt(st.cible)
      rendre()
    }
    let glisse: { x: number; y: number } | null = null
    const down = (e: PointerEvent) => { glisse = { x: e.clientX, y: e.clientY } }
    const up = () => { glisse = null }
    const move = (e: PointerEvent) => {
      if (!glisse) return
      st.theta += (e.clientX - glisse.x) * 0.006
      st.phi = Math.min(Math.max(st.phi - (e.clientY - glisse.y) * 0.006, 0.1), Math.PI - 0.1)
      glisse = { x: e.clientX, y: e.clientY }
      placer()
    }
    const wheel = (e: WheelEvent) => { e.preventDefault(); st.r *= Math.exp(e.deltaY * 0.001); placer() }
    rendu.domElement.addEventListener('pointerdown', down)
    window.addEventListener('pointerup', up)
    window.addEventListener('pointermove', move)
    rendu.domElement.addEventListener('wheel', wheel, { passive: false })
    placer()
    const redim = () => { rendu.setSize(el.clientWidth, hauteur); cam.aspect = el.clientWidth / hauteur; cam.updateProjectionMatrix(); rendre() }
    window.addEventListener('resize', redim)
    return () => {
      window.removeEventListener('pointerup', up)
      window.removeEventListener('pointermove', move)
      window.removeEventListener('resize', redim)
      viderGroupe(groupe)
      rendu.dispose()
      el.removeChild(rendu.domElement)
      etat.current = null
    }
  }, [hauteur])

  // reconstruction des solides à chaque schéma
  useEffect(() => {
    const st = etat.current
    if (!st) return
    viderGroupe(st.groupe)
    const boite = new THREE.Box3()
    for (const s of schema.solides) {
      const m = maillage(s)
      if (!m) continue
      st.groupe.add(m)
      if (!(s.repere === 0 && s.materiau === 'beton')) boite.expandByObject(m)
      const aretes = new THREE.LineSegments(new THREE.EdgesGeometry(m.geometry, 20), new THREE.LineBasicMaterial({ color: 0x1b2330, transparent: true, opacity: 0.55 }))
      aretes.position.copy(m.position)
      aretes.userData.arete = true
      st.groupe.add(aretes)
    }
    if (!boite.isEmpty()) {
      boite.getCenter(st.cible)
      st.r = 1.8 * boite.getSize(new THREE.Vector3()).length()
      st.cam.position.set(st.cible.x + st.r * Math.sin(st.phi) * Math.cos(st.theta), st.cible.y + st.r * Math.cos(st.phi), st.cible.z + st.r * Math.sin(st.phi) * Math.sin(st.theta))
      st.cam.lookAt(st.cible)
    }
    st.rendre()
  }, [schema])

  useEffect(() => {
    const st = etat.current
    if (!st) return
    st.scene.background = new THREE.Color(theme === 'sombre' ? 0x151a21 : 0xf7f8fa)
    st.rendre()
  }, [theme, schema])

  useEffect(() => {
    const st = etat.current
    if (!st) return
    st.groupe.traverse((o) => {
      const m = o as THREE.Mesh
      if (m.isMesh && m.material && 'emissive' in (m.material as THREE.MeshLambertMaterial)) {
        (m.material as THREE.MeshLambertMaterial).emissive.setHex(reperes?.has(m.userData.repere) ? 0x2f5d8a : 0x000000)
      }
    })
    st.rendre()
  }, [reperes, schema])

  return <div ref={hote} style={{ width: '100%', height: hauteur, borderTop: '1px solid var(--filet)' }} />
}
