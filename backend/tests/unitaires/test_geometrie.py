"""Bloc `geometrie` (lot 4 du 25/10/2026) : forme ancienne convertie = même modèle, étendues (côté + tronçon),
tronçons automatiques, fond par zone, contrôles du lecteur, aller-retour de conversion, pont vers `plan`."""
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from ruamel.yaml import YAML

from sout import api, normes
from sout.geometrie import decoupage, derivation, normaliser
from sout.materiaux.base import catalogue_par_defaut
from sout.noyau.phasage import calculer
from sout.script.conversion import vers_modele
from sout.script.coupes import preparer
from sout.script.lecteur import ScriptInvalide, lire_script
from sout.sol.terrain import SurchargePlan

RACINE = Path(__file__).resolve().parents[3]
CAT, NRM = catalogue_par_defaut(), normes.charger()
ANCIEN = (RACINE / "exemples" / "fouille_coupes.yaml").read_text(encoding="utf-8")
ANCIEN = ANCIEN[:ANCIEN.index("\ncoupes:")] + "\n"          # sans coupes explicites : forme ancienne plan + fouille
EXEMPLE_ZONES = (RACINE / "exemples" / "geometrie_fouille_zones.yaml").read_text(encoding="utf-8")
COUPE_SUD = "coupe_calcul: { x: 15, y: 0, ni: [0, 1], t: [1, 0], k: 0, s: 15, cote: long_sud }\n"
COUPE_NORD = "coupe_calcul: { x: 15, y: 18, ni: [0, -1], t: [-1, 0], k: 2, s: 15, cote: long_nord }\n"
COUPE_EST = "coupe_calcul: { x: 30, y: 9, ni: [-1, 0], t: [0, 1], k: 1, s: 9, cote: court_est }\n"


def _nouveau_depuis_ancien() -> str:
    """Le même projet que fouille_coupes.yaml, écrit avec le bloc geometrie (plan et fouille retirés, position de
    l'immeuble portée par geometrie.surcharges)."""
    t = ANCIEN
    t = t[:t.index("\nfouille:")] + t[t.index("\nplan:"):]            # retire le bloc fouille
    t = t[:t.index("\nplan:")] + t[t.index("\nphases:"):]             # retire le bloc plan
    t = t.replace(", emprise: { de: 4, a: 26 }, cote_paroi: long_nord", "")
    assert "cote_paroi" not in t and "plan:" not in t and "fouille:" not in t
    return t + """
geometrie:
  ouvrages:
    contour: [[0, 0], [30, 0], [30, 18], [0, 18]]
    cotes: { long_sud: 0, court_est: 1, long_nord: 2, court_ouest: 3 }
  fouille:
    objets:
      - { nom: R1, type: risberme, cotes: [long_sud], phases: [3, 3], cote_crete: -4.0, largeur_crete: 2.0, pente: 1.5, cote_pied: -6.5 }
  surcharges:
    - { surcharge: immeuble, cotes: [long_nord], de: 4, a: 26 }
"""


@pytest.fixture(autouse=True)
def _cache_vide():
    api.vider_cache_coupes()
    yield
    api.vider_cache_coupes()


def _cle_objet(o):
    return (o.nom, o.type, o.face, tuple(o.profil), o.base, o.gamma, o.methode, o.phase_debut, o.phase_fin, o.cotes_paroi, o.troncon)


def _cle_surcharge(s):
    if isinstance(s, SurchargePlan):
        return (s.nom, s.type, s.q, s.distance, s.largeur, s.emprise, s.position, s.trace, s.profondeur, s.cote, s.cote_ecran, s.cotes_paroi)
    return (s.nom, s.type, s.q, s.distance, s.largeur, s.cote, s.cote_ecran)


def test_forme_ancienne_convertie_meme_modele_et_memes_resultats():
    nouveau = _nouveau_depuis_ancien()
    for coupe in (COUPE_SUD, COUPE_NORD):
        sa, sn = lire_script(ANCIEN + coupe), lire_script(nouveau + coupe)
        assert normaliser.forme_ancienne_presente(sa) == ["plan", "fouille.risbermes"] and normaliser.forme_ancienne_presente(sn) == []
        assert sn.plan is not None and sn.plan.contour == sa.plan.contour and sn.plan.cotes == sa.plan.cotes   # pont plan
        ma, mn = vers_modele(sa, CAT, NRM), vers_modele(sn, CAT, NRM)
        assert [(p.nom, p.excaver, p.retirer_surcharges) for p in ma.phases] == [(p.nom, p.excaver, p.retirer_surcharges) for p in mn.phases]
        assert [_cle_surcharge(s) for s in ma.surcharges] == [_cle_surcharge(s) for s in mn.surcharges]
        for pa, pn in zip(ma.phases, mn.phases):
            assert [_cle_surcharge(s) for s in pa.ajouter_surcharges] == [_cle_surcharge(s) for s in pn.ajouter_surcharges]
        assert [_cle_objet(o) for o in ma.terrain_objets] == [_cle_objet(o) for o in mn.terrain_objets]
        assert (ma.terrain_amont, ma.terrain_aval, ma.beta_amont) == (mn.terrain_amont, mn.terrain_aval, mn.beta_amont)
        ra, rn = calculer(ma), calculer(mn)
        for pa, pn in zip(ra.phases, rn.phases):
            np.testing.assert_allclose(pa.y, pn.y, rtol=1e-9, atol=1e-12)
    ga = normaliser.depuis_script(lire_script(ANCIEN))
    assert ga.forme_ancienne and ga.contour == ((0.0, 0.0), (30.0, 0.0), (30.0, 18.0), (0.0, 18.0)) and ga.cotes["long_nord"] == 2
    assert [o.nom for o in ga.objets] == ["R1"] and ga.objets[0].etendue.cotes == ("long_sud",) and ga.objets[0].etendue.troncon is None
    assert ga.positions["immeuble"].etendue.troncon == (4.0, 26.0) and ga.positions["grue"].position == (15.0, -8.0)


