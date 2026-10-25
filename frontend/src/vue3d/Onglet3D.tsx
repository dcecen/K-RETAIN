import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type * as THREE from 'three'
import { api, messageErreur, type ProjetCoupes, type Resultats } from '../lib/api'
import { informer, saisir } from '../lib/dialogue'
import { enregistrerExport, telecharger, telechargerTexte } from '../lib/exporter'
import { IconeCalques, IconeChevronB, IconeTableau } from '../lib/icones'
import type { Theme } from '../lib/theme'
import { nb } from '../lib/format'
import { Menu } from '../composants/Menu'
import { definirReglage, definirVisible, ecrireStockage, etatPrereglage, lireStockage, PREREGLAGES_LIVRES, versScene, type EtatCalques, type Prereglage } from './calques'
import { FABRIQUES_CHANTIER } from './elements'
import { Legendes } from './VueLegendes'
import { legendes as calculerLegendes } from './legendes'
import { PanneauCalques } from './PanneauCalques'
import { FABRIQUES_RESULTATS_PAROI, profilValeur, sourcePour } from './resultats'
import { FABRIQUES_RESULTATS_APPUIS } from './resultatsAppuis'
import { FABRIQUES_COUPES, resolveur } from './coupes'
import { FABRIQUES_COUPE_LOCALE, positionDepuisPoint, type PositionCoupeLocale } from './coupeLocale'
import { PanneauCoupeLocale } from './PanneauCoupeLocale'
import { entreeYamlCoupe, sourcePourProjet } from './sourceResultats'
import { Contour } from './geometrie'
import type { Modele } from '../lib/scriptDoc'
import { analyserSelection, filAriane, type SelectionAnalysee } from './navigation'
import { PanneauResultats } from './PanneauResultats'
import { FABRIQUES_REPERES } from './reperes'
import { entreeYamlSurcharge, FABRIQUES_SURCHARGES } from './surcharges'
import { entreeYamlRisberme, FABRIQUES_TERRAIN } from './terrain'
import { FABRIQUES_COMPARAISON } from './comparaison'
import { exporterGltf, imagePng } from './exports'
import type { EtatVue3D } from './etat3d'
import type { SceneRetainWall } from './scene'
import { Vue3D, type PoigneeVue3D } from './Vue3D'

const FABRIQUES = [...FABRIQUES_CHANTIER, ...FABRIQUES_RESULTATS_PAROI, ...FABRIQUES_RESULTATS_APPUIS, ...FABRIQUES_COUPES, ...FABRIQUES_COUPE_LOCALE, ...FABRIQUES_REPERES, ...FABRIQUES_SURCHARGES, ...FABRIQUES_TERRAIN, ...FABRIQUES_COMPARAISON]

type Outil = 'mesure' | 'risberme' | 'surcharge' | null
const OUTILS: { cle: Exclude<Outil, null>; nom: string; consigne: string }[] = [
  { cle: 'mesure', nom: 'Mesurer', consigne: 'deux clics dans la maquette : distance et dénivelée' },
  { cle: 'surcharge', nom: 'Tracer une surcharge sur le terrain', consigne: 'cliquez les deux coins de l’emprise sur le terrain' },
  { cle: 'risberme', nom: 'Ajouter une risberme', consigne: 'cliquez un côté de la paroi' },
]

/** Libellé lisible d'un objet de la maquette (info-bulle). */
function libelleSelection(sel: SelectionAnalysee, res: Resultats): string {
  switch (sel.type) {
    case 'couche': return `Couche ${(sel.index ?? 0) + 1}${res.couches[sel.index ?? 0]?.nom ? ` : ${res.couches[sel.index ?? 0].nom}` : ''}`
    case 'surcharge': return `Surcharge ${res.maquette?.surcharges?.[sel.index ?? 0]?.nom ?? sel.nom}`
    case 'fond': return 'Fond de fouille'
    case 'bouchon': return 'Bouchon de fond de fouille'
    case 'terrain': return `Terrain : ${sel.nom}`
    case 'coupe': return `Coupe de calcul ${sel.nom.split(' — ')[0]}`
    case 'coupe_locale': return 'Courbes en un point'
    case 'assemblage': return `Assemblage ${sel.nom}`
    default: return sel.nom
  }
}

