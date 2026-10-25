"""Scripts de vérification élémentaire du menu Fichier (exemples/elementaires) : chaque script est
calculé par l'API, comme depuis l'interface, et le résultat annoncé dans son en-tête est contrôlé
contre sa référence (équilibre limite, convention K-Réa, pseudo-3D, EC2, EC3)."""
import math
import re
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from sout.api import app
from sout.noyau.phasage import calculer
from sout.script.conversion import vers_modele
from sout.script.lecteur import lire_script
from sout.materiaux.base import catalogue_par_defaut
from sout.validation.cas_ecran import h_critique_ancre_butee_simple, h_critique_autostable_equilibre_limite

RACINE = Path(__file__).resolve().parents[3]
DOSSIER = RACINE / "exemples" / "elementaires" / "2d"
DOSSIER_3D = RACINE / "exemples" / "elementaires" / "3d"
CLIENT = TestClient(app)


def _texte(nom: str) -> str:
    return (DOSSIER / f"{nom}.yaml").read_text(encoding="utf-8")


def _calcul(nom: str) -> dict:
    r = CLIENT.post("/api/calcul", json={"texte": _texte(nom)}).json()
    assert r["ok"], r.get("erreurs")
    return r["resultats"]


def test_les_scripts_elementaires_sont_proposes_dans_le_menu():
    """Catalogue : tous les scripts des dossiers 2d et 3d, en-tête normalisé (VÉRIFICATION ÉLÉMENTAIRE, ATTENDU,
    SOURCE), titre lu dans la clé projet. (Le test comptait « exactement 8 » scripts avant l'ouverture du
    catalogue du 25/10/2026 : adaptation de la spécification, aucune valeur de référence concernée.)"""
    ex = CLIENT.get("/api/exemples").json()
    for groupe, dossier in (("Exemples élémentaires 2D", DOSSIER), ("Exemples élémentaires 3D", DOSSIER_3D)):
        elem = [e for e in ex if e.get("groupe") == groupe]
        assert [e["nom"] for e in elem] == sorted(p.stem for p in dossier.glob("*.yaml"))
        for e in elem:
            assert e["texte"].startswith("# VÉRIFICATION ÉLÉMENTAIRE"), e["nom"]
            assert e["attendu"] and e["source"] and e["titre"], f"{e['nom']} : en-tête incomplet (ATTENDU, SOURCE, projet)"
            assert e["titre"].startswith(e["nom"][:3]), f"{e['nom']} : le titre commence par le code"
    assert len([e for e in ex if e.get("groupe") == "Exemples élémentaires 2D"]) >= 8
    assert any(e.get("groupe") == "Exemples" for e in ex)


def test_chaque_exemple_elementaire_a_son_test():
    """Chaque script du catalogue est contrôlé par un test nommé d'après son code (E09 -> test_E09_...)."""
    codes = sorted(p.stem[:3] for d in (DOSSIER, DOSSIER_3D) for p in d.glob("*.yaml"))
    source = Path(__file__).read_text(encoding="utf-8")
    manquants = [c for c in codes if f"def test_{c}_" not in source and f"_{c}_" not in source.replace("def test_", "")]
    assert not manquants, f"exemples sans test : {manquants}"


def test_E01_autostable_equilibre_limite():
    h = h_critique_autostable_equilibre_limite(10.0, 1 / 3, 3.0, 20.0)
    assert h == pytest.approx(5.05, abs=0.01)
    ph = _calcul("E01_autostable_equilibre_limite")["phases"]
    assert ph[1]["ok"] and 4.90 / h == pytest.approx(0.97, abs=0.005)
    assert not ph[2]["ok"] and "upture" in ph[2]["message"] and 5.20 / h == pytest.approx(1.03, abs=0.005)


def test_E02_ancre_butee_simple():
    h, T = h_critique_ancre_butee_simple(12.0, 1 / 3, 3.0, 20.0)
    assert h == pytest.approx(8.57, abs=0.01) and T == pytest.approx(126.3, abs=0.1)
    ph = _calcul("E02_ancre_butee_simple")["phases"]
    assert ph[2]["ok"] and ph[2]["appuis"][0]["effort_kN_m"] == pytest.approx(T, rel=0.05)
    assert not ph[3]["ok"]


