import { useCallback, useEffect, useRef, useState } from 'react'
import { api, type ErreurScript, type Resultats } from './lib/api'
import { Editeur } from './vues/Editeur'
import { Coupe } from './vues/Coupe'
import { Diagrammes, Enveloppes } from './vues/Diagrammes'
import { Synthese, TableauAppuis, Verifications } from './vues/Tableaux'
import { Maquette } from './vues/Maquette'
import { Materiaux } from './vues/Materiaux'
import { Pseudo3D } from './vues/Pseudo3D'

const ONGLETS = ['Synthèse', 'Coupe', 'Diagrammes', 'Enveloppes', 'Appuis', 'Vérifications', 'Pseudo-3D', 'Maquette 3D'] as const
type Onglet = (typeof ONGLETS)[number]
const CLE_BROUILLON = 'retainwall.brouillon'

function lireBrouillon(): string | null {
  try {
    return localStorage.getItem(CLE_BROUILLON)
  } catch {
    return null
  }
}

function ecrireBrouillon(t: string) {
  try {
    localStorage.setItem(CLE_BROUILLON, t)
  } catch {
    /* stockage indisponible : sans conséquence */
  }
}

export default function App() {
  const [texte, setTexte] = useState<string>(() => lireBrouillon() ?? '')
  const [erreurs, setErreurs] = useState<ErreurScript[]>([])
  const [res, setRes] = useState<Resultats | null>(null)
  const [phase, setPhase] = useState(0)
  const [onglet, setOnglet] = useState<Onglet>('Synthèse')
  const [schema, setSchema] = useState<unknown>(null)
  const [references, setReferences] = useState<Record<string, string[]>>({})
  const [exemples, setExemples] = useState<{ nom: string; texte: string }[]>([])
  const [enCours, setEnCours] = useState(false)
  const [serveur, setServeur] = useState<string>('connexion…')
  const [ligneCible, setLigneCible] = useState<number | null>(null)
  const [vueMateriaux, setVueMateriaux] = useState(false)
  const [rapportRido, setRapportRido] = useState<string[] | null>(null)
  const minuterie = useRef<number | undefined>(undefined)

  useEffect(() => {
    fetch('/api/sante')
      .then((r) => r.json())
      .then((d) => setServeur(`serveur v${d.version}`))
      .catch(() => setServeur('serveur de calcul injoignable'))
    api.schema().then(setSchema).catch(() => {})
    api.references().then(setReferences)
    api.exemples()
      .then((ex) => {
        setExemples(ex)
        if (!lireBrouillon() && ex.length) setTexte(ex[0].texte)
      })
      .catch(() => {})
  }, [])

  // Validation en direct (après une courte pause de frappe)
  useEffect(() => {
    ecrireBrouillon(texte)
    window.clearTimeout(minuterie.current)
    minuterie.current = window.setTimeout(() => {
      if (texte.trim()) api.valider(texte).then((r) => setErreurs(r.erreurs)).catch(() => {})
    }, 600)
  }, [texte])

  const calculer = useCallback(async () => {
    setEnCours(true)
    try {
      const r = await api.calcul(texte)
      setErreurs(r.erreurs)
      if (r.ok && r.resultats) {
        setRes(r.resultats)
        setPhase(r.resultats.phases.length - 1)
      }
    } catch (e) {
      setErreurs([{ ligne: null, chemin: '', message: String(e) }])
    } finally {
      setEnCours(false)
    }
  }, [texte])

  useEffect(() => {
    const raccourci = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault()
        void calculer()
      }
    }
    window.addEventListener('keydown', raccourci)
    return () => window.removeEventListener('keydown', raccourci)
  }, [calculer])

  const enregistrer = () => {
    const nom = (texte.match(/^projet:\s*(.+)$/m)?.[1] ?? 'projet').trim().replace(/[^\w-]+/g, '_')
    const url = URL.createObjectURL(new Blob([texte], { type: 'text/yaml' }))
    const a = document.createElement('a')
    a.href = url
    a.download = `${nom}.yaml`
    a.click()
    URL.revokeObjectURL(url)
  }

  const ouvrir = (fichier: File | undefined) => {
    if (fichier) void fichier.text().then(setTexte)
  }

  const importerRido = async (fichier: File | undefined) => {
    if (!fichier) return
    const r = await fetch('/api/rido', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ texte: await fichier.text(), nom: fichier.name }),
    })
    const d = (await r.json()) as { texte: string; rapport: string[] }
    setTexte(d.texte)
    setRapportRido(d.rapport)
  }

  const ph = res?.phases[Math.min(phase, (res?.phases.length ?? 1) - 1)]

  return (
    <div className="appli">
      <header>
        <h1>RetainWall</h1>
        <span className="sous-titre">écrans de soutènement — coefficients de réaction</span>
        <span className="espace" />
        <button className="secondaire" onClick={() => setVueMateriaux(!vueMateriaux)}>
          {vueMateriaux ? 'Retour aux résultats' : 'Base matériaux'}
        </button>
        <span className="serveur">{serveur}</span>
      </header>
      <div className="avertissement-global">
        Outil en cours de validation : aucun résultat ne doit servir à un projet réel avant comparaison à K-Réa ou RIDO
        sur plusieurs cas et visa d'un ingénieur.
      </div>
      <main>
        <section className="panneau-script">
          <div className="barre">
            <select
              value=""
              onChange={(e) => {
                const ex = exemples.find((x) => x.nom === e.target.value)
                if (ex) setTexte(ex.texte)
              }}
            >
              <option value="">Exemples…</option>
              {exemples.map((e) => (
                <option key={e.nom} value={e.nom}>{e.nom}</option>
              ))}
            </select>
            <label className="bouton secondaire">
              Ouvrir
              <input type="file" accept=".yaml,.yml,.txt" hidden onChange={(e) => ouvrir(e.target.files?.[0])} />
            </label>
            <button className="secondaire" onClick={enregistrer}>Enregistrer</button>
            <label className="bouton secondaire" title="Conversion selon docs/rido/correspondance.yaml">
              Importer RIDO
              <input type="file" hidden onChange={(e) => void importerRido(e.target.files?.[0])} />
            </label>
            <span className="espace" />
            <button onClick={() => void calculer()} disabled={enCours} title="Ctrl+Entrée">
              {enCours ? 'Calcul…' : 'Calculer'}
            </button>
          </div>
          <div className="editeur">
            <Editeur texte={texte} onChange={setTexte} erreurs={erreurs} schema={schema} references={references} ligneCible={ligneCible} />
          </div>
          {rapportRido && (
            <div className="rapport-rido">
              <b>Rapport de conversion RIDO</b>{' '}
              <button className="secondaire" onClick={() => setRapportRido(null)}>Fermer</button>
              <ul>{rapportRido.map((l, i) => <li key={i}>{l}</li>)}</ul>
            </div>
          )}
          <div className={`erreurs ${erreurs.length ? '' : 'vide'}`}>
            {erreurs.length === 0 ? (
              <span>Script valide.</span>
            ) : (
              <ul>
                {erreurs.map((e, i) => (
                  <li key={i} onClick={() => e.ligne && setLigneCible(e.ligne)}>
                    <b>{e.ligne ? `ligne ${e.ligne}` : 'script'}</b>
                    {e.chemin ? ` (${e.chemin})` : ''} : {e.message}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
        <section className="panneau-resultats">
          {vueMateriaux ? (
            <Materiaux surImport={() => api.references().then(setReferences)} />
          ) : !res || !ph ? (
            <div className="vide-resultats">Saisissez ou chargez un script, puis « Calculer » (Ctrl+Entrée).</div>
          ) : (
            <>
              <div className="curseur-phase">
                <label>
                  Phase {phase + 1}/{res.phases.length} : <b>{ph.nom}</b>
                </label>
                <input
                  type="range"
                  min={0}
                  max={res.phases.length - 1}
                  value={phase}
                  onChange={(e) => setPhase(Number(e.target.value))}
                />
                <button className="secondaire" onClick={() => setPhase(Math.max(0, phase - 1))}>◀</button>
                <button className="secondaire" onClick={() => setPhase(Math.min(res.phases.length - 1, phase + 1))}>▶</button>
              </div>
              {res.avertissements.map((a, i) => (
                <div key={i} className="alerte">{a}</div>
              ))}
              {!res.complet && (
                <div className="alerte rouge-fond">
                  Calcul interrompu : {res.phases[res.phases.length - 1].message}
                </div>
              )}
              <nav className="onglets">
                {ONGLETS.filter((o) => o !== 'Pseudo-3D' || res.pseudo3d).map((o) => (
                  <button key={o} className={o === onglet ? 'actif' : ''} onClick={() => setOnglet(o)}>
                    {o}
                  </button>
                ))}
              </nav>
              <div className="contenu-onglet">
                {onglet === 'Synthèse' && <Synthese res={res} phaseActive={phase} choisir={setPhase} />}
                {onglet === 'Coupe' && <Coupe res={res} phase={ph} />}
                {onglet === 'Diagrammes' && <Diagrammes res={res} phase={ph} />}
                {onglet === 'Enveloppes' && <Enveloppes res={res} />}
                {onglet === 'Appuis' && <TableauAppuis res={res} phaseActive={phase} />}
                {onglet === 'Vérifications' && <Verifications res={res} />}
                {onglet === 'Pseudo-3D' && res.pseudo3d && <Pseudo3D res={res} phase={phase} />}
                {onglet === 'Maquette 3D' && <Maquette texte={texte} />}
              </div>
            </>
          )}
        </section>
      </main>
    </div>
  )
}
