import { useEffect, useRef, useState, type ReactNode } from 'react'
import * as THREE from 'three'
import type { Resultats } from '../lib/api'
import type { Theme } from '../lib/theme'
import { FABRIQUES_CHANTIER } from './elements'
import { SceneRetainWall, type Diagnostic, type DonneesScene, type FabriqueSpecs } from './scene'

export interface PoigneeVue3D {
  scene: SceneRetainWall
  rendu: THREE.WebGLRenderer
  canvas: HTMLCanvasElement
}

/** Vue 3D persistante : la scène est créée une fois au montage, puis mise à jour (phase, recalcul, thème). */
export function Vue3D({ res, extra, phase, theme, selection, fabriques = FABRIQUES_CHANTIER, onSelection, onSurvol, onPret, enfants, surCalques }: {
  res: Resultats
  /** Données complémentaires de la scène (projet à coupes, résolution par tronçon). */
  extra?: Partial<DonneesScene>
  phase: number
  theme: Theme
  selection: string | null
  fabriques?: FabriqueSpecs[]
  onSelection: (id: string | null, point?: THREE.Vector3) => void
  onSurvol?: (id: string | null, point?: THREE.Vector3) => void
  onPret?: (p: PoigneeVue3D | null) => void
  enfants?: ReactNode
  /** Appelé quand la scène est prête et à chaque recalcul : application des calques par le parent. */
  surCalques?: (sc: SceneRetainWall) => void
}) {
  const hote = useRef<HTMLDivElement>(null)
  const couche = useRef<HTMLDivElement>(null)
  const poignee = useRef<PoigneeVue3D | null>(null)
  const etiquettesDom = useRef(new Map<string, HTMLDivElement>())
  const [diag, setDiag] = useState<Diagnostic | null>(null)
  const [voirDiag, setVoirDiag] = useState(false)
  const voirDiagRef = useRef(false)
  const rappels = useRef({ onSelection, onSurvol, surCalques })
  rappels.current = { onSelection, onSurvol, surCalques }

  // Création unique de la scène et du moteur de rendu
  useEffect(() => {
    const el = hote.current!
    const doms = etiquettesDom.current
    let rendu: THREE.WebGLRenderer
    try {
      rendu = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true })
    } catch {
      el.textContent = 'WebGL indisponible : la vue 3D ne peut pas s\'afficher dans ce navigateur.'
      return
    }
    rendu.setPixelRatio(window.devicePixelRatio)
    rendu.localClippingEnabled = true
    el.appendChild(rendu.domElement)
    const sc = new SceneRetainWall({ rendu, fabriques, planifier: (f) => requestAnimationFrame(f) })
    sc.apresRendu = () => {
      placerEtiquettes()
      if (voirDiagRef.current) setDiag(sc.diagnostic())
    }
    const p = { scene: sc, rendu, canvas: rendu.domElement }
    poignee.current = p

    const placerEtiquettes = () => {
      const cont = couche.current
      if (!cont) return
      const l = el.clientWidth
      const h = el.clientHeight
      const vus = new Set<string>()
      const v = new THREE.Vector3()
      for (const e of sc.etiquettesCourantes) {
        v.copy(e.pos).project(sc.camera)
        if (v.z > 1 || v.z < -1) continue
        if (sc.coupe.actif && sc.planCoupe.distanceToPoint(e.pos) < -0.01 && e.calque.startsWith('annotations')) continue
        vus.add(e.id)
        let d = etiquettesDom.current.get(e.id)
        if (!d) {
          d = document.createElement('div')
          cont.appendChild(d)
          etiquettesDom.current.set(e.id, d)
        }
        const cls = `etiquette-3d ${e.classe ?? ''}`
        if (d.className !== cls) d.className = cls
        if (d.textContent !== e.texte) d.textContent = e.texte
        d.style.transform = `translate(${((v.x + 1) / 2) * l}px, ${((1 - v.y) / 2) * h}px) translate(-50%, -100%)`
        if (e.selection) {
          d.dataset.selection = e.selection
          d.classList.toggle('choisie', e.selection === sc.selection)
        } else delete d.dataset.selection
      }
      for (const [id, d] of etiquettesDom.current) if (!vus.has(id)) { d.remove(); etiquettesDom.current.delete(id) }
    }

    const redim = () => {
      const l = el.clientWidth
      const h = el.clientHeight
      rendu.setSize(l, h)
      sc.redimensionner(l, h)
    }
    const obs = new ResizeObserver(redim)
    obs.observe(el)
    redim()

    // Interactions : orbite, déplacement, zoom, clic, survol
    let glisse: { x: number; y: number; pan: boolean; x0: number; y0: number } | null = null
    const ndc = (e: PointerEvent | MouseEvent) => {
      const r = rendu.domElement.getBoundingClientRect()
      return [((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1] as const
    }
    const bas = (e: PointerEvent) => {
      glisse = { x: e.clientX, y: e.clientY, x0: e.clientX, y0: e.clientY, pan: e.button === 2 || e.shiftKey }
      rendu.domElement.setPointerCapture(e.pointerId)
    }
    let survolPlanifie = false
    const bouge = (e: PointerEvent) => {
      if (glisse) {
        const dx = e.clientX - glisse.x
        const dy = e.clientY - glisse.y
        glisse.x = e.clientX
        glisse.y = e.clientY
        if (glisse.pan) sc.deplacer(dx, dy)
        else sc.orbiter(dx, dy)
        return
      }
      if (!rappels.current.onSurvol || survolPlanifie) return
      survolPlanifie = true
      const [nx, ny] = ndc(e)
      requestAnimationFrame(() => {
        survolPlanifie = false
        const t = sc.viser(nx, ny)
        rappels.current.onSurvol?.(t?.selection ?? null, t?.point)
      })
    }
    const haut = (e: PointerEvent) => {
      const g = glisse
      glisse = null
      if (!g || e.button !== 0 || Math.hypot(e.clientX - g.x0, e.clientY - g.y0) > 4) return
      const [nx, ny] = ndc(e)
      const t = sc.viser(nx, ny)
      rappels.current.onSelection(t?.selection ?? null, t?.point)
    }
    const molette = (e: WheelEvent) => { e.preventDefault(); sc.zoomer(e.deltaY) }
    const menu = (e: Event) => e.preventDefault()
    const quitter = () => rappels.current.onSurvol?.(null)
    const cv = rendu.domElement
    cv.addEventListener('pointerdown', bas)
    cv.addEventListener('pointermove', bouge)
    cv.addEventListener('pointerup', haut)
    cv.addEventListener('pointerleave', quitter)
    cv.addEventListener('wheel', molette, { passive: false })
    cv.addEventListener('contextmenu', menu)
    const touche = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.shiftKey && (e.key === 'D' || e.key === 'd')) {
        e.preventDefault()
        voirDiagRef.current = !voirDiagRef.current
        setVoirDiag(voirDiagRef.current)
        setDiag(sc.diagnostic())
      }
    }
    window.addEventListener('keydown', touche)
    onPret?.(p)

    return () => {
      obs.disconnect()
      window.removeEventListener('keydown', touche)
      cv.removeEventListener('pointerdown', bas)
      cv.removeEventListener('pointermove', bouge)
      cv.removeEventListener('pointerup', haut)
      cv.removeEventListener('pointerleave', quitter)
      cv.removeEventListener('wheel', molette)
      cv.removeEventListener('contextmenu', menu)
      sc.liberer()
      rendu.dispose()
      cv.remove()
      for (const d of doms.values()) d.remove()
      doms.clear()
      poignee.current = null
      onPret?.(null)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Recalcul : mise à jour incrémentale (même phase conservée)
  useEffect(() => {
    const p = poignee.current
    if (!p) return
    p.scene.phaseActive = phase
    p.scene.charger(res, extra)
    rappels.current.surCalques?.(p.scene)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [res, extra])

  useEffect(() => { poignee.current?.scene.phase(phase) }, [phase])
  useEffect(() => { poignee.current?.scene.appliquerTheme(theme === 'sombre') }, [theme])
  useEffect(() => { poignee.current?.scene.selectionner(selection) }, [selection])

  return (
    <div className="vue3d">
      <div ref={hote} className="vue3d-canvas" />
      <div ref={couche} className="vue3d-etiquettes" onClick={(e) => {
        const s = (e.target as HTMLElement).dataset?.selection
        if (s) onSelection(s)
      }} />
      {enfants}
      {voirDiag && diag && (
        <div className="vue3d-diag" role="status" aria-label="Diagnostic de la vue 3D">
          <b>Diagnostic 3D</b> <span className="doux">Ctrl+Maj+D</span>
          <table><tbody>
            <tr><td>Objets dans la scène</td><td className="num">{diag.objets}</td></tr>
            <tr><td>Géométries / matériaux</td><td className="num">{diag.geometries} / {diag.materiaux}</td></tr>
            <tr><td>Triangles</td><td className="num">{diag.triangles.toLocaleString('fr-FR')}</td></tr>
            <tr><td>Dernier rendu</td><td className="num">{diag.dernierRenduMs.toFixed(1)} ms</td></tr>
            <tr><td>Dernier changement de phase</td><td className="num">{diag.dernierePhaseMs.toFixed(1)} ms</td></tr>
            <tr><td>Dernière mise à jour (recalcul)</td><td className="num">{diag.dernierRecalculMs.toFixed(1)} ms</td></tr>
            <tr><td>Mémoire GPU estimée</td><td className="num">{diag.memoireGpuMo.toFixed(1)} Mo</td></tr>
            <tr><td>Rendus effectués</td><td className="num">{diag.rendus}</td></tr>
            <tr><td>Objets three créés (cumul)</td><td className="num">{diag.creations}</td></tr>
          </tbody></table>
        </div>
      )}
    </div>
  )
}
