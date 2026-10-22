import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type * as THREE from 'three'
import { api, type ProjetCoupes, type Resultats } from '../lib/api'
import { enregistrerExport, telecharger, telechargerTexte } from '../lib/exporter'
import { IconeCalques } from '../lib/icones'
import type { Theme } from '../lib/theme'
import { nb } from '../lib/format'
import { ecrireStockage, lireStockage, versScene, type EtatCalques, type Prereglage } from './calques'
import { FABRIQUES_CHANTIER } from './elements'
import { Legendes } from './VueLegendes'
import { legendes as calculerLegendes } from './legendes'
import { PanneauCalques } from './PanneauCalques'
import { FABRIQUES_RESULTATS_PAROI } from './resultats'
import { FABRIQUES_RESULTATS_APPUIS } from './resultatsAppuis'
import { FABRIQUES_COUPES, resolveur } from './coupes'
import { FABRIQUES_COUPE_LOCALE, positionDepuisPoint, type PositionCoupeLocale } from './coupeLocale'
import { PanneauCoupeLocale } from './PanneauCoupeLocale'
import { entreeYamlCoupe, sourcePourProjet } from './sourceResultats'
import { Contour } from './geometrie'
import { IconeCiseaux, IconeTableau } from '../lib/icones'
import type { Modele } from '../lib/scriptDoc'
import { analyserSelection, filAriane } from './navigation'
import { PanneauResultats, type Volet } from './PanneauResultats'
import { FABRIQUES_REPERES } from './reperes'
import { entreeYamlSurcharge, FABRIQUES_SURCHARGES } from './surcharges'
import { entreeYamlRisberme, FABRIQUES_TERRAIN } from './terrain'
import { IconeRemblai, IconeCoupe } from '../lib/icones'
import { IconeSurcharge } from '../lib/icones'
import { etatPrereglage } from './calques'

const FABRIQUES = [...FABRIQUES_CHANTIER, ...FABRIQUES_RESULTATS_PAROI, ...FABRIQUES_RESULTATS_APPUIS, ...FABRIQUES_COUPES, ...FABRIQUES_COUPE_LOCALE, ...FABRIQUES_REPERES, ...FABRIQUES_SURCHARGES, ...FABRIQUES_TERRAIN]
import type { EtatCoupe, SceneRetainWall } from './scene'
import { Vue3D, type PoigneeVue3D } from './Vue3D'