def test_E03_precharge_au_verin_et_equilibre():
    ph = _calcul("E03_precharge_au_verin")["phases"]
    assert ph[2]["appuis"][0]["effort_kN_m"] == pytest.approx(300 / 6, abs=1e-6)
    assert ph[3]["appuis"][0]["effort_kN_m"] > 50.0
    s = lire_script(_texte("E03_precharge_au_verin"))
    res = calculer(vers_modele(s, catalogue_par_defaut()))
    for p in res.phases[1:]:
        am, av = p.pressions["amont"], p.pressions["aval"]
        L = np.repeat(np.diff(p.z) / 2, 2)
        F = (np.sum(am["L"] * am["p"]) - np.sum(av["L"] * av["p"]) + np.sum((p.eau["u_amont"] - p.eau["u_aval"]) * L)
             - sum(a["effort"] for a in p.appuis))
        assert abs(F) < 1e-6


def test_E04_E05_coupes_2d_assemblees_contre_plaque():
    r4, r5 = _calcul("E04_pseudo3d_coupes_2d_assemblees"), _calcul("E05_pseudo3d_plaque_isotrope")
    # E04 : |y| max = écran 2D sans appui
    s = lire_script(_texte("E04_pseudo3d_coupes_2d_assemblees").replace("poser: B", "poser: []"))
    y_sans = float(np.abs(calculer(vers_modele(s, catalogue_par_defaut())).phases[-1].y).max() * 1e3)
    q4, q5 = r4["pseudo3d"]["phases"][-1], r5["pseudo3d"]["phases"][-1]
    assert q4["y_max_mm"] == pytest.approx(y_sans, rel=1e-5)
    # E05 : effort d'un buton intérieur = effort 2D × espacement, déplacement bien plus faible
    H2 = r5["phases"][-1]["appuis"][0]["effort_kN_m"]
    interieurs = [a["effort"] for a in q5["appuis"][3:-3]]
    assert np.mean(interieurs) == pytest.approx(H2 * 4.0, rel=0.05)
    assert q5["y_max_mm"] < 0.1 * q4["y_max_mm"]
    for q in (q4, q5):
        assert abs(q["bilan"]["residu"]) <= 1e-6 * q["bilan"]["echelle"]


def test_E06_double_ecran():
    avec = _calcul("E06_fouille_fermee_double_ecran")["pseudo3d"]["phases"][-1]
    texte = _texte("E06_fouille_fermee_double_ecran")
    texte = texte[:texte.index("surcharges:")] + texte[texte.index("phases:"):]
    sans = CLIENT.post("/api/calcul", json={"texte": texte}).json()["resultats"]["pseudo3d"]["phases"][-1]
    ea = {round(a["s"], 3): a for a in avec["appuis"]}
    es = {round(a["s"], 3): a for a in sans["appuis"]}
    assert ea[10.0]["s2"] == pytest.approx(42.0)
    assert ea[10.0]["effort"] / es[10.0]["effort"] == pytest.approx(1.13, abs=0.05)
    assert abs(avec["bilan"]["residu"]) <= 1e-6 * avec["bilan"]["echelle"]


def test_E07_section_beton_arme():
    vs = {v["nom"]: v for v in _calcul("E07_str_paroi_moulee")["verifications"]}
    v = vs["Paroi moulée — flexion (face fouille)"]
    fcd, fyd = 30 / 1.5, 500 / 1.15
    lx = 20e-4 * fyd / fcd
    MR = fcd * 1e3 * lx * (0.53 - lx / 2)
    assert MR == pytest.approx(442, abs=0.5)
    assert f"M_Rd = {MR:.0f} kN·m/m" in v["detail"]


def test_E08_flambement_buton():
    vs = {v["nom"]: v for v in _calcul("E08_str_buton_flambement")["verifications"]}
    v = vs["Buton — flambement et flexion"]
    E, A, I, fy, L = 210000e3, 194.6e-4, 59755e-8, 355e3, 16.0
    Ncr, Npl = math.pi ** 2 * E * I / L ** 2, A * fy
    lam = math.sqrt(Npl / Ncr)
    phi = 0.5 * (1 + 0.21 * (lam - 0.2) + lam ** 2)
    chi = 1 / (phi + math.sqrt(phi ** 2 - lam ** 2))
    assert chi * Npl == pytest.approx(3683, abs=1)
    assert f"χ = {chi:.2f}" in v["detail"] and f"N_b,Rd = {chi * Npl:.0f} kN" in v["detail"]
    assert float(re.search(r"λ̄ = ([\d.]+)", v["detail"]).group(1)) == pytest.approx(lam, abs=0.01)


