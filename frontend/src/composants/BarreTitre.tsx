import type { EtatCalcul } from '../lib/etat'
import {
  IconeCalcul, IconeChevronB, IconeExport, IconeFichier, IconeLogo, IconeLune, IconeMenu, IconePanneauD,
  IconePanneauG, IconeSoleil,
} from '../lib/icones'
import type { Theme } from '../lib/theme'
import { Menu } from './Menu'

export function BarreTitre(p: {
  projet: string
  etat: EtatCalcul
  enCours: boolean
  exemples: { nom: string; texte: string }[]
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
            {p.exemples.map((e) => (
              <button key={e.nom} onClick={() => { p.onExemple(e.texte); fermer() }}>{e.nom}</button>
            ))}
            <hr />
            <button onClick={() => { choisirFichier('.yaml,.yml,.txt', p.onOuvrir); fermer() }}>Ouvrir un script…</button>
            <button onClick={() => { p.onEnregistrer(); fermer() }}>Enregistrer le script</button>
            <button onClick={() => { choisirFichier('*', p.onRido); fermer() }}>Importer un fichier RIDO…</button>
            <hr />
            <button onClick={() => { p.onMateriaux(); fermer() }}>Base matériaux</button>
          </>
        )}
      </Menu>
      <div className="projet" title={p.projet}><span className="nom">{p.projet || 'Sans titre'}</span></div>
      <span className="bandeau-demo" title="Aucun résultat ne doit servir à un projet réel avant comparaison à K-Réa ou RIDO et visa d'un ingénieur.">
        Démonstrateur — calculs non validés
      </span>
      <span className="espace" />
      <span className={`pastille-etat ${p.enCours ? 'calcul' : p.etat.genre === 'rupture' ? 'erreur' : p.etat.genre}`}
        onClick={p.etat.genre === 'erreur' ? p.onAllerErreur : undefined}
        title={p.etat.genre === 'erreur' ? 'Aller à l’erreur dans le script' : undefined}>
        {p.enCours ? 'Calcul en cours…' : p.etat.texte}
      </span>
      <span className="espace" />
      <button className="btn principal" onClick={p.onRecalculer} disabled={p.enCours} title="Recalculer (Ctrl+Entrée)">
        <IconeCalcul /> Recalculer <span className="raccourci masquer-etroit">Ctrl+↵</span>
      </button>
      <Menu droite bouton={<><IconeExport /> <span className="masquer-etroit">Exporter</span></>} titre="Exporter">
        {(fermer) => (
          <>
            <button disabled={!p.imagePossible} onClick={() => { p.onImage(); fermer() }}>Image PNG de la vue active</button>
            <button disabled={!p.resultatsDisponibles} onClick={() => { p.onNote(); fermer() }}>Note de synthèse imprimable</button>
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