/** Onglet « Maquette 3D » : vue persistante, outils de vue, plan de coupe, calques, exports. */
export function Onglet3D({ res, texte, phase, theme, selection, onSelection, projet, coupeActive = 0, onCoupe, cotes = {}, onEpingler, modele, onPhase, onOuvrir, prereglageInitial, onPrereglage, onAjouterSurcharge, onAjouterRisberme }: {
  res: Resultats
  texte: string
  projet?: ProjetCoupes | null
  coupeActive?: number
  onCoupe?: (i: number) => void
  /** Noms des côtés (plan.cotes du script) et ajout d'une coupe épinglée au script. */
  cotes?: Record<string, number>
  onEpingler?: (entree: Record<string, unknown>) => void
  modele?: Modele
  onPhase?: (i: number) => void
  onOuvrir?: (onglet: 'coupe' | 'efforts' | 'verifications') => void
  /** Préréglage de calques demandé par l'ancre d'URL à l'ouverture. */
  prereglageInitial?: string | null
  onPrereglage?: (id: string | null) => void
  /** Ajout d'une surcharge tracée dans la maquette (entrée du bloc surcharges). */
  onAjouterSurcharge?: (entree: Record<string, unknown>) => void
  /** Ajout d'une risberme (entrée du bloc fouille.risbermes). */
  onAjouterRisberme?: (entree: Record<string, unknown>) => void
  phase: number
  theme: Theme
  selection: string | null
  onSelection: (id: string | null) => void
}) {
  const poignee = useRef<PoigneeVue3D | null>(null)
  const [coupe, setCoupe] = useState<EtatCoupe>({ actif: false, axe: 'x', t: 0.5 })
  const [exportEnCours, setExportEnCours] = useState(false)
  const [stock] = useState(lireStockage)
  const [calques, setCalques] = useState<EtatCalques>(() => (prereglageInitial && etatPrereglage(prereglageInitial, stock.perso)) || stock.etat)
  const [perso, setPerso] = useState<Prereglage[]>(stock.perso)
  const [voirCalques, setVoirCalques] = useState(false)
  const [disponibles, setDisponibles] = useState<Set<string>>(new Set())
  const calquesRef = useRef(calques)
  calquesRef.current = calques
  const liste = useMemo(() => calculerLegendes(res, versScene(calques), phase), [res, calques, phase])
  const premiers = useMemo(() => (projet && !projet.unique ? projet.coupes[0].resultats ?? res : res), [projet, res])
  const extra = useMemo(() => ({ cotes, ...(projet ? { projet, resultatsPour: resolveur(projet, premiers, coupeActive) } : {}) }), [projet, premiers, coupeActive, cotes])
  const plusieurs = !!projet && !projet.unique && projet.coupes.length > 1
  const [outilCoupe, setOutilCoupe] = useState(false)
  const [positionLocale, setPositionLocale] = useState<PositionCoupeLocale | null>(null)
  const geo = useMemo(() => new Contour(res.maquette?.contour ?? [[0, 0], [20, 0], [20, 12], [0, 12]]), [res])
  const source = useMemo(() => sourcePourProjet(res, projet ?? null, premiers, coupeActive, geo), [res, projet, premiers, coupeActive, geo])
  useEffect(() => { poignee.current?.scene.definirCoupeLocale(outilCoupe ? positionLocale : null) }, [outilCoupe, positionLocale, res])
  const placerCoupe = (p: PositionCoupeLocale) => { setPositionLocale(p); setOutilCoupe(true) }
  const basculerOutil = () => {
    if (outilCoupe) setOutilCoupe(false)
    else { setOutilCoupe(true); if (!positionLocale) { const a = geo.aretes.reduce((m, x) => (x.L > m.L ? x : m), geo.aretes[0]); setPositionLocale({ k: a.k, sl: a.L / 2 }) } }
  }
  const [voirResultats, setVoirResultats] = useState(false)
  const [volet, setVolet] = useState<Volet>('courbes')
  const [largeurPanneau, setLargeurPanneau] = useState(420)
  const [curseurZ, setCurseurZ] = useState<number | null>(null)
  const selRef = useRef(selection)
  selRef.current = selection
  const [outilSurcharge, setOutilSurcharge] = useState<{ p1: [number, number] | null } | null>(null)
  const [outilRisberme, setOutilRisberme] = useState(false)
  const [outilMesure, setOutilMesure] = useState(false)
  const nomCote = (k: number) => Object.entries(cotes).find(([, v]) => v === k)?.[0] ?? k
  const choisir = (id: string | null, point?: THREE.Vector3) => {
    const sc = poignee.current?.scene
    if (outilMesure && point && sc) {
      const m = sc.mesure
      if (!m || m.b) sc.definirMesure({ a: point.clone(), b: null })
      else sc.definirMesure({ a: m.a, b: point.clone() })
      return
    }
    if (outilRisberme && point && id?.startsWith('paroi:')) {
      const k = Number(id.slice(6)) || 0
      const fond = res.phases[phase]?.terrain_aval ?? res.maquette!.paroi.pied
      const crete = Number(window.prompt(`Risberme contre le côté ${nomCote(k)} — cote de la crête (m) :`, nb(fond + 2.5, 2).replace(',', '.')))
      const largeur = Number(window.prompt('Largeur de la crête (m) :', '2'))
      const pente = Number(window.prompt('Pente du talus (horizontal / vertical) :', '1.5'))
      const pied = Number(window.prompt('Cote du pied, fond général (m) :', nb(fond, 2).replace(',', '.')))
      const nom = window.prompt('Nom de la risberme :', `R${(res.maquette?.terrain?.objets.length ?? 0) + 1}`)
      setOutilRisberme(false)
      if ([crete, largeur, pente, pied].every(Number.isFinite) && nom) onAjouterRisberme?.(entreeYamlRisberme(nom, nomCote(k), crete, largeur, pente, pied, [Math.max(1, phase), Math.max(1, phase)]))
      return
    }
    if (outilSurcharge && point && (id?.startsWith('couche:') || id === null)) {
      const pt: [number, number] = [point.x, -point.z]
      if (!outilSurcharge.p1) { setOutilSurcharge({ p1: pt }); return }
      const q = Number(window.prompt('Valeur de la surcharge (kPa) :', '20'))
      const nom = window.prompt('Nom de la surcharge :', `S${(res.maquette?.surcharges?.length ?? 0) + 1}`)
      setOutilSurcharge(null)
      if (Number.isFinite(q) && q > 0 && nom) onAjouterSurcharge?.(entreeYamlSurcharge(nom, q, outilSurcharge.p1, pt, phase > 0 ? phase : null))
      return
    }
    if (outilCoupe && point && id?.startsWith('paroi:')) { setPositionLocale(positionDepuisPoint(geo, point)); return }
    onSelection(id)
    if (id) setVoirResultats(true)
  }
  const survoler = useCallback((id: string | null, point?: THREE.Vector3) => {
    const sc = poignee.current?.scene
    if (id?.startsWith('paroi:') && point) {
      const k = Number(id.slice(6)) || 0
      setCurseurZ(point.y)
      sc?.definirRepere({ k, z: point.y })
    } else { setCurseurZ(null); sc?.definirRepere(null) }
  }, [])
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
      if (cible?.closest?.('input, textarea, select, .monaco-editor') || e.ctrlKey || e.metaKey || e.altKey) return
      if (e.key === 'l' || e.key === 'L') { e.preventDefault(); setVoirCalques((v) => !v) }
      if (e.key === 'c' || e.key === 'C') { e.preventDefault(); basculerOutil() }
      if (e.key === 'r' || e.key === 'R') { e.preventDefault(); setVoirResultats((v) => !v) }
      if (e.key === 'Escape') { onSelection(null); setOutilCoupe(false); setOutilMesure(false); setOutilRisberme(false); setOutilSurcharge(null); poignee.current?.scene.definirMesure(null) }
      if (e.key === 'f' || e.key === 'F') { e.preventDefault(); poignee.current?.scene.recadrer() }
    }
    window.addEventListener('keydown', touche)
    return () => window.removeEventListener('keydown', touche)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [outilCoupe, positionLocale, geo])

  useEffect(() => {
    enregistrerExport(() => {
      const p = poignee.current
      if (!p) return
      p.scene.rendreMaintenant()
      telecharger(p.canvas.toDataURL('image/png'), `maquette_phase${phase + 1}.png`)
    })
    return () => enregistrerExport(null)
  }, [phase])

  const exporterHtml = async () => {
    setExportEnCours(true)
    try { telechargerTexte(await api.maquette(texte), 'maquette_retainwall.html', 'text/html') }
    catch (e) { alert(String(e)) }
    finally { setExportEnCours(false) }
  }

  const vue = (n: 'iso' | 'face' | 'dessus' | 'coupe') => {
    poignee.current?.scene.vue(n)
    if (n === 'coupe') setCoupe({ actif: true, axe: 'x', t: 0.5 })
  }

  return (
    <div className="onglet-3d">
      <div className="barre-outils">
        <span className="doux">Vue :</span>
        <button className="btn" onClick={() => vue('iso')}>Iso</button>
        <button className="btn" onClick={() => vue('face')}>Face</button>
        <button className="btn" onClick={() => vue('dessus')}>Dessus</button>
        <button className="btn" onClick={() => vue('coupe')}>Coupe</button>
        <button className="btn" title="Recadrer sur la fouille (F)" onClick={() => poignee.current?.scene.recadrer()}>Recadrer</button>
        <span className="separateur-v" />
        <label><input type="checkbox" checked={coupe.actif} onChange={(e) => setCoupe({ ...coupe, actif: e.target.checked })} /> plan de coupe</label>
        <select value={coupe.axe} disabled={!coupe.actif} onChange={(e) => setCoupe({ ...coupe, axe: e.target.value as 'x' | 'y' })} aria-label="Axe du plan de coupe">
          <option value="x">selon x</option>
          <option value="y">selon y</option>
        </select>
        <input type="range" min={0} max={1000} value={Math.round(coupe.t * 1000)} disabled={!coupe.actif} aria-label="Position du plan de coupe"
          onChange={(e) => setCoupe({ ...coupe, t: Number(e.target.value) / 1000 })} style={{ width: 140 }} />
        <span className="espace" />
        {plusieurs && (
          <label title="Coupe de calcul affichée (touches 1 à 9)">Coupe :
            <select value={coupeActive} onChange={(e) => onCoupe?.(Number(e.target.value))} aria-label="Coupe de calcul active">
              {projet!.coupes.map((c, i) => <option key={c.nom} value={i}>{i + 1}. {c.nom}</option>)}
            </select>
          </label>
        )}
        <button className={`btn ${outilCoupe ? 'actif' : ''}`} title="Couper ici (C) : cliquer sur la paroi ou glisser la coupe locale" onClick={basculerOutil}><IconeCiseaux taille={14} /> Couper ici</button>
        <button className={`btn ${outilRisberme ? 'actif' : ''}`} title="Ajouter une risberme : cliquer un côté de la paroi, puis saisir la géométrie" onClick={() => setOutilRisberme(!outilRisberme)}><IconeRemblai taille={14} /> {outilRisberme ? 'Cliquez un côté…' : 'Ajouter une risberme'}</button>
        <button className={`btn ${outilMesure ? 'actif' : ''}`} title="Mesurer : deux clics, distance et dénivelée" onClick={() => { setOutilMesure(!outilMesure); if (outilMesure) poignee.current?.scene.definirMesure(null) }}><IconeCoupe taille={14} /> Mesurer</button>
        <button className={`btn ${outilSurcharge ? 'actif' : ''}`} title="Ajouter une surcharge : cliquer deux coins de l'emprise sur le terrain, puis saisir la valeur" onClick={() => setOutilSurcharge(outilSurcharge ? null : { p1: null })}><IconeSurcharge taille={14} /> {outilSurcharge ? (outilSurcharge.p1 ? 'Second coin…' : 'Premier coin…') : 'Ajouter une surcharge'}</button>
        <button className={`btn ${voirResultats ? 'actif' : ''}`} title="Panneau de résultats (R)" onClick={() => setVoirResultats(!voirResultats)}><IconeTableau taille={14} /> Résultats</button>
        <button className={`btn ${voirCalques ? 'actif' : ''}`} title="Calques (L)" onClick={() => setVoirCalques(!voirCalques)}><IconeCalques taille={14} /> Calques</button>
        <button className="btn" disabled={exportEnCours} onClick={() => void exporterHtml()}>
          {exportEnCours ? 'Génération…' : 'Exporter le fichier HTML autonome'}
        </button>
      </div>
      <nav className="fil-ariane" aria-label="Fil d'Ariane">
        {miettes.map((m, i) => (
          <span key={i}>
            {i > 0 && <span className="sep">›</span>}
            <button className="miette" onClick={() => onSelection(m.selection)}>{m.libelle}</button>
          </span>
        ))}
        {!selection && <span className="doux" style={{ marginLeft: 8 }}>Cliquez un objet de la maquette pour ouvrir ses résultats.</span>}
      </nav>
      <div className="onglet-3d-corps">
        <Vue3D res={res} extra={extra} phase={phase} theme={theme} selection={selection} onSelection={choisir} onSurvol={survoler} onPret={pret} surCalques={appliquer} fabriques={FABRIQUES}
          enfants={<>
            <Legendes liste={liste} />
            <div className="vue3d-note">
              {res.maquette?.plan_defaut && <div>Plan par défaut (rectangle 20 × 12 m) : ajoutez un bloc « plan » au script.</div>}
              <div>Glisser : tourner · clic droit ou Maj+glisser : déplacer · molette : zoom.</div>
              <div>Déplacement positif vers la fouille ; moment positif quand la face côté fouille est tendue.</div>
            </div>
          </>} />
        {voirResultats && (
          <PanneauResultats res={res} projet={projet ?? null} coupeActive={coupeActive} phase={phase} selection={selection} modele={modele} theme={theme}
            resultatsPour={extra.resultatsPour} largeur={largeurPanneau} curseurZ={curseurZ} volet={volet} onVolet={setVolet}
            onSelection={(id) => onSelection(id)} onPhase={(i) => onPhase?.(i)} onOuvrir={(o) => onOuvrir?.(o)} onFermer={() => setVoirResultats(false)}
            onCentrer={centrer} onSurvolZ={survolCourbe} onLargeur={setLargeurPanneau} />
        )}
        {outilCoupe && positionLocale && (
          <PanneauCoupeLocale geo={geo} source={source} position={positionLocale} phase={phase} theme={theme} cotes={cotes}
            onPosition={placerCoupe} onFermer={() => setOutilCoupe(false)}
            onEpingler={(nom) => onEpingler?.(entreeYamlCoupe(nom, geo, positionLocale.k, positionLocale.sl, cotes))} />
        )}
        {voirCalques && (
          <PanneauCalques etat={calques} perso={perso} onEtat={setCalques} onPerso={setPerso} onPrereglage={onPrereglage} onFermer={() => setVoirCalques(false)} disponibles={disponibles} />
        )}
      </div>
    </div>
  )
}
