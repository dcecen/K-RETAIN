import type { Exemple } from '../lib/api'
import type { EtatCalcul } from '../lib/etat'
import { titreScript } from '../lib/format'
import { IconeCalcul, IconeChevronB, IconeExport, IconeFichier, IconeInfo, IconeLogo, IconeLune, IconeMenu, IconePanneauD, IconeSoleil } from '../lib/icones'
import type { Theme } from '../lib/theme'
import type { SectionAide } from '../vues/Aide'
import { Menu } from './Menu'

/** Groupes du menu Fichier pour les exemples élémentaires (dossiers exemples/elementaires/2d et 3d ; l'ancien
 *  groupe « Vérifications élémentaires » reste lu si des scripts sont encore à la racine du dossier). */
const GROUPES_ELEMENTAIRES = ['Exemples élémentaires 2D', 'Exemples élémentaires 3D', 'Vérifications élémentaires']
/** Groupes affichés dans le menu Fichier : élémentaires, puis cas convertis depuis RIDO (exemples/rido). */
const GROUPES_MENU = [...GROUPES_ELEMENTAIRES, 'Comparaison RIDO']

/** En-tête de commentaires d'un script (ce qui est vérifié, résultat attendu, source) pour l'info-bulle. */
function enTete(texte: string): string {
  return texte.split('\n').filter((l) => l.startsWith('#')).map((l) => l.replace(/^#\s?/, '')).join('\n')
}

export function BarreTitre(p: {
  projet: string
  etat: EtatCalcul
  enCours: boolean
  exemples: Exemple[]
  theme: Theme
  version: string
  imagePossible: boolean
  resultatsDisponibles: boolean
  onRecalculer: () => void
  onNouveau: () => void
  onExemple: (e: Exemple) => void
  onOuvrir: (f: File) => void
  onEnregistrer: () => void
  onRido: (f: File) => void
  onImage: () => void
  onNote: () => void
  onNoteFichier: () => void
  onMaquette: () => void
  onTheme: () => void
  onAllerErreur: () => void
  onAide: (section: SectionAide) => void
  onAPropos: () => void
  onTiroirNav: () => void
  onTiroirInsp: () => void
}) {
  const choisirFichier = (accept: string, action: (f: File) => void) => {
    const i = document.createElement('input')
    i.type = 'file'
    i.accept = accept
    i.onchange = () => { if (i.files?.[0]) action(i.files[0]) }
    i.click()
  }
  const groupe = (g: string) => p.exemples.filter((e) => (e.groupe ?? 'Exemples') === g)
  const nouveauPossible = groupe('Modèles').length > 0
  return (
    <header className="barre-titre zone-titre">
      <button className="btn icone discret btn-tiroir nav" onClick={p.onTiroirNav} title="Navigation"><IconeMenu /></button>
      <div className="logo"><IconeLogo taille={18} /> K-Retain</div>
      <div className="separateur-v masquer-etroit" />
      <Menu bouton={<><IconeFichier /> <span className="masquer-etroit">Fichier</span> <IconeChevronB taille={12} /></>} titre="Fichier">
        {(fermer) => (
          <>
            <button onClick={() => { p.onNouveau(); fermer() }} disabled={!nouveauPossible} title={nouveauPossible ? 'Script minimal à adapter (gabarit exemples/modeles)' : 'Gabarit indisponible (serveur injoignable)'}>Nouveau projet</button>
            <button onClick={() => { choisirFichier('.yaml,.yml,.txt', p.onOuvrir); fermer() }}>Ouvrir un script…</button>
            <button onClick={() => { p.onEnregistrer(); fermer() }}>Enregistrer le script</button>
            <hr />
            <div className="titre-groupe">Exemples</div>
            {groupe('Exemples').map((e) => (
              <button key={e.nom} onClick={() => { p.onExemple(e); fermer() }}>
                {titreScript(e.texte, e.nom)}
                <span className="detail-entree">{e.nom}.yaml</span>
              </button>
            ))}
            {GROUPES_MENU.filter((g) => groupe(g).length > 0).map((g) => (
              <div key={g}>
                <hr />
                <div className="titre-groupe">{g}</div>
                {groupe(g).map((e) => (
                  <button key={e.nom} onClick={() => { p.onExemple(e); fermer() }}
                    title={e.attendu ? `Attendu : ${e.attendu}${e.source ? `\nSource : ${e.source}` : ''}` : enTete(e.texte)}>
                    {e.titre || titreScript(e.texte, e.nom)}
                  </button>
                ))}
              </div>
            ))}
            {GROUPES_ELEMENTAIRES.some((g) => groupe(g).length > 0) && (
              <button onClick={() => { p.onAide('catalogue'); fermer() }}>
                Catalogue des exemples élémentaires
                <span className="detail-entree">résultat attendu et source de chaque exemple</span>
              </button>
            )}
            <hr />
            <button onClick={() => { choisirFichier('*', p.onRido); fermer() }}>Importer un fichier RIDO…</button>
          </>
        )}
      </Menu>
      <div className="projet" title={p.projet}><span className="nom">{p.projet || 'Sans titre'}</span></div>
      <span className="bandeau-demo masquer-etroit" title="Aucun résultat ne doit servir à un projet réel avant comparaison à K-Réa ou RIDO sur plusieurs cas et visa d'un ingénieur.">
        Version non validée
      </span>
      <span className="espace" />
      <span className={`etat-calcul ${p.enCours ? 'calcul' : p.etat.genre === 'rupture' ? 'erreur' : p.etat.genre}`}
        onClick={p.etat.genre === 'erreur' ? p.onAllerErreur : undefined}
        title={p.etat.genre === 'erreur' ? 'Aller à l’erreur dans le script' : p.etat.texte}>
        {p.enCours ? 'Calcul en cours' : p.etat.texte}
      </span>
      <span className="espace" />
      <button className="btn principal" onClick={p.onRecalculer} disabled={p.enCours} title="Lancer le calcul (Ctrl+Entrée)">
        <IconeCalcul /> Calculer <span className="raccourci masquer-etroit">Ctrl+Entrée</span>
      </button>
      <Menu droite bouton={<><IconeExport /> <span className="masquer-etroit">Exporter</span></>} titre="Exporter">
        {(fermer) => (
          <>
            <button disabled={!p.resultatsDisponibles} onClick={() => { p.onNote(); fermer() }}>Note de calcul : imprimer ou enregistrer en PDF</button>
            <button disabled={!p.resultatsDisponibles} onClick={() => { p.onNoteFichier(); fermer() }}>Note de calcul : fichier HTML</button>
            <button disabled={!p.imagePossible} onClick={() => { p.onImage(); fermer() }}>Image PNG de la vue affichée</button>
            <button disabled={!p.resultatsDisponibles} onClick={() => { p.onMaquette(); fermer() }}>Maquette 3D : fichier HTML autonome</button>
            <hr />
            <button onClick={() => { p.onEnregistrer(); fermer() }}>Script de calcul (.yaml)</button>
          </>
        )}
      </Menu>
      <Menu droite bouton={<><IconeInfo /> <span className="masquer-etroit">Aide</span></>} titre="Aide">
        {(fermer) => (
          <>
            <button onClick={() => { p.onAide('premiers-pas'); fermer() }}>Premiers pas</button>
            <button onClick={() => { p.onAide('guide'); fermer() }}>Guide du langage de script</button>
            <button onClick={() => { p.onAide('raccourcis'); fermer() }}>Raccourcis clavier</button>
            <button onClick={() => { p.onAide('conventions'); fermer() }}>Conventions de signe et unités</button>
            <button onClick={() => { p.onAide('catalogue'); fermer() }}>Catalogue des exemples élémentaires</button>
            <hr />
            <button onClick={() => { window.open('/api/validation/rapport', '_blank', 'noopener'); fermer() }}>
              Rapport de validation
              <span className="detail-entree">45 cas : poutres RDM, Winkler, plaque, écran 2D, balayages, pseudo-3D</span>
            </button>
            <button onClick={() => { p.onAPropos(); fermer() }}>À propos de K-Retain {p.version}</button>
          </>
        )}
      </Menu>
      <button className="btn icone" onClick={p.onTheme} title={p.theme === 'sombre' ? 'Thème clair' : 'Thème sombre'}>
        {p.theme === 'sombre' ? <IconeSoleil /> : <IconeLune />}
      </button>
      <button className="btn icone discret btn-tiroir insp" onClick={p.onTiroirInsp} title="Phase et résultats"><IconePanneauD /></button>
    </header>
  )
}