# ---------------------------------------------------------------------------
# E09 à E25 (catalogue du 25/10/2026) : chaque test recalcule le résultat annoncé dans l'en-tête du script
# ---------------------------------------------------------------------------
def _demi_mailles(ph: dict) -> np.ndarray:
    """Longueurs des demi-mailles (ordre des tableaux de pressions et d'eau : deux par élément)."""
    return np.repeat(np.diff(np.array(ph["z"])) / 2, 2)


def test_E09_etat_initial_au_repos():
    ph = _calcul("E09_etat_initial_repos")["phases"][1]
    assert ph["nom"] == "Repos" and ph["ok"]
    assert np.abs(ph["y_mm"]).max() < 1e-9 and np.abs(ph["M"]).max() < 1e-9
    k0 = 1 - math.sin(math.radians(35))
    for face in ("amont", "aval"):
        pr = ph["pressions"][face]
        z, p0 = np.array(pr["z"]), np.array(pr["p0"])
        i = int(np.argmin(np.abs(z + 5.0)))
        assert z[i] == pytest.approx(-5.0, abs=0.06)
        sv = 18 * 2 + 9 * 1 + 11 * (-3.0 - z[i])                  # σ'v à la cote exacte de la demi-maille
        assert p0[i] == pytest.approx(k0 * sv, rel=1e-6)
        assert k0 * (18 * 2 + 9 + 11 * 2) == pytest.approx(28.6, abs=0.05)
    e = ph["eau"]
    z, u = np.array(ph["pressions"]["amont"]["z"]), np.array(e["u_amont"])
    assert len(z) == len(u) == len(_demi_mailles(ph))
    sous = z < -2.0 - 1e-9
    np.testing.assert_allclose(u[sous], 10 * (-2.0 - z[sous]), rtol=1e-9, atol=1e-9)
    assert np.all(u[~sous] == 0)


def test_E10_eau_dissymetrique():
    ph = _calcul("E10_eau_dissymetrique")["phases"][2]
    assert ph["ok"]
    z = np.array(ph["pressions"]["amont"]["z"])
    ua, uv = np.array(ph["eau"]["u_amont"]), np.array(ph["eau"]["u_aval"])
    am, av = z < -1.0 - 1e-9, z < -4.0 - 1e-9
    np.testing.assert_allclose(ua[am], 10 * (-1.0 - z[am]), rtol=1e-9, atol=1e-9)
    np.testing.assert_allclose(uv[av], 10 * (-4.0 - z[av]), rtol=1e-9, atol=1e-9)
    assert np.all(ua[~am] == 0) and np.all(uv[~av] == 0)
    np.testing.assert_allclose((ua - uv)[av], 30.0, rtol=1e-9)
    assert np.sum((ua - uv) * _demi_mailles(ph)) == pytest.approx(345.0, rel=1e-6)


def test_E11_surcharge_uniforme():
    ph1, ph2 = _calcul("E11_surcharge_uniforme")["phases"][1:3]
    a1, a2 = ph1["pressions"]["amont"], ph2["pressions"]["amont"]
    np.testing.assert_allclose(np.array(a2["p0"]) - np.array(a1["p0"]), 0.5 * 20, rtol=1e-9, atol=1e-9)
    np.testing.assert_allclose(np.array(a2["pa"]) - np.array(a1["pa"]), 20 / 3, rtol=1e-9, atol=1e-9)
    for cle in ("p0", "pa", "pp"):
        np.testing.assert_allclose(ph2["pressions"]["aval"][cle], ph1["pressions"]["aval"][cle], rtol=1e-12, atol=1e-12)


def _boussinesq_bande(q: float, d: float, b: float, h):
    """Δσv sous une bande (Poulos & Davis 1974, § 3.2) à la profondeur h, au bord de la bande distant de d."""
    h = np.asarray(h, float)
    b1, b2 = np.arctan(d / h), np.arctan((d + b) / h)
    al = b2 - b1
    return q / math.pi * (al + np.sin(al) * np.cos(al + 2 * b1))


