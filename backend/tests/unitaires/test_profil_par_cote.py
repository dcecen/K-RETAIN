"""Profil par côté (lot 1 du 25/10/2026).

- Pseudo-3D fouille fermée : un objet de terrain rattaché à un côté (risberme `cote_paroi`) ne charge que les
  lignes verticales de ce côté (bandes `SurchargePlan` filtrées par ligne) ; avec Ds = 0, la ligne du côté sud
  est l'écran 2D calculé avec la risberme et la ligne du côté nord l'écran 2D sans.
- Coupes automatiques (`calcul.coupes_automatiques`) : une coupe 2D par côté dès que des données dépendent du
  côté ; géométrie uniforme = coupe unique, texte identique.
- Coupe 2D : fond équivalent et pente côté terre rattachés à un autre côté restent sans effet ; refus explicites
  en pseudo-3D fouille fermée (fond et coefficients uniques sur le contour).
- Filtre par tronçon (`objet_concerne`, `effet_butee`).
"""
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient

from sout import api, normes
from sout.materiaux.base import catalogue_par_defaut
from sout.noyau.phasage import calculer
from sout.plan.geometrie import objet_concerne
from sout.pseudo3d.calcul import moteur_depuis_script
from sout.script.conversion import ErreurConversion, vers_modele
from sout.script.coupes import preparer
from sout.script.lecteur import lire_script
from sout.sol.surcharges import Surcharge
from sout.sol.terrain import CoupeCalcul, ObjetTerrain, SurchargePlan, bandes_equivalentes, effet_butee, profil_risberme

RACINE = Path(__file__).resolve().parents[3]
CAT, NRM = catalogue_par_defaut(), normes.charger()
BASE = (RACINE / "exemples" / "fouille_exemple.yaml").read_text(encoding="utf-8")
BLOC_PLAN = """
plan:
  contour: [[0, 0], [20, 0], [20, 12], [0, 12]]
  cotes: { long_sud: 0, court_est: 1, long_nord: 2, court_ouest: 3 }
"""
RISBERME_SUD = """
fouille:
  risbermes:
    - { nom: R1, cote_paroi: long_sud, phases: [3, 3], cote_crete: -4.0, largeur_crete: 2.0, pente: 1.5, cote_pied: -6.5 }
"""
COUPE_SUD = "coupe_calcul: { x: 10, y: 0, ni: [0, 1], t: [1, 0], k: 0, s: 10, cote: long_sud }\n"
COUPE_NORD = "coupe_calcul: { x: 10, y: 12, ni: [0, -1], t: [-1, 0], k: 2, s: 10, cote: long_nord }\n"

# Fouille fermée 20 × 12 sans appui, Ds = 0 : chaque ligne verticale est un écran 2D indépendant.
P3D = """
projet: Risberme sur le seul côté sud
calcul: { kh: impose, mode: pseudo3d, pas: 0.25 }
paroi: { type: paroi_moulee, EI: 100000, tete: 0.0, pied: -12.0 }
sol:
  - { nom: Sable, toit: 0.0, gamma: 20, gamma_dejauge: 10, phi: 32, c: 0, kh: 12000 }
eau: { service: { amont: null, aval: null } }
fouille:
  risbermes:
    - { nom: R1, cote_paroi: sud, phases: [3, 3], cote_crete: -3.0, largeur_crete: 2.0, pente: 1.5, cote_pied: -6.0 }
phases:
  - { nom: Exc1, excaver: -2.0 }
  - { nom: P2 }
  - { nom: Exc2, excaver: -6.0 }
pseudo3d: { pas_horizontal: 1.0, rapport_rigidite_horizontale: 0 }
plan:
  contour: [[0, 0], [20, 0], [20, 12], [0, 12]]
  cotes: { sud: 0, est: 1, nord: 2, ouest: 3 }
"""


def _auto(texte: str) -> str:
    return texte.replace("calcul:\n", "calcul:\n  coupes_automatiques: true\n", 1)


def _2d(texte: str, avec_risberme: bool) -> str:
    """Version 2D du script P3D : sans plan ni pseudo3d ; risberme sur toute la paroi ou absente."""
    t = texte.replace("mode: pseudo3d, ", "").replace("cote_paroi: sud, ", "")
    t = t[:t.index("pseudo3d:")]
    if not avec_risberme:
        t = t[:t.index("\nfouille:")] + t[t.index("\nphases:"):]
    return t


@pytest.fixture(autouse=True)
def _cache_vide():
    api.vider_cache_coupes()
    yield
    api.vider_cache_coupes()


