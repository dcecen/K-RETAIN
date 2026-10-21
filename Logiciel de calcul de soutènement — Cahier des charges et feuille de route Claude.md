# RetainWall — Cahier des charges et feuille de route Claude

Oct 21, 2026 · @CECEN

## Objet et périmètre

L'objectif est une application web interne qui calcule les écrans de soutènement par la méthode aux coefficients de réaction (le principe de RIDO et K-Réa). Elle vérifie aussi les appuis et les sections, puis produit une maquette 3D HTML. La cible est la version complète, construite par jalons : chaque jalon livre un outil utilisable et validé.

| Sujet | Choix retenu |
| --- | --- |
| Utilisateurs | Personnel pour les tests, puis bureau d'études interne |
| Normes | France : NF P 94-282 (écrans), Eurocode 7, Eurocode 2 (béton), Eurocode 3 (acier) |
| Mode de développement | Vibe coding : Claude écrit le code, vous pilotez et validez |
| Calcul | 2D par sections, plus un pseudo-3D (paroi en plaque sur ressorts) si faisable |
| Modèle de sol | Ressorts élasto-plastiques, kh selon Schmitt ; données pressiométriques et CPT |
| Types de paroi | Berlinoise, pieux disjoints, pieux sécants, palplanches, paroi moulée |
| Appuis | Butons, tirants, bracons, liernes, dalles |
| Vérifications | Toutes : butée, équilibre vertical, Kranz, fond de fouille, stabilité générale, déplacements, structure |
| Base matériaux | À créer : profilés et butons modulaires |
| Langage | Nouveau langage lisible pour l'équipe, plus lecture des fichiers RIDO |
| Sorties | Visualisations 2D, maquette 3D en HTML ; pas de note de calcul pour l'instant |
| Plateforme | Application web |

**Avertissement.** Un outil de soutènement décide de la sécurité d'une fouille. En vibe coding, vous ne relisez pas le code ligne à ligne : la seule protection est donc la validation par cas tests. Aucun résultat ne doit servir à un projet réel avant d'avoir été comparé à K-Réa ou RIDO sur plusieurs cas, et signé par un ingénieur.

## Méthode de travail avec Claude

En vibe coding, la qualité vient du cadre et des tests, pas de la relecture du code. Travaillez dans Claude Code en local (application de bureau ou terminal), sur un dossier suivi par Git.

1. **Un jalon par session.** Collez le prompt du jalon (section Feuille de route). Demandez d'abord un plan, lisez-le, puis lancez l'implémentation.
2. **Les tests avant le code.** Chaque formule a un test : une valeur calculée à la main, tirée d'un exemple publié ou d'une sortie K-Réa ou RIDO.
3. **Ne jamais modifier un test pour le faire passer.** Si un test échoue, demandez à Claude d'expliquer l'écart avant toute correction.
4. **Traçabilité.** Chaque formule cite sa source (norme et article, ou publication) dans le code et dans l'interface.
5. **Valeurs normatives fournies par vous.** Claude n'a pas le texte intégral de la NF P 94-282 ni des Eurocodes. Donnez-lui les extraits utiles (coefficients partiels, tableaux, formules) en fichiers dans le dépôt, dossier `docs/normes/`.
6. **Relecture croisée.** À la fin de chaque jalon, demandez une revue par un sous-agent qui n'a pas écrit le code : il compare chaque formule à la source citée.
7. **Un commit par étape validée.** On peut revenir en arrière à tout moment.

Tolérance de validation proposée face à K-Réa ou RIDO : écart de 5 % au plus sur le déplacement maximal, le moment maximal et les efforts d'appui. À confirmer selon votre pratique.

À rassembler avant de commencer :

- [ ] Extraits de la NF P 94-282 : coefficients partiels, butée mobilisée, Kranz, fond de fouille
- [ ] Manuel du format d'entrée RIDO et 3 à 5 fichiers exemples
- [ ] 3 à 5 calculs de référence K-Réa ou RIDO, avec entrées et sorties
- [ ] Catalogues fournisseurs : profilés, palplanches, butons modulaires