def test_E12_surcharge_bande_boussinesq():
    ph1, ph2 = _calcul("E12_surcharge_bande_boussinesq")["phases"][1:3]
    a1, a2 = ph1["pressions"]["amont"], ph2["pressions"]["amont"]
    z = np.array(a1["z"])
    np.testing.assert_allclose(np.array(a2["p0"]) - np.array(a1["p0"]), 0.5 * _boussinesq_bande(50, 2, 4, -z), rtol=1e-6, atol=1e-9)
    assert _boussinesq_bande(50, 2, 4, 2.0) == pytest.approx(4.2, abs=0.05)
    assert _boussinesq_bande(50, 2, 4, 5.0) == pytest.approx(10.2, abs=0.05)


def test_E13_hetenyi_force_en_tete():
    ph = _calcul("E13_hetenyi_force_en_tete")["phases"][1]
    assert ph["ok"]
    EI, k, F0 = 1e5, 2 * 20000.0, 10.0
    lam = (k / (4 * EI)) ** 0.25
    assert lam * 30 > 4 * math.pi
    assert ph["appuis"][0]["effort_kN_m"] == pytest.approx(F0, abs=1e-6)
    assert abs(ph["y_mm"][-1]) / 1000 == pytest.approx(2 * F0 * lam / k, rel=0.05)     # tête = dernier nœud
    assert 2 * F0 * lam / k * 1000 == pytest.approx(0.281, abs=0.001)
    M, zd = np.array(ph["M"]), np.array(ph["z_diag"])
    i = int(np.argmax(np.abs(M)))
    assert abs(M[i]) == pytest.approx(0.3224 * F0 / lam, rel=0.05)
    assert zd[i] == pytest.approx(-math.pi / (4 * lam), abs=0.1)


def test_E14_equilibre_global():
    res = _calcul("E14_equilibre_global")
    for ph in res["phases"]:
        assert ph["ok"], ph["message"]
        assert abs(ph["synthese"]["bilan"]["relatif"]) <= 1e-6
        for face in ("amont", "aval"):
            pr = ph["pressions"][face]
            p, pa, pp = (np.array(pr[k]) for k in ("p", "pa", "pp"))
            assert np.all(p >= pa - 1e-6) and np.all(p <= pp + 1e-6)
    assert res["phases"][2]["appuis"][0]["effort_kN_m"] == pytest.approx(40.0, abs=1e-6)


def test_E15_butee_limite():
    res = _calcul("E15_butee_limite")
    s = res["phases"][1]["synthese"]
    assert s["Bt_kN_m"] == pytest.approx(3 * 20 * 7**2 / 2, rel=1e-6)
    assert 0 < s["Bm_kN_m"] < s["Bt_kN_m"]
    v = {x["nom"]: x for x in res["verifications"]}["Mobilisation de la butée"]
    assert "Bt = 1470 kN/m" in v["detail"]


def test_E16_convergence_maillage():
    texte = _texte("E16_convergence_maillage")

    def valeurs(pas: float) -> np.ndarray:
        r = CLIENT.post("/api/calcul", json={"texte": texte.replace("pas: 0.5", f"pas: {pas}")}).json()
        assert r["ok"], r.get("erreurs")
        ph = r["resultats"]["phases"][-1]
        return np.array([ph["synthese"]["y_max_mm"], ph["synthese"]["M_max"], ph["appuis"][0]["effort_kN_m"]])

    v05, v01, v002 = valeurs(0.5), valeurs(0.1), valeurs(0.02)
    e05, e01 = np.abs(v05 - v002) / np.abs(v002), np.abs(v01 - v002) / np.abs(v002)
    assert np.all(e05 < 0.02) and np.all(e01 < 0.002) and np.all(e01 < e05)     # mesuré : 1,3 % puis 0,1 %


