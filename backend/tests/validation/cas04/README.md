# Cas de validation cas04

Contenu attendu (voir docs/specs.md, section « Cas de validation ») :
- `entree.yaml` : le cas saisi dans le langage RetainWall ;
- `reference.json` : sorties K-Réa ou RIDO par phase, au format
  `{"logiciel": "K-Réa v4", "phases": [{"nom": ..., "deplacement_max_mm": ..., "moment_max_kNm": ..., "efforts_appuis_kN": {"B1": ...}}]}` ;
- le fichier d'origine K-Réa / RIDO, pour traçabilité.

Tant que ces fichiers manquent, le test correspondant est ignoré (skip).
