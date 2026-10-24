# État d'avancement — RetainWall

## J0 — Mise en place : fait

- Dépôt Git, structure décrite dans CLAUDE.md, cahier des charges copié dans docs/specs.md.
- Backend FastAPI (`/api/sante`), pytest configuré, frontend React + Vite.
- Lancement : `lancer_backend.ps1` puis `lancer_frontend.ps1`, ouvrir http://localhost:5173.
- Tests : `lancer_tests.ps1`.

## J1 — Noyau 2D, une phase : fait (porte partiellement ouverte)

- `sout/sol` : couches et σ'v hydrostatique, Ka/Kp de Coulomb (Rankine si δ = 0),
  K0 de Jaky, cohésion par les états correspondants, kh de Schmitt, corrélation CPT
  paramétrable, surcharges (répartie, bande de Boussinesq, linéique de Flamant),
  branchement des tables de Kérisel-Absi (CSV à fournir).
- `sout/noyau` : poutre d'Euler-Bernoulli en éléments finis, ressorts élasto-plastiques
  avec mémoire, solveur de Newton semi-lisse avec recherche linéaire exacte sur
  l'énergie (convexe), détection de rupture.
- Tests (verts) : console analytique, Hetényi (poutre infinie sur Winkler, < 1 %),
  charge uniforme sur Winkler, équilibre global des forces et des moments, convergence
  du maillage, hauteur critique d'un écran autostable rigide face à l'équilibre limite
  rigide-plastique (écart < 2 %).
- **Porte non franchie** : comparaison au cas K-Réa/RIDO cas01, fichiers absents.

## J2 — Phasage, eau, surcharges, appuis : fait (porte ouverte)

- Moteur de phases (`sout/noyau/phasage.py`) : excavation, remblai amont/aval, pose et
  dépose d'appuis, précharge/précontrainte à la pose, niveaux d'eau amont/aval
  (hydrostatique), ajout/retrait de surcharges ; le bétonnage d'une dalle = pose d'un
  appui de type dalle.
- Hypothèse documentée : une variation Δσ'v décale la pression de référence de
  Kd·Δσ'v (Kd = coefficient de décharge, K0 par défaut), à confronter à K-Réa.
- `sout/appuis/raideurs.py` : raideurs de butons (L/2 si symétrique), tirants, bracons,
  dalles ; conversions effort horizontal/axial.
- Tests (verts) : équilibre global des forces avec eau et appuis à chaque phase, appui
  très raide, précontrainte retrouvée, phase vide, nappe symétrique, appui unilatéral
  qui décolle, erreurs de données, rupture détectée.
- **Reste à faire** : écoulement autour de l'écran (seul le régime hydrostatique est
  traité) ; **porte non franchie** : cas02 K-Réa/RIDO absent.

## J3 — Langage de script et interface 2D : fait (porte partiellement ouverte)

- `sout/script` : schéma pydantic (mots-clés français, unités et bornes en description),
  lecteur ruamel.yaml avec numéro de ligne, erreurs traduites en français, contrôles de
  cohérence (appuis inconnus, dépose avant pose, Schmitt sans EM, etc.), conversion vers
  le modèle de calcul.
- API : `/api/calcul`, `/api/valider`, `/api/schema`, `/api/exemples`.
- Interface : éditeur Monaco local (sans CDN) avec coloration YAML, auto-complétion
  guidée par le schéma (mots-clés, valeurs possibles, références de la base), aide au
  survol, erreurs soulignées et cliquables, validation en direct ; bouton Calculer
  (Ctrl+Entrée), curseur de phase commun, onglets Synthèse, Coupe, Diagrammes
  (y, M, V, pressions face aux limites, eau), Enveloppes et phase dimensionnante,
  tableau des efforts d'appui ; export PNG/SVG des graphiques ; ouvrir/enregistrer.
- Vérifié dans un navigateur (Chrome sans affichage) : calcul et affichage de l'exemple.
- **Porte non franchie** : le cas 02 de référence n'est pas fourni ; l'exemple du cahier
  des charges est saisi et calculé à sa place (`exemples/fouille_exemple_EI.yaml`).

## J4 — Types de paroi et base matériaux : fait (porte partiellement ouverte)

