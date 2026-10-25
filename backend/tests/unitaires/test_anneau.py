"""Paroi circulaire : anneau comprimé axisymétrique (sout/parois/anneau.py, moteur 2D, vérifications).

Références : Timoshenko & Woinowsky-Krieger, Theory of Plates and Shells, ch. 15 § 114 (D·w'''' + E·h/a²·w = Z,
N_θ = E·h·w/a) ; Hetényi (1946), Beams on Elastic Foundation (poutre semi-infinie, force à l'extrémité) ;
Timoshenko & Gere, Theory of Elastic Stability, ch. 7 (q_cr = 3·E·I/R³). Les coefficients partiels viennent de
docs/normes (aucune valeur ajoutée par ces tests).
"""
import math
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from sout.api import app
from sout.parois.anneau import (Anneau, ErreurAnneau, construire_anneau, contour_polygone, longueur_tributaire,
                                nombre_cotes_polygone, pression_critique_tube, raideurs_nodales)
from sout.script.lecteur import ScriptInvalide, lire_script

CLIENT = TestClient(app)
E13 = (Path(__file__).resolve().parents[3] / "exemples" / "elementaires" / "2d" / "E13_hetenyi_force_en_tete.yaml").read_text(encoding="utf-8")
PAROI_E13 = "paroi: { type: palplanche, EI: 1.0e5, tete: 0.0, pied: -30.0 }"


class _P:
    """Paroi minimale pour construire_anneau (attributs du schéma)."""
    def __init__(self, **kw):
        base = dict(forme="circulaire", rayon=6.0, type="pieux_secants", tete=0.0, pied=-16.0, epaisseur=None, diametre=0.8,
                    entraxe=0.6, epaisseur_anneau=None, tolerance_verticalite=0.0)
        base.update(kw)
        self.__dict__.update(base)


# --------------------------------------------------------------------------- 1. géométrie et formules de l'anneau
def test_epaisseur_raideur_et_effort_normal_de_l_anneau():
    a = construire_anneau(_P(), 3.3e7)
    z = np.array([0.0, -8.0, -16.0])
    np.testing.assert_allclose(a.t(z), math.sqrt(0.8**2 - 0.6**2), rtol=1e-12)        # corde commune √(D² − e²)
    np.testing.assert_allclose(a.k(z), 3.3e7 * a.t(z) / 36.0, rtol=1e-12)              # k = E·t/R²
    w = np.array([1e-3, 2e-3, -1e-3])
    np.testing.assert_allclose(a.N(z, w), 6.0 * a.k(z) * w, rtol=1e-12)                # N_θ = R·k·w (chaudronnier)
    # tolérance de verticalité : entraxe effectif e + 2·tol·profondeur, l'anneau s'amincit vers le pied
    b = construire_anneau(_P(tolerance_verticalite=0.005), 3.3e7)
    assert b.t(np.array([-16.0]))[0] == pytest.approx(math.sqrt(0.8**2 - (0.6 + 2 * 0.005 * 16) ** 2), rel=1e-12)
    # paroi moulée : épaisseur de la paroi ; epaisseur_anneau imposée prioritaire
    assert construire_anneau(_P(type="paroi_moulee", epaisseur=0.8), 3e7).t(np.array([-3.0]))[0] == 0.8
    assert construire_anneau(_P(epaisseur_anneau=0.4), 3e7).t(np.array([-3.0]))[0] == 0.4
    assert construire_anneau(_P(forme="plane"), 3e7) is None


def test_refus_anneau_non_traite_ou_discontinu():
    with pytest.raises(ErreurAnneau, match="palplanche"):
        construire_anneau(_P(type="palplanche"), 2.1e8)
    with pytest.raises(ErreurAnneau, match="rayon"):
        construire_anneau(_P(rayon=None), 3e7)
    with pytest.raises(ErreurAnneau, match="recouvrement"):
        construire_anneau(_P(tolerance_verticalite=0.01), 3e7)     # e(−16) = 0,6 + 0,32 = 0,92 > D


def test_raideurs_nodales_trapezes_et_polygone():
    z = np.array([-4.0, -3.0, -1.0, 0.0])
    np.testing.assert_allclose(longueur_tributaire(z), [0.5, 1.5, 1.5, 0.5])
    a = Anneau(rayon=5.0, E=2.5e7, tete=0.0, epaisseur=0.5)
    np.testing.assert_allclose(raideurs_nodales(a, z), 2.5e7 * 0.5 / 25.0 * np.array([0.5, 1.5, 1.5, 0.5]))
    assert nombre_cotes_polygone(6.0, 0.5) == math.ceil(2 * math.pi * 6 / 0.5) and nombre_cotes_polygone(1.0, 2.0) == 24
    c = contour_polygone(6.0, 24)
    assert len(c) == 24 and all(abs(math.hypot(x, y) - 6.0) < 1e-12 for x, y in c)