def test_aller_retour_vers_bloc_geometrie():
    s = lire_script(ANCIEN)
    bloc = normaliser.vers_bloc_geometrie(s)
    assert set(bloc) == {"ouvrages", "terrain", "fouille", "surcharges"} or set(bloc) >= {"ouvrages", "fouille", "surcharges"}
    assert bloc["fouille"]["objets"][0] == {"nom": "R1", "type": "risberme", "phases": [3, 3], "cote_crete": -4.0, "largeur_crete": 2.0,
                                            "pente": 1.5, "cote_pied": -6.5, "cotes": ["long_sud"]}
    # réécriture : bloc + script sans forme ancienne -> même géométrie
    t = ANCIEN[:ANCIEN.index("\nfouille:")] + ANCIEN[ANCIEN.index("\nplan:"):]
    t = t[:t.index("\nplan:")] + t[t.index("\nphases:"):]
    t = t.replace(", emprise: { de: 4, a: 26 }, cote_paroi: long_nord", "").replace(", position: [15, -8], emprise: [6, 6]", "")
    t = t.replace(", position: [38, 9], emprise: [10, 8]", "")
    y = YAML(typ="safe")
    y.default_flow_style = False
    import io
    flux = io.StringIO()
    y.dump({"geometrie": bloc}, flux)
    g2 = normaliser.depuis_script(lire_script(t + flux.getvalue()))
    g1 = normaliser.depuis_script(s)
    assert (g2.contour, g2.cotes, g2.objets, g2.zones_terrain, g2.zones_fond) == (g1.contour, g1.cotes, g1.objets, g1.zones_terrain, g1.zones_fond)
    assert {k: (v.etendue, v.position, v.emprise, v.trace) for k, v in g2.positions.items()} == {k: (v.etendue, v.position, v.emprise, v.trace) for k, v in g1.positions.items()}


def test_etendue_troncon_et_coupes_automatiques():
    s = lire_script(EXEMPLE_ZONES)
    geo = normaliser.depuis_script(s)
    assert geo.varie() and not geo.forme_ancienne
    r1 = geo.objets[0]
    assert r1.etendue.cotes == ("long_sud",) and r1.etendue.troncon == (4.0, 26.0)
    # tronçons homogènes : le côté sud est coupé aux bornes de la risberme, le nord à celles de l'immeuble
    tr = decoupage.troncons_automatiques(geo)
    assert tr == [(0, 0.0, 4.0), (0, 4.0, 26.0), (0, 26.0, 30.0), (1, 0.0, 18.0), (2, 0.0, 4.0), (2, 4.0, 26.0), (2, 26.0, 30.0), (3, 0.0, 18.0)]
    p = preparer(EXEMPLE_ZONES, s)
    assert not p.unique and len(p.coupes) == 8 and all(c.automatique for c in p.coupes) and p.orphelins == []
    assert p.coupes[1].nom == "Auto — côté long_sud (4 à 26 m)" and (p.coupes[1].de, p.coupes[1].a) == (4.0, 26.0)
    assert p.coupes[3].nom == "Auto — côté court_est"
    # l'objet n'existe que sur son tronçon : bandes présentes à s = 10, absentes à s = 2 du même côté
    m10 = vers_modele(lire_script(EXEMPLE_ZONES + "coupe_calcul: { x: 10, y: 0, ni: [0, 1], t: [1, 0], k: 0, s: 10, cote: long_sud }\n"), CAT, NRM)
    m2 = vers_modele(lire_script(EXEMPLE_ZONES + "coupe_calcul: { x: 2, y: 0, ni: [0, 1], t: [1, 0], k: 0, s: 2, cote: long_sud }\n"), CAT, NRM)
    assert any(b.nom.startswith("~terrain:R1") for b in m10.phases[2].ajouter_surcharges)
    assert not any(b.nom.startswith("~terrain:R1") for b in m2.phases[2].ajouter_surcharges)
    assert m10.terrain_objets[0].troncon == (4.0, 26.0) and m2.terrain_objets[0].nom == "R1"   # affichage : tous les objets
    # position de l'immeuble : bande sur 4 à 26 m du côté nord, portée par geometrie.surcharges
    imm = next(x for x in m10.surcharges if x.nom == "immeuble")
    assert isinstance(imm, SurchargePlan) and imm.cotes_paroi == ("long_nord",) and imm.emprise == (4.0, 26.0)
    grue = next(x for ph in m10.phases for x in ph.ajouter_surcharges if x.nom == "grue")
    assert grue.position == (15.0, -8.0) and grue.emprise == (6.0, 6.0)


