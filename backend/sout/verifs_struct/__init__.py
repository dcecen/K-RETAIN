"""Vérifications structurelles (EC3 : butons, bracons, liernes, profilés, palplanches ;
EC2 : paroi moulée, pieux) à partir des efforts de chaque phase.

Efforts de calcul : effets caractéristiques (calcul aux ELS) multipliés par
gamma_effets de la combinaison (docs/normes/nf_p94_282.yaml -> combinaisons) ;
combinaison accidentelle pour un jeu d'eau dont le nom contient « except » ou
« accid », fondamentale sinon.
"""
from .elements import executer

__all__ = ["executer"]
