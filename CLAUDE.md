# Projet : K-Retain, logiciel de calcul d'écrans de soutènement

Application web interne de calcul d'écrans par coefficients de réaction
(principe RIDO / K-Réa), vérifications NF P 94-282, EC2, EC3, maquette 3D HTML.
L'utilisateur est ingénieur géotechnicien, pas développeur : explique tes choix
en français simple.

## Pile technique
- Backend : Python 3.12, numpy, scipy, pydantic, FastAPI, pytest, SQLite.
- Frontend : React + TypeScript + Vite, Plotly.js, three.js, éditeur Monaco.
- Script d'entrée : YAML (ruamel.yaml pour garder les numéros de ligne).

## Organisation
- backend/sout/noyau : solveur poutre sur ressorts, phasage
- backend/sout/sol : couches, poussée/butée, kh
- backend/sout/parois : types de paroi -> rigidités et sections
- backend/sout/appuis : butons, tirants, bracons, liernes, dalles
- backend/sout/verifs_geo, verifs_struct : vérifications
- backend/sout/pseudo3d : plaque sur ressorts
- backend/sout/script : schéma, lecteur, import RIDO
- backend/sout/materiaux : base SQLite et imports
- backend/tests/unitaires, backend/tests/validation
- frontend/ : interface
- docs/normes/ : extraits de normes fournis par l'utilisateur
- docs/rido/ : manuel et exemples RIDO
- docs/ETAT.md : état d'avancement, mis à jour en fin de session

## Conventions
- Unités SI : kN, m, kPa, kN/m3, degrés. Jamais d'unité implicite.
- Cotes en mètres, axe vertical vers le haut.
- Déplacement positif vers la fouille. Moment positif quand la face
  côté fouille est tendue. À rappeler dans chaque légende.
- Noms de code en français sans accents ; interface en français.
- Les fonctions de calcul sont pures : pas de lecture de fichier, pas d'affichage.

## Règles absolues
1. Ne jamais inventer un coefficient, une formule ou une valeur de norme.
   Source autorisée : docs/normes/ ou une publication citée. Si elle manque,
   arrête-toi, laisse un marqueur TODO-NORME et demande.
2. Chaque formule a une docstring qui cite sa source (norme + article).
3. Chaque fonction de calcul a des tests. Les cas de validation sont dans
   tests/validation avec une tolérance de 5 %.
4. Ne jamais modifier un test ou une valeur de référence pour qu'un test
   passe. En cas d'échec, explique l'écart et propose avant de corriger.
5. Commencer chaque jalon par un plan soumis à l'utilisateur.
6. Lancer tous les tests avant de déclarer une tâche terminée.
7. Un commit par étape validée, message en français.
8. En fin de session, mettre à jour docs/ETAT.md : fait, testé,
   reste à faire, questions ouvertes.