# ---------------------------------------------------------------------------
# bandes équivalentes et filtre par tronçon
# ---------------------------------------------------------------------------
def test_bandes_historiques_sans_cote_et_surcharges_plan_avec_cote_ou_troncon():
    p = profil_risberme(-3.0, 2.0, 1.5, -6.0)
    sans = bandes_equivalentes(ObjetTerrain("R", "risberme", "aval", p, base=-6.0, gamma=18.0))
    avec = bandes_equivalentes(ObjetTerrain("R", "risberme", "aval", p, base=-6.0, gamma=18.0, cotes_paroi=("sud",)))
    tron = bandes_equivalentes(ObjetTerrain("R", "risberme", "aval", p, base=-6.0, gamma=18.0, troncon=(4.0, 12.0)))
    assert all(isinstance(b, Surcharge) for b in sans) and all(isinstance(b, SurchargePlan) for b in avec + tron)
    assert len(sans) == len(avec) == len(tron) > 3
    for a, b in zip(sans, avec):
        assert (a.nom, a.type, a.q, a.distance, a.largeur, a.cote, a.cote_ecran) == (b.nom, b.type, b.q, b.distance, b.largeur, b.cote, b.cote_ecran)
    assert avec[0].cotes_paroi == ("sud",) and avec[0].emprise is None
    assert tron[0].emprise == (4.0, 12.0) and tron[0].cotes_paroi is None


def test_objet_concerne_par_cote_et_tronçon():
    c7 = CoupeCalcul(x=7, y=0, ni=(0, 1), t=(1, 0), k=0, s=7.0, cote="sud")
    c12 = CoupeCalcul(x=12, y=0, ni=(0, 1), t=(1, 0), k=0, s=12.0, cote="sud")
    assert objet_concerne(None, None, c7) and objet_concerne(("sud",), (5.0, 10.0), None)
    assert objet_concerne(("sud",), (5.0, 10.0), c7) and not objet_concerne(("sud",), (5.0, 10.0), c12)
    assert not objet_concerne(("nord",), None, c7) and objet_concerne(("#0",), (10.0, 5.0), c7)


def test_effet_butee_limite_au_troncon():
    p = profil_risberme(-3.0, 2.0, 1.5, -6.0)
    o = ObjetTerrain("R", "risberme", "aval", p, base=-6.0, gamma=18.0, cotes_paroi=("sud",), troncon=(5.0, 10.0))
    z = np.linspace(-12.0, -6.0, 25)
    kph = np.full_like(z, 3.0)
    dedans = CoupeCalcul(x=7, y=0, ni=(0, 1), t=(1, 0), k=0, s=7.0, cote="sud")
    dehors = CoupeCalcul(x=12, y=0, ni=(0, 1), t=(1, 0), k=0, s=12.0, cote="sud")
    assert effet_butee([o], kph, z, -6.0, dedans).max() > 1.0
    assert np.all(effet_butee([o], kph, z, -6.0, dehors) == 0.0)


# ---------------------------------------------------------------------------
# pseudo-3D fouille fermée : objet d'un seul côté rapporté ligne par ligne
# ---------------------------------------------------------------------------
def test_risberme_sur_le_seul_cote_sud_en_fouille_fermee():
    s = lire_script(P3D)
    m = vers_modele(s, CAT, NRM)
    bandes = m.phases[2].ajouter_surcharges
    assert bandes and all(isinstance(b, SurchargePlan) and b.cotes_paroi == ("sud",) for b in bandes)
    mo = moteur_depuis_script(SimpleNamespace(script=s, modele=m))
    assert mo.sol_par_ligne
    r3 = mo.calculer()
    assert r3.complet
    W = r3.phases[-1].W                             # dernière phase (les résultats comptent l'état initial en 0)
    i_sud, i_nord = 10, 42                          # x = 10 m sur le côté sud ; son vis-à-vis au nord
    avec = calculer(vers_modele(lire_script(_2d(P3D, True)), CAT, NRM)).phases[-1].y
    sans = calculer(vers_modele(lire_script(_2d(P3D, False)), CAT, NRM)).phases[-1].y
    np.testing.assert_allclose(W[i_sud], avec, rtol=1e-5, atol=1e-9)
    np.testing.assert_allclose(W[i_nord], sans, rtol=1e-5, atol=1e-9)
    assert np.abs(W[i_sud]).max() < 0.9 * np.abs(W[i_nord]).max()     # la risberme retient le côté sud
    assert np.abs(avec).max() < np.abs(sans).max()
    # côtés est et ouest : sans risberme, identiques entre eux (symétrie) et égaux au 2D sans risberme
    np.testing.assert_allclose(W[26], W[58], rtol=1e-9, atol=1e-12)
    np.testing.assert_allclose(W[26], sans, rtol=1e-5, atol=1e-9)