## Architecture technique

Un serveur Python fait tous les calculs ; l'interface web saisit, affiche et exporte. Ce découpage garde les formules testables sans passer par l'interface.

&#91;embedded content: architecture · calcul côté serveur, saisie et affichage côté navigateur\]

Les deux moteurs lisent le même script et rendent les mêmes résultats par phase : vérifications et vues ne savent pas lequel a tourné.

| Brique | Technologie | Raison du choix |
| --- | --- | --- |
| Calcul | Python, numpy, scipy | Bibliothèques numériques éprouvées, formules lisibles par un ingénieur |
| Données d'entrée | YAML, pydantic | Validation stricte du script |
| Serveur | FastAPI | Relie le calcul à l'interface |
| Base matériaux | SQLite | Un seul fichier, aucun serveur à installer |
| Interface | React, TypeScript, Vite | Standard du web, bien maîtrisé par Claude |
| Graphiques 2D | Plotly.js | Interactif, export image |
| 3D | three.js | Maquette en un seul fichier HTML |
| Tests | pytest | Tests unitaires et cas de validation |

## Spécifications fonctionnelles

Le cœur est une poutre sur ressorts élasto-plastiques calculée phase par phase, comme RIDO et K-Réa. Tout le reste (vérifications, structure, 3D) se branche sur ses résultats.

### Types de paroi

| Type | Modélisation par mètre linéaire | Points particuliers |
| --- | --- | --- |
| Palplanches | EI et section du catalogue | Réduction d'inertie des profils en U (serrures), corrosion, vérifications EN 1993-5 |
| Paroi moulée | EI béton, fissuré ou non au choix | Ferraillage en flexion composée et tranchant, EC2 |
| Pieux sécants | EI des pieux armés divisé par l'entraxe | Pieux primaires armés ou non |
| Pieux disjoints | EI d'un pieu divisé par l'entraxe | Fiche discontinue : largeur de réaction limitée sous le fond de fouille |
| Berlinoise | EI d'un profilé divisé par l'entraxe | Fiche discontinue ; vérification du blindage entre profilés |

Pour les fiches discontinues, la largeur de calcul de la butée et de la réaction suit les règles de la NF P 94-282, à fournir en extrait.

### Sol

- Couches horizontales : γ, γ', φ', c', module pressiométrique EM, coefficient rhéologique α, pression limite pl, résistance de pointe qc.
- Coefficients de poussée et de butée avec obliquité δ (tables de Kérisel-Absi, à fournir).
- Loi d'interaction : pression bornée entre poussée et butée limites, linéaire entre les deux avec la pente kh. Décharge et rechargement à chaque phase, comme RIDO et K-Réa.
- Coefficient de réaction selon Schmitt, avec EM en kPa, EI en kN·m²/m et kh en kN/m³ :

```latex
k_h = 2{,}1 \, \frac{(E_M/\alpha)^{4/3}}{(EI)^{1/3}}
```

- Données CPT : il faut une corrélation qc vers EM. Il n'en existe pas d'universelle ; la vôtre doit être choisie, documentée et paramétrable par couche.
- Surcharges : réparties, en bande, ponctuelles, avec diffusion.

### Phasage

Un calcul est une liste ordonnée de phases. Chaque phase part de l'état de la précédente (déplacements, pressions, efforts d'appui). Actions possibles :

- excavation ou remblai à une cote ;
- pose ou dépose d'un appui, mise en précontrainte d'un tirant ;
- changement des niveaux d'eau ;
- ajout ou retrait d'une surcharge ;
- bétonnage d'une dalle définitive.

### Eau

- Niveaux amont et aval par phase, en régime hydrostatique ou avec écoulement autour de l'écran.
- Plusieurs jeux de niveaux (service, exceptionnel) combinés aux ELS et ELU, selon le rapport géotechnique.

### Appuis et structure

