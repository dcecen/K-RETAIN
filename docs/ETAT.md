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