def test_refus_du_fond_equivalent_et_de_la_pente_par_cote_en_fouille_fermee():
    fe = P3D.replace("pente: 1.5, cote_pied: -6.0 }", "pente: 1.5, cote_pied: -6.0, methode: fond_equivalent, cote_equivalente: -4.0 }")
    with pytest.raises(ErreurConversion, match="fond équivalent"):
        vers_modele(lire_script(fe), CAT, NRM)
    pente = P3D.replace("eau:", "terrain: { pente_beta: 10, cote_paroi: nord }\neau:")
    with pytest.raises(ErreurConversion, match="pente"):
        vers_modele(lire_script(pente), CAT, NRM)


# ---------------------------------------------------------------------------
# coupe 2D : objets des autres côtés sans effet
# ---------------------------------------------------------------------------
def test_fond_equivalent_et_pente_filtres_par_cote_sur_une_coupe_2d():
    fe = (BASE + BLOC_PLAN + RISBERME_SUD.replace("cote_paroi: long_sud", "cote_paroi: long_nord")
          .replace("cote_pied: -6.5 }", "cote_pied: -6.5, methode: fond_equivalent, cote_equivalente: -4.0 }"))
    m_sud = vers_modele(lire_script(fe + COUPE_SUD), CAT, NRM)
    m_nord = vers_modele(lire_script(fe + COUPE_NORD), CAT, NRM)
    assert m_sud.phases[2].excaver == -6.5 and m_nord.phases[2].excaver == -4.0
    pente = BASE.replace("eau:\n", "terrain: { pente_beta: 10, cote_paroi: long_nord }\neau:\n") + BLOC_PLAN
    assert vers_modele(lire_script(pente + COUPE_SUD), CAT, NRM).beta_amont is None
    assert vers_modele(lire_script(pente + COUPE_NORD), CAT, NRM).beta_amont == 10


# ---------------------------------------------------------------------------
# coupes automatiques
# ---------------------------------------------------------------------------
def test_geometrie_uniforme_coupe_unique_identique():
    texte = _auto(BASE + BLOC_PLAN)
    s = lire_script(texte)
    assert s.calcul.coupes_automatiques
    p = preparer(texte, s)
    assert p.unique and len(p.coupes) == 1 and p.coupes[0].texte == texte and not p.coupes[0].automatique
    assert p.avertissements == []


def test_coupes_automatiques_une_par_cote():
    texte = _auto(BASE + BLOC_PLAN + RISBERME_SUD)
    s = lire_script(texte)
    p = preparer(texte, s)
    assert not p.unique and [c.nom for c in p.coupes] == ["Auto — côté long_sud", "Auto — côté court_est", "Auto — côté long_nord", "Auto — côté court_ouest"]
    assert all(c.automatique for c in p.coupes) and len({c.empreinte for c in p.coupes}) == 4 and p.orphelins == []
    assert [(c.k, c.de, c.a) for c in p.coupes] == [(0, 0.0, 20.0), (1, 0.0, 12.0), (2, 0.0, 20.0), (3, 0.0, 12.0)]
    assert any("Coupes automatiques" in a for a in p.avertissements)
    r = TestClient(api.app).post("/api/calcul", json={"texte": texte}).json()
    assert r["ok"], r.get("erreurs")
    coupes = r["projet"]["coupes"]
    assert [c["automatique"] for c in coupes] == [True] * 4 and not r["projet"]["unique"]
    res = {c["nom"]: (r["resultats"] if i == 0 else c["resultats"]) for i, c in enumerate(coupes)}
    y = {n: x["phases"][3]["synthese"]["y_max_mm"] for n, x in res.items()}
    assert y["Auto — côté long_sud"] < 0.95 * y["Auto — côté long_nord"]            # la risberme ne retient que le sud
    assert y["Auto — côté court_est"] == pytest.approx(y["Auto — côté court_ouest"], rel=1e-9)
    assert y["Auto — côté court_est"] == pytest.approx(y["Auto — côté long_nord"], rel=1e-9)
    assert res["Auto — côté long_sud"]["maquette"]["coupe_calcul"]["cote"] == "long_sud"


def test_sans_coupes_automatiques_coupe_unique_avertie():
    texte = BASE + BLOC_PLAN + RISBERME_SUD
    p = preparer(texte, lire_script(texte))
    assert p.unique and len(p.coupes) == 1
    assert any("coupes_automatiques" in a and "même profil" in a for a in p.avertissements)
    assert "coupe_calcul" in p.coupes[0].texte          # rapportée au milieu du côté le plus long
    p3 = preparer(_auto(P3D), lire_script(_auto(P3D)))   # mode pseudo3d : la plaque traite les côtés, pas de coupes auto
    assert p3.unique and any("accompagnement" in a for a in p3.avertissements)
