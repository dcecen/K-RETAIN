"""Géométrie du terrain (sol/terrain.py, étape 9) : risbermes, talus, gradins côté fouille,
terrain en pente côté terre (Coulomb avec β, surcharge équivalente), remblai à une phase."""
import math
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from sout import api, normes
from sout.materiaux.base import catalogue_par_defaut
from sout.noyau.phasage import calculer
from sout.script.conversion import ErreurConversion, vers_modele
from sout.script.lecteur import ScriptInvalide, lire_script
from sout.sol import coefficients as coef
from sout.sol.terrain import ObjetTerrain, bandes_equivalentes, profil_gradins, profil_risberme

RACINE = Path(__file__).resolve().parents[3]
BASE = (RACINE / "exemples" / "fouille_exemple.yaml").read_text(encoding="utf-8")
CAT, NRM = catalogue_par_defaut(), normes.charger()

PHASES_10 = """
phases:
  - { nom: P1, excaver: -1.0 }
  - { nom: P2, excaver: -2.0 }
  - { nom: P3, poser: B1 }
  - { nom: P4, excaver: -3.0 }
  - { nom: P5, excaver: -4.0 }
  - { nom: P6, excaver: -6.5, eau: { aval: -7.0 } }
  - { nom: P7 }
  - { nom: P8 }
  - { nom: P9 }
  - { nom: P10 }
"""


def _script_10(bloc_fouille: str = "") -> str:
    s = BASE[:BASE.index("phases:")] + PHASES_10 + "\nverifications: [butee]\n" + bloc_fouille
    return s


def test_coulomb_avec_talus_beta_10_superieur_au_cas_horizontal():
    ka0 = coef.ka_coulomb(30.0, 0.0)
    ka10 = coef.ka_coulomb_talus(30.0, 0.0, 10.0)
    assert ka10 > ka0
    assert coef.ka_coulomb_talus(30.0, 0.0, 0.0) == pytest.approx(ka0, rel=1e-12)
    # à la main (φ = 30°, δ = 0, β = 10°) : √(sin φ·sin(φ−β)/cos β) = √(0,5·0,3420/0,9848) = 0,4167 ;
    # Ka = cos²φ / (1 + 0,4167)² = 0,75 / 2,0071 = 0,3737
    racine = math.sqrt(math.sin(math.radians(30)) * math.sin(math.radians(20)) / math.cos(math.radians(10)))
    assert ka10 == pytest.approx(0.75 / (1 + racine) ** 2, rel=1e-9)
    assert ka10 == pytest.approx(0.3737, abs=0.0005)
    assert coef.ka_coulomb_talus(30.0, 20.0, 10.0) > coef.ka_coulomb_talus(30.0, 20.0, 0.0)
    with pytest.raises(ValueError):
        coef.ka_coulomb_talus(30.0, 0.0, 35.0)


def test_profils_et_bandes_equivalentes():
    p = profil_risberme(cote_crete=-3.0, largeur_crete=2.0, pente=1.5, cote_pied=-6.0)
    assert p[0] == (0.0, -3.0) and p[1] == (2.0, -3.0) and p[2] == (2.0 + 4.5, -6.0)
    o = ObjetTerrain("R1", "risberme", "aval", p, base=-6.0, gamma=18.0, pas=0.5)
    assert o.hauteur(1.0) == pytest.approx(3.0) and o.hauteur(2.0 + 2.25) == pytest.approx(1.5) and o.hauteur(10.0) == 0
    b = bandes_equivalentes(o)
    assert all(x.cote == -6.0 and x.cote_ecran == "aval" and x.type == "bande" for x in b)
    assert b[0].q == pytest.approx(18.0 * 3.0) and max(x.q for x in b) == pytest.approx(54.0)
    # le poids total des bandes vaut le poids du volume (crête 2 m + triangle 4,5 × 3 / 2) × γ
    assert sum(x.q * x.largeur for x in b) == pytest.approx(18.0 * (2 * 3 + 4.5 * 3 / 2), rel=0.03)
    g = profil_gradins([(-2.0, 4.0), (-4.0, 4.0)], -6.0)
    assert g[:4] == ((0.0, -2.0), (4.0, -2.0), (4.0, -4.0), (8.0, -4.0))
    with pytest.raises(Exception):
        profil_gradins([(-7.0, 2.0)], -6.0)


