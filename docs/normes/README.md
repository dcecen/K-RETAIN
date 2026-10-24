# Extraits de normes

Ce dossier contient **les seules valeurs normatives** que RetainWall a le droit d'utiliser
(règle absolue n° 1 du CLAUDE.md). Le code ne contient aucun coefficient de norme en dur.

Les fichiers `*.yaml` de ce dossier ont été **renseignés de mémoire le 22 octobre 2026**, à la
demande de l'utilisateur, chaque valeur portant son article d'origine et la mention « à
confirmer » : **ils doivent être relus sur le texte des normes par un ingénieur avant tout usage
en projet.** Les modèles vides (valeurs à `null`, marqueur `TODO-NORME`) sont conservés dans
`modeles/`. Une valeur absente, `null` ou égale à zéro rend la vérification qui en dépend
« non vérifiable : valeur de norme manquante », avec le fichier et la clé concernés.

Pour remplir : recopiez la valeur depuis votre exemplaire de la norme, et complétez le
champ `source` (article, tableau, annexe nationale). Déposez aussi les extraits PDF ou
scans à côté, pour la relecture croisée.

| Fichier | Contenu attendu |
| --- | --- |
| `nf_p94_282.yaml` | Coefficients partiels ELU/ELS, approche de calcul, butée mobilisée, Kranz, fond de fouille, largeur de réaction des fiches discontinues |
| `ec3.yaml` | γM0, γM1, γM2, courbes de flambement, facteurs d'imperfection, EN 1993-5 (réduction d'inertie des profils en U, corrosion) |
| `ec2.yaml` | γc, γs, αcc, diagramme parabole-rectangle, tranchant (CRd,c, vmin, θ) |
| `kerisel_absi/` | Tables de Kérisel-Absi en CSV (facultatif ; sinon Coulomb/Rankine) |