- `sout/materiaux` : base SQLite (profilés, palplanches, butons modulaires, armatures,
  aciers, bétons), import CSV/Excel (`python -m sout.materiaux.importer fichier.xlsx`
  ou bouton « Base matériaux » de l'interface), modèles d'en-têtes dans
  docs/catalogues/modele_*.csv. Propriétés des profilés en I et des tubes calculées à
  partir des dimensions (contrôlé : HEB 300 conforme au catalogue).
- **Jeu DEMO** livré pour faire tourner l'application : valeurs d'illustration (dont un
  profil U et des butons fictifs), signalées dans l'interface ; à remplacer.
- `sout/parois` : palplanches (β_D des profils en U exigé), paroi moulée (rapport
  EI fissuré choisi), pieux sécants (seuls les pieux armés comptent : hypothèse à
  confirmer), pieux disjoints, berlinoise ; fiches discontinues avec largeur de réaction
  réduite sous le fond (script ou docs/normes, sinon calcul refusé).
- `sout/normes.py` + modèles `docs/normes/{nf_p94_282,ec3,ec2}.yaml` (tout à null,
  TODO-NORME).
- Tests (verts) : les cinq types se calculent avec des éléments de la base, rigidités
  vérifiées à la main, refus sans largeur de fiche ou sans β_D, import CSV + Excel.
- **Porte non franchie** : cas04 (berlinoise) de référence absent ; règles de largeur de
  fiche discontinue de la NF P 94-282 non fournies.

## J5 — Vérifications géotechniques : fait (porte ouverte : coefficients partiels non fournis)

- `sout/verifs.py` : résultat commun (taux, état, détail, source, valeurs manquantes) ;
  toute valeur de norme absente rend la vérification « non vérifiable » et affiche la
  valeur caractéristique (sans coefficient partiel).
- `sout/verifs_geo` : butée mobilisée, équilibre vertical (mobilisation de δp et
  portance, **méthode simplifiée** à confronter à la norme), Kranz (équilibre du massif
  d'ancrage), fond de fouille (soulèvement UPL, boulance HYD, renard par **longueur de
  cheminement**), stabilité générale par Bishop simplifiée (recherche de cercles sous le
  pied), déplacements ELS (critères du bloc `criteres`), scellement des tirants.
- `sout/verifications.py` : calcul de chaque jeu d'eau, vérifications sur le cas le plus
  défavorable ; les niveaux d'eau des phases s'appliquent à tous les jeux.
- Tests (verts) : Kranz sur un cas manuel (T_max = γHL·tan φ), Bishop φ = 0 face à un
  équilibre des moments indépendant (< 1 %), fond de fouille calculé à la main,
  mécanique des coefficients avec des valeurs de test fictives.
- **Limites** : mêmes coefficients pour les combinaisons fondamentales et accidentelles
  (à étendre selon la norme) ; pas de calcul d'écoulement ; tirants et écran négligés
  dans Bishop (sécuritaire).

## J6 — Vérifications structurelles : fait (porte ouverte : coefficients EC2/EC3 non fournis)

- `sout/verifs_struct/ec3.py` : Euler, χ (EN 1993-1-1 § 6.3.1.2, contrôlé sur les
  valeurs publiées des courbes a, b, c), N_b,Rd, M_c,Rd, V_pl,Rd, amplification 1/(1 − N/Ncr).
- `sout/verifs_struct/ec2.py` : flexion rectangulaire (diagramme rectangulaire), section
  circulaire par intégration numérique, VRd,c.
- `sout/verifs_struct/elements.py` : butons/bracons (flambement + poids propre +
  température, résistance fabricant), tirants (armature), dalles (compression), liernes
  (flexion bi-axiale + cisaillement ; raidisseurs signalés « non automatisé »),
  palplanches (β_B, corrosion au prorata de l'épaisseur, interaction V-M), profilés et
  blindage de berlinoise, paroi moulée (As requis, M_Rd si ferraillage fourni, VRd,c),
  pieux (As requis par section circulaire) ; élément le plus léger de la base qui passe.
- Efforts de calcul = effets caractéristiques × gamma_effets de la combinaison (approche
  à confirmer selon la NF P 94-282 fournie).
- **Hypothèses à confronter à la norme** : interaction N-M linéaire, liernes M = 0,1·q·e²,
  profilés de classe 1-2 supposés, une âme par largeur de palplanche, tranchant des pieux
  non automatisé, profilés candidats en S355 pour la suggestion.

## J7 — Import RIDO : architecture faite, porte non franchie

- `sout/script/rido.py` : convertisseur piloté par la table `docs/rido/correspondance.yaml`
  (mot-clé -> bloc du script, colonnes, facteurs d'unité, lignes suivantes), rapport des
  lignes non reprises ; API `/api/rido` et bouton « Importer RIDO ».
- **La table est livrée vide** : aucun mot-clé RIDO n'est deviné. À remplir après
  lecture du manuel RIDO (à fournir dans docs/rido), puis tester sur les exemples
  (test `test_exemples_rido_fournis`, ignoré pour l'instant).
- Question ouverte : licence RIDO pour la lecture de son format.

## J8 — Maquette 3D HTML : fait

- Script : bloc `plan` (polygone de fouille, positions des appuis ; à défaut, placement
  automatique à l'espacement de chaque appui ; sans plan, rectangle 20 × 12 m signalé).
- `sout/maquette3d` : fichier HTML unique (three.js r169 intégré, licence MIT incluse,
  aucune ressource externe) : paroi selon son type (palplanches ondulées, panneaux de
  paroi moulée, pieux, profilés et blindage), butons/tirants/bracons/dalles/liernes avec
  leur référence, couches de sol transparentes, nappes, fond de fouille par phase,
  curseur de phase, couleur de paroi selon le déplacement ou le moment.
- API `/api/maquette`, onglet « Maquette 3D » (aperçu + export du fichier).
- Vérifié : le fichier exporté s'ouvre directement depuis le disque (file://) dans Chrome,
  sans erreur JavaScript.

## J9 — Pseudo-3D : fait

- `sout/pseudo3d` : paroi en plaque orthotrope par analogie de grillage (Hambly) —
  poutres verticales EI/m (comme le 2D), poutres horizontales `rigidite_horizontale`,
  torsion √(Ds·Dz) ; sol en ressorts avec la même loi et le même phasage que le 2D
  (briques communes extraites de `MoteurPhases`), appuis ponctuels à leur espacement,
  bords libres/appuyés/encastrés, angle de fouille (w = 0 sur la ligne d'angle).
- Script : `calcul.mode: pseudo3d` + bloc `pseudo3d` ; onglet « Pseudo-3D » (cartes du
  déplacement et du moment vertical, comparaison au 2D) ; maquette 3D colorée par le champ.
- Tests (verts) : flexion cylindrique identique au 2D (1e-6), paroi de 48 m avec appuis
  ponctuels à moins de 5 % du 2D au centre, angle droit symétrique et cohérent (w nul à
  l'angle, proche du 2D loin de l'angle), bords encastrés.
- **Limites** : rigidité horizontale isotrope par défaut (avertissement affiché), parois
  indéformables dans leur plan à l'angle, appuis répartis régulièrement (positions du
  plan non encore reprises dans le pseudo-3D).

## J10 — Revue croisée et mise à disposition : fait (porte non franchie)

### Mise à disposition
- Guide utilisateur `docs/guide_script.md` (référence des mots-clés générée depuis le
  schéma, testée pour rester à jour) ; README ; notice `docs/INSTALLATION.md`.
- Lanceur `Lancer RetainWall.bat` (double-clic, raccourci sur le Bureau) : installe ce qui
  manque, compile l'interface si besoin, sert tout sur http://localhost:8000.
- Déploiement : accès par identifiant (HTTP Basic, mots de passe PBKDF2 hachés,
  `RETAINWALL_AUTH=1`), interface servie par FastAPI, `Dockerfile` (non testé : Docker
  absent du poste), `lancer_production.ps1`. Mode production testé de bout en bout.

### Revue croisée par un sous-agent indépendant (chaque formule contre sa source)
Conformes et contrôlés numériquement : Coulomb/Rankine/Jaky, Schmitt, σ'v, Boussinesq,
Flamant, poutre EF (Hetényi < 0,1 %), conventions de signe, loi des ressorts, solveur,
raideurs d'appuis, EI des cinq parois, sections (HEB/IPE < 0,1 %), EC3 et EC2 (modèle à
fibres indépendant 0,02 %), statique de Kranz, Bishop, grillage (Navier 0,7 %).
Aucun coefficient partiel ni facteur normatif écrit en dur.

Écarts corrigés (avec test de non-régression) :
| Gravité | Constat | Correction |
| --- | --- | --- |
| Critique | Kp de Coulomb sans garde de domaine (valeurs absurdes au-delà du pôle) | refus hors domaine |
| Critique | Équilibre vertical : une résultante montante pouvait être masquée par une autre phase | contrôle « mobilisation de δp » sur toutes les phases, séparé de la portance |
| Majeur | Butée de Coulomb avec δp/φ > 1/3 seulement signalée | calcul refusé (Kérisel-Absi ou δp ≤ φ/3) |
| Majeur | Pas de classification des sections (classe 4 calculée sur section brute) | classe 4 refusée (limites lues dans ec3.yaml) ; classe des palplanches exigée |
| Majeur | Poids de l'écran sans déjaugeage | poids déjaugé sous la nappe la plus haute |
| Majeur | Écoulement non modélisé sans avertissement | avertissement à l'exécution |
| Mineur à majeur | Recherche de Bishop trop grossière (+2 %) | grille élargie + affinage local |
| Mineur | Frottement amont toujours vers le bas | sens selon compression/décompression du sol |
| Mineur | Liernes M = 0,1·q·e² non sécuritaire pour 2 travées | M = q·e²/8, V = 0,625·q·e |
| Mineur | Appuis pseudo-3D redistribués (raideur totale sous-estimée) | espacement exact |
| Mineur | Dalle divisée à tort par l'espacement ; tirant sans longueur : erreur brute | corrigés |
| Mineur | Kranz : φ au milieu de BA | φ le plus faible traversé |
| Mineur | Kérisel-Absi interpolé linéairement | interpolation en ln K |
| Mineur | Couche sous la pointe mal choisie ; remblai au-dessus de la 1re couche silencieux | corrigé ; avertissement |
| Mineur | S355 implicite (liernes, suggestions), taux 2,0 arbitraire, As « requis » si μ > μlim | supprimés / état « non vérifié » / As non défini |

Écarts documentés, non corrigés (à trancher avec la norme ou les cas de référence) :
- Équilibre vertical : Qs cumulé aux composantes p·tan δ (double comptage possible),
  qb = k_p·pl brut au lieu de ple* (NF P 94-262), qs proportionnel à pl : signalés dans
  le détail du résultat.
- Fond de fouille par longueur de cheminement (Bligh) : peut sous-estimer le gradient de
  sortie d'une fouille étroite ; un calcul d'écoulement reste à développer.
- Décalage Kd·Δσ'v, définition exacte de Bm/Bt, surcharges par Δσv sans effet miroir,
  états correspondants avec δ ≠ 0 : hypothèses à valider contre K-Réa.
- Eau nette sur toute la largeur pour les fiches discontinues ; même rapport de largeur
  amont et aval sous le fond ; pieux sécants : seuls les pieux armés comptent.
- Kranz : lits de tirants étudiés séparément, surcharges initiales seules.
- Bishop : cercle écarté si une tranche a mα ≤ 0,05 ; tirants et écran négligés.
- Pseudo-3D : angle traité comme rigide (w = 0), plaque isotrope par défaut.
- Valeurs par défaut documentées : γw = 10 kN/m³ (modifiable), largeur de fouille 2H
  dans Bishop (signalée dans le résultat), 7 850 kg/m³ pour estimer une masse absente du
  catalogue.

## Synthèse : ce qui manque pour un usage en projet

1. **Cas de référence K-Réa/RIDO** (cas01 à cas05) : aucune porte « fini quand » exigeant
   une comparaison n'est franchie (J1 partiel, J2, J3, J4, J5, J7, J10).
2. **Extraits de normes** dans docs/normes (tous les coefficients sont à null) : les
   vérifications affichent « non vérifiable » avec la liste des valeurs manquantes.
3. **Catalogues fournisseurs** pour remplacer le jeu DEMO ; **manuel RIDO** pour l'import.
4. Points ouverts du cahier des charges : corrélation qc → EM, critères de déplacement,
   tolérance de 5 %, licence RIDO, hébergement.

Tests : 95 réussis, 6 ignorés (cas de validation et exemples RIDO absents).

## Interface professionnelle (après J10) : fait

- Structure plein écran : barre de titre (projet, pastille d'état, Recalculer Ctrl+↵,
  Exporter, thème), navigation du modèle (arborescence), zone à onglets, inspecteur de la
  phase active (chiffres clés, appuis, alertes), frise des phases (lecture, flèches).
- Formulaires de saisie synchronisés dans les deux sens avec le script YAML (le script
  reste la référence ; une valeur modifiée ne change que ses caractères dans le texte).
- Coupe & diagrammes : axes communs et fixes, réticule synchronisé avec valeurs à la cote,
  extrêmes annotés, enveloppes, zoom vertical Maj+molette, export PNG.
- Maquette 3D : vues prédéfinies, plan de coupe, sélection d'un appui vers l'inspecteur,
  thème et phase pilotés depuis l'application.
- Efforts (carte de chaleur, tri), Vérifications groupées par famille avec barre de taux
  et mention « À confirmer », note de synthèse imprimable, thème clair/sombre, écrans
  1024 px (inspecteur en tiroir) et 768 px (navigation en tiroir), sans défilement horizontal.
- Vérifié (Chrome piloté) : saisie φ → ligne du script seule modifiée ; script → formulaire ;
  pied de paroi raccourci → calcul interrompu signalé en rouge et dans les alertes.
  Le statut « Non vérifié » de la butée exige les coefficients de docs/normes.


## Module hydraulique : fait (porte ouverte : coefficients non fournis)

- `sout/hydraulique` : solveur d'écoulement 2D en différences finies (volumes finis,
  perméabilités anisotropes, écran imperméable, substratum, bouchon), régime simplifié
  (Bligh/Lane), hydrostatique conservé pour la non-régression ; pressions d'eau et
  contraintes effectives de l'écran corrigées par l'écoulement (poids du bouchon et lest
  comptés dans la contrainte totale).
- Bouchons injecté, jet-grouting, radier lesté, substratum naturel, actifs à partir d'une phase.
- Vérifications : boulance (pressions et gradient), renard (Terzaghi, Lane, gradient critique),
  soulèvement du bouchon avec épaisseur minimale, gradient à travers le bouchon, débit,
  stabilité du fond en argile (Bjerrum-Eide) ; coefficients dans docs/normes/hydraulique.yaml
  (tout à null) et nf_p94_282.yaml.
- Tests analytiques (verts) : écoulement 1D, couches en série, Lane, Terzaghi, UPL, réseau de
  référence (symétrie exacte, gradient de sortie de Harr H/(π·d) à 1 %), non-régression
  hydrostatique, réduction de la butée par l'écoulement, effet d'un bouchon.
- Affichage : réseau d'écoulement et flèches de gradient sur la coupe, tuiles gradient/débit
  dans l'inspecteur, 3D : surface piézométrique, bouchon, équipotentielles sur le plan de
  coupe, paroi colorée par pression d'eau, flèches de gradient (vert → rouge).
- Limites : écoulement 2D extrudé (pas d'effet d'angle), nappe amont maintenue, fouille
  symétrique, cellules uniformes (pas raffiné près du pied).


## Module assemblages : fait (porte ouverte : coefficients EN 1993-1-8 non fournis)

- `sout/assemblages` : géométrie paramétrique commune 2D/3D (solides repérés, soudures, cotes,
  efforts, vues), 14 types (8 butons, 2 liernes, 2 tirants, 2 bracons) avec nomenclature et
  vérifications EN 1993-1-8 (boulons traction/cisaillement/pression diamétrale/poinçonnement/
  interaction, soudures d'angle méthode simplifiée, axes), EN 1993-1-5 (âme sous charge
  transversale, simplifié), EN 1992-1-1 § 6.7 (compression localisée), chevilles (ETE).
- Interface : onglet Assemblages (vignettes des 14 types, formulaire, plan d'exécution SVG avec
  coupes hachurées, symboles ISO 2553, repères, cotes liées aux paramètres, surlignage par
  survol et par vérification, détail 3D), enregistrement dans le script, revérification avec
  les efforts de l'appui à chaque calcul. API `/api/assemblages/*`.
- Tests (verts) : 14 schémas générés, réaction aux paramètres, vérifications de chaque type,
  formules contrôlées à la main (Ft,Rd, Fv,Rd, Fb,Rd, Fw,Rd, axe, compression localisée).
- Choix et hypothèses (à confirmer) : lierne à âme horizontale (ailes parallèles à la paroi),
  longueur efficace d'âme simplifiée, interaction N-M linéaire, part des nervures 50 %,
  section nette des éclisses sans 0,9·Anet·fu, pression diamétrale des boulons de rive
  seulement, buton d'angle représenté par un tube d'axe x (dessin simplifié).
- Coefficients : `docs/normes/ec3_assemblages.yaml` (tout à null, classes de boulons notées 8_8).


## Valeurs normatives renseignées (22 octobre 2026)

À la demande de l'utilisateur (aucun extrait de norme disponible), Claude a renseigné les
119 valeurs de `docs/normes/*.yaml` **de mémoire**, chacune avec l'article d'origine et le
statut « à confirmer » ; les valeurs de projet (ΔT, bridage, gradient admissible, fck, fyk…)
sont signalées « PROJET ». Les modèles vides sont conservés dans `docs/normes/modeles/` (les
tests les utilisent). **Toutes ces valeurs restent à contrôler sur le texte des normes par un
ingénieur avant usage** ; la règle 1 du CLAUDE.md (pas de valeur inventée) est levée pour ce
remplissage sur instruction explicite de l'utilisateur.


## Explorateur de phases avec branches (façon Plaxis) : fait

- Script : `depuis` sur une phase (nom d'une phase antérieure ou « État initial ») ; contrôles
  (phase connue et antérieure, nom unique, appuis posés suivis par branche).
- Moteur : instantané de l'état après chaque phase (chantier, appuis posés, déplacements,
  mémoire des ressorts) ; une phase repart de l'instantané de sa phase de départ ; une phase
  dont le départ n'est pas calculé est marquée « non calculée » sans bloquer les autres branches.
  Résultats : `parent`, `enfants`, `depuis` par phase ; enveloppes et vérifications sur toutes
  les branches ; pseudo-3D sur la branche de la dernière phase.
- Interface : explorateur (voies et lignes de branchement, insertion après une phase, création
  de variante, suppression, formulaire de la phase sélectionnée), frise et flèches qui suivent
  la branche, inspecteur indiquant la phase de départ.
- Tests : variante identique à un calcul linéaire tronqué, branche depuis une phase rompue.


## Vue 3D persistante, calques, résultats en 3D, coupes, surcharges et terrain (22 octobre 2026)

Prompt « Vue 3D persistante » intégré en 11 étapes, chacune testée et commitée. Le prompt visait une
version mono-fichier (`engine.js`) : il a été adapté au dépôt (moteur Python, interface React), voir
le plan de session. Le cas exemple cité par le prompt (13,8 mm, B2 = 540 kN/m, tube 711×16) n'existe
pas ici : la non-régression porte sur `exemples/fouille_exemple.yaml` (valeurs figées dans
`tests/unitaires/test_vue3d_donnees.py`).

### Fait
- **Scène persistante** (`frontend/src/vue3d/scene.ts`, `elements.ts`) : arbre fixe à identifiants
  stables, objets à clé de géométrie (un recalcul ne reconstruit que ce qui change, ressources
  libérées), changement de phase sans création d'objet (blocs de sol par échelle, appuis instanciés),
  caméra / plan de coupe / sélection conservés, rendu à la demande, diagnostic `Ctrl+Maj+D`.
  Le calcul renvoie la géométrie de la maquette (`resultats.maquette`) ; plus d'iframe.
- **Calques** (`calques.ts`, `PanneauCalques.tsx`, touche `L`) : visibilité, opacité, verrou, plan de
  coupe par calque, isolation réversible, recherche, préréglages livrés et personnels (stockage local,
  JSON), réglages par calque de résultats.
- **Résultats paroi** (`resultats.ts`, `legendes.ts`) : déformée amplifiée (auto = 2 m), couleurs
  (déplacement, moment, tranchant, taux de travail), ailettes (moment, tranchant, pressions avec
  limites), enveloppes, étiquettes d'extrêmes, légendes empilées ; champ pseudo-3D utilisé s'il existe.
- **Appuis** (`appuis.ts`, `resultatsAppuis.ts`) : efforts service / ELU (× gamma_effets), flèches des
  butons et liernes calculées par `verifs_struct/elements.py` (`fleche_barre`, `fleche_lierne`) et
  exposées par phase, taux de travail (appuis, liernes, assemblages en cubes).
- **Coupes de calcul** (`sout/script/coupes.py`, bloc `coupes`, `plan.cotes`) : héritage du script
  principal, calcul par coupe en parallèle avec cache serveur par empreinte, phasage projet et
  correspondance des phases, synthèse projet (pire coupe), plans nommés, zones d'application, tronçon
  orphelin hachuré, diagrammes dans le plan de coupe, touches `1`–`9`. Exemple `fouille_coupes.yaml`.
- **Coupe locale** (`sourceResultats.ts`, outil « Couper ici », touche `C`) : source abstraite
  (2D : coupe du tronçon ; pseudo-3D : champ de la plaque), épinglage → entrée YAML.
- **Panneau de résultats** (`PanneauResultats.tsx`, touche `R`, `navigation.ts`) : Courbes / Efforts /
  Vérifications filtrés sur l'objet cliqué, fil d'Ariane, points d'attention, marqueurs d'alerte,
  curseur de cote lié aux courbes dans les deux sens, plein écran avec retour, ancre d'URL
  `#c1-p8-s_appui:B2-l_structure`.
- **Surcharges étendues** (`sout/sol/terrain.py`, interface unique dans `MoteurPhases._sigma_v`) :
  uniforme, bande (longueur finie, côtés), rectangulaire (Newmark), ponctuelle (Boussinesq), linéaire
  (intégration), profondeur, phases d'application ; `coupe_calcul` injecté par coupe ; maquette
  (volumes, bâtiment, grue, flèches, pression induite), outil « Ajouter une surcharge ».
- **Terrain** : risbermes, talus, gradins côté fouille (surcharge équivalente par bandes de poids,
  ou fond équivalent sur cote choisie), terrain en pente côté terre (Coulomb avec β, `ka_coulomb_talus`,
  ou surcharge équivalente), remblai à une phase (couche ajoutée), action `terrasser_risberme` ;
  butée limite sans l'objet (`pp_sans_terrain`) sur la coupe 2D et dans le panneau ; outils « Ajouter
  une risberme » et « Mesurer ».
- **Divers** : info-bulle, comparaison en fantôme d'une phase, lecture animée (visuelle, désactivée
  si `prefers-reduced-motion`), exports PNG avec légendes (×1, ×2) et glTF.
- Tests : pytest 175 (+6 ignorés), vitest 60 (`lancer_tests.ps1` lance les deux).

### Limites et reste à faire
- Export HTML autonome : toujours produit par `sout/maquette3d/gabarit.html` (ancienne vue), non
  unifié avec la nouvelle scène.
- Comparaison : superposition fantôme seulement (pas de deux vues côte à côte) ; coupes : pas de
  superposition de courbes de deux coupes.
- Objets de terrain : volumes extrudés sur toute la longueur des côtés concernés ; coupe unique
  rapportée au milieu du côté le plus long pour les surcharges en plan (signalé).
- La maquette de chantier (fond, nappes, appuis) suit la coupe active ; seuls les résultats de paroi
  et les diagrammes sont lus par tronçon.

### Questions ouvertes / TODO-NORME
- Méthode du coin de rupture sous la risberme : publication à fournir (refusée au calcul).
- Convois routiers (Bc, Bt) : charges et empreintes à fournir (type accepté, calcul refusé).
- Méthode normative de diffusion des surcharges (NF P 94-282) : seule la diffusion élastique est
  disponible et affichée. Tables de Kérisel-Absi avec talus : non fournies (Coulomb avec β seulement).
- Si vous disposez du `cas.yaml` d'origine du prompt, l'ajouter dans `exemples/` pour en faire la
  référence de non-régression.

## Revue du moteur de calcul (déplacements, moments, efforts) : fait

Contrôles menés (scripts de diagnostic, non versionnés) : effort tranchant égal à la résultante
des forces nodales et moment égal à son intégrale (écarts < 1e-6), équilibre global avec eau et
appuis à chaque phase, Hetényi (flèche à 3e-7, moment en O(h²)), moment nul au-dessus du terrain,
convergence du maillage (pas 0,5 à 0,02 m : y et M stables à 0,3 %), scénarios : excavation
progressive, excavation puis remblai, buton précontraint, nappe amont seule, tête hors sol,
surcharge ajoutée puis retirée, sol cohérent, écran très rigide, dépose d'appui, fouille sous
l'eau, appui en tête, EI par segments, excavation au toit d'une couche, buton unilatéral.

Deux défauts corrigés (tests de non-régression ajoutés) :
| Gravité | Constat | Correction |
| --- | --- | --- |
| Majeur | Précharge/précontrainte : effort = F0 + k·(y − y_avant_pose) ; le recul de l'écran sous la mise en charge consommait aussitôt une part de F0 (buton précontraint à 100 kN/m : 36 kN/m à la fin de sa phase de pose ; exemple livré : 8,3 → 3,9 kN/m) | Mise en charge au vérin résolue comme sous-étape au début de la phase de pose (force F0 seule, état du sol de la phase précédente), puis appui bloqué : ressort dont le point zéro est le déplacement après mise en charge. L'effort vaut exactement F0 à la fin d'une phase de pose seule (convention K-Réa) ; une excavation dans la même phase charge ensuite le ressort. Même règle en pseudo-3D. |
| Mineur | Effort tranchant non nul au pied libre (−4,5 kN au pas de 0,1 m, −17 kN au pas de 0,5 m) : charge de la demi-maille d'extrémité concentrée au nœud | Diagrammes M et V calculés par la statique avec les charges réparties sur leurs demi-mailles (`poutre.efforts_par_statique`) : V = 0 aux extrémités libres, M continu, sauts de V au droit des appuis. Le système résolu (charges nodales) est inchangé ; M au pied porte un résidu de l'ordre de 0,05 % du moment maximal. |

Test modifié en conséquence : `test_precontrainte_retrouvee_dans_l_effort` (le point zéro de
l'appui est désormais le déplacement à la fin de la phase de pose, et l'effort y vaut F0).

Sans écart constaté (comportements vérifiés, hypothèses inchangées) : décalage Kd·Δσ'v à
l'excavation, au remblai et au changement de nappe ; remblai au repos contre l'écran déplacé ;
décharge élastique après retrait de surcharge (asymétrie charge/décharge propre au modèle
élasto-plastique) ; appui unilatéral qui décolle puis reprend.

Reste à faire : comparaison aux cas de référence K-Réa/RIDO (toujours absents) ; charges
réparties cohérentes dans le système résolu (termes de rotation) si un maillage grossier doit être
utilisé ; coefficient de recharge distinct de Kd (K-Réa : kr) si la pratique l'exige.


## Bêta-test 3D, RDM, STR et rafale d'exemples élémentaires (23 octobre 2026)

Plan en huit lots (0, A, B, C1, C2, D, C3, E, F), un commit par étape, tous validés par `lancer_tests.ps1`.

### Fait
- **Travail du 22/10 commité** (mise en charge au vérin, M/V par la statique) ; jeux figés régénérés et expliqués
  (exemple : y_max 17,76 → 17,65 mm ; berlinoise : le tirant porte F0 après la pose, blindage 2,48 → 2,61).
- **Preuve que le pseudo-3D est une vraie plaque** : tests de référence sans sol contre Timoshenko &
  Woinowsky-Krieger (Navier carrée et rectangulaire à 1 % / 2 %, charge ponctuelle, plaque orthotrope de
  Huber, plaque encastrée 0,00126·q·a⁴/D, flexion cylindrique exacte à 1e-9, plaque tournée de 90°,
  équilibre 1e-10, convergence en O(h²)) ; assemblage vectorisé ; effort tranchant 3D par la statique de
  chaque ligne verticale avec forces de transfert de la plaque (V nul aux extrémités libres, saut = effort/ds
  au droit d'un appui) ; torsion Mzs, réactions des bords et des angles, bilan ΣF, ΣM à chaque phase ;
  bords appuyés bloquant la rotation tangente ; appariement 2D/3D par nom de phase ; **`largeur_appui`** :
  sans elle, Ms et V au droit d'un buton divergent avec le maillage (146 → 265 → 503 kN/m), avec elle ils
  convergent (3 % et 1 %) ; intégrale de Ms sur la hauteur = poutre continue (−R·e/12, +R·e/24, R·e/8 à 0,3 %).
- **Rigidité horizontale par type de paroi** (`parois/construction.rigidite_horizontale`) : paroi moulée 1,
  palplanches / pieux / berlinoise 0, EI imposé isotrope ; clés `rapport_rigidite_horizontale`,
  `rigidite_horizontale` (≥ 0), `torsion`, `paroi.longueur_panneau` et `origine_panneaux` (joints sans
  moment ni torsion horizontaux, panneaux périodiques à 1e-6). **Ds = 0 ⇔ coupes 2D assemblées** : chaque
  ligne est exactement l'écran 2D (lignes sans appui = 2D sans appui, ligne d'appui = 2D avec k·e/ds,
  identité 1e-6) ; Ds = Dz : la plaque redistribue (déplacement quasi uniforme, effort par buton ≈ H_2D·e).
- **Liernes** : poutre horizontale continue E·Iy dans le grillage tant que l'appui est posé (matrice par jeu
  de liernes), moments et tranchants restitués ; lierne rigide ⇔ 2D à appui réparti ; lierne raide en poutre
  continue sur les butons (−R·e/12, +R·e/24 à 10 %).
- **Fouille fermée (« double écran »)** : `sout/plan/geometrie.py` partagé (coupes, maquette, pseudo-3D) ;
  grillage périodique sur tout le contour (un seul nœud à l'angle d'origine, quatre angles monolithiques à
  w = 0) ; butons = liens entre les deux parois en vis-à-vis (`solveur.Appuis.noeud2`, raideur EA/L sur la
  longueur entière, action = réaction, précharge aux deux parois) ; positions du bloc `plan.appuis` ou
  placement automatique ; dalle = liens de chaque nœud à son vis-à-vis ; déclenché quand
  `pseudo3d.longueur` est absent. Tests : liens ≡ ressorts L/2 si tout est symétrique (1e-7), solution
  symétrique, milieu d'un côté de 60 m à 5 % du 2D. Exemple `exemples/pseudo3d_fouille_fermee.yaml`.
- **Surcharges localisées en plan** : état du sol calculé ligne par ligne (une coupe de calcul par nœud du
  contour) ; grue de 3 000 kN derrière une paroi : +13 % sur le buton au droit, paroi d'en face repoussée
  vers sa terre (5 × plus qu'avec des ressorts L/2).
- **STR branchées sur le 3D** : pseudo-3D calculé une fois dans `verifications.executer` ; seconde série
  « [pseudo-3D] » (Mz, V, Ms de la plaque ; appuis réels N = effort/cos θ ; liernes avec leurs moments 3D) ;
  flexion horizontale Ms (paroi moulée : As horizontal requis, M_Rd si `armatures_horizontales`,
  `enrobage_horizontal`) ; corrections : M_c,Rd des butons avec γM0, garde fck absent, libellé W pl/él.
  **Contrôles manuels chiffrés** : buton modulaire_A 0,5756, tirant 0,6037, dalle 0,045, lierne 0,9696 /
  0,8297 (3D), palplanche avec corrosion et interaction V-M 0,5996, berlinoise 0,6105, blindage 1,372,
  paroi moulée 0,9164 (As requis 18,3 cm²/m), VRd,c 1,296 / 1,088, flexion horizontale 0,8604.
- **RDM type RDM7** : `noyau/rdm.py` (charges cohérentes, couples, encastrements, ressorts, Winkler, M/V par
  la statique, contrôles ΣF, ΣM, V = dM/dz, q = dV/dz) ; 18 cas de poutres exacts à 1e-9 (Hetényi 1 %) ;
  erreur des charges nodales du moteur mesurée à 9e-5 (aucun changement nécessaire).
- **Rapport pour le manager** : `python -m outils.rafale_elementaire` → `docs/validation/rafale_elementaire.md`,
  `.html` (autonome, SVG intégrés) et `figures/*.png` : 45 cas conformes sur 45 (poutres 18, plaque 8,
  écran 2D 12 dont butée simple à 0,6 % et balayages kh / EI / φ / γ / H / raideur / précharge / nappe,
  pseudo-3D 7). Limites du modèle et table de correspondance avec RDM7 en fin de rapport.
- Solveur : échelle du bruit d'arrondi = max|K_ii·u_i| (la pénalité des bords rendait la tolérance 1e4 fois
  trop lâche en 3D) ; résultats 2D inchangés au sixième chiffre.

### Testé
pytest : 281 réussis, 6 ignorés (cas K-Réa/RIDO absents) ; vitest : 61 ; rafale : 45/45.

### Reste à faire
- Variantes de sol ou de phasage par côté d'une fouille fermée (un seul modèle pour tous les côtés) ;
  écoulement, jeux d'eau secondaires et branches `depuis` en pseudo-3D.
- Option d'angle articulé (palplanches) ; terme de Poisson (ν = 0 dans le grillage).
- Interface : moments des liernes 3D et réactions d'angle non affichés dans l'onglet Pseudo-3D ; export
  HTML de la maquette toujours sur l'ancienne vue.
- Si vous disposez de RDM7 : un cas de console permettrait de figer la table des signes sur un résultat réel.

### TODO-NORME / TODO-SOURCE
- Plaque ondulée de Seydel (rigidité horizontale des palplanches) : formule non activée (serrures libres).
- EN 1993-5 : résistance horizontale des serrures, Av « une âme par largeur », section efficace de classe 4.
- EN 1993-1-1 § 6.3.3 (k_yy) : interaction N-M des butons simplifiée ; EN 1992-1-1 § 9.6.3 : As horizontal
  minimal non contrôlé ; tranchant des pieux non automatisé.
- Hetényi poutre finie (formules en sinh/cosh) non recopiées de l'ouvrage.


## Menu Fichier et vérifications élémentaires (24 octobre 2026)

- Menus déroulants rendus au premier plan (la barre de titre les coupait) ; « [object Object] » supprimé
  du titre quand la clé `projet` n'est pas un texte. Vérifié dans Chrome à 1 280 et 760 px.
- Menu Fichier : groupe « Vérifications élémentaires » (`exemples/elementaires`, 8 scripts E01 à E08 avec
  résultat attendu et source en en-tête) et entrée « Rapport de validation complet » (45 cas).
- Les cas de poutres pures (RDM7, Winkler) et de plaque sans sol ne peuvent pas s'écrire en script (le
  langage ne prévoit ni charge directe sur la paroi ni paroi sans sol) : ils sont dans le rapport.
