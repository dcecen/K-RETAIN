"""Assemblages : les 14 types se dessinent sans erreur, réagissent aux paramètres, se vérifient."""
import copy

import pytest

from sout import normes as mod_normes
from sout.assemblages import ec3_assemblages as ec3
from sout.assemblages.base import REGISTRE
from sout.assemblages.service import PARAMS_COMMUNS, liste_types, schema, verifier
from sout.materiaux.base import catalogue_par_defaut
from sout.normes import Normes
from sout.verifs import Lecteur

CAT = catalogue_par_defaut()
NORMES_VIDES = mod_normes.charger()
EFFORTS = {"N": 850.0, "V": 20.0, "M": 120.0, "T": 600.0}
COMMUN = {"acier": "S355", "lierne": "HEB 300", "buton": "modulaire_A"}

V = lambda x: {"valeur": x, "source": "valeur de test fictive"}  # noqa: E731
NORMES_TEST = Normes({
    "ec3_assemblages": {
        "gamma_M0": V(1.0), "gamma_M1": V(1.0), "gamma_M2": V(1.25),
        "boulons": {"k2": V(0.9), "coef_poinconnement": V(0.6), "coef_interaction": V(1.4), "jeu_trou_M16_M24": V(2), "jeu_trou_sup_M24": V(3),
                    "fub": {"8_8": V(800), "10_9": V(1000), "4_6": V(400), "5_6": V(500)},
                    "alpha_v": {"8_8": V(0.6), "10_9": V(0.5), "4_6": V(0.6), "5_6": V(0.6)},
                    "As": {"M12": V(84.3), "M16": V(157), "M20": V(245), "M24": V(353), "M27": V(459), "M30": V(561), "M36": V(817)},
                    "dm": {"M12": V(20), "M16": V(26), "M20": V(32), "M24": V(40), "M27": V(44), "M30": V(50), "M36": V(60)}},
        "soudures": {"beta_w": {"S235": V(0.8), "S275": V(0.85), "S355": V(0.9)}, "gorge_min": V(3)},
        "axes": {"coef_cisaillement": V(0.6), "coef_pression": V(1.5), "coef_flexion": V(1.5)},
        "ame": {"coef_diffusion": V(2.0)}, "beton": {"coef_max_compression_localisee": V(3.0)},
        "chevilles": {"exposant_interaction": V(1.5)},
    },
    "ec2": {"gamma_c": V(1.5), "alpha_cc": V(1.0)},
})


def test_quatorze_types():
    assert len(REGISTRE) == 14
    noms = {t["cle"] for t in liste_types()}
    assert {"platine_about", "buton_lierne_boulonne", "chaise_buton", "appui_biais", "raboutage_buton", "boite_verin", "buton_angle",
            "raidisseurs_lierne", "chaise_lierne", "eclisse_lierne", "tete_tirant_lierne", "tete_tirant_paroi", "bracon_tete", "bracon_pied"} == noms


@pytest.mark.parametrize("cle", list(REGISTRE))
def test_schema_se_genere_et_reagit_aux_parametres(cle):
    t = REGISTRE[cle]
    base = {**COMMUN, **t.defauts()}
    s = schema(cle, base, EFFORTS, CAT, NORMES_VIDES, fck=30)
    assert s["solides"] and s["vues"] and s["cotes"] and s["efforts"]
    assert len(s["vues"]) >= 2 and any(v["coupe"] for v in s["vues"])
    assert s["nomenclature"] and all(n["repere"] >= 0 for n in s["nomenclature"])
    # toute cote liée à un paramètre doit désigner un paramètre existant
    cles = {p.cle for p in PARAMS_COMMUNS + t.parametres}
    for c in s["cotes"]:
        if c["parametre"]:
            assert c["parametre"] in cles, (cle, c["parametre"])
    for so in s["solides"]:
        for pk in so["parametres"]:
            assert pk in cles, (cle, pk)
    # modifier chaque paramètre numérique change le schéma (au moins une fois sur l'ensemble)
    change = False
    for p in t.parametres:
        if p.genre not in ("nombre", "entier"):
            continue
        autre = copy.deepcopy(base)
        v = float(base[p.cle])
        autre[p.cle] = (v + 1 if p.maxi is None or v + 1 <= p.maxi else max(p.mini or 0, v - 1)) if p.genre == "entier" else (v * 1.3 if p.maxi is None or v * 1.3 <= p.maxi else v * 0.8)
        if autre[p.cle] == base[p.cle]:
            continue
        s2 = schema(cle, autre, EFFORTS, CAT, NORMES_VIDES, fck=30)
        if s2["solides"] != s["solides"] or s2["cotes"] != s["cotes"]:
            change = True
    assert change, cle