/** Vue « Maquette 3D » : scène persistante, menus Affichage / Plan de coupe / Comparer / Outils / Exporter,
 *  un seul panneau latéral à la fois (Résultats, Calques, Courbes en un point). */
export function Onglet3D({ res, texte, phase, theme, selection, onSelection, projet, coupeActive = 0, cotes = {}, onEpingler, modele, onPhase, onOuvrir, prereglageInitial, onPrereglage, onAjouterSurcharge, onAjouterRisberme, etat3d, onEtat3d, unite }: {
  res: Resultats
  texte: string
  projet?: ProjetCoupes | null
  coupeActive?: number
  /** Noms des côtés (plan.cotes du script) et ajout d'une coupe épinglée au script. */
  cotes?: Record<string, number>
  onEpingler?: (entree: Record<string, unknown>) => void
  modele?: Modele
  onPhase?: (i: number) => void
  onOuvrir?: (vue: 'coupe' | 'efforts' | 'verifications' | 'synthese') => void
  /** Préréglage de calques demandé par l'ancre d'URL à l'ouverture. */
  prereglageInitial?: string | null
  onPrereglage?: (id: string | null) => void
  /** Ajout d'une surcharge tracée dans la maquette (entrée du bloc surcharges). */
  onAjouterSurcharge?: (entree: Record<string, unknown>) => void
  /** Ajout d'une risberme (entrée du bloc fouille.risbermes). */
  onAjouterRisberme?: (entree: Record<string, unknown>) => void
  /** État d'interface conservé par l'application (plan de coupe, panneau, courbes en un point). */
  etat3d: EtatVue3D
  onEtat3d: (e: Partial<EtatVue3D>) => void
  unite: string
  phase: number
  theme: Theme
  selection: string | null
  onSelection: (id: string | null) => void
}) {
  const poignee = useRef<PoigneeVue3D | null>(null)
  const { coupe, panneau, volet, largeur: largeurPanneau, positionLocale } = etat3d
  const setCoupe = (c: EtatVue3D['coupe']) => onEtat3d({ coupe: c })
  const basculerPanneau = (p: Exclude<EtatVue3D['panneau'], null>) => onEtat3d({ panneau: panneau === p ? null : p })
  const outilCoupe = panneau === 'courbes'
  const [exportEnCours, setExportEnCours] = useState(false)
  const [stock] = useState(lireStockage)
  const [calques, setCalques] = useState<EtatCalques>(() => (prereglageInitial && etatPrereglage(prereglageInitial, stock.perso)) || stock.etat)
  const [perso, setPerso] = useState<Prereglage[]>(stock.perso)
  const [disponibles, setDisponibles] = useState<Set<string>>(new Set())
  const calquesRef = useRef(calques)
  calquesRef.current = calques
  const [animation, setAnimation] = useState(() => { try { return localStorage.getItem('retainwall.3d.animation') !== '0' } catch { return true } })
  useEffect(() => { try { localStorage.setItem('retainwall.3d.animation', animation ? '1' : '0') } catch { /* stockage indisponible */ } }, [animation])
  const liste = useMemo(() => calculerLegendes(res, versScene(calques), phase, animation), [res, calques, phase, animation])
  const [infobulle, setInfobulle] = useState<{ x: number; y: number; lignes: string[] } | null>(null)
  const premiers = useMemo(() => (projet && !projet.unique ? projet.coupes[0].resultats ?? res : res), [projet, res])
  const extra = useMemo(() => ({ cotes, ...(projet ? { projet, resultatsPour: resolveur(projet, premiers, coupeActive) } : {}) }), [projet, premiers, coupeActive, cotes])
  const geo = useMemo(() => new Contour(res.maquette?.contour ?? [[0, 0], [20, 0], [20, 12], [0, 12]]), [res])
  const source = useMemo(() => sourcePourProjet(res, projet ?? null, premiers, coupeActive, geo), [res, projet, premiers, coupeActive, geo])
  useEffect(() => { poignee.current?.scene.definirCoupeLocale(outilCoupe ? positionLocale : null) }, [outilCoupe, positionLocale, res])
  const placerCoupe = (p: PositionCoupeLocale) => onEtat3d({ positionLocale: p, panneau: 'courbes' })
  const basculerCourbes = () => {
    if (outilCoupe) { onEtat3d({ panneau: null }); return }
    const a = geo.aretes.reduce((m, x) => (x.L > m.L ? x : m), geo.aretes[0])
    onEtat3d({ panneau: 'courbes', positionLocale: positionLocale ?? { k: a.k, sl: a.L / 2 } })
  }
  const [curseurZ, setCurseurZ] = useState<number | null>(null)
  const selRef = useRef(selection)
  selRef.current = selection
  const [outil, setOutil] = useState<Outil>(null)
  const [coinSurcharge, setCoinSurcharge] = useState<[number, number] | null>(null)
  const quitterOutil = () => { setOutil(null); setCoinSurcharge(null); poignee.current?.scene.definirMesure(null) }
  const choisirOutil = (o: Exclude<Outil, null>) => { if (outil === o) quitterOutil(); else { quitterOutil(); setOutil(o) } }
  const nomCote = (k: number) => Object.entries(cotes).find(([, v]) => v === k)?.[0] ?? k
  const choisir = (id: string | null, point?: THREE.Vector3) => {
    const sc = poignee.current?.scene
    if (outil === 'mesure' && point && sc) {
      const m = sc.mesure
      if (!m || m.b) sc.definirMesure({ a: point.clone(), b: null })
      else sc.definirMesure({ a: m.a, b: point.clone() })
      return
    }
    if (outil === 'risberme' && point && id?.startsWith('paroi:')) {
      const k = Number(id.slice(6)) || 0
      const fond = res.phases[phase]?.terrain_aval ?? res.maquette?.paroi.pied ?? 0
      setOutil(null)
      // une seule boîte, annulable : rien n'est écrit sans validation
      void saisir({
        titre: `Risberme contre le côté ${nomCote(k)}`, ok: 'Ajouter au script',
        champs: [
          { cle: 'crete', libelle: 'Cote de la crête (m)', type: 'number', defaut: nb(fond + 2.5, 2) },
          { cle: 'largeur', libelle: 'Largeur de la crête (m)', type: 'number', defaut: 2 },
          { cle: 'pente', libelle: 'Pente du talus (horizontal / vertical)', type: 'number', defaut: 1.5 },
          { cle: 'pied', libelle: 'Cote du pied, fond général (m)', type: 'number', defaut: nb(fond, 2) },
          { cle: 'nom', libelle: 'Nom', type: 'text', defaut: `R${(res.maquette?.terrain?.objets.length ?? 0) + 1}` },
        ],
      }).then((v) => {
        if (!v) return
        const largeur = Number(v.largeur), pente = Number(v.pente), nom = String(v.nom).trim()
        if (largeur <= 0 || pente <= 0 || !nom) { void informer('Largeur et pente doivent être positives, et le nom renseigné : rien n’a été ajouté.'); return }
        onAjouterRisberme?.(entreeYamlRisberme(nom, nomCote(k), Number(v.crete), largeur, pente, Number(v.pied), [Math.max(1, phase), Math.max(1, phase)]))
      })
      return
    }
    if (outil === 'surcharge' && point && (id?.startsWith('couche:') || id === null)) {
      const pt: [number, number] = [point.x, -point.z]
      if (!coinSurcharge) { setCoinSurcharge(pt); return }
      const p1 = coinSurcharge
      setOutil(null)
      setCoinSurcharge(null)
      void saisir({
        titre: 'Surcharge rectangulaire tracée sur le terrain', ok: 'Ajouter au script',
        champs: [
          { cle: 'q', libelle: 'Valeur (kPa)', type: 'number', defaut: 20 },
          { cle: 'nom', libelle: 'Nom', type: 'text', defaut: `S${(res.maquette?.surcharges?.length ?? 0) + 1}` },
        ],
      }).then((v) => {
        if (!v) return
        const q = Number(v.q), nom = String(v.nom).trim()
        if (q <= 0 || !nom) { void informer('La valeur doit être positive et le nom renseigné : rien n’a été ajouté.'); return }
        onAjouterSurcharge?.(entreeYamlSurcharge(nom, q, p1, pt, phase > 0 ? phase : null))
      })
      return
    }
    if (outilCoupe && point && id?.startsWith('paroi:')) { onEtat3d({ positionLocale: positionDepuisPoint(geo, point) }); return }
    onSelection(id)
    if (id && panneau === null) onEtat3d({ panneau: 'resultats' })
  }
  const survoler = useCallback((id: string | null, point?: THREE.Vector3, ecran?: { x: number; y: number }) => {
    const sc = poignee.current?.scene
    if (id?.startsWith('paroi:') && point) {
      const k = Number(id.slice(6)) || 0
      setCurseurZ(point.y)
      sc?.definirRepere({ k, z: point.y })
    } else { setCurseurZ(null); sc?.definirRepere(null) }
    if (!id || !ecran || !sc?.d) { setInfobulle(null); return }
    const sel = analyserSelection(id)
    const lignes: string[] = []
    if (sel?.type === 'paroi' && point) {
      const ctx = { scene: sc, d: sc.d, phase: sc.phaseActive, ph: sc.d.res.phases[sc.phaseActive], fab: sc.fab, plan: sc.planCoupe }
      const sl = sc.d.geo.projeter(point.x, -point.z).sl
      const src = sourcePour(ctx, sel.k ?? 0, sl)
      const fy = profilValeur(src.res, src.phase, 'y', sc.d.geo.aretes[sel.k ?? 0].s0 + sl)
      const fM = profilValeur(src.res, src.phase, 'M', sc.d.geo.aretes[sel.k ?? 0].s0 + sl)
      lignes.push(`Écran · côté ${sel.k ?? 0}${src.coupe ? ` · ${src.coupe.split(' — ')[0]}` : ''} · z = ${nb(point.y, 2)} m`)
      if (fy) lignes.push(`déplacement y = ${nb(fy(point.y), 1)} mm`)
      if (fM) lignes.push(`moment M = ${nb(fM(point.y), 0)} kN·m/m`)
    } else if (sel?.type === 'appui' || sel?.type === 'lierne') {
      const a = sc.d.res.phases[sc.phaseActive]?.appuis?.find((x) => x.nom === sel.nom)
      lignes.push(`${sel.type === 'lierne' ? 'Lierne de ' : ''}${sel.nom}`)
      if (a) lignes.push(`effort ${nb(a.effort_kN_m, 1)} kN/m · ${nb(a.effort_axial_kN, 0)} kN${a.fleche_mm != null ? ` · flèche ${nb(a.fleche_mm, 1)} mm` : ''}`)
    } else if (sel) lignes.push(libelleSelection(sel, sc.d.res))
    else lignes.push(id)
    setInfobulle({ x: ecran.x + 14, y: ecran.y + 14, lignes })
  }, [])
  const exporterImage = (facteur: 1 | 2) => {
    const p = poignee.current
    if (!p) return
    telecharger(imagePng(p.rendu, p.scene.scene, p.scene.camera, liste, facteur, theme === 'sombre'), `maquette_phase${phase}${facteur === 2 ? '_x2' : ''}.png`)
  }
  const exporterScene = async () => {
    const p = poignee.current
    if (!p) return
    try {
      const blob = await exporterGltf(p.scene.scene)
      const url = URL.createObjectURL(blob)
      telecharger(url, `maquette_phase${phase}.glb`)
      window.setTimeout(() => URL.revokeObjectURL(url), 30_000)
    } catch (e) {
      void informer(`Export glTF impossible : ${messageErreur(e)}`)
    }
  }
  const comparer = (ref: number) => {
    let e = definirVisible(calquesRef.current, 'resultats.comparaison', ref > 0)
    e = definirReglage(e, 'resultats.comparaison', 'phase', ref)
    if (ref > 0) e = definirVisible(e, 'resultats.deformee', true)
    setCalques(e)
  }
  const appliquerPrereglage = (id: string) => {
    const e = etatPrereglage(id, perso)
    if (e) { setCalques(e); onPrereglage?.(id) }
  }
  const survolCourbe = useCallback((z: number | null) => {
    const sc = poignee.current?.scene
    const sel = analyserSelection(selRef.current)
    sc?.definirRepere(z === null ? null : { k: sel?.type === 'paroi' ? sel.k ?? 0 : geo.aretes.reduce((m, x) => (x.L > m.L ? x : m), geo.aretes[0]).k, z })
  }, [geo])
  const centrer = (id: string) => {
    const sc = poignee.current?.scene
    const c = sc?.centreDe(id)
    if (sc && c) sc.centrerSur(c, Math.max(12, sc.orbite.rayon * 0.5))
  }
  const miettes = useMemo(() => filAriane(analyserSelection(selection), projet ?? null, coupeActive, res.maquette?.assemblages ?? {}, (res.maquette?.surcharges ?? []).map((x) => x.nom)), [selection, projet, coupeActive, res])

  const appliquer = useCallback((sc: SceneRetainWall) => {
    sc.appliquerCalques(versScene(calquesRef.current))
    setDisponibles(new Set([...sc.elements.values()].map((e) => e.calque)))
  }, [])

  const pret = useCallback((p: PoigneeVue3D | null) => { poignee.current = p }, [])

  useEffect(() => { poignee.current?.scene.definirCoupe(coupe) }, [coupe])
  useEffect(() => {
    ecrireStockage(calques, perso)
    const p = poignee.current
    if (p) appliquer(p.scene)
  }, [calques, perso, appliquer])

  useEffect(() => {
    const touche = (e: KeyboardEvent) => {
      const cible = e.target as HTMLElement | null
      if (cible?.closest?.('input, textarea, select, .monaco-editor, .dialogue') || e.ctrlKey || e.metaKey || e.altKey) return
      if (e.key === 'l' || e.key === 'L') { e.preventDefault(); basculerPanneau('calques') }
      if (e.key === 'c' || e.key === 'C') { e.preventDefault(); basculerCourbes() }
      if (e.key === 'r' || e.key === 'R') { e.preventDefault(); basculerPanneau('resultats') }
      if (e.key === 'Escape') { onSelection(null); quitterOutil(); if (outilCoupe) onEtat3d({ panneau: null }) }
      if (e.key === 'f' || e.key === 'F') { e.preventDefault(); poignee.current?.scene.recadrer() }
    }
    window.addEventListener('keydown', touche)
    return () => window.removeEventListener('keydown', touche)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [etat3d, geo, outil])

  useEffect(() => {
    enregistrerExport(() => exporterImage(1))
    return () => enregistrerExport(null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, liste, theme])

  const exporterHtml = async () => {
    setExportEnCours(true)
    try { telechargerTexte(await api.maquette(texte), 'maquette_retainwall.html', 'text/html') }
    catch (e) { void informer(`Export de la maquette impossible : ${messageErreur(e)}`) }
    finally { setExportEnCours(false) }
  }

  const vue = (n: 'iso' | 'face' | 'dessus' | 'coupe') => {
    poignee.current?.scene.vue(n)
    if (n === 'coupe') setCoupe({ actif: true, axe: 'x', t: 0.5 })
  }
  const refComparaison = Number(calques.feuilles['resultats.comparaison']?.reglages?.phase ?? 0)
  const outilCourant = OUTILS.find((o) => o.cle === outil)

  return (
    <div className="onglet-3d">
      <div className="barre-outils barre-3d">
        <button className="btn" onClick={() => vue('iso')} title="Vue isométrique">Iso</button>
        <button className="btn" onClick={() => vue('face')} title="Vue de face">Face</button>
        <button className="btn" onClick={() => vue('dessus')} title="Vue de dessus">Dessus</button>
        <button className="btn" title="Recadrer sur la fouille (F)" onClick={() => poignee.current?.scene.recadrer()}>Recadrer</button>
        <span className="separateur-v" />
        <Menu bouton={<>Affichage <IconeChevronB taille={12} /></>} titre="Préréglages de calques et animation">
          {(fermer) => (
            <>
              <div className="titre-groupe">Préréglages de calques</div>
              {[...PREREGLAGES_LIVRES, ...perso].map((p) => (
                <button key={p.id} title={p.description} onClick={() => { appliquerPrereglage(p.id); fermer() }}>{p.nom}<span className="detail-entree">{p.description}</span></button>
              ))}
              <hr />
              <label title="Interpolation visuelle entre deux phases pendant la lecture et les changements de phase (désactivée si le système demande moins d'animations)">
                <input type="checkbox" checked={animation} onChange={(e) => setAnimation(e.target.checked)} /> Animation entre les phases (purement visuelle)
              </label>
              <button onClick={() => { basculerPanneau('calques'); fermer() }}>Tous les calques… <span className="raccourci">L</span></button>
            </>
          )}
        </Menu>
        <Menu bouton={<>Plan de coupe <IconeChevronB taille={12} /></>} titre="Plan de coupe de la maquette">
          {(fermer) => (
            <>
              <label><input type="checkbox" checked={coupe.actif} onChange={(e) => setCoupe({ ...coupe, actif: e.target.checked })} /> Plan de coupe actif</label>
              <label>Axe
                <select value={coupe.axe} disabled={!coupe.actif} onChange={(e) => setCoupe({ ...coupe, axe: e.target.value as 'x' | 'y' })} aria-label="Axe du plan de coupe">
                  <option value="x">selon x</option>
                  <option value="y">selon y</option>
                </select>
              </label>
              <label>Position
                <input type="range" min={0} max={1000} value={Math.round(coupe.t * 1000)} disabled={!coupe.actif} aria-label="Position du plan de coupe"
                  onChange={(e) => setCoupe({ ...coupe, t: Number(e.target.value) / 1000 })} style={{ width: 160 }} />
              </label>
              <hr />
              <button onClick={() => { vue('coupe'); fermer() }}>Vue en coupe (caméra de face, plan actif)</button>
            </>
          )}
        </Menu>
        <Menu bouton={<>Comparer{refComparaison > 0 ? ` : ${refComparaison - 1}` : ''} <IconeChevronB taille={12} /></>} titre="Superpose en fantôme la déformée d'une phase de référence">
          {(fermer) => (
            <>
              <div className="titre-groupe">Phase de référence (fantôme)</div>
              <button onClick={() => { comparer(0); fermer() }}>Aucune</button>
              {res.phases.map((p, i) => <button key={i} className={refComparaison === i + 1 ? 'actif' : ''} onClick={() => { comparer(i + 1); fermer() }}>{i}. {p.nom}</button>)}
            </>
          )}
        </Menu>
        <Menu bouton={<>Outils <IconeChevronB taille={12} /></>} titre="Outils de mesure et d'ajout au script">
          {(fermer) => (
            <>
              {OUTILS.map((o) => <button key={o.cle} onClick={() => { choisirOutil(o.cle); fermer() }}>{outil === o.cle ? 'Quitter : ' : ''}{o.nom}<span className="detail-entree">{o.consigne}</span></button>)}
              <hr />
              <button onClick={() => { basculerCourbes(); fermer() }}>{outilCoupe ? 'Fermer les courbes en un point' : 'Courbes en un point de la paroi'} <span className="raccourci">C</span><span className="detail-entree">cliquez la paroi ou glissez le curseur du panneau ; épinglage possible comme coupe de calcul</span></button>
            </>
          )}
        </Menu>
        {outilCourant && (
          <span className="outil-actif" role="status">
            Outil : {outilCourant.nom}{outil === 'surcharge' && coinSurcharge ? ' (second coin)' : ''} · {outilCourant.consigne} · <button className="btn discret" onClick={quitterOutil}>Quitter (Échap)</button>
          </span>
        )}
        <span className="espace" />
        <button className={`btn ${panneau === 'resultats' ? 'actif' : ''}`} title="Panneau de résultats de la sélection (R)" onClick={() => basculerPanneau('resultats')}><IconeTableau taille={14} /> Résultats</button>
        <button className={`btn ${panneau === 'calques' ? 'actif' : ''}`} title="Calques (L)" onClick={() => basculerPanneau('calques')}><IconeCalques taille={14} /> Calques</button>
        <Menu droite bouton={<>{exportEnCours ? 'Génération…' : 'Exporter'} <IconeChevronB taille={12} /></>} titre="Exports de la maquette">
          {(fermer) => (
            <>
              <button onClick={() => { exporterImage(1); fermer() }}>Image PNG avec légendes (×1)</button>
              <button onClick={() => { exporterImage(2); fermer() }}>Image PNG avec légendes (×2)</button>
              <button onClick={() => { void exporterScene(); fermer() }}>Scène glTF (.glb), phase active</button>
              <button onClick={() => { void exporterHtml(); fermer() }}>Fichier HTML autonome</button>
            </>
          )}
        </Menu>
      </div>
      <nav className="fil-ariane" aria-label="Fil d'Ariane">
        {miettes.map((m, i) => (
          <span key={i}>
            {i > 0 && <span className="sep">›</span>}
            <button className="miette" onClick={() => onSelection(m.selection)}>{m.libelle}</button>
          </span>
        ))}
        {!selection && <span className="doux" style={{ marginLeft: 8 }}>Cliquez un objet de la maquette : ses résultats s'affichent dans le panneau Résultats.</span>}
      </nav>
      <div className="onglet-3d-corps">
        <Vue3D res={res} extra={extra} phase={phase} theme={theme} selection={selection} onSelection={choisir} onSurvol={survoler} onPret={pret} animationMs={animation ? 350 : 0} surCalques={appliquer} fabriques={FABRIQUES}
          enfants={<>
            <Legendes liste={liste} />
            {infobulle && <div className="vue3d-infobulle" style={{ left: infobulle.x, top: infobulle.y }}>{infobulle.lignes.map((l, i) => <div key={i} className={i === 0 ? 'titre' : ''}>{l}</div>)}</div>}
            <div className="vue3d-note">
              {res.maquette?.plan_defaut && <div>Plan par défaut (rectangle 20 × 12 m) : la géométrie réelle se déclare dans le bloc « plan » du script.</div>}
              <div>Glisser : rotation · clic droit ou Maj+glisser : translation · molette : zoom.</div>
            </div>
          </>} />
        {panneau === 'resultats' && (
          <PanneauResultats res={res} projet={projet ?? null} coupeActive={coupeActive} phase={phase} selection={selection} modele={modele} theme={theme} unite={unite}
            resultatsPour={extra.resultatsPour} largeur={largeurPanneau} curseurZ={curseurZ} volet={volet} onVolet={(v) => onEtat3d({ volet: v })}
            onSelection={(id) => onSelection(id)} onPhase={(i) => onPhase?.(i)} onOuvrir={(o) => onOuvrir?.(o)} onFermer={() => onEtat3d({ panneau: null })}
            onCentrer={centrer} onSurvolZ={survolCourbe} onLargeur={(l) => onEtat3d({ largeur: l })} />
        )}
        {outilCoupe && positionLocale && (
          <PanneauCoupeLocale geo={geo} source={source} position={positionLocale} phase={phase} theme={theme} cotes={cotes} unite={unite}
            onPosition={placerCoupe} onFermer={() => onEtat3d({ panneau: null })}
            onEpingler={(nom) => onEpingler?.(entreeYamlCoupe(nom, geo, positionLocale.k, positionLocale.sl, cotes))} />
        )}
        {panneau === 'calques' && (
          <PanneauCalques etat={calques} perso={perso} onEtat={setCalques} onPerso={setPerso} onPrereglage={onPrereglage} onFermer={() => onEtat3d({ panneau: null })} disponibles={disponibles} />
        )}
      </div>
    </div>
  )
}
