/** Aide intégrée : premiers pas, raccourcis clavier, conventions. (Le guide du script est ajouté au lot suivant.) */
const RACCOURCIS: [string, string, string][] = [
  ['Ctrl+Entrée', 'Lancer le calcul', 'partout, y compris dans l’éditeur'],
  ['← / →', 'Phase précédente / suivante (dans la branche)', 'vues de résultats, hors champs de saisie'],
  ['1 à 9', 'Coupe de calcul affichée', 'projets à plusieurs coupes'],
  ['Entrée / Échap', 'Valider / annuler la saisie d’un champ', 'formulaires'],
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

export function Aide({ version }: { version: string }) {
  return (
    <div className="saisie aide-vue">
      <div className="bloc"><div className="bloc-titre">Premiers pas</div>
        <ol className="etapes-aide">
          <li><b>Données</b> : huit étapes dans la colonne de gauche. Chaque champ modifié met à jour la ligne correspondante du script YAML (vue « Script YAML »), qui reste la référence du modèle ; le script peut aussi être édité directement, avec auto-complétion (Ctrl+Espace) et erreurs cliquables.</li>
          <li><b>Calcul</b> : bouton « Calculer » ou Ctrl+Entrée. Les phases s'enchaînent ; une rupture est signalée avec la phase concernée.</li>
          <li><b>Résultats</b> : synthèse, diagrammes de la phase active (frise en bas), efforts d'appui, vérifications, maquette 3D, hypothèses et référentiel. Exports : menu « Exporter » (note de calcul, image, maquette HTML, script).</li>
        </ol>
      </div>
      <div className="bloc"><div className="bloc-titre">Conventions et unités</div>
        <ul className="liste-aide">
          <li>Unités : kN, m, kPa, kN/m³, degrés ; cotes en mètres, axe vertical vers le haut (m NGF par défaut, ou le système indiqué dans le bloc projet).</li>
          <li>Déplacement positif vers la fouille ; moment positif quand la face côté fouille est tendue ; effort d'appui positif quand l'appui retient l'écran (buton comprimé, tirant tendu).</li>
          <li>Amont = côté terre (côté retenu) ; aval = côté fouille.</li>
          <li>Écran : la paroi de soutènement (clé <span className="mono">paroi</span> du script : palplanches, paroi moulée, pieux sécants ou disjoints, berlinoise).</li>
          <li>Vérifié si le taux de travail (valeur de calcul / valeur limite) est inférieur ou égal à 100 % ; « non vérifiable » quand une valeur de norme manque dans docs/normes.</li>
        </ul>
      </div>
      <div className="bloc"><div className="bloc-titre">Raccourcis clavier</div>
        <table className="tableau">
          <thead><tr><th>Touche</th><th>Action</th><th>Où</th></tr></thead>
          <tbody>{RACCOURCIS.map(([t, a, o]) => <tr key={t + a}><td className="mono">{t}</td><td>{a}</td><td className="doux">{o}</td></tr>)}</tbody>
        </table>
      </div>
      <p className="note">RetainWall {version}. Version non validée : aucun résultat ne doit servir à un projet réel avant comparaison à K-Réa ou RIDO sur plusieurs cas et visa d'un ingénieur.</p>
    </div>
  )
}
