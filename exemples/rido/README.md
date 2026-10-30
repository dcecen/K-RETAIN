# Comparaison K-Retain / RIDO

Ce dossier contient les cas à comparer à RIDO :

- `<cas>.rid` (ou `.rido`, `.dat`) : le fichier d'entrée RIDO ;
- `<cas>.yaml` : le même cas en script K-Retain, converti depuis le fichier RIDO (il apparaît dans le menu
  **Fichier > Comparaison RIDO** de l'interface) ;
- `<cas>.rapport.txt` : les lignes du fichier RIDO non reprises par la conversion (à relire) ;
- `<cas>.resultats_rido.yaml` (facultatif) : résultats RIDO recopiés, sous la forme
  `- {phase: "...", grandeur: "Déplacement maximal", valeur: 12.3}`, pour pré-remplir le classeur ;
- `comparaison_rido.xlsx` : le classeur de comparaison.

Régénérer le classeur (conversion des fichiers RIDO puis calcul de chaque script) :

```
cd backend
.venv\Scripts\python.exe -m outils.comparaison_rido
```

Dans le classeur, la feuille « Synthèse » donne, pour chaque cas et chaque phase, le déplacement en tête et
maximal, les moments maximal et minimal, le tranchant maximal et l'effort de chaque appui. Saisir la valeur
RIDO dans la colonne jaune : l'écart et le verdict (tolérance 5 %) se calculent seuls. Une feuille par cas donne
les profils z, y, M, V de chaque phase pour superposer les courbes.

Conventions K-Retain : y positif vers la fouille (mm) ; M positif quand la face côté fouille est tendue
(kN·m/m) ; effort d'appui positif quand l'appui retient l'écran (kN/m). Vérifier les conventions de RIDO avant
de comparer les signes.