def test_risberme_phases_6_a_9_modifie_la_butee_sur_ces_phases_seulement():
    sans = _script_10()
    avec = _script_10("""
fouille:
  risbermes:
    - { nom: R1, phases: [6, 9], cote_crete: -3.5, largeur_crete: 2.0, pente: 1.5, cote_pied: -6.5 }
""")
    api.vider_cache_coupes()
    client = TestClient(api.app)
    r0 = client.post("/api/calcul", json={"texte": sans}).json()
    r1 = client.post("/api/calcul", json={"texte": avec}).json()
    assert r0["ok"] and r1["ok"], (r0["erreurs"], r1["erreurs"])
    # indices : 0 = état initial, k = phase k ; risberme présente aux phases 6 à 9
    for k in range(11):
        y0 = r0["resultats"]["phases"][k]["synthese"]["y_max_mm"]
        y1 = r1["resultats"]["phases"][k]["synthese"]["y_max_mm"]
        pp0 = r0["resultats"]["phases"][k]["pressions"]["aval"]["pp"]
        pp1 = r1["resultats"]["phases"][k]["pressions"]["aval"]["pp"]
        if 6 <= k <= 9:
            assert max(pp1) > max(pp0) + 1.0, k          # butée limite augmentée par la risberme
            assert y1 < y0, k                             # paroi moins déplacée
            assert "pp_sans_terrain" in r1["resultats"]["phases"][k]
            assert np.allclose(r1["resultats"]["phases"][k]["pp_sans_terrain"], pp0, rtol=1e-6, atol=1e-6)
        else:
            assert np.allclose(pp1, pp0, rtol=1e-9, atol=1e-9), k
            assert "pp_sans_terrain" not in r1["resultats"]["phases"][k]
    # phases 1 à 5 et 10 : résultats identiques (y compris ressorts : déplacements égaux) — la phase 10 repart avec la mémoire
    for k in range(6):
        assert r1["resultats"]["phases"][k]["synthese"]["y_max_mm"] == pytest.approx(r0["resultats"]["phases"][k]["synthese"]["y_max_mm"], rel=1e-9)
    obj = r1["resultats"]["maquette"]["terrain"]["objets"]
    assert obj[0]["nom"] == "R1" and obj[0]["phase_debut"] == 6 and obj[0]["phase_fin"] == 9 and obj[0]["methode"] == "surcharge_equivalente"
    assert any("mise en place de R1" in a["texte"] for a in r1["resultats"]["phases"][6]["actions"])
    assert any("terrassement de R1" in a["texte"] for a in r1["resultats"]["phases"][10]["actions"])
    assert all(not x["nom"].startswith("~") for x in r1["resultats"]["maquette"]["surcharges"])


def test_terrasser_risberme_fond_equivalent_coin_refuse_et_controles():
    avec = _script_10("""
fouille:
  talus:
    - { nom: T1, phases: [6, 10], cote_crete: -4.0, largeur_banquette: 1.0, pente: 2.0, cote_pied: -6.5 }
""").replace("  - { nom: P8 }", "  - { nom: P8, terrasser_risberme: T1 }")
    m = vers_modele(lire_script(avec), CAT, NRM)
    o = m.terrain_objets[0]
    assert o.type == "talus" and o.phase_fin == 7 and o.profil[1] == (1.0, -4.0)
    assert any(n.startswith("~terrain:T1") for n in m.phases[7].retirer_surcharges)    # retirées à la phase 8
    # fond équivalent : fond relevé à la cote choisie pendant la vie de la risberme
    fe = _script_10("""
fouille:
  risbermes:
    - { nom: R1, phases: [6, 9], cote_crete: -3.5, pente: 1.5, cote_pied: -6.5, methode: fond_equivalent, cote_equivalente: -5.0 }
""")
    m2 = vers_modele(lire_script(fe), CAT, NRM)
    assert m2.phases[5].excaver == -5.0 and m2.phases[9].excaver == -6.5
    assert not any(s.nom.startswith("~terrain") for p in m2.phases for s in p.ajouter_surcharges)
    with pytest.raises(ScriptInvalide):
        lire_script(_script_10("""
fouille:
  risbermes:
    - { nom: R1, phases: [6, 9], cote_crete: -3.5, pente: 1.5, cote_pied: -6.5, methode: fond_equivalent }
"""))
    # coin de rupture : TODO-NORME, refusé au calcul
    cr = _script_10("""
fouille:
  risbermes:
    - { nom: R1, phases: [6, 9], cote_crete: -3.5, pente: 1.5, cote_pied: -6.5, methode: coin_de_rupture }
""")
    with pytest.raises(ErreurConversion, match="TODO-NORME"):
        vers_modele(lire_script(cr), CAT, NRM)
    # fond au-dessus du pied à la phase de mise en place : refusé
    with pytest.raises(ErreurConversion, match="au-dessus du pied"):
        vers_modele(lire_script(_script_10("""
fouille:
  risbermes:
    - { nom: R1, phases: [2, 3], cote_crete: -1.0, pente: 1.5, cote_pied: -6.5 }
""")), CAT, NRM)


