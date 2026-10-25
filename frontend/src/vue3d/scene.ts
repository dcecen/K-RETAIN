// Scène 3D persistante de RetainWall.
//
// La scène est construite une fois. Ensuite :
// - un changement de phase ne modifie que des attributs (visibilité, échelle, position, couleurs) ;
// - un recalcul compare la clé de chaque objet (type, dimensions, position) et ne reconstruit
//   que les objets dont la géométrie a changé ; les ressources remplacées sont libérées.
// Le rendu n'est déclenché que sur événement (pas de boucle continue au repos).
//
// Conventions affichées : déplacement positif vers la fouille ; moment positif quand la face
// côté fouille est tendue.
import * as THREE from 'three'
import type { Maquette, PhaseRes, ProjetCoupes, Resultats } from '../lib/api'
import { Fabrique } from './fabrique'
import { Contour } from './geometrie'

/** Nœuds fixes de l'arbre de la scène (identifiants stables). */
export const NOEUDS = [
  'terrain', 'fouille', 'eau', 'surcharges', 'environnement', 'paroi',
  'appuis', 'appuis.butons', 'appuis.tirants', 'appuis.dalles',
  'resultats', 'coupes', 'annotations', 'outils',
] as const
export type NomNoeud = (typeof NOEUDS)[number]

export interface Etiquette {
  id: string
  pos: THREE.Vector3
  texte: string
  calque: string
  classe?: string
  selection?: string
}

/** Vue de l'état des calques telle que la scène la consomme (voir calques.ts). */
export interface EtatCalquesScene {
  visible(id: string): boolean
  opacite(id: string): number
  verrouille(id: string): boolean
  coupe(id: string): boolean
  /** Mode d'affichage du calque (voir calques.ts) et réglages propres. */
  mode?(id: string): string | undefined
  reglage?<T extends number | string | boolean>(id: string, cle: string, defaut: T): T
}

/** Mode et réglage d'un calque avec repli sur la valeur par défaut. */
export function modeCalque(c: EtatCalquesScene, id: string, defaut: string): string {
  return c.mode?.(id) ?? defaut
}
export function reglageCalque<T extends number | string | boolean>(c: EtatCalquesScene, id: string, cle: string, defaut: T): T {
  return c.reglage ? c.reglage(id, cle, defaut) : defaut
}

/** État par défaut : tout est visible sauf les résultats ; le plan de coupe s'applique au terrain, à la fouille et à l'eau. */
export const CALQUES_DEFAUT: EtatCalquesScene = {
  visible: (id) => (!id.startsWith('resultats') || id === 'resultats.alertes') && !id.startsWith('coupes.diagrammes') && id !== 'surcharges.pressions',
  opacite: () => 1,
  verrouille: () => false,
  coupe: (id) => /^(terrain|fouille|eau)/.test(id),
}

/** Ce que la scène affiche : résultats d'une coupe (ou projet), géométrie de la maquette. */
export interface DonneesScene {
  res: Resultats
  m: Maquette
  geo: Contour
  /** Projet à coupes de calcul (plans, zones, diagrammes). */
  projet?: ProjetCoupes | null
  /** Noms des côtés de la fouille (plan.cotes du script). */
  cotes?: Record<string, number>
  /** Résultats et phase à afficher pour un point de paroi (arête k, abscisse locale sl) — coupes de calcul. */
  resultatsPour?: (k: number, sl: number, phase: number) => { res: Resultats; phase: number; coupe: string | null }
}

export interface Contexte {
  d: DonneesScene
  phase: number
  ph: PhaseRes
  fab: Fabrique
  plan: THREE.Plane
  scene: SceneRetainWall
}

/** Un objet de la scène, identifié par un id stable et une clé de géométrie. */
export interface Element {
  id: string
  cle: string
  noeud: NomNoeud
  calque: string
  objet: THREE.Object3D
  /** Calques supplémentaires : l'élément est visible si l'un d'eux (ou ) est visible. */
  calques?: string[]
  /** Identifiant de sélection (clic) : « appui:B1 », « paroi:0 », « couche:1 »… */
  selection?: string
  /** Visibilité propre à la phase (indépendante des calques). */
  visiblePhase: boolean
  appliquerPhase?(ctx: Contexte): void
  /** Nouvelles valeurs de résultats, même géométrie. */
  majDonnees?(ctx: Contexte): void
  /** Le plan de coupe a bougé. */
  majCoupe?(ctx: Contexte): void
  etiquettes?(ctx: Contexte, out: Etiquette[]): void
  surligner?(actif: boolean): void
}

