# RIDO

- `berlinoise_IPE400_excel.rid` : fichier RIDO réel fourni le 30/10/2026 (berlinoise IPE 400 autostable), lié à
  la feuille « Données RIDO.xls » (fonctions xlc), **feuille non fournie**.
- `correspondance.yaml` : lecture du format, établie sur ce seul fichier, **sans le manuel RIDO** ; chaque
  position porte son statut (« lu » dans le fichier ou « à confirmer »). Le convertisseur
  (`backend/sout/script/rido.py`) relit l'ordre des colonnes dans cette table.

À déposer ici pour confirmer la lecture :
- le manuel du format d'entrée RIDO (PDF) ;
- la feuille « Données RIDO.xls » du fichier fourni ;
- les sorties RIDO (déplacements, moments, efforts d'appui par phase) des cas de `exemples/rido`.

Vérifiez aussi que la licence RIDO autorise la lecture de son format par un autre outil.
