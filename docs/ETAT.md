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