def test_fond_par_zone():
    m_est = vers_modele(lire_script(EXEMPLE_ZONES + COUPE_EST), CAT, NRM)
    m_sud = vers_modele(lire_script(EXEMPLE_ZONES + COUPE_SUD), CAT, NRM)
    assert m_est.phases[2].excaver == -5.0 and m_sud.phases[2].excaver == -6.5
    assert m_est.excaver_zones[2] == {"defaut": -6.5, "est": -5.0}
    geo = normaliser.depuis_script(lire_script(EXEMPLE_ZONES))
    assert derivation.fonds_par_zone(geo, m_est.excaver_zones, geo.fond_initial) == {"defaut": -6.5, "est": -5.0}
    assert derivation.fonds_par_zone(geo, m_est.excaver_zones[:1], geo.fond_initial) == {"defaut": -2.0, "est": -2.0}
    poly = decoupage.polygone_zone(geo, geo.zones_fond[0])
    assert len(poly) == 4 and poly[0] == (30.0, 0.0) and poly[1] == (30.0, 18.0) and poly[2][0] == pytest.approx(15.0)
    r = TestClient(api.app).post("/api/calcul", json={"texte": EXEMPLE_ZONES}).json()
    assert r["ok"], r.get("erreurs")
    coupes = {c["nom"]: (r["resultats"] if i == 0 else c["resultats"]) for i, c in enumerate(r["projet"]["coupes"])}
    y_est = coupes["Auto — côté court_est"]["phases"][3]["synthese"]["y_max_mm"]
    y_ouest = coupes["Auto — côté court_ouest"]["phases"][3]["synthese"]["y_max_mm"]
    assert coupes["Auto — côté court_est"]["phases"][3]["terrain_aval"] == -5.0 and coupes["Auto — côté court_ouest"]["phases"][3]["terrain_aval"] == -6.5
    assert y_est < 0.8 * y_ouest                                   # fouille moins profonde : écran moins déplacé
    assert r["projet"]["phasage_projet"] == ["État initial", "Terrassement à -2,0", "Pose du buton B1", "Terrassement final et pompage"]


def test_refus_du_lecteur():
    def erreur(texte: str) -> str:
        with pytest.raises(ScriptInvalide) as ex:
            lire_script(texte)
        return " | ".join(e.message for e in ex.value.erreurs)
    assert "forme ancienne" in erreur(EXEMPLE_ZONES + "plan:\n  contour: [[0, 0], [30, 0], [30, 18], [0, 18]]\n")
    assert "côté « sud » inconnu" in erreur(EXEMPLE_ZONES.replace("cotes: [long_sud], de: 4, a: 26", "cotes: [sud], de: 4, a: 26"))
    assert "doit dépasser son début" in erreur(EXEMPLE_ZONES.replace("de: 4, a: 26, phases", "de: 26, a: 4, phases"))
    assert "au-delà de la longueur du côté" in erreur(EXEMPLE_ZONES.replace("de: 4, a: 26, phases", "de: 4, a: 40, phases"))
    assert "surcharge « engin » inconnue" in erreur(EXEMPLE_ZONES.replace("surcharge: grue,", "surcharge: engin,"))
    assert "zone de fond « ouest » inconnue" in erreur(EXEMPLE_ZONES.replace("est: -5.0", "ouest: -5.0"))
    assert "hors de la paroi" in erreur(EXEMPLE_ZONES.replace("est: -5.0", "est: -15.0"))


def test_geometrie_uniforme_coupe_unique_identique():
    texte = EXEMPLE_ZONES[:EXEMPLE_ZONES.index("  terrain:")] + EXEMPLE_ZONES[EXEMPLE_ZONES.index("\nphases:"):]
    texte = texte.replace("excaver: { defaut: -6.5, est: -5.0 }", "excaver: -6.5").replace("  - { nom: grue, type: ponctuelle, q: 1200, phases: [2, 3] }\n", "")
    s = lire_script(texte)
    assert not normaliser.depuis_script(s).varie()
    p = preparer(texte, s)
    assert p.unique and p.coupes[0].texte == texte