| Appui | Données de calcul | Vérifications internes |
| --- | --- | --- |
| Buton | Section, longueur, angle, espacement, précharge | Flambement, flexion sous poids propre, effet de température (EC3) |
| Tirant | Raideur, inclinaison, longueur libre et scellée, précontrainte | Kranz, résistance du scellement, armature |
| Bracon | Section, angle, appui en pied | Flambement, appui en pied |
| Lierne | Poutre continue sur les appuis | Flexion bi-axiale, cisaillement, raidisseurs (EC3) |
| Dalle | Raideur axiale, cote | Compression, appui de la paroi |

### Vérifications géotechniques (NF P 94-282)

- Mobilisation de la butée à l'ELU.
- Équilibre vertical de l'écran : composantes verticales, tirants, résistance en pointe et frottement.
- Stabilité du massif d'ancrage (Kranz).
- Fond de fouille : soulèvement, boulance, renard.
- Stabilité générale par cercles de glissement (Bishop).
- Déplacements et efforts aux ELS, comparés à des critères que vous fixez.

Les coefficients partiels et l'approche de calcul viennent des extraits de norme fournis, jamais de la mémoire de Claude.

### Pseudo-3D

La paroi devient une plaque sur ressorts, maillée en éléments finis. On capte les effets d'angle, la répartition des butons en plan et les parois de longueur finie. Le sol reste en ressorts, comme en 2D. Ce mode n'arrive qu'une fois le 2D validé : il le prend comme référence pour une paroi très longue.

### Base matériaux

Base SQLite, alimentée par import Excel ou CSV :

- profilés : HEA, HEB, HEM, IPE, tubes ;
- palplanches : catalogues fournisseurs ;
- butons modulaires : fabricant, élément, longueur, section, résistance, poids ;
- bétons et aciers : classes et caractéristiques.

## Langage de script

Je recommande un langage basé sur YAML, avec des mots-clés en français. Il se lit comme une fiche, il s'édite dans n'importe quel éditeur, et un schéma le valide avant le calcul. Une syntaxe entièrement nouvelle demanderait d'écrire et de maintenir un analyseur : c'est une source d'erreurs inutile en vibe coding.

- **Validation.** Un schéma décrit chaque champ, son unité et ses bornes. Erreurs en français, avec le numéro de ligne.
- **Éditeur intégré.** Dans l'application : coloration, auto-complétion des mots-clés et des références de la base matériaux.
- **Unités fixes.** kN, m, kPa, degrés ; cotes en mètres, dans un repère choisi par projet.
- **Import RIDO.** Un convertisseur lit un fichier RIDO et produit le script équivalent, avec un rapport des données non reprises. Claude ne connaît pas le format RIDO de façon fiable : il faut lui donner le manuel et vos fichiers exemples.

