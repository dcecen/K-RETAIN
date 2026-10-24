import type { ErreurScript } from '../lib/api'
import type { EtatCalcul } from '../lib/etat'
import { IconeCalcul } from '../lib/icones'

/** Page d'accueil des résultats tant qu'aucun calcul n'existe : les trois étapes, ou les erreurs bloquantes. */
export function PremiersPas({ etat, erreurs, enCours, onDonnees, onCalculer, onLigne }: {
  etat: EtatCalcul
  erreurs: ErreurScript[]
  enCours: boolean
  onDonnees: () => void
  onCalculer: () => void
  onLigne: (l: number | null) => void
}) {
  if (erreurs.length) {
    return (
      <div className="vide-centre bloque">
        <b>Le calcul ne peut pas être lancé : {erreurs.length} erreur{erreurs.length > 1 ? 's' : ''} dans le script</b>
        <span>Un clic sur une erreur ouvre la ligne du script. Les mots-clés inconnus sont ignorés et n'empêchent pas le calcul.</span>
        <ul className="erreurs-bloquantes">
          {erreurs.slice(0, 12).map((e, i) => (
            <li key={i} onClick={() => onLigne(e.ligne)}>
              <b className="mono">{e.ligne ? `ligne ${e.ligne}` : 'script'}</b> <span>{e.chemin ? `${e.chemin} : ` : ''}{e.message}</span>
            </li>
          ))}
          {erreurs.length > 12 && <li className="doux">… et {erreurs.length - 12} autre(s) (vue Script YAML)</li>}
        </ul>
      </div>
    )
  }
  return (
    <div className="premiers-pas">
      <h2>Premiers pas</h2>
      <ol className="etapes-accueil">
        <li>
          <b>Renseigner les données</b>
          <span>Huit étapes dans la colonne de gauche : projet, sols, écran, eau, surcharges, appuis, phases, vérifications. Chaque champ met à jour le script YAML, qui reste la référence du modèle.</span>
          <button className="btn" onClick={onDonnees}>Ouvrir les données</button>
        </li>
        <li>
          <b>Calculer</b>
          <span>Bouton « Calculer » ou Ctrl+Entrée. Le calcul enchaîne toutes les phases ; une rupture est signalée avec la phase concernée.</span>
          <button className="btn principal" onClick={onCalculer} disabled={enCours}><IconeCalcul /> Calculer</button>
        </li>
        <li>
          <b>Lire les résultats</b>
          <span>Synthèse, diagrammes de la phase active, efforts d'appui, vérifications, maquette 3D, hypothèses ; exports par le menu « Exporter ».</span>
        </li>
      </ol>
      <p className="note">Conventions : cotes en mètres, axe vertical vers le haut ; déplacement positif vers la fouille ; moment positif quand la face côté fouille est tendue ; unités kN, m, kPa, kN/m³, degrés.</p>
      <p className="note">{etat.genre === 'erreur' ? etat.texte : 'Le script chargé est calculable.'} Menu « Fichier » : nouveau projet, exemples, ouvrir un fichier.</p>
    </div>
  )
}
