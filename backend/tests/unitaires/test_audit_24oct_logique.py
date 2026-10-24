"""Audit du 24 octobre 2026 — lot 2 : erreurs de logique (côté concerné, bouchon, fiche discontinue à EI
imposé, classe de section, contrôles du lecteur, normes nulles, synthèse projet, emprise)."""
from pathlib import Path

import pytest

from sout import normes as mod_normes
from sout.hydraulique.bouchons import Bouchon
from sout.materiaux.base import catalogue_par_defaut
from sout.normes import Normes, ValeurNormeManquante
from sout.plan.geometrie import cote_concerne
from sout.script.conversion import ErreurConversion, vers_modele
from sout.script.coupes import synthese_projet
from sout.script.lecteur import ScriptInvalide, lire_script
from sout.sol.terrain import CoupeCalcul, ErreurTerrain, SurchargePlan, delta_sigma_v_plan
from sout.verifs_struct.elements import _classe_section

RACINE = Path(__file__).resolve().parents[3]
EXEMPLE = (RACINE / "exemples" / "fouille_exemple_EI.yaml").read_text(encoding="utf-8")


def _erreurs(texte):
    with pytest.raises(ScriptInvalide) as ex:
        lire_script(texte)
    return [e.message for e in ex.value.erreurs]


def _coupe(k, cote=None):
    return CoupeCalcul(x=0.0, y=0.0, ni=(0.0, 1.0), t=(1.0, 0.0), k=k, cote=cote)


# ---------------------------------------------------------------- 1. côté concerné
def test_cote_concerne_accepte_le_numero_d_arete_et_le_nom():
    assert cote_concerne(None, _coupe(0))
    assert cote_concerne(("#0",), None)
    assert cote_concerne(("#0",), _coupe(0))            # forme « #k » : était ignorée par les surcharges en plan
    assert not cote_concerne(("#1",), _coupe(0))
    assert cote_concerne(("nord",), _coupe(2, "nord"))
    assert not cote_concerne(("nord",), _coupe(2, "sud"))
    assert not cote_concerne(("nord",), _coupe(2, None))


def test_surcharge_en_plan_limitee_a_une_arete_par_numero_est_appliquee():
    z = [-1.0, -3.0]
    s = SurchargePlan("q", "uniforme", 20.0, cotes_paroi=("#0",))
    assert delta_sigma_v_plan(s, z, 0.0, _coupe(0)).max() > 0
    assert delta_sigma_v_plan(s, z, 0.0, _coupe(1)).max() == 0


# ---------------------------------------------------------------- 2. bouchon « à partir de »
def test_bouchon_actif_a_partir_de_la_phase():
    b = Bouchon("injecte", -8.0, -10.0, phase=2)
    assert not b.actif(1, "a") and b.actif(2, "b") and b.actif(3, "c")
    b = Bouchon("injecte", -8.0, -10.0, phase="b")      # nom non résolu : actif à partir de la phase de ce nom
    assert not b.actif(1, "a") and b.actif(2, "b") and b.actif(3, "c")


def test_nom_de_phase_du_bouchon_resolu_en_indice_a_la_conversion():
    texte = EXEMPLE + "\nhydraulique:\n  bouchon: { type: injecte, toit: -8, base: -10, phase: Pose du buton B1 }\n"
    s = lire_script(texte)
    m = vers_modele(s, catalogue_par_defaut(), mod_normes.charger())
    assert m.hydraulique["bouchon"]["phase"] == 2
    assert any("inconnue" in m for m in _erreurs(texte.replace("phase: Pose du buton B1", "phase: Phase fantôme")))
    assert any("hors de" in m for m in _erreurs(texte.replace("phase: Pose du buton B1", "phase: 9")))


# ---------------------------------------------------------------- 3. fiche discontinue à EI imposé
def _berlinoise(extra: str) -> str:
    return EXEMPLE.replace("paroi:\n  type: palplanche\n  EI: 110000            # kN·m²/m\n",
                           "paroi:\n  type: berlinoise\n  EI: 110000\n" + extra)


