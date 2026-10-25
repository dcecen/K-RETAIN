import { useEffect, useRef, useState } from 'react'
import { marked } from 'marked'
import type { Exemple } from '../lib/api'

export type SectionAide = 'premiers-pas' | 'conventions' | 'raccourcis' | 'guide' | 'catalogue'

/** Groupes du catalogue des exemples élémentaires, dans l'ordre d'affichage. */
const GROUPES_CATALOGUE = ['Exemples élémentaires 2D', 'Exemples élémentaires 3D', 'Vérifications élémentaires']

/** Catalogue des exemples élémentaires : code, titre, résultat attendu, source, ouverture dans l'application.
 *  Les cas de poutres pures et de plaque sans sol (rapport de validation) ne s'écrivent pas en script : le langage
 *  ne prévoit ni charge directe sur la paroi ni paroi sans sol. */
export function CatalogueExemples({ exemples, onExemple }: { exemples: Exemple[]; onExemple?: (e: Exemple) => void }) {
  const groupes = GROUPES_CATALOGUE.map((g) => [g, exemples.filter((e) => e.groupe === g)] as const).filter(([, l]) => l.length > 0)
  if (groupes.length === 0) return <div className="note" style={{ padding: 10 }}>Aucun exemple élémentaire proposé par le serveur (dossier exemples/elementaires).</div>
  return (
    <>
      {groupes.map(([g, liste]) => (
        <div key={g}>
          <h3 style={{ margin: '10px 0 4px' }}>{g} <span className="doux" style={{ fontWeight: 400 }}>({liste.length})</span></h3>
          <table className="tableau catalogue-exemples">
            <thead><tr><th>Code</th><th>Titre</th><th>Résultat attendu</th><th>Source</th><th /></tr></thead>
            <tbody>
              {liste.map((e) => {
                const code = e.nom.slice(0, 3)
                const titre = (e.titre || e.nom).replace(new RegExp(`^${code}\\s*`), '')
                return (
                  <tr key={e.nom}>
                    <td className="mono">{code}</td>
                    <td>{titre}<div className="doux" style={{ fontSize: 11 }}>{e.nom}.yaml</div></td>
                    <td>{e.attendu || <span className="faible">non renseigné dans l'en-tête</span>}</td>
                    <td className="doux">{e.source || <span className="faible">non renseignée</span>}</td>
                    <td>{onExemple && <button className="btn" onClick={() => onExemple(e)} title="Charger ce script (le script courant est remplacé après confirmation)">Ouvrir</button>}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      ))}
      <p className="note">Chaque exemple est aussi un test automatique (backend/tests/validation/test_exemples_elementaires.py) qui recalcule le résultat attendu.
        Les poutres pures (RDM, Winkler) et la plaque sans sol du rapport de validation ne s'écrivent pas en script : le langage ne prévoit ni charge directe sur la paroi ni paroi sans sol.</p>
    </>
  )
}

/** Aide intégrée : premiers pas, conventions, raccourcis clavier, guide du script (docs/guide_script.md). */
const RACCOURCIS: [string, string, string][] = [
  ['Ctrl+Entrée', 'Lancer le calcul', 'partout, y compris dans l’éditeur'],
  ['← / →', 'Phase précédente / suivante (dans la branche)', 'vues de résultats, hors champs de saisie'],
  ['1 à 9', 'Coupe de calcul affichée', 'projets à plusieurs coupes'],
  ['Entrée / Échap', 'Valider / annuler la saisie d’un champ', 'formulaires'],
  ['Ctrl+Espace', 'Auto-complétion des mots-clés', 'script YAML'],
  ['Maj+molette', 'Zoom vertical des diagrammes', 'vue Diagrammes'],
  ['Double-clic', 'Rétablir le zoom des diagrammes', 'vue Diagrammes'],
  ['R', 'Panneau de résultats de la sélection', 'maquette 3D'],
  ['L', 'Panneau des calques', 'maquette 3D'],
  ['C', 'Courbes en un point de la paroi', 'maquette 3D'],
  ['F', 'Recadrer la vue sur la fouille', 'maquette 3D'],
  ['Échap', 'Désélectionner, quitter l’outil en cours', 'maquette 3D'],
  ['Glisser / clic droit / molette', 'Rotation / translation / zoom', 'maquette 3D'],
  ['Ctrl+Maj+D', 'Diagnostic de rendu (objets, triangles, mémoire)', 'maquette 3D'],
]

export function Aide({ version, section, exemples = [], onExemple }: { version: string; section: SectionAide | null; exemples?: Exemple[]; onExemple?: (e: Exemple) => void }) {
  const [guide, setGuide] = useState<string | null>(null)
  const [erreur, setErreur] = useState<string | null>(null)
  const [sommaire, setSommaire] = useState<{ id: string; texte: string; niveau: number }[]>([])
  const conteneur = useRef<HTMLDivElement>(null)

  useEffect(() => {
    fetch('/api/guide').then((r) => { if (!r.ok) throw new Error(`erreur ${r.status}`); return r.text() })
      .then((md) => setGuide(marked.parse(md, { async: false }) as string))
      .catch((e) => setErreur(`Guide indisponible : ${e instanceof Error ? e.message : String(e)}`))
  }, [])

  // identifiants des titres du guide (sommaire), puis défilement vers la section demandée
  useEffect(() => {
    const el = conteneur.current
    if (!el || !guide) return
    const titres = [...el.querySelectorAll('h2, h3')] as HTMLElement[]
    titres.forEach((h, i) => { h.id = `guide-${i}` })
    setSommaire(titres.map((h, i) => ({ id: `guide-${i}`, texte: h.textContent ?? '', niveau: h.tagName === 'H2' ? 2 : 3 })))
  }, [guide])
  useEffect(() => {
    if (section) document.getElementById(`aide-${section}`)?.scrollIntoView({ block: 'start' })
  }, [section, guide])

  return (
    <div className="saisie aide-vue">
      <div className="bloc" id="aide-premiers-pas"><div className="bloc-titre">Premiers pas</div>
        <ol className="etapes-aide">
          <li><b>Données</b> : huit étapes dans la colonne de gauche. Chaque champ modifié met à jour la ligne correspondante du script YAML (vue « Script YAML »), qui reste la référence du modèle ; le script peut aussi être édité directement, avec auto-complétion (Ctrl+Espace) et erreurs cliquables. Les options rarement utiles sont repliées sous « Options avancées ».</li>
          <li><b>Calcul</b> : bouton « Calculer » ou Ctrl+Entrée. Les phases s'enchaînent ; une rupture est signalée avec la phase concernée.</li>
          <li><b>Résultats</b> : synthèse, diagrammes de la phase active (frise en bas), efforts d'appui, vérifications, maquette 3D, hypothèses et référentiel. Exports : menu « Exporter » (note de calcul, image, maquette HTML, script).</li>
        </ol>
      </div>
      <div className="bloc" id="aide-catalogue"><div className="bloc-titre">Catalogue des exemples élémentaires <span className="doux" style={{ fontWeight: 400 }}>(menu Fichier)</span></div>
        <div style={{ padding: '0 10px 6px' }}><CatalogueExemples exemples={exemples} onExemple={onExemple} /></div>
      </div>
      <div className="bloc" id="aide-conventions"><div className="bloc-titre">Conventions et unités</div>
        <ul className="liste-aide">
          <li>Unités : kN, m, kPa, kN/m³, degrés ; cotes en mètres, axe vertical vers le haut (m NGF par défaut, ou le système indiqué dans le bloc projet).</li>
          <li>Déplacement positif vers la fouille ; moment positif quand la face côté fouille est tendue ; effort d'appui positif quand l'appui retient l'écran (buton comprimé, tirant tendu).</li>
          <li>Amont = côté terre (côté retenu) ; aval = côté fouille.</li>
          <li>Écran : la paroi de soutènement (clé <span className="mono">paroi</span> du script : palplanches, paroi moulée, pieux sécants ou disjoints, berlinoise).</li>
          <li>Vérifié si le taux de travail (valeur de calcul / valeur limite) est inférieur ou égal à 100 % ; « non vérifiable » quand une valeur de norme manque dans docs/normes.</li>
        </ul>
      </div>
      <div className="bloc" id="aide-raccourcis"><div className="bloc-titre">Raccourcis clavier</div>
        <table className="tableau">
          <thead><tr><th>Touche</th><th>Action</th><th>Où</th></tr></thead>
          <tbody>{RACCOURCIS.map(([t, a, o]) => <tr key={t + a}><td className="mono">{t}</td><td>{a}</td><td className="doux">{o}</td></tr>)}</tbody>
        </table>
      </div>
      <div className="bloc" id="aide-guide"><div className="bloc-titre">Guide du langage de script <span className="doux" style={{ fontWeight: 400 }}>(docs/guide_script.md)</span></div>
        {erreur && <div className="alerte orange" style={{ margin: 10 }}>{erreur}</div>}
        {!guide && !erreur && <div className="note" style={{ padding: 10 }}>Chargement du guide…</div>}
        {guide && (
          <div className="guide-colonnes">
            <nav className="sommaire-guide" aria-label="Sommaire du guide">
              {sommaire.map((s) => <a key={s.id} href={`#${s.id}`} className={s.niveau === 3 ? 'niveau3' : ''} onClick={(e) => { e.preventDefault(); document.getElementById(s.id)?.scrollIntoView({ block: 'start' }) }}>{s.texte}</a>)}
            </nav>
            <div ref={conteneur} className="guide" dangerouslySetInnerHTML={{ __html: guide }} />
          </div>
        )}
      </div>
      <p className="note">RetainWall {version}. Version non validée : aucun résultat ne doit servir à un projet réel avant comparaison à K-Réa ou RIDO sur plusieurs cas et visa d'un ingénieur.</p>
    </div>
  )
}