@pytest.mark.parametrize("cle", list(REGISTRE))
def test_verifications_de_chaque_type(cle):
    t = REGISTRE[cle]
    base = {**COMMUN, **t.defauts()}
    if cle == "chaise_lierne":
        base.update(N_Rd_cheville=40.0, V_Rd_cheville=30.0)
    vs = verifier(cle, base, EFFORTS, CAT, NORMES_VIDES, fck=30)
    assert vs and all(v.etat == "non_verifiable" for v in vs if v.taux is None)
    assert all(v.reperes for v in vs), [v.nom for v in vs if not v.reperes]
    vt = verifier(cle, base, EFFORTS, CAT, NORMES_TEST, fck=30)
    calcules = [v for v in vt if v.taux is not None]
    assert calcules, cle
    for v in calcules:
        assert v.taux >= 0


def test_formules_ec3_calcul_manuel():
    lect = Lecteur(NORMES_TEST)
    # Ft,Rd M20 8.8 : 0,9·800·245/1,25 = 141,1 kN ; Fv,Rd : 0,6·800·245/1,25 = 94,1 kN
    assert ec3.ft_rd(20, "8.8", lect) == pytest.approx(141.12, rel=1e-3)
    assert ec3.fv_rd(20, "8.8", lect) == pytest.approx(94.08, rel=1e-3)
    # pression diamétrale : d0 = 22, e1 = 40 -> αb = min(40/66, 800/490, 1) = 0,606 ; k1 = min(2,8·40/22 − 1,7 ; 2,5) = 2,5
    assert ec3.fb_rd(20, 15, 490, "8.8", 40, 40, None, lect) == pytest.approx(2.5 * (40 / 66) * 490 * 20 * 15 / 1.25 / 1000, rel=1e-3)
    # soudure a = 6 mm S355 : 6·490/(√3·0,9·1,25) = 1,509 kN/mm
    assert ec3.fw_rd(6, 490, "S355", lect) == pytest.approx(6 * 490 / (3**0.5 * 0.9 * 1.25) / 1000, rel=1e-6)
    # axe Ø60 S355 : Fv = 0,6·2827·490/1,25 = 665 kN
    r = ec3.axe(60, 355, 490, 25, 355, lect)
    assert r["Fv_Rd"] == pytest.approx(0.6 * 3.14159 * 900 * 490 / 1.25 / 1000, rel=1e-3)
    # compression localisée : Ac0 = 400×400, Ac1 = 800×800, fcd = 20 : min(160000·20·2, 3·20·160000)/1000 = 6400 kN
    assert ec3.compression_localisee_beton(30, 160000, 640000, lect) == pytest.approx(6400.0)


def test_platine_about_valeurs_coherentes():
    base = {**COMMUN, **REGISTRE["platine_about"].defauts()}
    vt = {v.nom: v for v in verifier("platine_about", base, {"N": 850.0}, CAT, NORMES_TEST, fck=30)}
    soud = next(v for k, v in vt.items() if "Soudure tube" in k)
    # Fw,Rd = 1,509 kN/mm × π·508 = 2408 kN -> taux 850/2408
    assert soud.taux == pytest.approx(850 / (ec3.fw_rd(6, 490, "S355", Lecteur(NORMES_TEST)) * 3.14159265 * 508), rel=1e-3)
    assert 2 in soud.reperes and 3 in soud.reperes
