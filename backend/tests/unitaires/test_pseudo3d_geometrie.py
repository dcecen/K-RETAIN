"""Pseudo-3D en fouille fermée avec le bloc geometrie (lot 4e) : un état de chantier et de sol par classe de lignes.

- risberme sur le seul côté sud : le côté sud se déplace moins que le côté nord ; avec Ds = 0 chaque ligne est
  l'écran 2D calculé avec (sud) ou sans (nord) la risberme ;
- fond par zone : le côté est, moins excavé, se déplace moins et retrouve le 2D excavé à sa cote ;
- mode « lignes » forcé = mode « troncons » ; objet sans restriction = chemin uniforme (identique à la forme ancienne).
"""
from types import SimpleNamespace

import numpy as np
import pytest

from sout import normes
from sout.materiaux.base import catalogue_par_defaut
from sout.noyau.phasage import calculer
from sout.pseudo3d.calcul import moteur_depuis_script
from sout.script.conversion import vers_modele
from sout.script.lecteur import lire_script

CAT, NRM = catalogue_par_defaut(), normes.charger()
TETE = """
projet: Fouille fermée 20 x 12, Ds = 0, sans appui
calcul: { kh: impose, mode: pseudo3d, pas: 0.25 }
paroi: { type: paroi_moulee, EI: 100000, tete: 0.0, pied: -12.0 }
sol:
  - { nom: Sable, toit: 0.0, gamma: 20, gamma_dejauge: 10, phi: 32, c: 0, kh: 12000 }
eau: { service: { amont: null, aval: null } }
pseudo3d: { pas_horizontal: 1.0, rapport_rigidite_horizontale: 0 }
"""
OUVRAGES = """
geometrie:
  ouvrages:
    contour: [[0, 0], [20, 0], [20, 12], [0, 12]]
    cotes: { sud: 0, est: 1, nord: 2, ouest: 3 }
"""
PHASES = """
phases:
  - { nom: Exc1, excaver: -2.0 }
  - { nom: P2 }
  - { nom: Exc2, excaver: -6.0 }
"""
RISBERME_SUD = """  fouille:
    objets:
      - { nom: R1, type: risberme, cotes: [sud], phases: [3, 3], cote_crete: -3.0, largeur_crete: 2.0, pente: 1.5, cote_pied: -6.0 }
"""
I_SUD, I_NORD, I_EST, I_OUEST = 10, 42, 26, 58     # x = 10 m au sud, son vis-à-vis au nord ; milieux est et ouest


def _plaque(texte: str):
    s = lire_script(texte)
    m = vers_modele(s, CAT, NRM)
    mo = moteur_depuis_script(SimpleNamespace(script=s, modele=m))
    return mo, mo.calculer()


def _2d(texte_2d: str):
    return calculer(vers_modele(lire_script(texte_2d), CAT, NRM)).phases[-1].y


def test_risberme_sur_le_seul_cote_sud_par_classes_de_lignes():
    mo, r3 = _plaque(TETE + OUVRAGES + RISBERME_SUD + PHASES)
    assert mo.mode_sol == "troncons" and len(mo.representants) == 2 and r3.complet
    assert any("classes de lignes" in a for a in r3.avertissements)
    W = r3.phases[-1].W
    avec = _2d(TETE.replace("mode: pseudo3d, ", "") + "fouille:\n  risbermes:\n    - { nom: R1, phases: [3, 3], cote_crete: -3.0, largeur_crete: 2.0, pente: 1.5, cote_pied: -6.0 }\n" + PHASES)
    sans = _2d(TETE.replace("mode: pseudo3d, ", "") + PHASES)
    np.testing.assert_allclose(W[I_SUD], avec, rtol=1e-5, atol=1e-9)
    np.testing.assert_allclose(W[I_NORD], sans, rtol=1e-5, atol=1e-9)
    assert np.abs(W[I_SUD]).max() < 0.9 * np.abs(W[I_NORD]).max()
    assert abs(r3.phases[-1].bilan["residu"]) <= 1e-6 * r3.phases[-1].bilan["echelle"]


def test_fond_par_zone_en_fouille_fermee():
    zones = "  fouille:\n    zones:\n      - { nom: est, cotes: [est] }\n"
    phases = PHASES.replace("excaver: -6.0", "excaver: { defaut: -6.0, est: -4.0 }")
    mo, r3 = _plaque(TETE + OUVRAGES + zones + phases)
    assert mo.mode_sol == "troncons" and len(mo.representants) == 2 and r3.complet
    W = r3.phases[-1].W
    fond_6 = _2d(TETE.replace("mode: pseudo3d, ", "") + PHASES)
    fond_4 = _2d(TETE.replace("mode: pseudo3d, ", "") + PHASES.replace("excaver: -6.0", "excaver: -4.0"))
    np.testing.assert_allclose(W[I_EST], fond_4, rtol=1e-5, atol=1e-9)
    np.testing.assert_allclose(W[I_OUEST], fond_6, rtol=1e-5, atol=1e-9)
    np.testing.assert_allclose(W[I_SUD], fond_6, rtol=1e-5, atol=1e-9)
    assert np.abs(W[I_EST]).max() < 0.5 * np.abs(W[I_OUEST]).max()
    assert abs(r3.phases[-1].bilan["residu"]) <= 1e-6 * r3.phases[-1].bilan["echelle"]


def test_mode_lignes_force_egal_mode_troncons():
    mo, r_tr = _plaque(TETE + OUVRAGES + RISBERME_SUD + PHASES)
    mo2, _ = _plaque(TETE + OUVRAGES + RISBERME_SUD + PHASES)
    mo2.mode_sol = "lignes"
    r_li = mo2.calculer()
    for a, b in zip(r_tr.phases, r_li.phases):
        np.testing.assert_allclose(a.W, b.W, rtol=1e-12, atol=1e-15)


def test_objet_sans_restriction_chemin_uniforme_identique_a_la_forme_ancienne():
    partout = RISBERME_SUD.replace("cotes: [sud], ", "")
    mo, r_new = _plaque(TETE + OUVRAGES + partout + PHASES)
    assert mo.mode_sol == "uniforme" and len(mo.representants) == 1
    ancien = TETE + "plan:\n  contour: [[0, 0], [20, 0], [20, 12], [0, 12]]\n  cotes: { sud: 0, est: 1, nord: 2, ouest: 3 }\n" \
        + "fouille:\n  risbermes:\n    - { nom: R1, phases: [3, 3], cote_crete: -3.0, largeur_crete: 2.0, pente: 1.5, cote_pied: -6.0 }\n" + PHASES
    _, r_old = _plaque(ancien)
    for a, b in zip(r_old.phases, r_new.phases):
        np.testing.assert_allclose(a.W, b.W, rtol=1e-12, atol=1e-15)
    with pytest.raises(AssertionError):
        np.testing.assert_allclose(r_new.phases[-1].W[I_SUD], r_new.phases[-1].W[I_NORD] * 0 + 1e9)   # garde-fou du test