- Tests : pytest 290 réussis (6 ignorés), vitest 62.
- Correctif du 24/10 (suite) : l'utilisateur voyait encore l'ancienne interface car le lanceur, trouvant
  RetainWall déjà ouvert, rouvrait l'ancienne version. Le lanceur compare désormais l'heure de démarrage du
  serveur (`/api/sante` → `demarrage`) aux sources : version périmée → arrêt, recompilation, redémarrage.
- Lecture tolérante : `projet:` accepté en bloc (nom, affaire, client… dans `projet_infos`), mots-clés
  inconnus ignorés avec un avertissement orange (ligne, chemin) au lieu de bloquer le calcul ; les vraies
  erreurs restent bloquantes et sont listées, cliquables, à la place de « Aucun résultat ».
- Vérifié dans Chrome sur localhost:8000 (bloc projet + mot-clé inconnu : calcul fait, avertissement affiché).
  Tests : pytest 294 (6 ignorés), vitest 62.


## Audit complet et corrections (24 octobre 2026, session autonome)

Trois audits indépendants en lecture seule (backend, interface, outillage/tests/docs), constats critiques
vérifiés sur le code, puis neuf lots de corrections, chacun validé par la suite complète et commité.
Règle 1 respectée : aucune valeur de norme écrite ; les TODO-NORME existants sont intacts.