def test_terrain_en_pente_beta_et_profil_en_surcharge_equivalente():
    pente = BASE.replace("eau:\n", "terrain: { pente_beta: 10 }\neau:\n")
    m = vers_modele(lire_script(pente), CAT, NRM)
    assert m.beta_amont == 10
    r_ref = calculer(vers_modele(lire_script(BASE), CAT, NRM))
    r_b = calculer(m)
    assert abs(r_b.phases[-2].y).max() > abs(r_ref.phases[-2].y).max()      # poussée accrue par le talus
    with pytest.raises(ScriptInvalide):
        lire_script(BASE.replace("eau:\n", "terrain: { pente_beta: 40 }\neau:\n"))        # β > φ' (28°)
    profil = BASE.replace("eau:\n", "terrain: { profil: [[0, 0], [6, 0], [20, 3.5], [40, 3.5]] }\neau:\n")
    m2 = vers_modele(lire_script(profil), CAT, NRM)
    o = m2.terrain_objets[0]
    assert o.type == "pente" and o.face == "amont" and o.base == 0.0
    assert o.hauteur(13.0) == pytest.approx(1.75) and o.hauteur(3.0) == 0
    assert len(m2.surcharges) > 1 and all(s.cote_ecran == "amont" for s in m2.surcharges[1:])
    r_p = calculer(m2)
    assert abs(r_p.phases[-2].y).max() > abs(r_ref.phases[-2].y).max()
    # profil en coulomb_beta avec trois points : refusé ; deux points : β déduit
    with pytest.raises(ScriptInvalide):
        lire_script(BASE.replace("eau:\n", "terrain: { profil: [[0, 0], [6, 0], [20, 3.5]], methode_pente: coulomb_beta }\neau:\n"))
    m3 = vers_modele(lire_script(BASE.replace("eau:\n", "terrain: { profil: [[0, 0], [20, 3.5]], methode_pente: coulomb_beta }\neau:\n")), CAT, NRM)
    assert m3.beta_amont == pytest.approx(math.degrees(math.atan2(3.5, 20)))


def test_remblai_a_une_phase_ajoute_une_couche():
    rb = BASE.replace("eau:\n", "terrain: { remblai: { cote: 1.5, materiau: Sable dense, phase: 2 } }\neau:\n")
    m = vers_modele(lire_script(rb), CAT, NRM)
    assert m.couches[0].nom.startswith("Remblai") and m.couches[0].toit == 1.5 and m.couches[0].phi == 35
    assert m.phases[1].remblayer_amont == 1.5 and m.phases[0].remblayer_amont is None
    r = calculer(m)
    assert r.phases[2].terrain_amont == 1.5 and r.phases[1].terrain_amont == 0.0
    with pytest.raises(ScriptInvalide):
        lire_script(BASE.replace("eau:\n", "terrain: { remblai: { cote: 1.5, materiau: Inconnu, phase: 2 } }\neau:\n"))


def test_non_regression_sans_objet_de_terrain():
    api.vider_cache_coupes()
    r = TestClient(api.app).post("/api/calcul", json={"texte": BASE}).json()
    assert r["resultats"]["dimensionnant"]["deplacement"]["valeur_mm"] == pytest.approx(17.6472, rel=1e-3)
    assert r["resultats"]["maquette"]["terrain"]["objets"] == [] and r["resultats"]["maquette"]["terrain"]["pente_beta"] is None
