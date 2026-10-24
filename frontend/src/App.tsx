import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { api, ErreurServeur, messageErreur, type ErreurScript, type Exemple, type ProjetCoupes, type ReponseCalcul, type Resultats } from './lib/api'
import type { EtatCalcul, Onglet, Section, Selection } from './lib/etat'
import { exporterImage, imprimerNote, telechargerNote, telechargerTexte } from './lib/exporter'
import { nomProjet, uniteCote } from './lib/format'
import { IconeAppui, IconeBase, IconeCoupe, IconeCube, IconeFichier, IconePlaque, IconeProjet, IconeScript, IconeTableau, IconeVerif } from './lib/icones'
import * as sd from './lib/scriptDoc'
import { appliquerTheme, choisirTheme, themeInitial, type Theme } from './lib/theme'
import { BarreTitre } from './composants/BarreTitre'
import { FrisePhases } from './composants/FrisePhases'
import { Inspecteur } from './composants/Inspecteur'
import { Navigation } from './composants/Navigation'
import { CoupeDiagrammes } from './vues/CoupeDiagrammes'
import { Efforts } from './vues/Efforts'
import { Materiaux } from './vues/Materiaux'
import { Pseudo3D } from './vues/Pseudo3D'
import { Saisie } from './vues/Saisie'
import { Verifications } from './vues/Verifications'
import { Hypotheses } from './vues/Hypotheses'
import { Assemblages } from './vues/Assemblages'
import { decoderAncre, encoderAncre } from './vue3d/navigation'

// Éditeur (Monaco) et maquette (three.js) chargés à la demande : la page s'ouvre sans les attendre.
const Editeur = lazy(() => import('./vues/Editeur').then((m) => ({ default: m.Editeur })))
const Onglet3D = lazy(() => import('./vue3d/Onglet3D').then((m) => ({ default: m.Onglet3D })))
const CHARGEMENT = <div className="vide-centre"><span>Chargement…</span></div>

const CLE_BROUILLON = 'retainwall.brouillon'
const COTES_VIDES: Record<string, number> = {}
const lireBrouillon = () => { try { return localStorage.getItem(CLE_BROUILLON) } catch { return null } }
const ecrireBrouillon = (t: string) => { try { localStorage.setItem(CLE_BROUILLON, t) } catch { /* stockage indisponible */ } }