def test_E17_kranz_massif_ancrage():
    """Les grandeurs exposées par la fiche (W, P1, Fh, Fv, R, φ', A, B) sont contrôlées : poids = γ × aire du polygone
    (formule des lacets), P1 = Ka·γ·h²/2 (Rankine, δ = 0, sable sec), puis T_max par la résolution indépendante de
    l'équilibre des forces du massif (deux inconnues : T selon l'axe du tirant, R inclinée de φ' sur la normale à BA)."""
    res = _calcul("E17_kranz_massif_ancrage")
    v = {x["nom"]: x for x in res["verifications"]}["Stabilité du massif d'ancrage (Kranz)"]
    d = {x["symbole"]: x["valeur"] for x in v["donnees"]}
    s = v["schema"]
    assert v["famille"] == "massif_ancrage" and s["type"] == "kranz" and v["principe"] and len(v["etapes"]) >= 5
    (xB, zB), (xA, zA), zt = s["B"], s["A"], s["terrain_amont"]
    assert xA == pytest.approx(-11.0) and zA == pytest.approx(-1.5) and xB == 0.0 and zB < s["fond"]
    # poids du massif O-B-A-A' : aire par la formule des lacets, sable sec γ = 20
    poly = [(0.0, zt), (0.0, zB), (xA, zA), (xA, zt)]
    aire = 0.5 * abs(sum(x0 * z1 - x1 * z0 for (x0, z0), (x1, z1) in zip(poly, poly[1:] + poly[:1])))
    assert d["W"] == pytest.approx(20 * aire, rel=1e-3)
    # poussée sur l'écran fictif passant par A (Rankine, δ = 0)
    ka = math.tan(math.radians(45 - 15)) ** 2
    assert d["P1"] == pytest.approx(ka * 20 * (zt - zA) ** 2 / 2, rel=1e-3)
    # équilibre des forces du massif, recalculé : T·u_T + R·u_R + (−Fh + P1, −W + Fv) = 0
    phi = math.radians(d["φ'"])
    t = np.array([xA - xB, zA - zB]); t /= np.linalg.norm(t)
    n = np.array([-t[1], t[0]])
    if n[1] < 0:
        n = -n
    uR = n * math.cos(phi) + t * math.sin(phi)
    uT = np.array([1.0, 0.0])
    T, R = np.linalg.solve(np.column_stack([uT, uR]), -np.array([-d["Fh"] + d["P1"], -d["W"] + d["Fv"]]))
    assert d["Fv"] == pytest.approx(0.0, abs=1e-9) and d["φ'"] == pytest.approx(30.0)
    assert T == pytest.approx(d["T_max"], rel=1e-6) and R == pytest.approx(d["R"], rel=1e-6)
    assert d["T/T_max"] == pytest.approx(d["T"] / d["T_max"], rel=1e-9)


def test_E18_fond_de_fouille():
    vs = {v["nom"]: v for v in _calcul("E18_fond_de_fouille")["verifications"]}
    dh_av = 5 * 9 / 23
    upl = vs["Fond de fouille — soulèvement (UPL)"]["detail"]
    assert "u au pied (charge amont) = 140 kPa" in upl and "= 180 kPa" in upl and f"{140 / 180:.2f}" in upl
    hyd = vs["Fond de fouille — boulance (HYD)"]["detail"]
    nombres = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", hyd)]
    for attendu in (5.0, round(dh_av, 2), round(10 * dh_av, 1), 90.0, round(10 * dh_av / 90, 2)):
        assert any(abs(n - attendu) < 1e-9 for n in nombres), (attendu, hyd)
    assert f"i = {dh_av / 9:.2f}" in vs["Fond de fouille — renard"]["detail"]


def test_E19_bishop_phi_nul():
    from sout.sol.couches import Couche
    from sout.verifs_geo import bishop

    v = {x["nom"]: x for x in _calcul("E19_bishop_phi_nul")["verifications"]}["Stabilité générale (Bishop)"]
    m = re.search(r"F caractéristique = ([\d.]+) \(centre x = ([-\d.]+), z = ([-\d.]+), R = ([\d.]+) m\)", v["detail"])
    assert m, v["detail"]
    F, xc, zc, R = (float(g) for g in m.groups())
    argile = Couche("Argile", 0.0, gamma=18, gamma_dejauge=8, phi=0.0, c=25.0)
    p = bishop.Profil([argile], 0.0, -4.0, 30.0, None, None, 10.0, [])
    x = np.linspace(xc - R, xc + R, 400001)
    zarc = zc - np.sqrt(np.maximum(R**2 - (x - xc) ** 2, 0))
    h = np.maximum(p.terrain(x) - zarc, 0)
    dx = x[1] - x[0]
    moment = np.sum(18 * h * (xc - x)) * dx
    dans = h > 0
    xa, xb = x[dans].min(), x[dans].max()
    arc = R * (math.asin((xb - xc) / R) - math.asin((xa - xc) / R))
    assert F == pytest.approx(25 * arc * R / moment, rel=0.01)


