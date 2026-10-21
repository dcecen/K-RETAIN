# Catalogues fournisseurs

Déposez ici les catalogues au format Excel (.xlsx) ou CSV, sur le modèle des fichiers
`modele_*.csv` (mêmes en-têtes, unités dans l'en-tête). Import :

    cd backend
    .venv\Scripts\python -m sout.materiaux.importer ..\docs\catalogues\mon_catalogue.xlsx

La base livrée contient un petit jeu **DEMO** (valeurs d'illustration) qui sert seulement
à faire tourner l'application. Il doit être remplacé par vos catalogues avant tout usage.
