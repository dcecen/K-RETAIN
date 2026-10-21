# RetainWall

Application web interne de calcul d'écrans de soutènement par la méthode aux
coefficients de réaction (principe de RIDO et K-Réa) : calcul phasé 2D, pseudo-3D,
vérifications géotechniques (NF P 94-282) et structurelles (EC2, EC3), maquette 3D HTML.

> **Outil en cours de validation.** Aucun résultat ne doit servir à un projet réel avant
> comparaison à K-Réa ou RIDO sur plusieurs cas et visa d'un ingénieur. Les valeurs de
> norme ne sont pas fournies : voir `docs/normes/` et l'état d'avancement `docs/ETAT.md`.

## Lancer le logiciel

Double-cliquez sur **`Lancer RetainWall.bat`** (ou le raccourci « RetainWall » du Bureau).
La première fois, il installe ce qui manque (Python 3.12 et Node.js doivent être présents),
puis le navigateur s'ouvre sur http://localhost:8000. Fermer la fenêtre noire arrête le logiciel.

## Démarrage pour le développement (poste local)

```powershell
cd backend ; py -3.12 -m venv .venv ; .venv\Scripts\python -m pip install -e ".[test]" ; cd ..
cd frontend ; npm install ; cd ..
.\lancer_backend.ps1      # terminal 1 : serveur de calcul (port 8000)
.\lancer_frontend.ps1     # terminal 2 : interface, puis ouvrir http://localhost:5173
.\lancer_tests.ps1        # tests
```

## Documentation

| Document | Contenu |
| --- | --- |
| `docs/specs.md` | Cahier des charges et feuille de route |
| `docs/guide_script.md` | Guide utilisateur du langage de script |
| `docs/ETAT.md` | État d'avancement, limites, questions ouvertes |
| `docs/INSTALLATION.md` | Déploiement sur le serveur interne |
| `docs/normes/` | Valeurs normatives à fournir (modèles vides) |
| `docs/catalogues/` | Catalogues fournisseurs à importer |
| `docs/rido/` | Manuel et exemples RIDO, table de correspondance |
| `exemples/` | Scripts d'exemple (valeurs d'illustration) |
