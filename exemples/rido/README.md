# Comparaison K-Retain / RIDO

Fichiers RIDO **prêts à ouvrir dans RIDO**, sans feuille Excel, avec leur conversion K-Retain et un classeur de
comparaison. Sols **fictifs** (valeurs d'illustration) : ces cas comparent deux logiciels sur les mêmes données.

| Fichier | Cas | Ce qui est testé |
|---|---|---|
| `R00_fichier_fourni_sans_excel.rid` | votre fichier berlinoise IPE 400, rendu indépendant de la feuille | structure complète du fichier fourni (rrc, coe Z0 Zf, MEL, ELU) ; **cellules de démonstration** |
| `R01_sable_homogene.rid` | IPE 400 / 2,1 m, sable, H = 3 m | cas de base, δ = 0 |
| `R02_surcharge_bande.rid` | R01 + `sub(1) TN 0.50 10.5 5` | surcharge de bande |
| `R03_bicouche.rid` | limon (c = 5 kPa) sur sable | cohésion, deux couches |
| `R04_HEB300_tricouche.rid` | HEB 300 / 2,0 m, H = 4 m, trois couches | autre profilé, fiche de 6 m |
| `R05_nappe_fiche.rid` | R03 avec nappe à 131,0 sous le fond | poids déjaugés |
| `R06_frottement_poussee.rid` | R01 avec δa/φ = 2/3 | frottement côté poussée (écart de quelques % attendu sur Ka) |
| `R07_deux_phases.rid` | IPE 500 / 2,4 m, terrassement 2 m puis 3,5 m | phasage |

Pour chaque cas : `<cas>.yaml` (script K-Retain, menu **Fichier > Comparaison RIDO**), `<cas>.rapport.txt` (données
non reprises et hypothèses de lecture), et `comparaison_rido.xlsx` (tous les cas).

## Déroulé de la comparaison

1. Ouvrir `R01_sable_homogene.rid` dans RIDO et **contrôler la relecture des données** (points ci-dessous).
2. Lancer les cas dans RIDO, reporter déplacement en tête, déplacement maximal, moment minimal (et maximal),
   tranchant maximal dans la colonne jaune de `comparaison_rido.xlsx` : écart et verdict (5 %) se calculent seuls.
3. Dans K-Retain : **Fichier > Comparaison RIDO > R01…**, Calculer : mêmes valeurs que le classeur.

## Points à contrôler sur la première sortie RIDO

Le format a été lu sur un seul fichier, sans le manuel (`docs/rido/correspondance.yaml`) :

1. Ligne de couche `base γ γ' 0 0 0 φ c + δa δp kh` : φ et c bien à leur place, base (et non toit) de couche.
2. kh relu par RIDO = valeur Re calculée dans le fichier (feuille du cas dans le classeur, colonne kh).
3. `coe` : pressions et kh multipliés des deux côtés entre les deux cotes.
4. `sub(1) TN 0.50 10.5 5` : bande de 5 kPa entre 0,50 m et 10,5 m de l'écran.
5. R06 : δa lu comme un rapport (2/3 φ) et non comme un angle.

Si une lecture est fausse : corriger l'ordre dans `docs/rido/correspondance.yaml`, puis
`python -m outils.rido_exemples` et `python -m outils.comparaison_rido` (aucun code à modifier).

## Écarts attendus entre les deux logiciels

- δ = 0 (R01 à R05, R07) : Ka et Kp de Rankine identiques à ceux de Caquot-Kérisel ; seuls restent le maillage
  et la convergence.
- δ ≠ 0 : K-Retain prend Ka, Kp de Coulomb ; il **refuse** δp/φ > 1/3 sans les tables de Kérisel-Absi
  (`docs/normes/kerisel_absi`, non fournies).
- Les calculs MEL et ELU (tel, fap) ne sont pas repris : seul le calcul aux coefficients de réaction est comparé.
- `rrc` (sens inconnu) n'est pas repris : retiré des cas R01 à R07, conservé dans R00.

## Votre fichier avec sa vraie feuille Excel

```
cd backend
.venv\Scripts\python.exe -m outils.rido_sans_excel ..\docs\rido\berlinoise_IPE400_excel.rid "Données RIDO.xlsx"
```

écrit `berlinoise_IPE400_sans_excel.rid` (valeurs des cellules recopiées). Un `.xls` demande le module xlrd, ou
« Enregistrer sous » `.xlsx` dans Excel. Sans classeur, la commande écrit un gabarit avec une variable
`A_RENSEIGNER` par cellule.

## Régénérer

```
cd backend
.venv\Scripts\python.exe -m outils.rido_exemples      # fichiers .rid
.venv\Scripts\python.exe -m outils.comparaison_rido   # .yaml, .rapport.txt, comparaison_rido.xlsx
```

Conventions K-Retain : y positif vers la fouille (mm) ; M positif quand la face côté fouille est tendue
(kN·m/m) ; effort d'appui positif quand l'appui retient l'écran (kN/m). Vérifier les conventions de RIDO avant
de comparer les signes. Fichiers `.rid` écrits en Windows-1252 avec fins de ligne Windows (CRLF).