def test_E20_risberme_deux_methodes():
    texte = _texte("E20_risberme_deux_methodes")
    a = _calcul("E20_risberme_deux_methodes")["phases"][3]
    sans = (texte[:texte.index("\nfouille:")] + texte[texte.index("\nphases:"):]).replace("excaver: -6.5", "excaver: -4.0")
    r = CLIENT.post("/api/calcul", json={"texte": sans}).json()
    assert r["ok"], r.get("erreurs")
    b = r["resultats"]["phases"][3]
    np.testing.assert_allclose(a["y_mm"], b["y_mm"], rtol=1e-9, atol=1e-12)
    np.testing.assert_allclose(a["M"], b["M"], rtol=1e-9, atol=1e-9)
    assert a["appuis"][0]["effort_kN_m"] == pytest.approx(b["appuis"][0]["effort_kN_m"], rel=1e-9)
    s = lire_script(texte.replace("methode: fond_equivalent, cote_equivalente: -4.0", "methode: surcharge_equivalente"))
    bandes = vers_modele(s, catalogue_par_defaut()).phases[2].ajouter_surcharges
    assert len(bandes) == 9 and all(x.largeur == pytest.approx(0.5) for x in bandes)   # 11 bandes de 0,5 m, les 2 de poids nul omises
    assert bandes[0].q == pytest.approx(20 * 2.5) and bandes[0].cote == -6.5 and bandes[0].cote_ecran == "aval"
    assert sum(x.q * x.largeur for x in bandes) == pytest.approx(20 * 8.125, rel=1e-9)


def test_E21_palplanche_moment_resistant():
    from sout import normes
    from sout.parois import construire_ecran

    n = normes.charger()
    s = lire_script(_texte("E21_palplanche_moment_resistant"))
    ec = construire_ecran(s.paroi, catalogue_par_defaut(), n)
    sec, fy = ec.infos["section"], ec.infos["acier"]["fy_MPa"]
    W = sec["Wpl_cm3_m"] if sec.get("Wpl_cm3_m") else sec["Wel_cm3_m"]           # classe 2 : module plastique
    MR = W * fy / 1000 / n.valeur("ec3", "palplanches.gamma_M0")                  # cm³/m × MPa / 1000 = kN·m/m
    v = {x["nom"]: x for x in _calcul("E21_palplanche_moment_resistant")["verifications"]}["Palplanches — flexion et cisaillement"]
    assert v["etat"] != "non_verifiable", v["manquants"]
    assert f"M_c,Rd = {MR:.0f} kN·m/m" in v["detail"], v["detail"]
    M_Ed = float(re.search(r"M_Ed = ([\d.]+)", v["detail"]).group(1))
    assert v["taux"] == pytest.approx(M_Ed / MR, rel=0.02)


def test_E22_tirant_armature():
    from sout import normes

    n = normes.charger()
    res = _calcul("E22_tirant_armature")
    v = {x["nom"]: x for x in res["verifications"]}["Tirant — armature"]
    el = catalogue_par_defaut().element("TORON-DEMO-T15.7")
    f = el.get("fp01k_MPa") or el["fyk_MPa"]
    R = 2 * el["A_cm2"] * 1e-4 * f * 1e3 / n.valeur("nf_p94_282", "tirants.gamma_armature")
    assert f"résistance de calcul {R:.0f} kN" in v["detail"], v["detail"]
    T = max(a["effort_axial_kN"] for ph in res["phases"] if ph["ok"] for a in ph["appuis"])
    assert f"T_k = {T:.0f} kN" in v["detail"]
    g = n.valeur("nf_p94_282", "combinaisons.ELU_fondamental.gamma_effets")
    assert v["taux"] == pytest.approx(g * T / R, rel=1e-3)


