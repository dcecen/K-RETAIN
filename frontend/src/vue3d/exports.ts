// Exports de la vue 3D : image PNG avec ses légendes (×1 ou ×2), scène glTF de la phase active.
import * as THREE from 'three'
import type { Legende } from './legendes'

/** Dessine les légendes sur un contexte 2D, empilées en bas à droite (même contenu que VueLegendes). */
export function dessinerLegendes(ctx: CanvasRenderingContext2D, legendes: Legende[], largeur: number, hauteur: number, facteur: number, sombre: boolean) {
  const f = facteur
  const boxW = 260 * f
  let y = hauteur - 10 * f
  const fond = sombre ? 'rgba(21,26,33,0.92)' : 'rgba(255,255,255,0.92)'
  const texte = sombre ? '#d9dfe8' : '#1b2330'
  const doux = sombre ? '#9aa4b3' : '#5a6475'
  for (const l of [...legendes].reverse()) {
    const lignes = 1 + (l.type === 'continue' ? 2 : Math.ceil(l.classes.length / 2) || 0) + 1 + (l.note ? 1 : 0)
    const boxH = (8 + 14 * lignes) * f
    const x = largeur - boxW - 10 * f
    y -= boxH
    ctx.fillStyle = fond
    ctx.strokeStyle = sombre ? '#39424f' : '#dde2e9'
    ctx.lineWidth = f
    ctx.fillRect(x, y, boxW, boxH)
    ctx.strokeRect(x, y, boxW, boxH)
    let ty = y + 15 * f
    ctx.fillStyle = texte
    ctx.font = `600 ${11 * f}px IBM Plex Sans, system-ui, sans-serif`
    ctx.fillText(l.titre, x + 8 * f, ty)
    ctx.font = `${10.5 * f}px IBM Plex Sans, system-ui, sans-serif`
    if (l.type === 'continue') {
      ty += 6 * f
      const m = /linear-gradient\(to right, (.*)\)/.exec(l.degrade)
      const grad = ctx.createLinearGradient(x + 8 * f, 0, x + boxW - 8 * f, 0)
      if (m) for (const part of m[1].split(/\), /)) {
        const mm = /rgb\((\d+),(\d+),(\d+)\)? (\d+(?:\.\d+)?)%/.exec(part.endsWith(')') ? part : part + ')')
        if (mm) grad.addColorStop(Number(mm[4]) / 100, `rgb(${mm[1]},${mm[2]},${mm[3]})`)
      }
      ctx.fillStyle = grad
      ctx.fillRect(x + 8 * f, ty, boxW - 16 * f, 10 * f)
      ty += 22 * f
      ctx.fillStyle = texte
      ctx.fillText(l.min.toLocaleString('fr-FR', { maximumFractionDigits: 1 }), x + 8 * f, ty)
      ctx.fillStyle = doux
      ctx.fillText(l.unite, x + boxW / 2 - 10 * f, ty)
      ctx.fillStyle = texte
      const sMax = l.max.toLocaleString('fr-FR', { maximumFractionDigits: 1 })
      ctx.fillText(sMax, x + boxW - 8 * f - ctx.measureText(sMax).width, ty)
      ty += 14 * f
    } else {
      l.classes.forEach((c, i) => {
        const cx = x + 8 * f + (i % 2) * (boxW / 2)
        if (i % 2 === 0) ty += 14 * f
        ctx.fillStyle = c.couleur
        ctx.fillRect(cx, ty - 9 * f, 10 * f, 10 * f)
        ctx.fillStyle = texte
        ctx.fillText(c.texte, cx + 14 * f, ty)
      })
      ty += 14 * f
    }
    ctx.fillStyle = doux
    ctx.fillText(l.phase + (l.note ? ` · ${l.note}` : ''), x + 8 * f, ty)
  }
}

/** Image PNG de la vue (canvas WebGL rendu au facteur demandé) avec les légendes dessinées. */
export function imagePng(rendu: THREE.WebGLRenderer, scene: THREE.Scene, camera: THREE.Camera, legendes: Legende[], facteur: 1 | 2, sombre: boolean): string {
  const canvas = rendu.domElement
  const l = canvas.clientWidth
  const h = canvas.clientHeight
  const ratio = rendu.getPixelRatio()
  rendu.setPixelRatio(facteur)
  rendu.setSize(l, h, false)
  rendu.render(scene, camera)
  const sortie = document.createElement('canvas')
  sortie.width = l * facteur
  sortie.height = h * facteur
  const ctx = sortie.getContext('2d')!
  ctx.drawImage(canvas, 0, 0, sortie.width, sortie.height)
  dessinerLegendes(ctx, legendes, sortie.width, sortie.height, facteur, sombre)
  rendu.setPixelRatio(ratio)
  rendu.setSize(l, h, false)
  rendu.render(scene, camera)
  return sortie.toDataURL('image/png')
}

/** Objets exportables en glTF : copie de la scène sans les lumières ni les objets masqués. */
export function sceneExportable(scene: THREE.Scene): THREE.Group {
  const g = new THREE.Group()
  g.name = 'RetainWall'
  scene.updateMatrixWorld(true)
  scene.traverse((o) => {
    const m = o as THREE.Mesh
    if (!m.isMesh || !o.visible) return
    let p: THREE.Object3D | null = o
    while (p) { if (!p.visible) return; p = p.parent }
    const copie = m.clone()
    copie.matrixAutoUpdate = false
    copie.matrix.copy(m.matrixWorld)
    // matériaux convertis en « standard » (format glTF) : couleur, opacité, faces
    const conv = (mat: THREE.Material) => {
      const src = mat as THREE.MeshLambertMaterial
      return new THREE.MeshStandardMaterial({ color: src.color ?? new THREE.Color(0xcccccc), transparent: src.transparent, opacity: src.opacity, side: src.side,
        vertexColors: src.vertexColors, wireframe: (src as unknown as THREE.MeshBasicMaterial).wireframe ?? false, roughness: 0.9, metalness: 0 })
    }
    copie.material = Array.isArray(m.material) ? m.material.map(conv) : conv(m.material)
    g.add(copie)
  })
  return g
}

/** Export glTF binaire (.glb) de la phase active. */
export async function exporterGltf(scene: THREE.Scene): Promise<Blob> {
  const { GLTFExporter } = await import('three/examples/jsm/exporters/GLTFExporter.js')
  const exp = new GLTFExporter()
  const groupe = sceneExportable(scene)
  const resultat = await exp.parseAsync(groupe, { binary: true, onlyVisible: true })
  return new Blob([resultat as ArrayBuffer], { type: 'model/gltf-binary' })
}
