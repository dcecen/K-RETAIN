# Installation et mise à disposition de K-Retain

Ce document s'adresse à la personne qui installe K-Retain sur le serveur interne du
bureau d'études. Rappel : l'outil est **en cours de validation**. Aucun résultat ne doit
servir à un projet réel avant comparaison à K-Réa ou RIDO sur plusieurs cas et visa d'un
ingénieur (voir docs/ETAT.md).

## 1. Poste de développement (un seul utilisateur)

Prérequis : Python 3.12, Node.js 20 ou plus récent.

```powershell
cd backend
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -e ".[test]"
cd ..\frontend
npm install
```

Puis, dans deux terminaux : `.\lancer_backend.ps1` et `.\lancer_frontend.ps1`, et ouvrir
http://localhost:5173. Les tests : `.\lancer_tests.ps1`.

## 2. Serveur interne avec Docker (recommandé)

```bash
docker build -t retainwall .
docker volume create retainwall-donnees
# création d'un compte (mot de passe demandé, stocké haché dans le volume)
docker run --rm -it -v retainwall-donnees:/donnees retainwall python -m sout.utilisateurs ajouter jdupont
# lancement
docker run -d --name retainwall --restart unless-stopped -p 8000:8000 -v retainwall-donnees:/donnees retainwall
```

L'application est servie sur le port 8000 : interface et calcul par le même serveur.
Chaque utilisateur s'identifie (nom et mot de passe) à l'ouverture.

## 3. Serveur interne Windows sans Docker

1. Installer comme au § 1, puis compiler l'interface : `cd frontend ; npm run build`.
2. Créer les comptes : `backend\.venv\Scripts\python -m sout.utilisateurs ajouter jdupont`.
3. Lancer : `.\lancer_production.ps1` (à inscrire comme tâche planifiée au démarrage, ou
   comme service avec NSSM).

## 4. Sécurité et données

- **HTTPS obligatoire** : l'identification HTTP Basic transmet le mot de passe à chaque
  requête. Placez K-Retain derrière un proxy inverse en HTTPS (IIS, nginx, Traefik) et
  n'exposez pas le port 8000 hors du réseau interne.
- Les mots de passe sont stockés hachés (PBKDF2-SHA256, sel aléatoire) dans
  `utilisateurs.json` ; gestion : `python -m sout.utilisateurs ajouter|supprimer|lister`.
- Les scripts de calcul restent sur les postes des utilisateurs (ouvrir / enregistrer) :
  le serveur ne conserve aucune donnée de projet. Sauvegardez `docs/normes`,
  `docs/catalogues` et le volume des comptes.
- Base matériaux (`backend/data/materiaux.sqlite`) : créée au premier démarrage à partir du
  jeu DEMO et de `docs/catalogues`, puis reconstruite à chaque import par l'interface ou par
  `python -m sout.materiaux.importer --reconstruire` (à lancer après avoir déposé un catalogue
  à la main dans `docs/catalogues`). Sauvegarder `docs/catalogues`.
- Le serveur n'écoute que sur ce poste (`127.0.0.1`) : c'est le proxy HTTPS qui l'expose.
  Pour l'exposer directement (réseau de confiance), définir `RETAINWALL_HOTE=0.0.0.0` avant
  `lancer_production.ps1`.

## 5. Mise à jour des valeurs normatives

Les fichiers `docs/normes/*.yaml` sont lus à chaque calcul et font partie de la clé du cache
des résultats : modifiez une valeur (avec sa source) puis relancez un calcul, le résultat est
recalculé sans redémarrage ni recompilation. Les valeurs livrées ont été renseignées de
mémoire (octobre 2026) et sont toutes marquées « à confirmer ».
Avec Docker, montez le dossier : `-v C:\retainwall\normes:/app/docs/normes`.

## 6. Questions ouvertes (à trancher par le bureau d'études)

Hébergement exact, sauvegarde et confidentialité des données de projet : voir la liste
des points ouverts dans docs/specs.md et docs/ETAT.md.