export interface Spec {
  id: string
  cle: string
  creer(ctx: Contexte): Element
}

export type FabriqueSpecs = (ctx: Contexte) => Spec[]

export interface Rendu {
  render(scene: THREE.Scene, camera: THREE.Camera): void
  info?: { render: { triangles: number }; memory: { geometries: number; textures: number } }
}

export interface OptionsScene {
  rendu?: Rendu
  /** Planificateur du rendu (requestAnimationFrame dans le navigateur). */
  planifier?: (f: () => void) => void
  maintenant?: () => number
  fabriques?: FabriqueSpecs[]
}

export interface EtatCoupe { actif: boolean; axe: 'x' | 'y'; t: number }

export interface Diagnostic {
  objets: number
  geometries: number
  materiaux: number
  triangles: number
  dernierRenduMs: number
  dernierePhaseMs: number
  dernierRecalculMs: number
  memoireGpuMo: number
  rendus: number
  creations: number
}

const PHASE_VIDE = (i: number): PhaseRes => ({
  nom: `Phase ${i + 1}`, ok: false, message: '', terrain_amont: 0, terrain_aval: 0, eau_amont: null, eau_aval: null,
  actions: [], parent: null, enfants: [], depuis: null,
})

export class SceneRetainWall {
  readonly scene = new THREE.Scene()
  readonly camera = new THREE.PerspectiveCamera(45, 1, 0.1, 5000)
  readonly fab = new Fabrique()
  readonly noeuds = {} as Record<NomNoeud, THREE.Group>
  readonly elements = new Map<string, Element>()
  readonly planCoupe = new THREE.Plane(new THREE.Vector3(-1, 0, 0), 1e6)
  coupe: EtatCoupe = { actif: false, axe: 'x', t: 0.5 }
  /** Position de l'outil « Couper ici » (arête, abscisse locale), null si inactif. */
  coupeLocale: { k: number; sl: number } | null = null
  /** Curseur de cote sur la paroi (survol d'une courbe du panneau de résultats). */
  repereCote: { k: number; z: number } | null = null
  /** Outil « Mesurer » : deux points (repère three). */
  mesure: { a: THREE.Vector3; b: THREE.Vector3 | null } | null = null
  calques: EtatCalquesScene = CALQUES_DEFAUT
  orbite = { theta: -0.9, phi: 0.95, rayon: 60, cible: new THREE.Vector3() }
  cameraTouchee = false
  selection: string | null = null
  d: DonneesScene | null = null
  phaseActive = 0
  etiquettesCourantes: Etiquette[] = []
  sombre = false
  /** Éléments reconstruits au dernier recalcul (contrôle de la mise à jour incrémentale). */
  derniersReconstruits: string[] = []
  readonly stats = { rendus: 0, dernierRenduMs: 0, dernierePhaseMs: 0, dernierRecalculMs: 0 }
  /** Appelé après chaque rendu (étiquettes HTML, diagnostic). */
  apresRendu: (() => void) | null = null

  private rendu?: Rendu
  private planifier: (f: () => void) => void
  private maintenant: () => number
  private fabriques: FabriqueSpecs[]
  private renduPlanifie = false
  private cleCadrage = ''
  private lumieres: THREE.Light[] = []

  constructor(o: OptionsScene = {}) {
    this.rendu = o.rendu
    this.planifier = o.planifier ?? ((f) => f())
    this.maintenant = o.maintenant ?? (() => (typeof performance !== 'undefined' ? performance.now() : Date.now()))
    this.fabriques = o.fabriques ?? []
    this.scene.name = 'Scène'
    for (const nom of NOEUDS) {
      const g = new THREE.Group()
      g.name = nom
      g.userData.id = nom
      this.noeuds[nom] = g
      const parent = nom.startsWith('appuis.') ? this.noeuds.appuis : this.scene
      parent.add(g)
    }
    const amb = new THREE.AmbientLight(0xffffff, 0.65)
    const soleil = new THREE.DirectionalLight(0xffffff, 0.9)
    soleil.position.set(40, 80, 30)
    this.lumieres = [amb, soleil]
    this.scene.add(amb, soleil)
    this.appliquerTheme(false)
  }