def test_E23_lierne_poutre_continue():
    res = _calcul("E23_lierne_poutre_continue")
    v = {x["nom"]: x for x in res["verifications"]}["Lierne — flexion bi-axiale et cisaillement"]
    q = max(a["effort_kN_m"] for ph in res["phases"] if ph["ok"] for a in ph["appuis"])
    My = float(re.search(r"My = ([\d.]+)", v["detail"]).group(1))
    V = float(re.search(r"; V = ([\d.]+) kN", v["detail"]).group(1))
    e = 4.0
    assert V / My == pytest.approx(5 / e, rel=0.01)                 # 0,625·q·e / (q·e²/8) = 5/e
    g = My / (0.125 * q * e**2)
    assert 1.0 <= g <= 1.5 and V == pytest.approx(g * 0.625 * q * e, rel=0.01)


def test_E24_appui_unilateral():
    ph = _calcul("E24_appui_unilateral")["phases"]
    assert ph[2]["appuis"][0]["effort_kN_m"] == 0.0                   # pose sans mouvement
    assert ph[3]["appuis"][0]["actif"] is False and ph[3]["appuis"][0]["effort_kN_m"] == 0.0
    assert ph[4]["appuis"][0]["actif"] is True and ph[4]["appuis"][0]["effort_kN_m"] > 0


def test_E25_variante_branche():
    texte = _texte("E25_variante_branche")
    res = _calcul("E25_variante_branche")
    var = res["phases"][4]
    assert var["depuis"] == "Pose du buton" and var["parent"] == 2
    lin = texte[:texte.index('  - { nom: "Terrassement à -6,5')] + '  - { nom: "Terrassement à -5,5", excaver: -5.5 }\n'
    r = CLIENT.post("/api/calcul", json={"texte": lin}).json()
    assert r["ok"], r.get("erreurs")
    ref = r["resultats"]["phases"][3]
    np.testing.assert_allclose(var["y_mm"], ref["y_mm"], rtol=1e-9, atol=1e-12)
    # moments par la statique : résidu de convergence du solveur près du pied (|M| ~ 0,02 kN·m) -> 1e-6 absolu
    np.testing.assert_allclose(var["M"], ref["M"], rtol=1e-6, atol=1e-6)
    assert var["appuis"][0]["effort_kN_m"] == pytest.approx(ref["appuis"][0]["effort_kN_m"], rel=1e-9)


def test_E26_ecran_non_etanche():
    """Écran non étanche en écoulement 2D : même charge des deux côtés sous le fond, suintement au-dessus, débit plus fort
    que l'écran étanche ; largeur de fouille (12 m) déduite du vis-à-vis de la géométrie."""
    texte = _texte("E26_ecran_non_etanche")
    res = _calcul("E26_ecran_non_etanche")
    ph = res["phases"][-1]
    assert ph["ok"] and ph["hydro"]["etancheite"] == "non_etanche" and ph["hydro"]["debit_paroi_m3_h_m"] > 0
    z = np.array(ph["pressions"]["amont"]["z"])
    ua, uv = np.array(ph["eau"]["u_amont"]), np.array(ph["eau"]["u_aval"])
    sous, dessus = (z < -5.3) & (z > -11.7), (z > -4.7) & (z < -1.3)
    assert np.max(np.abs(ua[sous] - uv[sous])) < 0.01 * 40.0
    assert np.max(np.abs(ua[dessus])) < 0.01 * 40.0
    assert res["hydraulique"]["largeur_fouille"] == pytest.approx(12.0)
    r = CLIENT.post("/api/calcul", json={"texte": texte.replace("etancheite: non_etanche", "etancheite: etanche")}).json()
    assert r["ok"], r.get("erreurs")
    phe = r["resultats"]["phases"][-1]
    assert phe["hydro"]["etancheite"] == "etanche" and phe["hydro"]["debit_m3_h_m"] < ph["hydro"]["debit_m3_h_m"]
    uae, uve = np.array(phe["eau"]["u_amont"]), np.array(phe["eau"]["u_aval"])
    assert np.max(uae[sous] - uve[sous]) > 0.1 * 40.0
    debit = next(v for v in res["verifications"] if v["nom"] == "Débit de pompage")
    assert "à travers l'écran" in debit["detail"]


def test_rapport_de_validation_servi():
    r = CLIENT.get("/api/validation/rapport")
    assert r.status_code == 200 and "Rafale d'exemples élémentaires" in r.text and "<svg" in r.text