export default function App() {
  const [texte, setTexteBrut] = useState<string>(() => lireBrouillon() ?? '')
  const [erreurs, setErreurs] = useState<ErreurScript[]>([])
  const [avertScript, setAvertScript] = useState<ErreurScript[]>([])
  const [res, setRes] = useState<Resultats | null>(null)
  const [resBase, setResBase] = useState<Resultats | null>(null)       // résultats de la première coupe
  const [projet, setProjet] = useState<ProjetCoupes | null>(null)      // coupes de calcul du projet
  const [coupeActive, setCoupeActive] = useState(0)
  const [selection3d, setSelection3d] = useState<string | null>(null)   // objet sélectionné dans la maquette
  const [prereglage, setPrereglage] = useState<string | null>(null)       // dernier préréglage de calques appliqué
  const [retour3d, setRetour3d] = useState(false)                         // onglet ouvert depuis la maquette
  const ancreInitiale = useRef(decoderAncre(window.location.hash))
  const [phase, setPhase] = useState(0)
  const [onglet, setOnglet] = useState<Onglet>('coupe')
  const [section, setSection] = useState<Section | null>(null)
  const [selection, setSelection] = useState<Selection>(null)
  const [schema, setSchema] = useState<unknown>(null)
  const [references, setReferences] = useState<Record<string, string[]>>({})
  const [exemples, setExemples] = useState<Exemple[]>([])
  const [enCours, setEnCours] = useState(false)
  const [etat, setEtat] = useState<EtatCalcul>({ genre: 'aucun', texte: 'Aucun calcul' })
  const [ligneCible, setLigneCible] = useState<{ ligne: number; n: number } | null>(null)
  const compteurCible = useRef(0)
  const [theme, setTheme] = useState<Theme>(themeInitial)
  const [nav, setNav] = useState(true)
  const [insp, setInsp] = useState(true)
  const [tiroirNav, setTiroirNav] = useState(false)
  const [tiroirInsp, setTiroirInsp] = useState(false)
  const [rapportRido, setRapportRido] = useState<string[] | null>(null)
  const [serveur, setServeur] = useState('')
  const minuterie = useRef<number | undefined>(undefined)
  const texteCalcule = useRef<string>('')
  const enCoursRef = useRef(false)              // Ctrl+Entrée pendant un calcul : ignoré (pas de second calcul concurrent)
  const numeroValidation = useRef(0)            // seule la dernière validation lancée met à jour l'affichage

  const { modele, erreur: erreurYaml } = useMemo(() => sd.lire(texte), [texte])
  const cotesPlan = useMemo<Record<string, number>>(() => (modele?.plan?.cotes && typeof modele.plan.cotes === 'object' ? modele.plan.cotes : COTES_VIDES), [modele])

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
      if (!texte.trim()) { setErreurs([]); setAvertScript([]); return }
      const numero = ++numeroValidation.current
      api.valider(texte).then((r) => {
        if (numero !== numeroValidation.current) return   // réponse périmée (une frappe plus récente a relancé la validation)
        setErreurs(r.erreurs)
        setAvertScript(r.avertissements ?? [])
        if (r.erreurs.length) {
          const e = r.erreurs[0]
          setEtat({ genre: 'erreur', texte: e.ligne ? `Erreur ligne ${e.ligne}` : 'Script invalide', ligne: e.ligne })
        } else if (texte !== texteCalcule.current) {
          setEtat(res ? { genre: 'modifie', texte: 'Script modifié depuis le dernier calcul' } : { genre: 'aucun', texte: 'Aucun calcul' })
        } else if (res) {
          setEtat((e) => (e.genre === 'ok' || e.genre === 'rupture' ? e : { genre: 'ok', texte: `Calcul terminé : ${res.phases.length} phases` }))
        }
      }).catch(() => {})
    }, 500)
  }, [texte, res])

  const setTexte = useCallback((t: string) => setTexteBrut(t), [])

  const calculer = useCallback(async () => {
    if (!texte.trim() || enCoursRef.current) return
    enCoursRef.current = true
    setEnCours(true)
    const t0 = performance.now()
    try {
      let r: ReponseCalcul
      const prep = await api.coupesPreparer(texte)
      if (prep.ok && !prep.unique && prep.coupes.length > 1) {
        // une requête par coupe, lancées en parallèle (cache serveur par coupe), puis la synthèse
        const faites = new Set<string>()
        const avancement = () => setEtat({ genre: 'calcul', texte: `Calcul des coupes : ${faites.size}/${prep.coupes.length} terminées (${prep.coupes.map((c) => `${c.nom.split(' — ')[0]}${faites.has(c.nom) ? '' : ' en cours'}`).join(', ')})` })
        avancement()
        const reps = await Promise.all(prep.coupes.map(async (c) => { const rc = await api.calcul(texte, c.nom); faites.add(c.nom); avancement(); return rc }))
        const echec = reps.find((x) => !x.ok || !x.resultats)
        if (echec) r = echec
        else {
          const syn = await api.coupesSynthese(texte)
          if (!syn.ok) r = { ok: false, erreurs: syn.erreurs }
          else {
            const coupes = syn.projet.coupes.map((c, i) => (i === 0 ? c : { ...c, resultats: reps[i].resultats }))
            r = { ok: true, erreurs: [], resultats: reps[0].resultats, projet: { ...syn.projet, coupes } }
          }
        }
      } else r = await api.calcul(texte)
      const ms = Math.round(performance.now() - t0)
      setErreurs(r.erreurs)
      if (r.ok && r.resultats) {
        // chaque coupe porte ses résultats (la première = ceux de la réponse)
        if (r.projet) r.projet = { ...r.projet, coupes: r.projet.coupes.map((c, i) => (i === 0 ? { ...c, resultats: r.resultats } : c)) }
        texteCalcule.current = texte
        setRes(r.resultats)
        setResBase(r.resultats)
        setProjet(r.projet ?? null)
        setCoupeActive(0)
        const nPhases = r.resultats.phases.length
        setPhase(Math.max(0, nPhases - 1))
        const derniere = nPhases ? r.resultats.phases[nPhases - 1] : null
        const rompue = r.resultats.phases.find((p) => !p.ok)
        const itMax = Math.max(0, ...r.resultats.phases.map((p) => p.iterations ?? 0))
        setEtat(r.resultats.complet
          ? { genre: 'ok', texte: `Calcul terminé : ${nPhases} phases, convergence atteinte (au plus ${itMax} itérations), ${ms} ms` }
          : { genre: 'rupture', texte: `Calcul interrompu à la phase « ${(rompue ?? derniere)?.nom ?? 'aucune'} » : ${(rompue ?? derniere)?.message ?? 'rupture'}` })
        if (onglet === 'script' || onglet === 'saisie') setOnglet('coupe')
      } else {
        const e = r.erreurs[0]
        setEtat({ genre: 'erreur', texte: e?.ligne ? `Erreur ligne ${e.ligne}` : `Erreur : ${e?.message ?? 'script invalide'}`, ligne: e?.ligne })
      }
    } catch (e) {
      // ErreurServeur : le serveur a répondu (erreur interne traduite en français) ; sinon il est injoignable
      setEtat({ genre: 'erreur', texte: e instanceof ErreurServeur ? `Erreur du serveur de calcul : ${e.message}` : messageErreur(e) })
    } finally {
      enCoursRef.current = false
      setEnCours(false)
    }
  }, [texte, onglet])

  // Raccourcis : Ctrl+Entrée, flèches de phase (hors champs de saisie)
  useEffect(() => {
    const touche = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); void calculer(); return }
      const cible = e.target as HTMLElement
      if (cible?.closest?.('input, textarea, select, .monaco-editor')) return
      if (!res) return
      if (e.key === 'ArrowLeft') setPhase((p) => res.phases[p]?.parent ?? Math.max(0, p - 1))
      if (e.key === 'ArrowRight') setPhase((p) => res.phases[p]?.enfants?.[0] ?? Math.min(res.phases.length - 1, p + 1))
      if (/^[1-9]$/.test(e.key) && projet && !projet.unique && Number(e.key) <= projet.coupes.length) changerCoupe(Number(e.key) - 1)
    }
    window.addEventListener('keydown', touche)
    return () => window.removeEventListener('keydown', touche)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [calculer, res, projet, coupeActive, phase])

  /** Change de coupe de calcul affichée en conservant la phase (même nom, sinon dernière phase projet précédente). */
  const changerCoupe = (i: number) => {
    if (!projet || !resBase || !res || i === coupeActive || i < 0 || i >= projet.coupes.length) return
    const cible = projet.coupes[i].resultats ?? resBase
    const nom = res.phases[phase]?.nom
    let j = cible.phases.findIndex((p) => p.nom === nom)
    if (j < 0) {
      const ip = projet.coupes[coupeActive].correspondance[phase] ?? phase
      j = 0
      projet.coupes[i].correspondance.forEach((c, k) => { if (c <= ip) j = k })
    }
    setRes(cible)
    setCoupeActive(i)
    setPhase(j)
  }

  const changerPhase = useCallback((i: number) => {
    if (i < 0) setPhase((p) => (res ? (res.phases[p]?.enfants?.[0] ?? Math.min(res.phases.length - 1, p + 1)) : p))
    else setPhase(i)
  }, [res])

  // Actions des formulaires : toutes passent par le document YAML
  const actions = useMemo(() => ({
    fixer: (c: sd.Chemin, v: unknown) => setTexteBrut((t) => sd.fixer(t, c, v)),
    ajouter: (c: sd.Chemin, v: unknown) => setTexteBrut((t) => sd.ajouter(t, c, v)),
    ajouterCle: (c: sd.Chemin, k: string, v: unknown) => setTexteBrut((t) => sd.ajouterCle(t, c, k, v)),
    supprimer: (c: sd.Chemin) => setTexteBrut((t) => sd.supprimer(t, c)),
    deplacer: (c: sd.Chemin, i: number, j: number) => setTexteBrut((t) => sd.deplacer(t, c, i, j)),
    inserer: (c: sd.Chemin, i: number, v: unknown) => setTexteBrut((t) => sd.inserer(t, c, i, v)),
    renommerAppui: (a: string, n: string) => setTexteBrut((t) => sd.renommerAppui(t, a, n)),
  }), [])

  /** Sélection depuis la maquette : « appui:B1 » -> inspecteur de l'appui, « couche:1 » -> couche. */
  const selectionner3d = useCallback((id: string | null) => {
    setSelection3d(id)
    if (id?.startsWith('appui:')) setSelection({ type: 'appui', nom: id.slice(6) })
    else if (id?.startsWith('couche:')) setSelection({ type: 'couche', index: Number(id.slice(7)) || 0 })
    else setSelection(null)
  }, [])

  // Ancre d'URL partageable : coupe, phase, sélection, préréglage de calques
  useEffect(() => {
    if (!res) return
    const h = encoderAncre({ coupe: coupeActive, phase, selection: selection3d, prereglage })
    if (window.location.hash !== h) window.history.replaceState(null, '', h)
  }, [res, coupeActive, phase, selection3d, prereglage])
  useEffect(() => {
    const a = ancreInitiale.current
    if (!a || !res || !projet) return
    ancreInitiale.current = null
    if (a.coupe > 0 && a.coupe < projet.coupes.length) changerCoupe(a.coupe)
    const cible = (projet.coupes[a.coupe]?.resultats ?? res)
    setPhase(Math.min(a.phase, cible.phases.length - 1))
    if (a.selection) selectionner3d(a.selection)
    if (a.prereglage) setPrereglage(a.prereglage)
    setOnglet('3d')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [res, projet])

  const choisirSection = (s: Section, sel: Selection = null) => {
    setSection(s)
    setSelection(sel)
    setOnglet('saisie')
    setTiroirNav(false)
  }
  /** Place le curseur de l'éditeur sur une ligne (chaque demande est distincte : recliquer la même erreur agit). */
  const viserLigne = (l: number | null | undefined) => { if (l) setLigneCible({ ligne: l, n: ++compteurCible.current }) }
  const allerErreur = () => {
    setOnglet('script')
    viserLigne(erreurs[0]?.ligne ?? etat.ligne)
  }
  const enregistrer = () => {
    const nom = (nomProjet(modele?.projet) || 'projet').trim().replace(/[^\w-]+/g, '_')
    telechargerTexte(texte, `${nom}.yaml`, 'text/yaml')
  }
  const importerRido = async (f: File) => {
    try {
      const d = await api.rido(await f.text(), f.name)
      if (typeof d?.texte !== 'string') throw new Error('réponse du serveur sans script converti')
      setTexteBrut(d.texte)
      setRes(null)
      setProjet(null)
      setRapportRido(Array.isArray(d.rapport) ? d.rapport : [])
      setOnglet('script')
      setEtat({ genre: 'aucun', texte: 'Fichier RIDO converti : rapport de conversion à relire avant calcul' })
    } catch (e) {
      setEtat({ genre: 'erreur', texte: `Import RIDO impossible : ${messageErreur(e)}` })
    }
  }
  const exporterMaquette = async () => {
    try { telechargerTexte(await api.maquette(texte), 'maquette_retainwall.html', 'text/html') } catch (e) { alert(`Export de la maquette impossible : ${messageErreur(e)}`) }
  }
  /** Ajout depuis la maquette : refusé si le script n'est pas lisible (sinon l'ajout serait perdu en silence). */
  const ajouterDepuis3d = (chemin: sd.Chemin, valeur: unknown, message: string) => {
    if (erreurYaml) { setEtat({ genre: 'erreur', texte: `Script YAML illisible (${erreurYaml}) : corrigez-le avant d'ajouter depuis la maquette` }); return }
    actions.ajouter(chemin, valeur)
    setEtat({ genre: 'modifie', texte: message })
  }

  const nNonOk = res?.verifications?.filter((v) => v.etat === 'non_ok').length ?? 0
  const ONGLETS: { cle: Onglet; lib: string; icone: ReactNode; visible: boolean; compteur?: string; rouge?: boolean }[] = [
    { cle: 'coupe', lib: 'Coupe & diagrammes', icone: <IconeCoupe />, visible: true },
    { cle: '3d', lib: 'Maquette 3D', icone: <IconeCube />, visible: true },
    { cle: 'efforts', lib: 'Efforts', icone: <IconeTableau />, visible: true },
    { cle: 'verifications', lib: 'Vérifications', icone: <IconeVerif />, visible: true,
      compteur: nNonOk ? `${nNonOk} non vérifiée${nNonOk > 1 ? 's' : ''}` : undefined, rouge: nNonOk > 0 },
    { cle: 'hypotheses', lib: 'Hypothèses et référentiel', icone: <IconeFichier />, visible: true },
    { cle: 'pseudo3d', lib: 'Pseudo-3D', icone: <IconePlaque />, visible: !!res?.pseudo3d },
    { cle: 'assemblages', lib: 'Assemblages', icone: <IconeAppui />, visible: true },
    { cle: 'saisie', lib: 'Saisie', icone: <IconeProjet />, visible: true },
    { cle: 'script', lib: 'Script', icone: <IconeScript />, visible: true, compteur: erreurs.length ? `${erreurs.length} erreur${erreurs.length > 1 ? 's' : ''}` : undefined, rouge: erreurs.length > 0 },
    { cle: 'materiaux', lib: 'Base matériaux', icone: <IconeBase />, visible: true },
  ]
  const allerLigne = (l: number | null) => {
    setOnglet('script')
    viserLigne(l)
  }
  const sansResultats = erreurs.length > 0 ? (
    <div className="vide-centre bloque">
      <b>Le calcul ne peut pas être lancé : {erreurs.length} erreur{erreurs.length > 1 ? 's' : ''} dans le script</b>
      <span>Un clic sur une erreur ouvre la ligne du script. Les mots-clés inconnus sont ignorés et n'empêchent pas le calcul.</span>
      <ul className="erreurs-bloquantes">
        {erreurs.slice(0, 12).map((e, i) => (
          <li key={i} onClick={() => allerLigne(e.ligne)}>
            <b className="mono">{e.ligne ? `ligne ${e.ligne}` : 'script'}</b> <span>{e.chemin ? `${e.chemin} : ` : ''}{e.message}</span>
          </li>
        ))}
        {erreurs.length > 12 && <li className="doux">… et {erreurs.length - 12} autre(s) (onglet Script)</li>}
      </ul>
    </div>
  ) : <div className="vide-centre"><b>Aucun calcul</b><span>Calcul : bouton « Calculer » ou Ctrl+Entrée.</span></div>

  const classes = ['appli', nav ? '' : 'sans-nav', insp ? '' : 'sans-insp', tiroirNav ? 'nav-ouvert' : '', tiroirInsp ? 'insp-ouvert' : ''].join(' ')
  return (
    <div className={classes}>
      <BarreTitre projet={nomProjet(modele?.projet)} etat={etat} enCours={enCours} exemples={exemples} theme={theme}
        imagePossible={!!res && (onglet === 'coupe' || onglet === '3d')} resultatsDisponibles={!!res}
        onRecalculer={() => void calculer()} onExemple={(t) => { setTexteBrut(t); setRes(null); setProjet(null); setEtat({ genre: 'aucun', texte: 'Exemple chargé, non calculé' }) }}
        onOuvrir={(f) => void f.text().then((t) => { setTexteBrut(t); setRes(null) })} onEnregistrer={enregistrer} onRido={(f) => void importerRido(f)}
        onMateriaux={() => setOnglet('materiaux')} onImage={exporterImage} onNote={() => res && void imprimerNote(res, erreurYaml ? null : modele, serveur)} onNoteFichier={() => res && void telechargerNote(res, erreurYaml ? null : modele, serveur)} onMaquette={() => void exporterMaquette()}
        onTheme={() => { const t: Theme = theme === 'sombre' ? 'clair' : 'sombre'; choisirTheme(t); setTheme(t) }} onAllerErreur={allerErreur}
        onBasculeNav={() => { if (window.innerWidth <= 768) setTiroirNav(!tiroirNav); else setNav(!nav) }}
        onBasculeInsp={() => { if (window.innerWidth <= 1100) setTiroirInsp(!tiroirInsp); else setInsp(!insp) }} />

      <div className="zone-nav">
        <Navigation modele={modele} erreurs={erreurs} section={onglet === 'saisie' ? section : null} selection={onglet === 'saisie' ? selection : null}
          onglet={onglet} resultats={!!res} onChoisir={choisirSection} onOnglet={(o) => { setOnglet(o); setTiroirNav(false) }} />
      </div>

      <main className="zone-centre">
        <nav className="onglets" role="tablist">
          {ONGLETS.filter((o) => o.visible).map((o) => (
            <button key={o.cle} role="tab" aria-selected={onglet === o.cle} className={`onglet ${onglet === o.cle ? 'actif' : ''}`} onClick={() => setOnglet(o.cle)}>
              {o.icone} {o.lib} {o.compteur && <span className={`compteur ${o.rouge ? 'rouge' : ''}`}>({o.compteur})</span>}
            </button>
          ))}
          <span className="espace" />
          {projet && !projet.unique && projet.coupes.length > 1 && (
            <label className="doux selecteur-coupe" title="Coupe de calcul affichée (touches 1 à 9)">Coupe
              <select value={coupeActive} onChange={(e) => changerCoupe(Number(e.target.value))} aria-label="Coupe de calcul affichée">
                {projet.coupes.map((c, i) => <option key={c.nom} value={i}>{i + 1}. {c.nom}</option>)}
              </select>
            </label>
          )}
          <span className="doux" style={{ alignSelf: 'center', paddingRight: 10, fontSize: 11 }}>{serveur}</span>
        </nav>
        <div className="contenu-onglet">
          <Suspense fallback={CHARGEMENT}>
          {onglet === 'coupe' && (res ? <CoupeDiagrammes res={res} phase={phase} theme={theme} unite={uniteCote(modele)} /> : sansResultats)}
          {retour3d && onglet !== '3d' && (
            <div className="barre-retour"><button className="btn" onClick={() => { setOnglet('3d'); setRetour3d(false) }}>Retour à la maquette 3D</button>
              {selection3d && <span className="doux">Ouvert depuis la maquette : {selection3d}</span>}</div>
          )}
          {onglet === '3d' && (res ? (res.maquette ? <Onglet3D res={res} texte={texteCalcule.current} phase={phase} theme={theme} projet={projet} coupeActive={coupeActive} onCoupe={changerCoupe} cotes={cotesPlan} onEpingler={(e) => ajouterDepuis3d(['coupes'], e, 'Coupe ajoutée au script : à recalculer')} onAjouterSurcharge={(e) => ajouterDepuis3d(['surcharges'], e, 'Surcharge ajoutée au script : à recalculer')} onAjouterRisberme={(e) => ajouterDepuis3d(['fouille', 'risbermes'], e, 'Risberme ajoutée au script : à recalculer')}
            selection={selection3d} onSelection={selectionner3d} modele={erreurYaml ? null : modele} onPhase={setPhase}
            onOuvrir={(o) => { setOnglet(o); setRetour3d(true) }} prereglageInitial={ancreInitiale.current?.prereglage ?? prereglage} onPrereglage={setPrereglage} />
            : <div className="vide-centre"><b>Maquette non disponible</b><span>Le serveur n’a pas renvoyé la géométrie de la maquette pour ce calcul.</span></div>) : sansResultats)}
          {onglet === 'efforts' && (res ? <Efforts res={res} phase={phase} onPhase={setPhase} onAppui={(n) => { setSelection({ type: 'appui', nom: n }); setTiroirInsp(true) }} /> : sansResultats)}
          {onglet === 'verifications' && (res ? <Verifications res={res} projet={projet} filtre={retour3d ? selection3d : null} onRetour={() => { setOnglet('3d'); setRetour3d(false) }} /> : sansResultats)}
          {onglet === 'hypotheses' && (res ? <Hypotheses res={res} modele={erreurYaml ? null : modele} phase={phase} version={serveur} /> : sansResultats)}
          {onglet === 'pseudo3d' && res?.pseudo3d && <Pseudo3D res={res} phase={phase} />}
          {onglet === 'assemblages' && (
            <Assemblages res={res} modele={erreurYaml ? null : modele} references={references} theme={theme}
              onEnregistrer={(nom, bloc) => { actions.ajouterCle(['assemblages'], nom, bloc); setOnglet('script') }} />
          )}
          {onglet === 'saisie' && (
            <Saisie modele={erreurYaml ? null : modele} erreurs={erreurs} schema={schema} references={references} actions={actions}
              section={section ?? 'projet'} selection={selection} onSelection={setSelection} phaseActive={phase} onPhaseActive={setPhase} res={res} />
          )}
          {onglet === 'script' && (
            <div className="vue-script">
              <div className="editeur">
                <Editeur texte={texte} onChange={setTexte} erreurs={[...erreurs, ...avertScript]} schema={schema} references={references} cible={ligneCible} />
              </div>
              {rapportRido && (
                <div className="rapport-rido"><b>Rapport de conversion RIDO</b> <button className="btn discret" onClick={() => setRapportRido(null)}>Fermer</button>
                  <ul style={{ margin: '4px 0 0', paddingLeft: 16 }}>{rapportRido.map((l, i) => <li key={i}>{l}</li>)}</ul></div>
              )}
              <div className="liste-erreurs">
                {erreurYaml ? <ul><li><b>YAML</b> {erreurYaml}</li></ul>
                  : erreurs.length === 0 && avertScript.length === 0 ? <div className="ok">Script valide.</div> : (
                    <ul>
                      {erreurs.length === 0 && <li className="ok-ligne">Script calculable ; les avertissements ci-dessous n'empêchent pas le calcul.</li>}
                      {[...erreurs, ...avertScript].map((e, i) => (
                        <li key={i} className={e.niveau === 'avertissement' ? 'avert' : ''}
                          onClick={() => viserLigne(e.ligne)}>
                          <b className="mono">{e.ligne ? `ligne ${e.ligne}` : 'script'}</b><span>{e.chemin ? `${e.chemin} : ` : ''}{e.message}</span>
                        </li>))}
                    </ul>
                  )}
              </div>
            </div>
          )}
          {onglet === 'materiaux' && <Materiaux surImport={() => api.references().then(setReferences)} />}
          </Suspense>
        </div>
      </main>

      <div className="zone-insp">
        <Inspecteur res={res} phase={phase} selection={selection} modele={modele} onSelection={(sel) => { setSelection(sel); setSelection3d(sel?.type === 'appui' ? `appui:${sel.nom}` : sel?.type === 'couche' ? `couche:${sel.index}` : null) }} />
      </div>

      <FrisePhases res={res} phase={phase} onPhase={changerPhase} />
    </div>
  )
}