  /** Nombre de nœuds de l'arbre fixe et de lumières (hors éléments). */
  get socle(): number {
    return NOEUDS.length + this.lumieres.length
  }

  // ------------------------------------------------------------------ données
  private contexte(): Contexte {
    const d = this.d!
    const ph = d.res.phases[this.phaseActive] ?? PHASE_VIDE(this.phaseActive)
    return { d, phase: this.phaseActive, ph, fab: this.fab, plan: this.planCoupe, scene: this }
  }

  /** Premier chargement ou recalcul : réconciliation des objets par clé de géométrie. */
  charger(res: Resultats, extra: Partial<DonneesScene> = {}) {
    if (!res.maquette) throw new Error('résultats sans géométrie de maquette')
    const t0 = this.maintenant()
    const geo = this.d && this.d.geo.cle() === new Contour(res.maquette.contour).cle() ? this.d.geo : new Contour(res.maquette.contour)
    // noms des côtés : ceux du script courant s'ils sont donnés, sinon ceux renvoyés avec la maquette (bloc geometrie)
    const cotes = extra.cotes && Object.keys(extra.cotes).length ? extra.cotes : res.maquette.cotes
    this.d = { res, m: res.maquette, geo, ...extra, ...(cotes ? { cotes } : {}) }
    this.phaseActive = Math.min(this.phaseActive, Math.max(0, res.phases.length - 1))
    const ctx = this.contexte()
    const specs = this.fabriques.flatMap((f) => f(ctx))
    this.reconcilier(specs, ctx)
    const cle = `${geo.cle()}|${res.maquette.paroi.tete}|${res.maquette.paroi.pied}|${(extra.projet?.coupes ?? []).map((c) => c.nom).join(',')}`
    if (cle !== this.cleCadrage) {
      if (!this.cleCadrage || !this.cameraTouchee) this.recadrer()
      this.cleCadrage = cle
    }
    this.majCoupe()
    this.appliquerPhase()
    this.stats.dernierRecalculMs = this.maintenant() - t0
  }

  private reconcilier(specs: Spec[], ctx: Contexte) {
    const vus = new Set<string>()
    this.derniersReconstruits = []
    for (const s of specs) {
      if (vus.has(s.id)) throw new Error(`identifiant d'objet en double : ${s.id}`)
      vus.add(s.id)
      const ex = this.elements.get(s.id)
      if (ex && ex.cle === s.cle) {
        ex.majDonnees?.(ctx)
        continue
      }
      if (ex) this.retirer(ex)
      const el = s.creer(ctx)
      el.objet.userData.id = el.id
      if (el.selection) el.objet.userData.selection = el.selection
      this.noeuds[el.noeud].add(el.objet)
      this.elements.set(el.id, el)
      this.appliquerCoupeMateriaux(el)
      this.appliquerOpacite(el)
      this.derniersReconstruits.push(el.id)
    }
    for (const [id, el] of [...this.elements]) if (!vus.has(id)) this.retirer(el)
  }

  private retirer(el: Element) {
    this.fab.liberer(el.objet)
    this.elements.delete(el.id)
  }

  // ------------------------------------------------------------------ phase
  phase(i: number) {
    if (!this.d) return
    const n = this.d.res.phases.length
    this.phaseActive = Math.min(Math.max(0, i), n - 1)
    this.appliquerPhase()
  }

  /** Applique la phase active aux éléments visibles ; les éléments masqués sont marqués à rafraîchir (calcul paresseux). */
  appliquerPhase() {
    if (!this.d) return
    const t0 = this.maintenant()
    const ctx = this.contexte()
    for (const el of this.elements.values()) this.majElement(el, ctx)
    this.calculerEtiquettes(ctx)
    this.stats.dernierePhaseMs = this.maintenant() - t0
    this.demanderRendu()
  }

  private sales = new Set<string>()

  private majElement(el: Element, ctx: Contexte) {
    const vis = this.calques.visible(el.calque) || (el.calques?.some((c) => this.calques.visible(c)) ?? false)
    if (!vis) {
      el.objet.visible = false
      this.sales.add(el.id)
      return
    }
    el.appliquerPhase?.(ctx)
    this.sales.delete(el.id)
    el.objet.visible = el.visiblePhase
  }

