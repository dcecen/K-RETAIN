import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { api, type ErreurScript, type Resultats } from './lib/api'
import type { EtatCalcul, Onglet, Section, Selection } from './lib/etat'
import { exporterImage, imprimerNote, telechargerTexte } from './lib/exporter'
import { IconeAppui, IconeBase, IconeCoupe, IconeCube, IconePlaque, IconeProjet, IconeScript, IconeTableau, IconeVerif } from './lib/icones'
import * as sd from './lib/scriptDoc'
import { appliquerTheme, themeInitial, type Theme } from './lib/theme'
import { BarreTitre } from './composants/BarreTitre'
import { FrisePhases } from './composants/FrisePhases'
import { Inspecteur } from './composants/Inspecteur'
import { Navigation } from './composants/Navigation'
import { CoupeDiagrammes } from './vues/CoupeDiagrammes'
import { Editeur } from './vues/Editeur'
import { Efforts } from './vues/Efforts'
import { Maquette3D } from './vues/Maquette3D'
import { Materiaux } from './vues/Materiaux'
import { Pseudo3D } from './vues/Pseudo3D'
import { Saisie } from './vues/Saisie'
import { Verifications } from './vues/Verifications'
import { Assemblages } from './vues/Assemblages'

const CLE_BROUILLON = 'retainwall.brouillon'
const lireBrouillon = () => { try { return localStorage.getItem(CLE_BROUILLON) } catch { return null } }
const ecrireBrouillon = (t: string) => { try { localStorage.setItem(CLE_BROUILLON, t) } catch { /* stockage indisponible */ } }