def test_berlinoise_a_ei_impose_sans_largeur_de_fiche_est_refusee():
    cat, nor = catalogue_par_defaut(), mod_normes.charger()
    with pytest.raises(ErreurConversion) as ex:
        vers_modele(lire_script(_berlinoise("  entraxe: 2.0\n")), cat, nor)
    assert "largeur_reaction_fiche" in str(ex.value)
    with pytest.raises(ErreurConversion) as ex:
        vers_modele(lire_script(_berlinoise("")), cat, nor)
    assert "entraxe" in str(ex.value)
    m = vers_modele(lire_script(_berlinoise("  entraxe: 2.0\n  largeur_reaction_fiche: 0.6\n")), cat, nor)
    assert m.ecran.infos["rapport_largeur_fiche"] == pytest.approx(0.3)
    assert m.ecran.largeur_reaction is not None


# ---------------------------------------------------------------- 4. classe de section
def test_classe_de_section_lue_en_texte():
    assert _classe_section("2") == 2 and _classe_section("2.0") == 2 and _classe_section(2.0) == 2
    assert _classe_section(4) == 4 and _classe_section(None) is None and _classe_section("") is None
    assert _classe_section("classe inconnue") is None


# ---------------------------------------------------------------- 5. contrôles du lecteur
def test_phases_homonymes_refusees():
    texte = EXEMPLE.replace("nom: Terrassement final et pompage", "nom: Pose du buton B1")
    assert any("s'appellent" in m for m in _erreurs(texte))


def test_re_pose_d_un_appui_deja_pose_refusee():
    texte = EXEMPLE.replace("  - nom: Terrassement final et pompage\n", "  - nom: Terrassement final et pompage\n    poser: B1\n")
    assert any("déjà posé" in m for m in _erreurs(texte))
    # déposer puis reposer reste permis
    texte2 = EXEMPLE.replace("  - nom: Terrassement final et pompage\n",
                             "  - nom: Dépose\n    deposer: B1\n  - nom: Terrassement final et pompage\n    poser: B1\n")
    assert lire_script(texte2).phases[-1].poser == "B1"


# ---------------------------------------------------------------- 6. valeur de norme nulle
def test_valeur_de_norme_nulle_traitee_comme_manquante():
    n = Normes({"ec3": {"gamma_M0": {"valeur": 0, "source": "test"}, "gamma_M1": 1.0, "nul": 0.0}})
    assert n.valeur("ec3", "gamma_M1") == 1.0
    with pytest.raises(ValeurNormeManquante) as ex:
        n.valeur("ec3", "gamma_M0")
    assert "nulle" in str(ex.value)
    with pytest.raises(ValeurNormeManquante):
        n.valeur("ec3", "nul")


# ---------------------------------------------------------------- 7. synthèse projet
def test_synthese_projet_un_non_ok_sans_taux_n_est_pas_masque():
    v_ok = {"nom": "Pieux — flexion", "element": "pieux", "etat": "ok", "taux": 0.5, "phase": "P", "detail": ""}
    v_ko = {"nom": "Pieux — flexion", "element": "pieux", "etat": "non_ok", "taux": None, "phase": "P", "detail": ""}
    v_nv = {"nom": "Pieux — flexion", "element": "pieux", "etat": "non_verifiable", "taux": None, "phase": "P", "detail": ""}
    s = synthese_projet({"C1": [v_ok], "C2": [v_ko], "C3": [v_nv]})
    assert len(s) == 1 and s[0]["coupe"] == "C2" and s[0]["etat"] == "non_ok"
    s = synthese_projet({"C1": [v_ok], "C3": [v_nv]})
    assert s[0]["coupe"] == "C1"


# ---------------------------------------------------------------- 8. emprise nulle
def test_emprise_nulle_refusee():
    s = SurchargePlan("grue", "ponctuelle", 3000.0, emprise=(0.0, 2.0), position=(0.0, 5.0))
    with pytest.raises(ErreurTerrain) as ex:
        delta_sigma_v_plan(s, [-1.0], 0.0, _coupe(0))
    assert "emprise" in str(ex.value)