  /** Éléments dont les attributs de phase n'ont pas été calculés (calques masqués). */
  get elementsEnAttente(): string[] {
    return [...this.sales]
  }

  private calculerEtiquettes(ctx: Contexte) {
    const out: Etiquette[] = []
    for (const el of this.elements.values()) {
      if (!el.objet.visible || !el.etiquettes) continue
      el.etiquettes(ctx, out)
    }
    this.etiquettesCourantes = out.filter((e) => this.calques.visible(e.calque))
  }

  // ------------------------------------------------------------------ calques
  appliquerCalques(etat: EtatCalquesScene) {
    this.calques = etat
    if (!this.d) return
    const ctx = this.contexte()
    for (const el of this.elements.values()) {
      this.appliquerCoupeMateriaux(el)
      this.appliquerOpacite(el)
      this.majElement(el, ctx)
    }
    this.calculerEtiquettes(ctx)
    this.demanderRendu()
  }

  private appliquerOpacite(el: Element) {
    const o = this.calques.opacite(el.calque)
    el.objet.traverse((x) => {
      const mats = materiaux(x)
      for (const m of mats) {
        if (m.userData.opaciteBase === undefined) {
          m.userData.opaciteBase = m.opacity
          m.userData.transparentBase = m.transparent
          m.userData.depthWriteBase = m.depthWrite
        }
        const op = m.userData.opaciteBase * o
        const transp = m.userData.transparentBase || o < 0.999
        if (m.transparent !== transp) m.needsUpdate = true
        m.opacity = op
        m.transparent = transp
        m.depthWrite = o < 0.999 ? false : m.userData.depthWriteBase
      }
    })
  }

  private appliquerCoupeMateriaux(el: Element) {
    const accepte = this.calques.coupe(el.calque)
    el.objet.traverse((x) => {
      for (const m of materiaux(x)) {
        const avant = !!(m.clippingPlanes && m.clippingPlanes.length)
        if (avant === accepte) continue
        m.clippingPlanes = accepte ? [this.planCoupe] : []
        m.needsUpdate = true
      }
    })
  }

  // ------------------------------------------------------------------ plan de coupe
  /** Bornes du terrain modélisé dans l'axe du plan de coupe. */
  bornesCoupe(axe: 'x' | 'y' = this.coupe.axe): [number, number] {
    const g = this.d?.geo
    if (!g) return [0, 1]
    return axe === 'x' ? [g.xmin - g.marge, g.xmax + g.marge] : [g.ymin - g.marge, g.ymax + g.marge]
  }

  /** Coordonnée en plan du plan de coupe (x ou y selon l'axe). */
  get valeurCoupe(): number {
    const [a, b] = this.bornesCoupe()
    return a + this.coupe.t * (b - a)
  }

  definirMesure(m: { a: THREE.Vector3; b: THREE.Vector3 | null } | null) {
    this.mesure = m
    if (!this.d) return
    const ctx = this.contexte()
    for (const el of this.elements.values()) if (el.id === 'outils.mesure') this.majElement(el, ctx)
    this.calculerEtiquettes(ctx)
    this.demanderRendu()
  }

  definirRepere(p: { k: number; z: number } | null) {
    if (!p && !this.repereCote) return
    this.repereCote = p
    if (!this.d) return
    const ctx = this.contexte()
    for (const el of this.elements.values()) if (el.id === 'annotations.repere') this.majElement(el, ctx)
    this.calculerEtiquettes(ctx)
    this.demanderRendu()
  }

  /** Centre de la boîte englobante des objets d'une sélection (repère three), null si aucun. */
  centreDe(selection: string): THREE.Vector3 | null {
    const boite = new THREE.Box3()
    let n = 0
    for (const el of this.elementsDe(selection)) {
      if (!el.objet.visible) continue
      el.objet.updateMatrixWorld(true)
      const b = new THREE.Box3().setFromObject(el.objet)
      if (b.isEmpty()) continue
      boite.union(b)
      n++
    }
    return n ? boite.getCenter(new THREE.Vector3()) : null
  }