export default function App() {
  const [texte, setTexteBrut] = useState<string>(() => lireBrouillon() ?? '')
  const [erreurs, setErreurs] = useState<ErreurScript[]>([])
  const [res, setRes] = useState<Resultats | null>(null)
  const [version, setVersion] = useState(0)
  const [phase, setPhase] = useState(0)
  const [onglet, setOnglet] = useState<Onglet>('coupe')
  const [section, setSection] = useState<Section | null>(null)
  const [selection, setSelection] = useState<Selection>(null)
  const [schema, setSchema] = useState<unknown>(null)
  const [references, setReferences] = useState<Record<string, string[]>>({})
  const [exemples, setExemples] = useState<{ nom: string; texte: string }[]>([])
  const [enCours, setEnCours] = useState(false)
  const [etat, setEtat] = useState<EtatCalcul>({ genre: 'aucun', texte: 'Aucun calcul' })
  const [ligneCible, setLigneCible] = useState<number | null>(null)
  const [theme, setTheme] = useState<Theme>(themeInitial)
  const [nav, setNav] = useState(true)
  const [insp, setInsp] = useState(true)
  const [tiroirNav, setTiroirNav] = useState(false)
  const [tiroirInsp, setTiroirInsp] = useState(false)
  const [rapportRido, setRapportRido] = useState<string[] | null>(null)
  const [serveur, setServeur] = useState('')
  const minuterie = useRef<number | undefined>(undefined)
  const texteCalcule = useRef<string>('')

  const { modele, erreur: erreurYaml } = useMemo(() => sd.lire(texte), [texte])

  useEffect(() => { appliquerTheme(theme) }, [theme])

  useEffect(() => {
    fetch('/api/sante').then((r) => r.json()).then((d) => setServeur(`v${d.version}`)).catch(() => setServeur('serveur injoignable'))
    api.schema().then(setSchema).catch(() => {})
    api.references().then(setReferences)
    api.exemples().then((ex) => {
      setExemples(ex)
      if (!lireBrouillon() && ex.length) setTexteBrut(ex[0].texte)
    }).catch(() => {})
  }, [])

  // Validation en direct, état « modifié »
  useEffect(() => {
    ecrireBrouillon(texte)
    window.clearTimeout(minuterie.current)
    minuterie.current = window.setTimeout(() => {
      if (!texte.trim()) return
      api.valider(texte).then((r) => {
        setErreurs(r.erreurs)
        if (r.erreurs.length) {
          const e = r.erreurs[0]
          setEtat({ genre: 'erreur', texte: e.ligne ? `Erreur ligne ${e.ligne}` : 'Script invalide', ligne: e.ligne })
        } else if (texte !== texteCalcule.current) {
          setEtat(res ? { genre: 'modifie', texte: 'Script modifié — à recalculer' } : { genre: 'aucun', texte: 'Prêt à calculer' })
        } else if (res) {
          setEtat((e) => (e.genre === 'ok' || e.genre === 'rupture' ? e : { genre: 'ok', texte: `Calculé · ${res.phases.length} phases` }))
        }
      }).catch(() => {})
    }, 500)
  }, [texte, res])

  const setTexte = useCallback((t: string) => setTexteBrut(t), [])

  const calculer = useCallback(async () => {
    if (!texte.trim()) return
    setEnCours(true)
    const t0 = performance.now()
    try {
      const r = await api.calcul(texte)
      const ms = Math.round(performance.now() - t0)
      setErreurs(r.erreurs)
      if (r.ok && r.resultats) {
        texteCalcule.current = texte
        setRes(r.resultats)
        setVersion((v) => v + 1)
        setPhase(r.resultats.phases.length - 1)
        setEtat(r.resultats.complet
          ? { genre: 'ok', texte: `Calculé · ${r.resultats.phases.length} phases · ${ms} ms` }
          : { genre: 'rupture', texte: `Calcul interrompu — ${r.resultats.phases[r.resultats.phases.length - 1].nom}` })
        if (onglet === 'script' || onglet === 'saisie') setOnglet('coupe')
      } else {
        const e = r.erreurs[0]
        setEtat({ genre: 'erreur', texte: e?.ligne ? `Erreur ligne ${e.ligne}` : `Erreur : ${e?.message ?? 'script invalide'}`, ligne: e?.ligne })
      }
    } catch (e) {
      setEtat({ genre: 'erreur', texte: `Serveur de calcul injoignable (${String(e)})` })
    } finally {
      setEnCours(false)
    }
  }, [texte, onglet])

  // Raccourcis : Ctrl+Entrée, flèches de phase (hors champs de saisie)
  useEffect(() => {
    const touche = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); void calculer(); return }
      const cible = e.target as HTMLElement
      if (cible.closest('input, textarea, select, .monaco-editor')) return
      if (!res) return
      if (e.key === 'ArrowLeft') setPhase((p) => Math.max(0, p - 1))
      if (e.key === 'ArrowRight') setPhase((p) => Math.min(res.phases.length - 1, p + 1))
    }
    window.addEventListener('keydown', touche)
    return () => window.removeEventListener('keydown', touche)
  }, [calculer, res])

  const changerPhase = useCallback((i: number) => {
    if (i < 0) setPhase((p) => (res ? Math.min(res.phases.length - 1, p + 1) : p))
    else setPhase(i)
  }, [res])

  // Actions des formulaires : toutes passent par le document YAML
  const actions = useMemo(() => ({
    fixer: (c: sd.Chemin, v: unknown) => setTexteBrut((t) => sd.fixer(t, c, v)),
    ajouter: (c: sd.Chemin, v: unknown) => setTexteBrut((t) => sd.ajouter(t, c, v)),
    ajouterCle: (c: sd.Chemin, k: string, v: unknown) => setTexteBrut((t) => sd.ajouterCle(t, c, k, v)),
    supprimer: (c: sd.Chemin) => setTexteBrut((t) => sd.supprimer(t, c)),
    deplacer: (c: sd.Chemin, i: number, j: number) => setTexteBrut((t) => sd.deplacer(t, c, i, j)),
    renommerAppui: (a: string, n: string) => setTexteBrut((t) => sd.renommerAppui(t, a, n)),
  }), [])

  const choisirSection = (s: Section, sel: Selection = null) => {
    setSection(s)
    setSelection(sel)
    setOnglet('saisie')
    setTiroirNav(false)
  }
  const allerErreur = () => {
    setOnglet('script')
    const l = erreurs[0]?.ligne ?? etat.ligne
    if (l) setLigneCible(l === ligneCible ? l + 0.000001 : l)
  }
  const enregistrer = () => {
    const nom = (modele?.projet ? String(modele.projet) : 'projet').trim().replace(/[^\w-]+/g, '_')
    telechargerTexte(texte, `${nom}.yaml`, 'text/yaml')
  }
  const importerRido = async (f: File) => {
    const r = await fetch('/api/rido', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ texte: await f.text(), nom: f.name }) })
    const d = (await r.json()) as { texte: string; rapport: string[] }
    setTexteBrut(d.texte)
    setRapportRido(d.rapport)
    setOnglet('script')
  }
  const exporterMaquette = async () => {
    try { telechargerTexte(await api.maquette(texte), 'maquette_retainwall.html', 'text/html') } catch (e) { alert(String(e)) }
  }

  const nNonOk = res?.verifications?.filter((v) => v.etat === 'non_ok').length ?? 0
  const ONGLETS: { cle: Onglet; lib: string; icone: ReactNode; visible: boolean; badge?: string; rouge?: boolean }[] = [
    { cle: 'coupe', lib: 'Coupe & diagrammes', icone: <IconeCoupe />, visible: true },
    { cle: '3d', lib: 'Maquette 3D', icone: <IconeCube />, visible: true },
    { cle: 'efforts', lib: 'Efforts', icone: <IconeTableau />, visible: true },
    { cle: 'verifications', lib: 'Vérifications', icone: <IconeVerif />, visible: true,
      badge: res?.verifications?.length ? String(nNonOk || res.verifications.length) : undefined, rouge: nNonOk > 0 },
    { cle: 'pseudo3d', lib: 'Pseudo-3D', icone: <IconePlaque />, visible: !!res?.pseudo3d },
    { cle: 'assemblages', lib: 'Assemblages', icone: <IconeAppui />, visible: true },
    { cle: 'saisie', lib: 'Saisie', icone: <IconeProjet />, visible: true },
    { cle: 'script', lib: 'Script', icone: <IconeScript />, visible: true, badge: erreurs.length ? String(erreurs.length) : undefined, rouge: erreurs.length > 0 },
    { cle: 'materiaux', lib: 'Base matériaux', icone: <IconeBase />, visible: true },
  ]
  const sansResultats = <div className="vide-centre"><b>Aucun résultat</b><span>Lancez le calcul avec « Recalculer » ou Ctrl+Entrée.</span></div>

  const classes = ['appli', nav ? '' : 'sans-nav', insp ? '' : 'sans-insp', tiroirNav ? 'nav-ouvert' : '', tiroirInsp ? 'insp-ouvert' : ''].join(' ')
  return (
    <div className={classes}>
      <BarreTitre projet={modele?.projet ? String(modele.projet) : ''} etat={etat} enCours={enCours} exemples={exemples} theme={theme}
        imagePossible={!!res && (onglet === 'coupe' || onglet === '3d')} resultatsDisponibles={!!res}
        onRecalculer={() => void calculer()} onExemple={(t) => { setTexteBrut(t); setRes(null); setEtat({ genre: 'aucun', texte: 'Exemple chargé — à calculer' }) }}
        onOuvrir={(f) => void f.text().then((t) => { setTexteBrut(t); setRes(null) })} onEnregistrer={enregistrer} onRido={(f) => void importerRido(f)}
        onMateriaux={() => setOnglet('materiaux')} onImage={exporterImage} onNote={() => res && imprimerNote(res)} onMaquette={() => void exporterMaquette()}
        onTheme={() => setTheme(theme === 'sombre' ? 'clair' : 'sombre')} onAllerErreur={allerErreur}
        onBasculeNav={() => { if (window.innerWidth <= 768) setTiroirNav(!tiroirNav); else setNav(!nav) }}
        onBasculeInsp={() => { if (window.innerWidth <= 1100) setTiroirInsp(!tiroirInsp); else setInsp(!insp) }} />

      <div className="zone-nav">
        <Navigation modele={modele} erreurs={erreurs} section={onglet === 'saisie' ? section : null} selection={onglet === 'saisie' ? selection : null} onChoisir={choisirSection} />
      </div>

      <main className="zone-centre">
        <nav className="onglets" role="tablist">
          {ONGLETS.filter((o) => o.visible).map((o) => (
            <button key={o.cle} role="tab" aria-selected={onglet === o.cle} className={`onglet ${onglet === o.cle ? 'actif' : ''}`} onClick={() => setOnglet(o.cle)}>
              {o.icone} {o.lib} {o.badge && <span className={`badge ${o.rouge ? 'rouge' : ''}`}>{o.badge}</span>}
            </button>
          ))}
          <span className="espace" />
          <span className="doux" style={{ alignSelf: 'center', paddingRight: 10, fontSize: 11 }}>{serveur}</span>
        </nav>
        <div className="contenu-onglet">
          {onglet === 'coupe' && (res ? <CoupeDiagrammes res={res} phase={phase} theme={theme} /> : sansResultats)}
          {onglet === '3d' && (res ? <Maquette3D texte={texteCalcule.current} version={version} phase={phase} theme={theme}
            selection={selection?.type === 'appui' ? selection.nom : null} onPhase={changerPhase}
            onSelection={(n) => setSelection(n ? { type: 'appui', nom: n } : null)} /> : sansResultats)}
          {onglet === 'efforts' && (res ? <Efforts res={res} phase={phase} onPhase={setPhase} onAppui={(n) => { setSelection({ type: 'appui', nom: n }); setTiroirInsp(true) }} /> : sansResultats)}
          {onglet === 'verifications' && (res ? <Verifications res={res} /> : sansResultats)}
          {onglet === 'pseudo3d' && res?.pseudo3d && <Pseudo3D res={res} phase={phase} />}
          {onglet === 'assemblages' && (
            <Assemblages res={res} modele={erreurYaml ? null : modele} references={references} theme={theme}
              onEnregistrer={(nom, bloc) => { actions.ajouterCle(['assemblages'], nom, bloc); setOnglet('script') }} />
          )}
          {onglet === 'saisie' && (
            <Saisie modele={erreurYaml ? null : modele} erreurs={erreurs} schema={schema} references={references} actions={actions}
              section={section ?? 'projet'} selection={selection} onSelection={setSelection} />
          )}
          {onglet === 'script' && (
            <div className="vue-script">
              <div className="editeur">
                <Editeur texte={texte} onChange={setTexte} erreurs={erreurs} schema={schema} references={references} ligneCible={ligneCible ? Math.floor(ligneCible) : null} />
              </div>
              {rapportRido && (
                <div className="rapport-rido"><b>Rapport de conversion RIDO</b> <button className="btn discret" onClick={() => setRapportRido(null)}>Fermer</button>
                  <ul style={{ margin: '4px 0 0', paddingLeft: 16 }}>{rapportRido.map((l, i) => <li key={i}>{l}</li>)}</ul></div>
              )}
              <div className="liste-erreurs">
                {erreurYaml ? <ul><li><b>YAML</b> {erreurYaml}</li></ul>
                  : erreurs.length === 0 ? <div className="ok">Script valide.</div> : (
                    <ul>{erreurs.map((e, i) => (
                      <li key={i} onClick={() => { if (e.ligne) setLigneCible(e.ligne === ligneCible ? e.ligne + 0.000001 : e.ligne) }}>
                        <b className="mono">{e.ligne ? `ligne ${e.ligne}` : 'script'}</b><span>{e.chemin ? `${e.chemin} : ` : ''}{e.message}</span>
                      </li>))}</ul>
                  )}
              </div>
            </div>
          )}
          {onglet === 'materiaux' && <Materiaux surImport={() => api.references().then(setReferences)} />}
        </div>
      </main>

      <div className="zone-insp">
        <Inspecteur res={res} phase={phase} selection={selection} modele={modele} onSelection={setSelection} />
      </div>

      <FrisePhases res={res} phase={phase} onPhase={changerPhase} />
    </div>
  )
}