def test_pression_critique_du_tube_long():
    E, t, R = 3.3e7, 0.5, 6.0
    assert pression_critique_tube(E, t, R) == pytest.approx(E * t**3 / (4 * R**3), rel=1e-12)
    D = E * t**3 / (12 * (1 - 0.2**2))
    assert pression_critique_tube(E, t, R, nu=0.2) == pytest.approx(3 * D / R**3, rel=1e-12)


# --------------------------------------------------------------------------- 2. moteur 2D
def _circulaire(rayon: float) -> str:
    return E13.replace(PAROI_E13, "paroi: { type: paroi_moulee, EI: 1.0e5, beton: C30/37, epaisseur: 0.5, tete: 0.0, pied: -30.0, "
                                  f"forme: circulaire, rayon: {rayon} }}")


def _calcul(texte: str) -> dict:
    r = CLIENT.post("/api/calcul", json={"texte": texte}).json()
    assert r["ok"], r.get("erreurs")
    return r["resultats"]


def test_force_en_tete_hetenyi_avec_le_module_de_l_anneau():
    """E13 (force F0 = 10 kN/m en tête d'une poutre semi-infinie sur Winkler) en paroi circulaire : l'anneau ajoute
    E·t/R² au module de la fondation (Timoshenko § 114) ; y(0) = 2·F0·λ/k et |M| max = 0,3224·F0/λ avec
    k = 2·kh + E·t/R², λ = (k/4EI)^¼ (Hetényi) à 5 %."""
    res = _calcul(_circulaire(50.0))
    ph = res["phases"][1]
    E = res["paroi"]["anneau"]["E"]
    k = 2 * 20000.0 + E * 0.5 / 50.0**2
    lam = (k / (4 * 1e5)) ** 0.25
    assert abs(ph["y_mm"][-1]) / 1000 == pytest.approx(2 * 10.0 * lam / k, rel=0.05)
    assert np.max(np.abs(ph["M"])) == pytest.approx(0.3224 * 10.0 / lam, rel=0.05)
    assert abs(ph["synthese"]["bilan"]["relatif"]) < 1e-9
    # l'anneau est bien plus raide que le sol : la flèche diminue nettement par rapport à la paroi plane
    plane = _calcul(E13)["phases"][1]
    assert abs(ph["y_mm"][-1]) < abs(plane["y_mm"][-1])


def test_grand_rayon_retrouve_la_paroi_plane():
    """R → ∞ : k = E·t/R² → 0, les résultats tendent vers ceux de la paroi plane (1e-6 relatif, R = 1e5 m, posé sur le
    modèle de calcul : le script borne le rayon à 500 m)."""
    from sout.materiaux.base import catalogue_par_defaut
    from sout.noyau.phasage import calculer
    from sout.script.conversion import vers_modele
    m = vers_modele(lire_script(_circulaire(50.0)), catalogue_par_defaut())
    plane = calculer(vers_modele(lire_script(E13), catalogue_par_defaut())).phases[1]
    m.ecran.anneau = Anneau(rayon=1.0e5, E=m.ecran.anneau.E, tete=0.0, epaisseur=0.5)
    circ = calculer(m).phases[1]
    np.testing.assert_allclose(circ.y, plane.y, rtol=1e-6, atol=1e-12)
    np.testing.assert_allclose(circ.M, plane.M, rtol=1e-6, atol=1e-6)
    assert np.sum(np.abs(circ.anneau["reaction"])) < 1e-6 * 10.0          # force reprise par l'anneau négligeable devant F0


def test_lecteur_paroi_circulaire():
    def erreurs(paroi: str) -> str:
        with pytest.raises(ScriptInvalide) as ex:
            lire_script(E13.replace(PAROI_E13, paroi))
        return " | ".join(e.message for e in ex.value.erreurs)
    assert "rayon obligatoire" in erreurs("paroi: { type: paroi_moulee, EI: 1.0e5, beton: C30/37, epaisseur: 0.5, tete: 0.0, pied: -30.0, forme: circulaire }")
    assert "TODO-SOURCE" in erreurs("paroi: { type: palplanche, EI: 1.0e5, tete: 0.0, pied: -30.0, forme: circulaire, rayon: 6.0 }")
    assert "beton obligatoire" in erreurs("paroi: { type: paroi_moulee, EI: 1.0e5, epaisseur: 0.5, tete: 0.0, pied: -30.0, forme: circulaire, rayon: 6.0 }")
    assert "plus de recouvrement" in erreurs("paroi: { type: pieux_secants, beton: C30/37, diametre: 0.8, entraxe: 0.6, tete: 0.0, pied: -30.0, "
                                             "forme: circulaire, rayon: 6.0, tolerance_verticalite: 0.005 }")
    assert "sans effet" in erreurs("paroi: { type: palplanche, EI: 1.0e5, tete: 0.0, pied: -30.0, rayon: 6.0 }")