  definirCoupeLocale(p: { k: number; sl: number } | null) {
    this.coupeLocale = p
    if (!this.d) return
    const ctx = this.contexte()
    for (const el of this.elements.values()) if (el.id === 'coupes.locale') this.majElement(el, ctx)
    this.calculerEtiquettes(ctx)
    this.demanderRendu()
  }

  definirCoupe(c: Partial<EtatCoupe>) {
    this.coupe = { ...this.coupe, ...c }
    this.majCoupe()
    this.demanderRendu()
  }

  private majCoupe() {
    if (!this.coupe.actif || !this.d) {
      this.planCoupe.normal.set(-1, 0, 0)
      this.planCoupe.constant = 1e6
    } else if (this.coupe.axe === 'x') {
      this.planCoupe.normal.set(-1, 0, 0)          // garde x ≤ x0
      this.planCoupe.constant = this.valeurCoupe
    } else {
      this.planCoupe.normal.set(0, 0, 1)           // three z = −y : garde y ≤ y0
      this.planCoupe.constant = this.valeurCoupe
    }
    if (!this.d) return
    const ctx = this.contexte()
    for (const el of this.elements.values()) if (el.majCoupe && this.calques.visible(el.calque)) el.majCoupe(ctx)
  }

  // ------------------------------------------------------------------ caméra
  placerCamera() {
    const { theta, phi, rayon, cible } = this.orbite
    this.camera.position.set(cible.x + rayon * Math.sin(phi) * Math.cos(theta), cible.y + rayon * Math.cos(phi),
      cible.z + rayon * Math.sin(phi) * Math.sin(theta))
    this.camera.lookAt(cible)
    this.camera.updateMatrixWorld()
  }

  /** Cadre la fouille entière (vue isométrique). */
  recadrer() {
    if (!this.d) return
    const g = this.d.geo
    const p = this.d.m.paroi
    const H = p.tete - p.pied
    this.orbite.cible.set((g.xmin + g.xmax) / 2, p.tete - 0.4 * H, -(g.ymin + g.ymax) / 2)
    this.orbite.rayon = 1.1 * (g.taille + 2 * g.marge) + H
    this.placerCamera()
    this.demanderRendu()
  }

  orbiter(dx: number, dy: number) {
    this.orbite.theta += dx * 0.005
    this.orbite.phi = Math.min(Math.max(this.orbite.phi - dy * 0.005, 0.05), Math.PI - 0.05)
    this.cameraTouchee = true
    this.placerCamera()
    this.demanderRendu()
  }

  deplacer(dx: number, dy: number) {
    const droite = new THREE.Vector3().subVectors(this.camera.position, this.orbite.cible).cross(this.camera.up).normalize()
    const k = this.orbite.rayon / 800
    this.orbite.cible.addScaledVector(droite, dx * k)
    this.orbite.cible.y += dy * k
    this.cameraTouchee = true
    this.placerCamera()
    this.demanderRendu()
  }

  zoomer(deltaY: number) {
    this.orbite.rayon = Math.min(Math.max(this.orbite.rayon * Math.exp(deltaY * 0.001), 1), 4000)
    this.cameraTouchee = true
    this.placerCamera()
    this.demanderRendu()
  }

  vue(nom: 'iso' | 'face' | 'dessus' | 'coupe') {
    const o = this.orbite
    if (nom === 'iso') { o.theta = -0.9; o.phi = 0.95 }
    else if (nom === 'face') { o.theta = Math.PI / 2; o.phi = Math.PI / 2 - 0.05 }
    else if (nom === 'dessus') { o.theta = Math.PI / 2; o.phi = 0.02 }
    else { this.definirCoupe({ actif: true, axe: 'x', t: 0.5 }); o.theta = 0; o.phi = Math.PI / 2 - 0.05 }
    this.cameraTouchee = true
    this.placerCamera()
    this.demanderRendu()
  }

  /** Centre la caméra sur un point (repère three) sans changer l'orientation. */
  centrerSur(p: THREE.Vector3, rayon?: number) {
    this.orbite.cible.copy(p)
    if (rayon) this.orbite.rayon = rayon
    this.cameraTouchee = true
    this.placerCamera()
    this.demanderRendu()
  }

  redimensionner(l: number, h: number) {
    this.camera.aspect = l / Math.max(h, 1)
    this.camera.updateProjectionMatrix()
    this.demanderRendu()
  }

