# Guide du langage de script RetainWall

Ce guide s'adresse aux ingénieurs du bureau d'études qui saisissent un calcul d'écran.
Il décrit le langage, les conventions et la lecture des résultats.

> **Avertissement.** RetainWall est en cours de validation. Aucun résultat ne doit servir
> à un projet réel avant d'avoir été comparé à K-Réa ou RIDO sur plusieurs cas et visé par
> un ingénieur. L'état de la validation est tenu dans `docs/ETAT.md`.

## 1. Principe

Un calcul est décrit par un **script YAML** : une suite de blocs `mot-clé: valeur`, avec
une indentation de deux espaces pour les sous-blocs et un tiret `- ` pour chaque élément
d'une liste. Le script s'écrit dans l'éditeur de l'application (coloration, complétion
avec Ctrl+Espace, aide au survol d'un mot-clé) ou dans n'importe quel éditeur de texte.

Le script est validé avant le calcul. Chaque erreur est signalée en français avec son
numéro de ligne ; un clic sur l'erreur place le curseur sur la ligne.

### Unités (fixes, jamais implicites)

| Grandeur | Unité |
| --- | --- |
| Cotes, longueurs | m (cotes dans le repère du projet, axe vertical vers le haut) |
| Poids volumiques | kN/m³ |
| Pressions, cohésion, modules du sol (EM), pl, qc | kPa |
| Angles | degrés |
| Efforts | kN (appui) ; kN/m (par mètre d'écran) |
| Modules d'élasticité des matériaux (E) | MPa |
| Sections d'acier (A, armatures) | cm² (cm²/m pour une paroi moulée) |
| Rigidités EI | kN·m²/m |

### Conventions de signe

- Déplacement **y positif vers la fouille**.
- Moment **positif quand la face côté fouille est tendue**.
- Effort tranchant V = dM/dz (z vers le haut).
- Effort d'appui positif quand l'appui retient l'écran (buton comprimé, tirant tendu).

Ces conventions sont rappelées dans les légendes de tous les graphiques.

## 2. Structure d'un script

```yaml
projet: Fouille rue des Lilas          # nom libre
calcul:                                # options (toutes facultatives)
  coefficients: coulomb                # ou kerisel_absi (tables à fournir)
  pas: 0.1                             # maillage (m)
paroi:                                 # type, cotes, matériaux
  type: palplanche
  profil: AZ 26-700                    # référence de la base matériaux
  acier: S355GP
  tete: 0.0
  pied: -14.0
sol:                                   # couches, de haut en bas ou dans le désordre
  - { nom: Remblai, toit: 0.0, gamma: 18, gamma_dejauge: 9, phi: 28, EM: 4000, alpha: 0.5 }
  - { nom: Sable, toit: -3.0, gamma: 20, gamma_dejauge: 11, phi: 35, EM: 15000, alpha: 0.33 }
eau:                                   # un ou plusieurs jeux de niveaux
  service: { amont: -2.0, aval: -2.0 }
surcharges:
  - { nom: grue, type: bande, q: 20, distance: 1.0, largeur: 5.0 }
appuis:
  B1: { type: buton, element: modulaire_A, cote: -1.5, espacement: 6.0, longueur: 18.0, precharge: 50 }
phases:
  - nom: "Terrassement à -2,0"         # guillemets si le nom contient une virgule
    excaver: -2.0
  - nom: Pose du buton B1
    poser: B1
  - nom: Terrassement final et pompage
    excaver: -6.5
    eau: { aval: -7.0 }
verifications: [butee, equilibre_vertical, fond_de_fouille, stabilite_generale, deplacements, structure]
criteres: { deplacement_max_mm: 30 }
```

**Piège fréquent.** Dans un bloc en ligne `{ ... }`, la virgule sépare les champs :
`nom: Terrassement à -2,0` y est coupé en deux. Mettez le texte entre guillemets.

## 3. Paroi

| Type | Données nécessaires | Rigidité calculée |
| --- | --- | --- |
| `palplanche` | `profil`, `acier` (profils en U : `beta_D` ; `classe_section` si le catalogue ne la donne pas) | E·I du catalogue (× β_D pour les U) |
| `paroi_moulee` | `epaisseur`, `beton` (option `rapport_EI_fissure`) | Ecm·e³/12 |
| `pieux_secants` | `diametre`, `entraxe`, `beton`, `primaires_armes` | EI des pieux armés / entraxe des armés |
| `pieux_disjoints` | `diametre`, `entraxe`, `beton`, largeur de fiche | EI d'un pieu / entraxe |
| `berlinoise` | `profil`, `acier`, `entraxe`, largeur de fiche, `blindage` | E·Iy du profilé / entraxe |

`EI` peut toujours être imposé directement. Pour les fiches discontinues (pieux disjoints,
berlinoise), la largeur de réaction sous le fond de fouille est donnée par
`largeur_reaction_fiche` (m par élément) ou par `docs/normes/nf_p94_282.yaml` ; sans
l'une ni l'autre, le calcul est refusé (aucune règle n'est inventée).

## 4. Sol

Chaque couche est définie par la cote de son **toit** ; elle s'étend jusqu'au toit de la
couche suivante (la dernière se prolonge sous le pied). Le coefficient de réaction est
calculé par la formule de Schmitt à partir de `EM` et `alpha`, ou imposé par `kh`. Pour
des données CPT, donnez `qc` et la corrélation retenue `EM_sur_qc` (il n'existe pas de
corrélation universelle : elle doit être choisie et justifiée couche par couche).

Les obliquités sont données en rapport à φ' : `delta_a_sur_phi` (poussée) et
`delta_p_sur_phi` (butée), 0 par défaut (Rankine). Avec les coefficients de Coulomb,
`delta_p_sur_phi` est limité à 1/3 : au-delà, la butée de Coulomb (surface plane) n'est
pas du côté de la sécurité et le calcul est refusé ; utilisez alors les tables de
Kérisel-Absi (`calcul: { coefficients: kerisel_absi }`).

## 5. Eau

Le bloc `eau` contient un ou plusieurs **jeux de niveaux** (par exemple `service` et
`exceptionnel`). Chaque jeu est calculé ; les vérifications retiennent le cas le plus
défavorable. Un jeu dont le nom contient « except » ou « accid » est vérifié en
combinaison accidentelle. Dans une phase, `eau: { aval: -7.0 }` ne change que les clés
écrites (pour tous les jeux). Seul le régime hydrostatique est calculé (un avertissement
le rappelle dès que les nappes amont et aval diffèrent : la butée peut être surestimée) ;
le fond de fouille est vérifié par la méthode de la longueur de cheminement (simplifiée).
Le poids volumique de l'eau vaut 10 kN/m³ par défaut (`calcul.gamma_w`).

### Écoulement autour de l'écran (bloc `hydraulique`)

Trois régimes : `hydrostatique` (défaut), `simplifie` (perte de charge uniforme le long du
cheminement amont → pied → fouille, pondération de Lane pour un parcours horizontal sous un
bouchon étanche) et `differences_finies` (écoulement 2D permanent sur la coupe, couches
anisotropes `k_h` / `k_v`, écran imperméable, substratum, bouchon, fouille symétrique).
L'écoulement fournit les pressions d'eau sur l'écran et corrige les contraintes effectives :
un écoulement ascendant côté fouille réduit la butée disponible.

```yaml
hydraulique:
  regime: differences_finies
  substratum: -30          # toit du substratum imperméable (défaut : pied − 2H)
  largeur_amont: 50        # domaine amont (défaut : 4H)
  largeur_fouille: 24      # fouille symétrique (défaut : 2H)
  pas: 0.5                 # maillage d'écoulement (m)
  sol_lane: sable_moyen    # clé de la table de Lane (docs/normes/hydraulique.yaml)
  bouchon: { type: injecte, toit: -9, base: -12, k: 1.0e-8, gamma: 21, phase: 4, lest: 0 }
```

Types de bouchon : `injecte`, `jet_grouting`, `radier_leste` (avec `lest` en kPa) et
`substratum` (couche naturelle : la perméabilité et le poids sont ceux de la couche).
`phase` : numéro (à partir de 1) ou nom de la phase à partir de laquelle le bouchon est actif.
Les vérifications `fond_de_fouille` utilisent alors le réseau d'écoulement : boulance
(équilibre des pressions et gradient de sortie), renard (Terzaghi, Lane, gradient critique,
affichés ensemble), soulèvement du bouchon avec son épaisseur minimale, gradient à travers le
bouchon, débit de pompage, et la stabilité du fond en argile molle si `cu` est donné.
Limite : l'écoulement est résolu en 2D sur la coupe puis extrudé en 3D (pas d'effet d'angle
sur le débit).

## 6. Appuis

| Type | Données de raideur | Remarques |
| --- | --- | --- |
| `buton` | `element` (ou `E` et `A`), `longueur`, `espacement`, `angle` | longueur élastique L/2 si `symetrique: true` (défaut) |
| `tirant` | `element` ou `E`/`A`, `longueur_libre`, `angle`, `espacement` | `longueur_scellee`, `diametre_forage`, `qs` pour Kranz et le scellement ; `nombre` de torons |
| `bracon` | `element` ou `E`/`A`, `longueur`, `angle` | `pied_bracon` : cote de l'appui en pied |
| `dalle` | `epaisseur`, `beton` (ou `E`), `longueur` (portée) | bilatérale par défaut |

`raideur` (kN/m par mètre d'écran) court-circuite le calcul de raideur. `precharge` est
l'effort axial par appui (précharge d'un buton, précontrainte d'un tirant), appliqué au
vérin au début de la phase de pose : l'appui exerce d'abord cette seule force (l'écran
recule), puis il est bloqué et réagit élastiquement aux déplacements ultérieurs. À la fin
d'une phase de pose sans autre action, l'effort de l'appui vaut donc exactement sa
précharge. `lierne` désigne le profilé de lierne à vérifier (donnez aussi `acier`, sa nuance).
Un appui posé dans une phase qui comporte aussi une excavation est en place (et mis en
charge) avant cette excavation : il en reprend les déplacements.

## 7. Phases

Chaque phase part de l'état de la précédente. Actions possibles, cumulables dans une
même phase : `excaver` (cote du fond), `remblayer` (`amont` / `aval`), `poser` et
`deposer` (un nom ou une liste), `eau`, `ajouter_surcharges`, `retirer_surcharges`.
Le bétonnage d'une dalle définitive se modélise par la pose d'un appui de type `dalle`.
Une phase d'**état initial** (sol au repos) est toujours calculée en premier.

**Branches (variantes, comme dans Plaxis).** Par défaut une phase repart de l'état de la phase
précédente de la liste. Le mot-clé `depuis: <nom d'une phase antérieure>` (ou `depuis: État
initial`) fait repartir la phase de l'état de cette phase-là : on obtient une branche, par
exemple « terrassement final sans pompage » à côté de la séquence principale. Les noms des
phases servant de point de départ doivent être uniques. Dans l'application, l'explorateur de
phases (Saisie › Phases) dessine l'arbre, insère une phase après une autre, crée une variante
depuis une phase et affiche l'état de calcul de chacune ; la frise du bas parcourt la branche
de la phase active. Les enveloppes et les vérifications couvrent toutes les branches ; le
pseudo-3D suit la branche de la dernière phase de la liste.

## 8. Vérifications

Listez celles à mener dans `verifications` : `butee`, `equilibre_vertical`, `kranz`,
`fond_de_fouille`, `stabilite_generale`, `deplacements`, `structure`.

Chaque vérification affiche un **taux de travail** (sollicitation / résistance de calcul),
sa source et son état : vert (≤ 90 %), orange (90 à 100 %), rouge (> 100 %), ou gris
**« non vérifiable »** quand une valeur de norme manque. Les coefficients partiels et
valeurs normatives sont lus uniquement dans `docs/normes/*.yaml` (livrés vides) : tant
qu'ils ne sont pas renseignés, l'application donne les valeurs caractéristiques à titre
indicatif et liste précisément les valeurs manquantes.

Les critères de déplacement aux ELS sont fixés par l'ingénieur dans `criteres`.

## 9. Base matériaux

Les références (`profil`, `element`, `acier`, `beton`, `lierne`) renvoient à la base
SQLite, alimentée par import de catalogues CSV ou Excel (bouton « Base matériaux » ;
modèles d'en-têtes dans `docs/catalogues/modele_*.csv`). Le jeu **DEMO** livré ne sert
qu'à essayer l'application : ses valeurs sont signalées « DEMO » dans les résultats.

## 10. Plan, maquette 3D et pseudo-3D

Le bloc `plan` décrit la fouille en plan (`contour`, polygone en m) et, facultativement,
la position de chaque appui (`appuis`: `appui`, `de`, `a`). Sans positions, les appuis sont
répartis à leur espacement. L'onglet « Maquette 3D » produit un fichier HTML autonome
qui s'ouvre sans installation.

Le mode `calcul: { mode: pseudo3d }` avec le bloc `pseudo3d` calcule la paroi comme une
plaque sur ressorts (longueur développée, conditions aux extrémités, angle de fouille au
milieu). Donnez `rigidite_horizontale` pour une paroi peu rigide horizontalement
(palplanches, pieux disjoints, paroi moulée à joints) ; sinon la plaque est isotrope.

## 11. Assemblages

L'onglet **Assemblages** propose 14 types de la pratique française des parois butonnées et
tirantées : platine d'about, platine boulonnée, chaise d'appui, appui biais de buton d'angle
(dé de calage), raboutage, boîte de vérinage, buton d'angle en coin de fouille, raidisseurs
de lierne, console de lierne chevillée sur la paroi, éclissage de lierne, tête de tirant sur
lierne et sur paroi moulée, chaise à goussets et axe de bracon, appui de bracon en pied.
Chaque type a son plan d'exécution (élévation, coupe hachurée, vue de dessus), sa nomenclature
repérée, ses symboles de soudure ISO 2553 et ses efforts ; les cotes suivent les paramètres,
survoler un champ surligne sa cote, cliquer une vérification surligne la pièce. La vue de
détail 3D est construite à partir des mêmes solides.

Les efforts viennent de l'appui calculé (N axial, V d'inclinaison, M et V de lierne sur deux
travées) ou sont saisis. Un assemblage s'enregistre dans le script :

```yaml
assemblages:
  A1: { type: platine_about, appui: B1, lierne: HEB 400, acier: S355, parametres: { t_platine: 30 } }
  A2: { type: eclisse_lierne, efforts: { M: 180, V: 120, N: 0 }, lierne: HEB 400, acier: S355 }
```

Les coefficients (γM, fub, k2, αv, βw, As, coefficients des axes et des âmes…) viennent de
`docs/normes/ec3_assemblages.yaml`, livré vide : tant qu'ils manquent, les vérifications sont
« prévues » et affichent les sollicitations. Les résistances des chevilles (ETE) se saisissent
dans les paramètres. Les vérifications marquées « À confirmer » reposent sur des méthodes
simplifiées (âme sous charge transversale sans χF, interaction linéaire N-M, 50 % de l'effort
dans les nervures…) à valider par l'ingénieur.

## 12. Import RIDO

Le bouton « Importer RIDO » convertit un fichier RIDO selon la table
`docs/rido/correspondance.yaml`, puis affiche le rapport des données non reprises. Cette
table est vide tant que le manuel RIDO n'a pas été fourni et lu : aucun mot-clé n'est
deviné.

## 13. Référence des mots-clés

Section générée à partir du schéma (`python -m sout.script.documentation`).

<!-- REFERENCE:DEBUT -->

### Racine du script

| Mot-clé | Type | Obligatoire | Défaut | Description |
| --- | --- | --- | --- | --- |
| `projet` | texte | oui |  | nom du projet ; ou bloc d'informations libres (nom, affaire, client, lieu…), dont le nom est affiché et les autres lignes conservées |
| `projet_infos` | <class 'dict'> |  |  | informations du projet (rempli automatiquement quand projet est un bloc) |
| `calcul` | bloc |  |  |  |
| `paroi` | bloc | oui |  |  |
| `sol` | liste de bloc | oui |  |  |
| `terrain` | bloc |  |  |  |
| `fouille` | bloc |  |  | risbermes, talus et gradins côté fouille |
| `eau` | blocs nommés de bloc |  |  | jeux de niveaux d'eau (service, exceptionnel…) |
| `surcharges` | liste de bloc |  |  |  |
| `appuis` | blocs nommés de bloc |  |  |  |
| `phases` | liste de bloc | oui |  |  |
| `verifications` | liste de butee / equilibre_vertical / kranz / fond_de_fouille / stabilite_generale / deplacements / structure |  |  |  |
| `criteres` | bloc |  |  |  |
| `plan` | bloc |  |  |  |
| `pseudo3d` | bloc |  |  |  |
| `hydraulique` | bloc |  |  |  |
| `assemblages` | blocs nommés de bloc |  |  | assemblages à vérifier et à dessiner |
| `coupes` | liste de bloc |  |  | coupes de calcul 2D placées en plan (vide = une coupe unique sur toute la paroi) |
| `coupe_calcul` | bloc |  |  | position de cette coupe en plan (automatique) |

### calcul

| Mot-clé | Type | Obligatoire | Défaut | Description |
| --- | --- | --- | --- | --- |
| `methode` | coefficients_reaction |  | coefficients_reaction | méthode de calcul |
| `kh` | schmitt / impose |  | schmitt | coefficient de réaction : schmitt (EM, α) ou impose (kh par couche) |
| `norme` | texte |  | NF P 94-282 | norme de référence des vérifications |
| `coefficients` | coulomb / kerisel_absi |  | coulomb | coefficients de poussée/butée : coulomb (formule) ou kerisel_absi (tables à fournir) |
| `gamma_w` | nombre |  | 10.0 | poids volumique de l'eau (kN/m3) (> 0, ≤ 12) |
| `pas` | nombre |  | 0.1 | longueur maximale d'élément du maillage (m) (> 0.005, ≤ 1.0) |
| `jeu_eau` | texte |  |  | jeu de niveaux d'eau utilisé (défaut : le premier du bloc eau) |
| `mode` | 2d / pseudo3d |  | 2d | 2d (par section) ou pseudo3d (plaque sur ressorts) |
| `largeur_fouille` | nombre |  |  | largeur de la fouille pour la stabilité générale (m) ; défaut : 2 × hauteur de paroi (> 0) |

### paroi

| Mot-clé | Type | Obligatoire | Défaut | Description |
| --- | --- | --- | --- | --- |
| `type` | palplanche / paroi_moulee / pieux_secants / pieux_disjoints / berlinoise | oui |  | type de paroi |
| `tete` | nombre | oui |  | cote de la tête de paroi (m) |
| `pied` | nombre | oui |  | cote du pied de paroi (m) |
| `EI` | nombre |  |  | rigidité imposée par mètre linéaire (kN·m²/m) ; sinon calculée (> 0) |
| `profil` | texte |  |  | référence de la base matériaux (palplanche ou profilé) |
| `acier` | texte |  |  | nuance d'acier (base matériaux) |
| `beton` | texte |  |  | classe de béton (base matériaux) |
| `epaisseur` | nombre |  |  | épaisseur de paroi moulée (m) (> 0) |
| `diametre` | nombre |  |  | diamètre des pieux (m) (> 0) |
| `entraxe` | nombre |  |  | entraxe des pieux ou profilés (m) (> 0) |
| `profil_armature` | texte |  |  | profilé d'armature des pieux (base matériaux) |
| `primaires_armes` | true / false |  | False | pieux sécants : pieux primaires armés |
| `rapport_EI_fissure` | nombre |  |  | béton : rapport EI fissuré / EI non fissuré choisi par l'ingénieur (> 0, ≤ 1) |
| `beta_D` | nombre |  |  | palplanches en U : réduction d'inertie β_D (EN 1993-5, à fournir) (> 0, ≤ 1) |
| `classe_section` | entier |  |  | palplanches : classe de section (EN 1993-5) si le catalogue ne la donne pas (≥ 1, ≤ 4) |
| `perte_epaisseur` | nombre |  |  | palplanches : perte d'épaisseur par corrosion, totale (mm) (≥ 0) |
| `largeur_reaction_fiche` | nombre |  |  | fiche discontinue : largeur de réaction imposée sous le fond (m par élément) (> 0) |
| `blindage` | bloc |  |  | berlinoise : blindage entre profilés |
| `enrobage` | nombre |  |  | distance du parement à l'axe des armatures (m) (> 0) |
| `armatures_fouille` | nombre |  |  | paroi moulée : armatures côté fouille (cm²/m) (> 0) |
| `armatures_terre` | nombre |  |  | paroi moulée : armatures côté terre (cm²/m) (> 0) |
| `armatures_pieu` | nombre |  |  | pieux : armatures longitudinales par pieu (cm²) (> 0) |
| `armatures_horizontales` | nombre |  |  | paroi moulée (pseudo-3D) : armatures horizontales par face (cm²/m de hauteur), pour le moment horizontal Ms de la plaque (> 0) |
| `enrobage_horizontal` | nombre |  |  | paroi moulée (pseudo-3D) : distance du parement à l'axe des armatures horizontales (m) ; défaut : enrobage (> 0) |
| `longueur_panneau` | nombre |  |  | paroi moulée (pseudo-3D) : longueur des panneaux (m) ; un joint entre panneaux ne transmet ni moment ni torsion horizontaux (> 0) |
| `origine_panneaux` | nombre |  | 0.0 | paroi moulée (pseudo-3D) : abscisse du premier joint le long de la paroi (m) (≥ 0) |

### paroi.blindage

| Mot-clé | Type | Obligatoire | Défaut | Description |
| --- | --- | --- | --- | --- |
| `epaisseur` | nombre | oui |  | épaisseur du blindage (m) (> 0) |
| `materiau` | bois / beton / acier | oui |  | matériau du blindage |
| `resistance` | nombre |  |  | résistance de calcul en flexion (MPa) (> 0) |

### sol (chaque couche)

| Mot-clé | Type | Obligatoire | Défaut | Description |
| --- | --- | --- | --- | --- |
| `nom` | texte | oui |  | nom de la couche |
| `toit` | nombre | oui |  | cote du toit de la couche (m) |
| `gamma` | nombre | oui |  | poids volumique hors nappe (kN/m3) (> 0, ≤ 30) |
| `gamma_dejauge` | nombre | oui |  | poids volumique déjaugé sous nappe (kN/m3) (> 0, ≤ 20) |
| `phi` | nombre | oui |  | angle de frottement effectif φ' (degrés) (≥ 0, < 60) |
| `c` | nombre |  | 0.0 | cohésion effective c' (kPa) (≥ 0) |
| `EM` | nombre |  |  | module pressiométrique (kPa) (> 0) |
| `alpha` | nombre |  |  | coefficient rhéologique de Ménard α (> 0, ≤ 1) |
| `pl` | nombre |  |  | pression limite pressiométrique (kPa) (> 0) |
| `qc` | nombre |  |  | résistance de pointe CPT (kPa) (> 0) |
| `EM_sur_qc` | nombre |  |  | corrélation choisie EM = (EM/qc)·qc (> 0) |
| `kh` | nombre |  |  | coefficient de réaction imposé (kN/m3) (> 0) |
| `K0` | nombre |  |  | coefficient des terres au repos (défaut : Jaky 1 − sin φ') (> 0, ≤ 3) |
| `delta_a_sur_phi` | nombre |  | 0.0 | obliquité côté poussée δa/φ' (≥ 0, ≤ 1) |
| `delta_p_sur_phi` | nombre |  | 0.0 | obliquité côté butée |δp|/φ' (≥ 0, ≤ 1) |
| `coef_decharge` | nombre |  |  | coefficient de décharge Kd (défaut : K0) (> 0, ≤ 3) |
| `k_h` | nombre |  |  | perméabilité horizontale (m/s), nécessaire au calcul d'écoulement (> 0) |
| `k_v` | nombre |  |  | perméabilité verticale (m/s) ; défaut : k_h (> 0) |
| `cu` | nombre |  |  | cohésion non drainée (kPa), stabilité du fond en argile molle (> 0) |
| `sol_lane` | texte |  |  | type de sol de la table de Lane (clé de docs/normes/hydraulique.yaml → lane.C) |

### terrain

| Mot-clé | Type | Obligatoire | Défaut | Description |
| --- | --- | --- | --- | --- |
| `amont` | nombre |  |  | cote initiale du terrain amont (m) ; défaut : toit de la 1re couche |
| `aval` | nombre |  |  | cote initiale du terrain aval (m) ; défaut : terrain amont |
| `pente_beta` | nombre |  |  | terrain en pente uniforme côté terre : angle β sur l'horizontale (°), poussée de Coulomb avec talus (> -80, < 80) |
| `profil` | liste de liste de nombre |  |  | côté terre : ligne [distance à la paroi, cote] (m) ; le sol au-dessus de la cote amont est pris en surcharge équivalente |
| `methode_pente` | coulomb_beta / surcharge_equivalente |  | surcharge_equivalente | prise en compte du profil : coefficients avec β (pente uniforme) ou surcharge équivalente |
| `cote_paroi` | texte ou entier ou liste de texte ou entier |  |  | côté(s) concerné(s) par le profil (défaut : tous) |
| `remblai` | bloc |  |  | remblai côté terre mis en place à une phase (couche ajoutée) |

### eau (chaque jeu de niveaux)

| Mot-clé | Type | Obligatoire | Défaut | Description |
| --- | --- | --- | --- | --- |
| `amont` | nombre |  |  | cote de la nappe côté amont (m) ; vide = pas de nappe |
| `aval` | nombre |  |  | cote de la nappe côté aval (m) ; vide = pas de nappe |

### surcharges (chaque surcharge)

| Mot-clé | Type | Obligatoire | Défaut | Description |
| --- | --- | --- | --- | --- |
| `nom` | texte |  |  | nom (pour la retirer dans une phase, et pour la maquette) |
| `type` | repartie / uniforme / bande / rectangulaire / ponctuelle / lineique / lineaire / convoi | oui |  | uniforme (= répartie), bande parallèle à la paroi, rectangulaire (emprise en plan), ponctuelle, linéaire (= linéique), convoi (modèle routier à fournir) |
| `q` | nombre | oui |  | intensité : kPa (uniforme, bande, rectangulaire), kN (ponctuelle) ou kN/m (linéaire) |
| `distance` | nombre |  | 0.0 | bande : distance du parement au début de la bande (m) (≥ 0) |
| `largeur` | nombre |  |  | bande : largeur (m) ; uniforme : largeur de la zone chargée (vide = illimitée) (> 0) |
| `cote` | nombre |  |  | cote d'application (m) ; défaut : terrain − profondeur |
| `profondeur` | nombre |  | 0.0 | profondeur d'application sous le terrain (m), ex. fondation d'un bâtiment (≥ 0) |
| `cote_ecran` | amont / aval |  | amont | face de l'écran chargée |
| `cote_paroi` | texte ou entier ou liste de texte ou entier |  |  | côté(s) de paroi concerné(s) : nom de plan.cotes, numéro d'arête, liste ou « toutes » (défaut) |
| `emprise` | liste de nombre ou blocs nommés de nombre |  |  | rectangulaire/ponctuelle : [lx, ly] (m) ; bande : {de, a} ou [de, a], étendue le long du côté (m) |
| `position` | liste de nombre |  |  | rectangulaire/ponctuelle : centre en plan [x, y] (m) |
| `trace` | bloc |  |  | linéaire : segment en plan |
| `niveaux` | entier |  |  | bâtiment : nombre de niveaux (maquette) (≥ 1) |
| `modele` | texte |  |  | convoi : modèle routier (Bc, Bt…), charges à fournir dans docs/normes |
| `phase` | entier ou texte |  |  | phase d'application (numéro à partir de 1, ou nom) ; vide = dès le début |
| `phases` | liste de entier ou texte |  |  | [première, dernière] phase d'existence |

### appuis (chaque appui)

| Mot-clé | Type | Obligatoire | Défaut | Description |
| --- | --- | --- | --- | --- |
| `type` | buton / tirant / bracon / dalle | oui |  | type d'appui |
| `cote` | nombre | oui |  | cote de l'appui sur la paroi (m) |
| `element` | texte |  |  | référence de la base matériaux (buton modulaire, profilé, armature) |
| `E` | nombre |  |  | module d'Young (MPa) si pas d'élément de la base (> 0) |
| `A` | nombre |  |  | section (cm²) si pas d'élément de la base (> 0) |
| `raideur` | nombre |  |  | raideur imposée (kN/m par mètre d'écran) (≥ 0) |
| `espacement` | nombre |  | 1.0 | espacement horizontal des appuis (m) (> 0) |
| `longueur` | nombre |  |  | longueur du buton ou bracon, portée de la dalle (m) (> 0) |
| `angle` | nombre |  | 0.0 | inclinaison sur l'horizontale (degrés) (≥ -80, ≤ 80) |
| `precharge` | nombre |  | 0.0 | précharge ou précontrainte par appui (kN, axiale) (≥ 0) |
| `symetrique` | true / false |  | True | buton/dalle entre deux parois symétriques (longueur élastique L/2) |
| `longueur_libre` | nombre |  |  | tirant : longueur libre (m) (> 0) |
| `longueur_scellee` | nombre |  |  | tirant : longueur de scellement (m) (> 0) |
| `longueur_elastique` | nombre |  |  | tirant : longueur élastique imposée (m) (> 0) |
| `diametre_forage` | nombre |  |  | tirant : diamètre du forage (m) (> 0) |
| `qs` | nombre |  |  | tirant : frottement latéral limite du scellement (kPa) (> 0) |
| `epaisseur` | nombre |  |  | dalle : épaisseur (m) (> 0) |
| `unilateral` | true / false |  |  | ne reprend pas d'effort négatif (défaut : oui sauf dalle) |
| `lierne` | texte |  |  | profilé de lierne (base matériaux) ; en pseudo-3D, poutre horizontale continue E·Iy au niveau de l'appui (nuance acier requise), torsion négligée |
| `nombre` | entier |  |  | tirant : nombre de torons ou de barres de l'élément (≥ 1) |
| `acier` | texte |  |  | nuance d'acier de l'élément (base matériaux) |
| `beton` | texte |  |  | dalle : classe de béton (base matériaux) |
| `pied_bracon` | nombre |  |  | bracon : cote de l'appui en pied (m) |

### phases (chaque phase)

| Mot-clé | Type | Obligatoire | Défaut | Description |
| --- | --- | --- | --- | --- |
| `nom` | texte | oui |  | nom de la phase |
| `excaver` | nombre |  |  | cote du fond de fouille atteinte (m) |
| `remblayer` | bloc |  |  | remblai jusqu'à une cote, côté amont ou aval |
| `poser` | texte ou liste de texte |  |  | appui(s) posé(s) dans cette phase |
| `deposer` | texte ou liste de texte |  |  | appui(s) déposé(s) dans cette phase |
| `eau` | bloc |  |  | nouveaux niveaux d'eau (seules les clés écrites changent) |
| `ajouter_surcharges` | liste de bloc |  |  | surcharges ajoutées |
| `retirer_surcharges` | liste de texte |  |  | noms des surcharges retirées |
| `depuis` | texte |  |  | phase de départ : nom d'une phase antérieure ou « État initial » ; vide = la phase précédente ; permet des branches (variantes) |
| `terrasser_risberme` | texte ou liste de texte |  |  | risberme(s), talus ou gradins terrassés dans cette phase (noms) |

### phases.remblayer

| Mot-clé | Type | Obligatoire | Défaut | Description |
| --- | --- | --- | --- | --- |
| `amont` | nombre |  |  | nouvelle cote du terrain amont (m) |
| `aval` | nombre |  |  | nouvelle cote du terrain aval (m) |

### criteres

| Mot-clé | Type | Obligatoire | Défaut | Description |
| --- | --- | --- | --- | --- |
| `deplacement_max_mm` | nombre |  |  | déplacement admissible aux ELS (mm) (> 0) |
| `deplacement_tete_mm` | nombre |  |  | déplacement admissible en tête aux ELS (mm) (> 0) |

### plan

| Mot-clé | Type | Obligatoire | Défaut | Description |
| --- | --- | --- | --- | --- |
| `contour` | liste de liste de nombre | oui |  | polygone de la fouille [[x, y], ...] (m) |
| `appuis` | liste de bloc |  |  | positions des appuis en plan |
| `cote_terrain` | nombre |  |  | cote du terrain autour de la fouille (m) |
| `cotes` | blocs nommés de entier |  |  | noms des côtés de la fouille → numéro d'arête du contour (0 = premier segment) |

### plan.appuis (chaque position)

| Mot-clé | Type | Obligatoire | Défaut | Description |
| --- | --- | --- | --- | --- |
| `appui` | texte | oui |  | nom de l'appui (bloc appuis) |
| `de` | liste de nombre | oui |  | point de départ [x, y] (m) |
| `a` | liste de nombre | oui |  | point d'arrivée [x, y] (m) |

### pseudo3d

| Mot-clé | Type | Obligatoire | Défaut | Description |
| --- | --- | --- | --- | --- |
| `longueur` | nombre |  |  | paroi droite : longueur développée modélisée (m) ; absente avec un bloc plan : fouille fermée sur tout le contour, butons reliant les parois en vis-à-vis (double écran) (> 0) |
| `pas_horizontal` | nombre |  | 0.5 | taille des éléments selon la longueur (m) (> 0.05) |
| `bords` | libres / encastres / appuyes |  | libres | conditions aux extrémités |
| `angle` | nombre |  |  | angle de la fouille au milieu de la paroi (degrés) ; seule sa présence compte : la paroi perpendiculaire impose w = 0 sur la ligne d'angle (appui simple, continuité du ferraillage d'angle négligée) (> 0, < 360) |
| `rigidite_horizontale` | nombre |  |  | rigidité de flexion horizontale Ds imposée, par mètre de hauteur (kN·m²/m ; 0 = aucune) ; défaut selon le type de paroi (paroi moulée : Ds = Dz ; palplanches, pieux, berlinoise : 0) (≥ 0) |
| `rapport_rigidite_horizontale` | nombre |  |  | rapport Ds/Dz imposé (sans unité ; 0 = aucune flexion horizontale, 1 = plaque isotrope) ; prioritaire sur le défaut du type, moins que rigidite_horizontale (≥ 0) |
| `torsion` | nombre |  |  | rigidité de torsion GJ par mètre imposée (kN·m²/m) ; défaut √(Ds·Dz) (plaque de Huber) (≥ 0) |
| `largeur_appui` | nombre |  |  | largeur sur laquelle chaque appui ponctuel est réparti le long de la paroi (m : plaque d'appui, semelle de lierne) ; sans cette clé l'appui agit sur un seul nœud et Ms, V à son droit dépendent du maillage (> 0) |

<!-- REFERENCE:FIN -->