Exemple de script (projet fictif, valeurs d'illustration) :

```yaml
projet: Fouille exemple
calcul:
  methode: coefficients_reaction
  kh: schmitt
  norme: NF P 94-282

paroi:
  type: palplanche
  profil: AZ 26-700        # référence de la base matériaux
  acier: S355GP
  tete: 0.0
  pied: -14.0

sol:
  - nom: Remblai
    toit: 0.0
    gamma: 18
    gamma_dejauge: 9
    phi: 28
    c: 0
    EM: 4000
    alpha: 0.5
  - nom: Sable dense
    toit: -3.0
    gamma: 20
    gamma_dejauge: 11
    phi: 35
    c: 0
    EM: 15000
    alpha: 0.33

eau:
  service: { amont: -2.0, aval: -2.0 }

surcharges:
  - { type: bande, q: 20, distance: 1.0, largeur: 5.0 }

appuis:
  B1: { type: buton, element: modulaire_A, cote: -1.5, espacement: 6.0, longueur: 18.0, precharge: 50 }

phases:
  - nom: Terrassement à -2,0
    excaver: -2.0
  - nom: Pose du buton B1
    poser: B1
  - nom: Terrassement final et pompage
    excaver: -6.5
    eau: { aval: -7.0 }

verifications: [butee, equilibre_vertical, fond_de_fouille, stabilite_generale, structure]
```

## Visualisations 2D et maquette 3D

Toutes les vues lisent les mêmes résultats et suivent un curseur de phase commun : on fait défiler le chantier phase par phase.

### Vues 2D (Plotly, interactives, export PNG et SVG)

- Coupe : sol, nappes, paroi, appuis et cote de fouille de la phase choisie.
- Diagrammes le long de la paroi : déplacement, moment, effort tranchant, pressions mobilisées face aux pressions limites.
- Enveloppes toutes phases et repérage de la phase dimensionnante.
- Tableau des efforts d'appui par phase, et taux de travail de chaque vérification (vert, orange, rouge).

### Maquette 3D (three.js, fichier HTML autonome)

- Fouille définie en plan par un polygone ; paroi extrudée selon son type : palplanches, pieux, profilés avec blindage, panneaux de paroi moulée.
- Butons, liernes, tirants et bracons à leur position, avec leur référence de la base matériaux.
- Couches de sol en coupe transparente, nappe, fond de fouille par phase.
- En mode pseudo-3D : paroi colorée selon le déplacement ou le moment.
- Export en un seul fichier HTML qu'on ouvre sans installation. Un export IFC pourra s'ajouter plus tard.

## Fichier CLAUDE.md

Ce fichier, à la racine du dépôt, est relu par Claude à chaque session. Copiez-le tel quel, puis complétez-le au fil du projet.

```markdown
# Projet : RetainWall, logiciel de calcul d'écrans de soutènement

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
```

## Feuille de route et prompts

Onze jalons mènent à la version complète. Chacun se termine par une porte : on ne passe au suivant que si son critère est rempli. Collez chaque prompt au début d'une nouvelle session Claude Code.

### J0 — Mise en place

Fini quand : l'application vide s'ouvre et les tests tournent.

```text
Lis CLAUDE.md. Crée la structure du dépôt décrite, un backend FastAPI
minimal, un frontend React + Vite qui affiche « RetainWall »,
pytest configuré et docs/ETAT.md. Explique-moi comment lancer l'application.
Propose d'abord ton plan.
```

### J1 — Noyau 2D, une phase

Fini quand : résultats conformes à la solution analytique et à un cas K-Réa ou RIDO simple, à 5 % près.

```text
Implémente dans backend/sout/noyau le calcul d'un écran sur ressorts
élasto-plastiques, une seule phase : poutre en éléments finis, pression
bornée entre poussée et butée limites, résolution non linéaire itérative,
kh de Schmitt. Tests : poutre sur sol élastique (solution analytique) et le
cas de référence de tests/validation/cas01. Plan d'abord, puis tests, puis code.
```

### J2 — Phasage, eau, surcharges, appuis

Fini quand : un cas buté de référence en 4 phases ou plus est reproduit à 5 % près.

```text
Étends le noyau au calcul phasé : chaque phase part de l'état précédent
(déplacements, pressions, efforts d'appui). Ajoute excavation, remblai,
niveaux d'eau amont et aval, surcharges réparties et en bande, appuis
élastiques avec précharge et précontrainte. Valide sur tests/validation/cas02.
```

### J3 — Langage de script et interface 2D

Fini quand : le cas 02 se saisit en script, se calcule et s'affiche dans le navigateur.

```text
Crée le langage de script YAML décrit dans docs/specs.md : schéma pydantic,
erreurs en français avec numéro de ligne. Dans le frontend : éditeur Monaco
avec auto-complétion, bouton Calculer, coupe 2D, diagrammes déplacement,
moment, tranchant, pressions, curseur de phase, enveloppes (Plotly).
```

### J4 — Types de paroi et base matériaux

Fini quand : les cinq types de paroi se calculent avec des éléments tirés de la base.

```text
Crée la base SQLite des matériaux (profilés, palplanches, butons modulaires,
bétons, aciers) avec import Excel depuis docs/catalogues. Ajoute les cinq
types de paroi : palplanches, paroi moulée, pieux sécants, pieux disjoints,
berlinoise, avec rigidité par mètre linéaire et fiche discontinue selon
docs/normes. Arrête-toi et demande si une règle manque.
```

### J5 — Vérifications géotechniques

Fini quand : chaque vérification est validée sur un exemple calculé à la main ou issu d'un logiciel de référence.

```text
Implémente les combinaisons ELS et ELU et les vérifications de la
NF P 94-282 à partir de docs/normes uniquement : butée mobilisée, équilibre
vertical, Kranz, fond de fouille (soulèvement, boulance, renard), stabilité
générale par Bishop. Chaque résultat affiche son taux de travail et sa source.
```

### J6 — Vérifications structurelles

Fini quand : chaque vérification correspond à un calcul manuel de référence.

```text
Implémente les vérifications EC3 (butons, bracons, liernes, profilés,
palplanches) et EC2 (paroi moulée, pieux) à partir des efforts de chaque
phase et des éléments de la base. Pour chaque appui, propose aussi le plus
léger élément de la base qui passe.
```

### J7 — Import RIDO

Fini quand : les fichiers exemples se convertissent et redonnent les résultats RIDO à 5 % près.

```text
À partir du manuel et des exemples de docs/rido, écris un convertisseur
RIDO vers notre script, avec un rapport des données non reprises. Ne devine
aucun mot-clé : liste ceux que tu ne comprends pas et demande-moi.
```

### J8 — Maquette 3D HTML

Fini quand : un projet réel s'exporte en un fichier HTML lisible sans installation.

```text
Ajoute la géométrie en plan (polygone de fouille, positions des appuis) au
script. Génère une maquette three.js autonome : paroi selon son type, appuis,
couches de sol en coupe, nappe, curseur de phase, export en un seul fichier.
```

### J9 — Pseudo-3D

Fini quand : une paroi très longue donne les résultats du 2D, et un cas d'angle reste cohérent.

```text
Implémente dans backend/sout/pseudo3d une paroi en plaque sur ressorts
élasto-plastiques, phasée, avec appuis ponctuels. Premier test : une paroi
très longue doit retrouver le calcul 2D. Puis effets d'angle. Affiche la paroi
colorée par déplacement et moment dans la maquette 3D.
```

### J10 — Validation complète et mise à disposition

Fini quand : tous les cas de validation passent et un collègue a fait un calcul seul.

```text
Lance une revue complète par un sous-agent : chaque formule contre sa source.
Écris le guide utilisateur du langage de script. Prépare le déploiement sur
notre serveur interne avec accès par identifiant.
```

## Cas de validation et points ouverts

Cinq cas de référence suffisent pour couvrir les jalons 1 à 5. Chacun comprend le fichier d'entrée et les sorties K-Réa ou RIDO : déplacements, moments, efforts d'appui, par phase.

| Cas | Contenu | Jalon |
| --- | --- | --- |
| cas01 | Palplanche autostable, sol homogène, une phase | J1 |
| cas02 | Palplanche butée un niveau, deux couches, nappe, 4 phases ou plus | J2, J3 |
| cas03 | Paroi moulée, deux lits de tirants précontraints | J2, J5 (Kranz) |
| cas04 | Berlinoise butée, fiche discontinue | J4 |
| cas05 | Pieux sécants, fond de fouille sous la nappe | J5 (soulèvement, boulance) |

Points à trancher avant ou pendant le projet :

- [ ] Corrélation qc vers EM pour les données CPT, par type de sol
- [ ] Source et format des tables de poussée et butée (Kérisel-Absi)
- [ ] Critères de déplacement admissibles aux ELS
- [ ] Tolérance de validation : 5 % à confirmer
- [ ] Vérifier que la licence RIDO autorise la lecture de son format par un autre outil
- [ ] Hébergement interne : serveur, sauvegarde, confidentialité des données de projet

Pour démarrer :

1. Créez un dossier retainwall sur votre ordinateur, avec Git en local et une sauvegarde régulière (GitHub facultatif).
2. Ajoutez le CLAUDE.md ci-dessus, et exportez ce document en Markdown dans docs/specs.md.
3. Ouvrez Claude Code sur ce dépôt et collez le prompt J0.