  // ------------------------------------------------------------------ sélection
  private lanceur = (() => { const r = new THREE.Raycaster(); r.params.Line = { threshold: 0.05 }; return r })()

  /** Objet sélectionnable sous le point (coordonnées normalisées −1…1) ; les calques verrouillés sont ignorés. */
  viser(nx: number, ny: number): { selection: string; point: THREE.Vector3; instance?: number } | null {
    this.scene.updateMatrixWorld()
    this.lanceur.setFromCamera(new THREE.Vector2(nx, ny), this.camera)
    const cibles: THREE.Object3D[] = []
    for (const el of this.elements.values()) {
      if (!el.selection || !el.objet.visible || this.calques.verrouille(el.calque)) continue
      cibles.push(el.objet)
    }
    const touches = this.lanceur.intersectObjects(cibles, true)
    const coupe = this.coupe.actif ? this.planCoupe : null
    for (const t of touches) {
      if ((t.object as THREE.Line).isLine && !t.object.userData.selection) continue
      if (coupe && materiaux(t.object).some((m) => m.clippingPlanes?.length) && coupe.distanceToPoint(t.point) < 0) continue
      let o: THREE.Object3D | null = t.object
      while (o && !o.userData.selection) o = o.parent
      if (o) return { selection: o.userData.selection as string, point: t.point.clone(), instance: t.instanceId }
    }
    return null
  }

  selectionner(id: string | null) {
    this.selection = id
    for (const el of this.elements.values()) el.surligner?.(!!id && el.selection === id)
    this.demanderRendu()
  }

  /** Éléments portant un identifiant de sélection. */
  elementsDe(selection: string): Element[] {
    return [...this.elements.values()].filter((e) => e.selection === selection)
  }

  // ------------------------------------------------------------------ thème et rendu
  appliquerTheme(sombre: boolean) {
    this.sombre = sombre
    this.scene.background = this.scene.background instanceof THREE.Color ? this.scene.background : new THREE.Color()
    ;(this.scene.background as THREE.Color).setHex(sombre ? 0x161b22 : 0xeef1f5)
    this.demanderRendu()
  }

  demanderRendu() {
    if (!this.rendu || this.renduPlanifie) return
    this.renduPlanifie = true
    this.planifier(() => {
      this.renduPlanifie = false
      this.rendreMaintenant()
    })
  }

  rendreMaintenant() {
    if (!this.rendu) return
    const t0 = this.maintenant()
    this.rendu.render(this.scene, this.camera)
    this.stats.rendus++
    this.stats.dernierRenduMs = this.maintenant() - t0
    this.apresRendu?.()
  }

  diagnostic(): Diagnostic {
    let objets = 0
    let triangles = 0
    this.scene.traverse((o) => {
      objets++
      const m = o as THREE.Mesh
      if (!m.isMesh || !o.visible || !m.geometry) return
      const g = m.geometry
      const n = g.index ? g.index.count : (g.attributes.position?.count ?? 0)
      const inst = (o as THREE.InstancedMesh).isInstancedMesh ? (o as THREE.InstancedMesh).count : 1
      triangles += (n / 3) * inst
    })
    let octets = 0
    for (const g of this.fab.geometries) {
      for (const a of Object.values(g.attributes)) octets += (a as THREE.BufferAttribute).array.byteLength
      if (g.index) octets += g.index.array.byteLength
    }
    return {
      objets, geometries: this.fab.geometries.size, materiaux: this.fab.materiaux.size,
      triangles: Math.round(this.rendu?.info?.render.triangles || triangles),
      dernierRenduMs: this.stats.dernierRenduMs, dernierePhaseMs: this.stats.dernierePhaseMs,
      dernierRecalculMs: this.stats.dernierRecalculMs, memoireGpuMo: octets / 1e6, rendus: this.stats.rendus,
      creations: this.fab.creations,
    }
  }

  /** Libère toute la scène (démontage du composant). */
  liberer() {
    for (const el of [...this.elements.values()]) this.retirer(el)
    this.d = null
  }
}

export function materiaux(o: THREE.Object3D): THREE.Material[] {
  const m = (o as THREE.Mesh).material
  return Array.isArray(m) ? m : m ? [m] : []
}
