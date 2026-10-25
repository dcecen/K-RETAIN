"""Couche « géométrie » du modèle : ouvrages en plan, terrain côté terre, terrassements (fonds par zone, risbermes,
talus, gradins avec étendue le long des côtés) et positions des surcharges.

- `modele` : structures figées (fonctions pures, aucune lecture de fichier) ;
- `normaliser` : lecture du bloc `geometrie` du script, ou conversion de la forme ancienne (plan, fouille, terrain) ;
- `derivation` : données 2D locales en un point de la paroi (coupe de calcul) et classes de lignes du pseudo-3D ;
- `decoupage` : tronçons homogènes du contour (coupes automatiques) et polygones des zones de fond.
"""