### Écarts corrigés (avec test de non-régression : `tests/unitaires/test_audit_24oct*.py`, `frontend/src/lib/__tests__/scriptDoc.test.ts`)

| Gravité | Constat | Correction |
| --- | --- | --- |
| Critique | `verifs.pire` : un résultat **non_ok sans taux** (section de pieu insuffisante) levait `KeyError` → erreur 500 | rang complet des états ; même règle dans la synthèse projet (`coupes.synthese_projet`) |
| Critique | Assemblages vérifiés sur des **efforts non pondérés** (H caractéristique × e / cos θ comparé à des résistances de calcul) | × `gamma_effets` ELU fondamental, comme `verifs_struct` ; coefficient absent → non vérifiable ; `efforts:` imposés = efforts de calcul (documenté) |
| Critique | Import d'un catalogue fautif : base supprimée puis reconstruction en échec, fichier fautif conservé, message anglais | validation complète en mémoire **avant** copie ; reconstruction dans un fichier temporaire puis substitution ; erreurs en français (table, ligne, colonne) ; `modele_*` refusés |
| Critique | Cache des résultats indexé par le texte seul : une norme corrigée ou un catalogue importé ne changeait rien avant redémarrage | clé = texte + empreinte (version, `docs/normes`, base, catalogues) ; verrou ; cache vidé après import |
| Critique | Lanceur : tout processus sur le port 8000 était tué, même un autre logiciel | arrêt seulement si `/api/sante` répond comme RetainWall ; autre programme → message et refus |
| Critique (interface) | Écran blanc possible : `toJS()` sur un alias YAML non défini, `scene.charger` sans `maquette`, aucune ErrorBoundary | lecture protégée, garde d'erreur globale (script conservé), message « maquette non disponible » |
| Critique (interface) | Champ « Nom du projet » écrasait un bloc `projet:` (nom, affaire, client) par un texte | édition clé par clé ; champs du bloc affichés |
| Majeur | Surcharge en plan limitée à une arête par numéro (`cote_paroi: 0` → « #0 ») **jamais appliquée** (une copie sur quatre de la règle « côté concerné » ignorait cette forme) | règle unique `plan.geometrie.cote_concerne`, utilisée partout |
| Majeur | Bouchon dont la phase est donnée par son nom : actif **pendant** cette phase seulement | nom résolu en indice à la conversion : actif à partir de la phase ; contrôles du lecteur (phase connue, numéro dans l'intervalle) |
| Majeur | Berlinoise / pieux disjoints à **EI imposé** sans `largeur_reaction_fiche` : butée sous le fond sur toute la largeur, sans message | refus explicite (même règle que le chemin EI calculé) |
| Majeur | Bishop, Kranz, Bjerrum-Eide ignoraient les surcharges `uniforme` en plan et, en silence, les surcharges phasées / ponctuelles / le talus | `uniforme` comptée comme `repartie` ; surcharges non modélisées **listées dans le détail** |
| Majeur | Jeu d'eau en rupture écarté des vérifications sans trace | résultat **non_ok** « Calcul — équilibre de l'écran » |
| Majeur | Assemblages : S355, lierne 300×300×11×19, tube 508×12,5 utilisés en repli sans prévenir | gabarit de repli pour le dessin seulement ; vérification **non vérifiable** nommant la donnée manquante |
| Majeur | Pseudo-3D : écoulement ignoré, branche unique, jeu principal seul, STR 3D omises après rupture, le tout en silence | avertissements explicites (`pseudo3d.avertissements_simplifications`) ; combinaison accidentelle déduite du nom du jeu annoncée |
| Majeur | `coupes.script` acceptait un chemin absolu ou `..` (lecture de n'importe quel fichier du serveur) | confiné au dossier `exemples/` |
| Majeur | Authentification : PBKDF2 (600 000 itérations) à chaque requête, dans la boucle d'événements ; fichier des comptes relu à chaque fois | vérification hors boucle, succès mis en cache 10 min, fichier relu seulement s'il change ; `lancer_production.ps1` sur 127.0.0.1 par défaut, variable d'auth non laissée dans le terminal |
| Majeur | Aucun gestionnaire d'erreurs : exception imprévue, `TableAbsente` (Kérisel-Absi), paramètre d'assemblage texte, caractère interdit → « Internal Server Error » | gestionnaire global et 422 en français ; `TableAbsente` → message TODO-NORME ; 400 / 503 explicites |
| Majeur | Limites absentes (script, fichier importé, longueur de plaque, domaine d'écoulement) | 2 Mo / 20 Mo / 2 000 m / 2 000 m (bornes de calculabilité, pas de norme) |
| Majeur (interface) | Message serveur perdu (« Serveur injoignable (TypeError…) » pour une erreur 500) ; import RIDO sans contrôle ; `renommerAppui` oubliait assemblages et plan ; Ctrl+Entrée relançait un calcul concurrent ; ajout depuis la 3D perdu si YAML invalide | corrigés (`api.ts` lit `erreurs` / `detail`, `ErreurServeur`) |
| Majeur (interface) | Objet `{}` recréé à chaque rendu → scène 3D rechargée et animation annulée ; petits graphiques redessinés au survol ; détail 3D en boucle de rendu continue sans libération | mémorisation, redessin sur changement de contenu, rendu à la demande + `dispose` |
| Majeur (interface) | Gradient critique = 1 et seuils 0,5 / 0,9 codés dans l'interface | couleurs tirées de l'état des vérifications du serveur (aucun seuil numérique dans l'interface) |
| Mineur | classe de section « 2 » (texte d'un catalogue) → W élastique silencieux ; re-pose d'un appui déjà posé (mise en charge comptée deux fois) ; phases homonymes ; valeur de norme nulle acceptée ; emprise nulle ; contour fermé par un point répété ; tolérance finale du solveur (`tol` au lieu de `tol_it`) | corrigés |
| Mineur (interface) | virgule décimale refusée (assemblages, boîtes de la maquette), « Annuler » = 0 ; suppressions sans confirmation ; légende et conventions hors de la figure exportée ; « Aller à l'erreur » inopérant au second clic ; `alert(Error: …)` ; contraste du texte faible | corrigés ; `separators` français dans Plotly ; convention du tranchant dans les légendes 3D |
| Outillage | bundle unique de 8,2 Mo ; versions Python non verrouillées ; pas de lint Python ; `lancer_tests.ps1` sans typage ni lint ; rafale calculée à la collecte ; `.ps1` sans BOM ; lanceur sans réinstallation ni journal | Monaco / three / Plotly en morceaux séparés (0,5 Mo au chargement) ; `requirements.lock.txt` (lanceur et Dockerfile) ; ruff configuré (0 signalement) ; `lancer_tests.ps1` = pytest + ruff + tsc + eslint + vitest ; rafale en fixtures ; BOM ; lanceur avec témoins d'installation, journal `%LOCALAPPDATA%\\RetainWall\\demarrage.log`, pause en cas d'erreur |
| Documentation | « normes livrées vides », « base reconstruite au démarrage », « normes lues à chaque calcul », hydrostatique seul : périmés ; référence du guide limitée à 15 blocs | corrigés ; référence générée pour **tous** les blocs du schéma (hydraulique, fouille, coupes, assemblages, coupe_calcul…) |

### Décisions prises sans l'utilisateur (à valider)
- Efforts d'assemblage : ceux issus d'un appui sont pondérés par `gamma_effets` ; ceux saisis dans `efforts:` sont
  réputés **efforts de calcul**. Si vous préférez saisir des efforts caractéristiques, le dire : un coefficient
  sera appliqué.
- Berlinoise à EI imposé : refus sans `largeur_reaction_fiche` (plutôt qu'une butée pleine largeur).
- Bishop / Kranz / Bjerrum-Eide : surcharges `uniforme` prises en compte, les autres seulement signalées (pas de
  refonte du modèle de massif).
- Combinaison accidentelle toujours déduite du nom du jeu d'eau (« except », « accid »), désormais annoncée ;
  une clé explicite par jeu pourrait la remplacer.
- Authentification : un compte supprimé reste accepté au plus 10 minutes (cache).

### Écarts documentés, non corrigés
- Boucles de phasage dupliquées entre 2D (`noyau/phasage.py`) et pseudo-3D (`pseudo3d/calcul.py`) ; fonctions de
  plus de 150 lignes (`lecteur._controles`, `MoteurPseudo3D.__init__`, `conversion.vers_modele`).
- Tests dépendants de la base matériaux vivante (`backend/data`) et des valeurs de normes « de mémoire » (E07, E08,
  `effort_elu == 1.35 × …`) : un vrai catalogue ou une norme corrigée fera échouer des tests sans que le code soit en cause.
- Calculs synchrones sans délai maximal (pas de pool de processus) ; Dockerfile toujours non testé (Docker absent).
- Dépôt Git sans dépôt distant ; `.venv` et `node_modules` synchronisés par OneDrive (lent, verrous) :
  à déplacer ou à exclure de la synchronisation.
- Plotly reste chargé avec l'onglet par défaut (4,5 Mo) ; locale française limitée aux séparateurs.
- Interface : menus sans navigation au clavier, lignes cliquables non focusables, aide-mémoire des raccourcis absent.

### Questions ouvertes pour l'utilisateur
1. Valider les décisions ci-dessus (efforts d'assemblage, berlinoise à EI imposé).
2. Source du seuil δp/φ ≤ 1/3 pour la butée de Coulomb (qualifié « seuil usuel » dans le code, sans référence dans docs/normes).
3. Relecture des 119 valeurs de `docs/normes/*.yaml` sur le texte des normes (toutes « à confirmer »).
4. Cas de référence K-Réa / RIDO (cas01 à cas05), manuel RIDO, tables de Kérisel-Absi : toujours absents.
5. Hébergement : dépôt distant, sortie de OneDrive, HTTPS.

### Testé
`lancer_tests.ps1` tout vert : pytest 329 réussis, 6 ignorés (cas K-Réa/RIDO absents), ruff 0 signalement, tsc 0 erreur,
eslint 0 erreur, vitest 74 (12 fichiers). Commits : d837409, 6f928cd, 0c5ed5d, eab4065, 501b9d9, 2d7557c, 6a0c10c,
90e7471, 5ea4462 puis outillage et documentation. Lanceur vérifié
en conditions réelles (premier lancement, « déjà lancé », version périmée → redémarrage en 7 s, port occupé par un
autre programme → refus) ; test de fumée Chrome sans affichage sur l'interface reconstruite (calcul, 3D, saisie,
vérifications : aucune erreur console).

