"""Audit du 24 octobre 2026 — lot 3 : écarts côté insécurité rendus visibles (assemblages pondérés, valeurs de
repli non vérifiées, surcharges dans les stabilités d'ensemble, jeu d'eau en rupture, simplifications du pseudo-3D)."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from sout import normes as mod_normes
from sout.assemblages.service import verifier
from sout.materiaux.base import catalogue_par_defaut
from sout.pseudo3d.calcul import avertissements_simplifications
from sout.script.conversion import vers_modele
from sout.script.lecteur import lire_script
from sout.verifications import efforts_assemblage, executer, verif_rupture
from sout.verifs_geo import bishop
from sout.verifs_geo.surcharges_stabilite import charges_amont, q_uniforme_amont

RACINE = Path(__file__).resolve().parents[3]
EXEMPLE = (RACINE / "exemples" / "fouille_exemple_EI.yaml").read_text(encoding="utf-8")
CAT = catalogue_par_defaut()
NORMES = mod_normes.charger()
NORMES_VIDES = mod_normes.charger(mod_normes.DOSSIER / "modeles")
EFFORTS = {"N": 850.0, "V": 20.0, "M": 120.0, "T": 600.0}


# ---------------------------------------------------------------- 1. assemblages : efforts pondérés
def test_effort_d_assemblage_issu_d_un_appui_est_pondere():
    texte = EXEMPLE + "\nassemblages:\n  A1: { type: platine_about, appui: B1, lierne: HEB 300, buton: modulaire_A }\n"
    s = lire_script(texte)
    ex = executer(s, CAT, NORMES)
    H = max(x["effort"] for ph in ex.resultat.phases if ph.ok for x in ph.appuis if x["nom"] == "B1")
    g = NORMES.valeur("nf_p94_282", "combinaisons.ELU_fondamental.gamma_effets")
    e, manquants = efforts_assemblage(s, ex, s.assemblages["A1"], NORMES)
    assert manquants == []
    assert e["N"] == pytest.approx(H * 6.0 * g)            # espacement 6 m, θ = 0
    assert e["M"] == pytest.approx(0.125 * H * g * 36.0)
    # coefficient absent : efforts non pondérés signalés, vérifications non vérifiables
    e2, manquants2 = efforts_assemblage(s, ex, s.assemblages["A1"], NORMES_VIDES)
    assert e2["N"] == pytest.approx(H * 6.0) and manquants2 == ["nf_p94_282.yaml:combinaisons.ELU_fondamental.gamma_effets"]
    ex2 = executer(s, CAT, NORMES_VIDES)
    va = [v for v in ex2.verifications if v.element.startswith("A1 (")]
    assert va and all(v.etat == "non_verifiable" and v.taux is None for v in va)
    assert all("gamma_effets" in " ".join(v.manquants) for v in va)
    # efforts imposés : pris tels quels (efforts de calcul)
    s3 = lire_script(EXEMPLE + "\nassemblages:\n  A1: { type: platine_about, efforts: { N: 500 } }\n")
    assert efforts_assemblage(s3, ex, s3.assemblages["A1"], NORMES) == ({"N": 500.0}, [])


# ---------------------------------------------------------------- 2. valeurs de repli
def test_valeur_de_repli_rend_la_verification_non_verifiable():
    complet = verifier("platine_about", {"acier": "S355", "lierne": "HEB 300", "buton": "modulaire_A"}, EFFORTS, CAT, NORMES)
    assert any(v.taux is not None for v in complet)
    sans_lierne = verifier("platine_about", {"acier": "S355", "buton": "modulaire_A"}, EFFORTS, CAT, NORMES)
    assert sans_lierne and all(v.etat == "non_verifiable" and v.taux is None for v in sans_lierne)
    assert all(any("lierne" in m for m in v.manquants) for v in sans_lierne)
    acier_inconnu = verifier("platine_about", {"acier": "S999", "lierne": "HEB 300", "buton": "modulaire_A"}, EFFORTS, CAT, NORMES)
    assert all(v.etat == "non_verifiable" and any("S999" in m for m in v.manquants) for v in acier_inconnu)
    sans_base = verifier("platine_about", {"acier": "S355", "lierne": "HEB 300"}, EFFORTS, None, NORMES)
    assert all(v.etat == "non_verifiable" for v in sans_base)


# ---------------------------------------------------------------- 3. surcharges dans les stabilités d'ensemble
def _modele(surcharges: str, phase_extra: str = "") -> object:
    texte = EXEMPLE.replace("surcharges:\n  - { type: bande, q: 20, distance: 1.0, largeur: 5.0 }\n", surcharges)
    if phase_extra:
        texte = texte.replace("  - nom: Pose du buton B1\n", "  - nom: Pose du buton B1\n" + phase_extra)
    return vers_modele(lire_script(texte), CAT, NORMES)


def test_surcharge_uniforme_en_plan_comptee_comme_une_repartie():
    m_rep = _modele("surcharges:\n  - { nom: Q, type: repartie, q: 20 }\n")
    m_uni = _modele("surcharges:\n  - { nom: Q, type: uniforme, q: 20 }\n")
    assert charges_amont(m_rep) == charges_amont(m_uni) == ([(-1e6, 0.0, 20.0)], [])
    assert q_uniforme_amont(m_uni) == (20.0, [])
    ph = SimpleNamespace(terrain_amont=0.0, terrain_aval=-6.5, eau_amont=None, eau_aval=None)
    assert bishop.profil_de(m_rep, ph, None).charges == bishop.profil_de(m_uni, ph, None).charges == [(-1e6, 0.0, 20.0)]


def test_surcharges_non_modelisees_sont_listees():
    m = _modele("surcharges:\n  - { nom: Q, type: bande, q: 20, distance: 1.0, largeur: 5.0 }\n"
                "  - { nom: Ligne, type: lineique, q: 50, distance: 2.0 }\n",
                "    ajouter_surcharges: [{ nom: Q2, type: repartie, q: 10 }]\n")
    bandes, ignorees = charges_amont(m)
    assert bandes == [(-6.0, -1.0, 20.0)]
    assert any("Ligne" in x for x in ignorees) and any("Q2" in x and "Pose du buton B1" in x for x in ignorees)
    q, ign = q_uniforme_amont(m)
    assert q == 0.0 and any("bande" in x for x in ign)
    ph = SimpleNamespace(terrain_amont=0.0, terrain_aval=-6.5, eau_amont=None, eau_aval=None)
    assert bishop.profil_de(m, ph, None).charges == [(-6.0, -1.0, 20.0)]


# ---------------------------------------------------------------- 4. jeu d'eau en rupture
def test_jeu_d_eau_en_rupture_donne_un_resultat_non_ok():
    r = SimpleNamespace(phases=[SimpleNamespace(ok=True, nom="P1", message=""),
                               SimpleNamespace(ok=False, nom="P2", message="Rupture : déplacement supérieur à 5 m")])
    v = verif_rupture("crue", r)
    assert v.etat == "non_ok" and v.taux is None and v.phase == "P2"
    assert "crue" in v.detail and "Rupture" in v.detail
    assert verif_rupture(None, SimpleNamespace(phases=[])).phase is None


# ---------------------------------------------------------------- 5. pseudo-3D : simplifications annoncées
def test_pseudo3d_annonce_ses_simplifications():
    phases = [SimpleNamespace(nom="A", depuis=None), SimpleNamespace(nom="B", depuis=None), SimpleNamespace(nom="C", depuis="A")]
    modele = SimpleNamespace(hydraulique={"regime": "differences_finies"}, phases=phases)
    res = SimpleNamespace(phases=[SimpleNamespace(ok=True, nom="A", message=""), SimpleNamespace(ok=False, nom="C", message="Rupture")],
                          complet=False)
    av = avertissements_simplifications(modele, res, n_jeux=2)
    assert any("écoulement" in a for a in av) and any("branche" in a for a in av)
    assert any("jeu d'eau principal" in a for a in av) and any("interrompu à la phase « C »" in a for a in av)
    modele2 = SimpleNamespace(hydraulique=None, phases=phases[:2])
    res2 = SimpleNamespace(phases=[SimpleNamespace(ok=True, nom="A", message="")], complet=True)
    assert avertissements_simplifications(modele2, res2) == []
