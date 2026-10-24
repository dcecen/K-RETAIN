import type { Exemple } from '../lib/api'
import type { EtatCalcul } from '../lib/etat'
import {
  IconeCalcul, IconeChevronB, IconeExport, IconeFichier, IconeLogo, IconeLune, IconeMenu, IconePanneauD,
  IconePanneauG, IconeSoleil,
} from '../lib/icones'
import type { Theme } from '../lib/theme'
import { Menu } from './Menu'

/** Titre d'un script élémentaire : sa ligne « projet: », à défaut son nom de fichier. */
function libelleElementaire(e: Exemple): string {
  const m = e.texte.match(/^projet:\s*(.+)$/m)
  return m ? m[1].trim() : e.nom
}

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
  imagePossible: boolean
  resultatsDisponibles: boolean
  onRecalculer: () => void
  onExemple: (texte: string) => void
  onOuvrir: (f: File) => void
  onEnregistrer: () => void
  onRido: (f: File) => void
  onMateriaux: () => void
  onImage: () => void
  onNote: () => void
  onMaquette: () => void
  onTheme: () => void
  onAllerErreur: () => void
  onBasculeNav: () => void
  onBasculeInsp: () => void
}) {
  const choisirFichier = (accept: string, action: (f: File) => void) => {
    const i = document.createElement('input')
    i.type = 'file'
    i.accept = accept
    i.onchange = () => { if (i.files?.[0]) action(i.files[0]) }
    i.click()
  }
  return (
    <header className="barre-titre zone-titre">
      <button className="btn icone discret btn-tiroir nav" onClick={p.onBasculeNav} title="Navigation du modèle"><IconeMenu /></button>
      <div className="logo"><IconeLogo taille={18} /> RetainWall</div>
      <div className="separateur-v masquer-etroit" />
      <Menu bouton={<><IconeFichier /> <span className="masquer-etroit">Fichier</span> <IconeChevronB taille={12} /></>} titre="Fichier">
        {(fermer) => (
          <>
            <div className="titre-groupe">Exemples</div>
            {p.exemples.filter((e) => (e.groupe ?? 'Exemples') === 'Exemples').map((e) => (
              <button key={e.nom} onClick={() => { p.onExemple(e.texte); fermer() }}>{e.nom}</button>
            ))}
            {p.exemples.some((e) => e.groupe === 'Vérifications élémentaires') && (
              <>
                <hr />
                <div className="titre-groupe">Vérifications élémentaires</div>
                {p.exemples.filter((e) => e.groupe === 'Vérifications élémentaires').map((e) => (
                  <button key={e.nom} onClick={() => { p.onExemple(e.texte); fermer() }} title={enTete(e.texte)}>
                    {libelleElementaire(e)}
                  </button>
                ))}
                <button onClick={() => { window.open('/api/validation/rapport', '_blank', 'noopener'); fermer() }}>
                  Rapport de validation complet
                  <span className="detail-entree">45 cas : poutres RDM, Winkler, plaque, écran 2D, balayages, pseudo-3D</span>
                </button>
              </>
            )}
            <hr />
            <button onClick={() => { choisirFichier('.yaml,.yml,.txt', p.onOuvrir); fermer() }}>Ouvrir un script</button>
            <button onClick={() => { p.onEnregistrer(); fermer() }}>Enregistrer le script</button>
            <button onClick={() => { choisirFichier('*', p.onRido); fermer() }}>Importer un fichier RIDO</button>
            <hr />
            <button onClick={() => { p.onMateriaux(); fermer() }}>Base matériaux</button>
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
        title={p.etat.genre === 'erreur' ? 'Aller à l’erreur dans le script' : undefined}>
        {p.enCours ? 'Calcul en cours' : p.etat.texte}
      </span>
      <span className="espace" />
      <button className="btn principal" onClick={p.onRecalculer} disabled={p.enCours} title="Lancer le calcul (Ctrl+Entrée)">
        <IconeCalcul /> Calculer <span className="raccourci masquer-etroit">Ctrl+Entrée</span>
      </button>
      <Menu droite bouton={<><IconeExport /> <span className="masquer-etroit">Exporter</span></>} titre="Exporter">
        {(fermer) => (
          <>
            <button disabled={!p.imagePossible} onClick={() => { p.onImage(); fermer() }}>Image PNG de la vue active</button>
            <button disabled={!p.resultatsDisponibles} onClick={() => { p.onNote(); fermer() }}>Note de calcul (HTML imprimable)</button>
            <button disabled={!p.resultatsDisponibles} onClick={() => { p.onMaquette(); fermer() }}>Maquette 3D (fichier HTML autonome)</button>
            <hr />
            <button onClick={() => { p.onEnregistrer(); fermer() }}>Script de calcul (.yaml)</button>
          </>
        )}
      </Menu>
      <button className="btn icone" onClick={p.onTheme} title={p.theme === 'sombre' ? 'Thème clair' : 'Thème sombre'}>
        {p.theme === 'sombre' ? <IconeSoleil /> : <IconeLune />}
      </button>
      <button className="btn icone discret masquer-etroit" onClick={p.onBasculeNav} title="Afficher ou masquer la navigation"><IconePanneauG /></button>
      <button className="btn icone discret" onClick={p.onBasculeInsp} title="Afficher ou masquer l'inspecteur"><IconePanneauD /></button>
    </header>
  )
}
