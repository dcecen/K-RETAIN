"""J5 — vérifications géotechniques.

Les coefficients partiels utilisés ici sont des VALEURS DE TEST FICTIVES (1,1 ;
1,2 ; ...) qui servent à contrôler la mécanique des formules ; ce ne sont pas
des valeurs de norme.
"""
import math
from pathlib import Path

import numpy as np
import pytest

from sout import normes as mod_normes
from sout.normes import Normes
from sout.noyau.modele import DefAppui, Ecran, Modele, Phase
from sout.noyau.phasage import calculer
from sout.script.lecteur import lire_script
from sout.sol import coefficients as coef
from sout.sol.couches import Couche
from sout.verifications import executer
from sout.verifs_geo import bishop, butee, deplacements, equilibre_vertical, fond_de_fouille, kranz
from sout.materiaux.base import catalogue_par_defaut

RACINE = Path(__file__).resolve().parents[3]
V = lambda x: {"valeur": x, "source": "valeur de test fictive"}  # noqa: E731

NORMES_TEST = Normes({
    "nf_p94_282": {
        "butee": {"gamma_effet": V(1.1), "gamma_R_e": V(1.2), "gamma_R_d": V(1.3)},
        "kranz": {"gamma_effet": V(1.1), "gamma_R": V(1.5)},
        "fond_de_fouille": {"soulevement": {"gamma_dst": V(1.1), "gamma_stb": V(0.9)},
                            "boulance": {"gamma_dst": V(1.2), "gamma_stb": V(0.8)},
                            "renard": {"gradient_admissible": V(0.5)}},
        "stabilite_generale": {"gamma_phi": V(1.0), "gamma_c": V(1.0), "gamma_R_d": V(1.1), "gamma_Q": V(1.0)},
    }
})

SABLE = Couche("Sable", 0.0, gamma=20, gamma_dejauge=10, phi=30, EM=10000, alpha=1 / 3)


def _calc(phases, appuis=None, couches=(SABLE,), pied=-12.0, **kw):
    m = Modele(ecran=Ecran(0.0, pied, 1e5), couches=list(couches), phases=phases, appuis=appuis or {}, **kw)
    return m, calculer(m)


def test_butee_mecanique_avec_coefficients_fictifs():
    m, r = _calc([Phase("Exc", excaver=-4.0)])
    (nom, Bm, Bt), = butee.butee_par_phase(r)
    av = r.phases[-1].pressions["aval"]
    assert Bm == pytest.approx(np.sum(av["L"] * av["p"]))
    v, = butee.verifier(r, NORMES_TEST)
    assert v.taux == pytest.approx(1.1 * 1.2 * 1.3 * Bm / Bt)
    assert v.etat in ("ok", "attention", "non_ok")
    v, = butee.verifier(r, mod_normes.charger())  # modèles livrés : valeurs nulles
    assert v.etat == "non_verifiable" and len(v.manquants) == 3 and "Bm/Bt" in v.detail


def test_kranz_cas_manuel_plan_horizontal():
    """δa = 0, tirant horizontal, B et A à la même profondeur H, sable sec homogène :
    l'équilibre donne T_max = Fh − P1 + W·tan φ ; avec Fh = P1 (même hauteur) : T_max = γ·H·L·tan φ."""
    H, L = 8.0, 12.0
    P1 = 0.5 * coef.kah(30) * 20 * H**2
    T, info = kranz.t_max([SABLE], 0.0, None, -H, -L, -H, 0.0, Fh_ecran=P1, Fv_ecran=0.0)
    assert info["W"] == pytest.approx(20 * H * L, rel=1e-3)
    assert info["P1"] == pytest.approx(P1, rel=1e-3)
    assert T == pytest.approx(20 * H * L * math.tan(math.radians(30)), rel=2e-3)


def test_kranz_verification_sur_calcul_phase():
    app = {"T1": DefAppui("T1", -1.5, 8000.0, precharge=60.0, type="tirant",
                          infos={"angle": 20.0, "espacement": 2.5, "longueur_libre": 9.0, "longueur_scellee": 6.0})}
    m, r = _calc([Phase("Exc1", excaver=-2.5), Phase("T1", poser=["T1"]), Phase("Exc2", excaver=-6.0)], app)
    assert r.complet
    v, = kranz.verifier(m, r, NORMES_TEST)
    assert v.taux is not None and v.taux > 0 and "T_max" in v.detail
    assert -6.0 > kranz.point_B(r.phases[-1]) > -12.0


def test_fond_de_fouille_calcul_manuel():
    # pied −14, fond −5, nappe amont 0, aval au fond : Δh = 5 m, cheminement 14 m côté amont + 9 m côté fouille
    # (buton en tête pour que l'écran soit stable)
    app = {"B": DefAppui("B", -0.5, 1e5)}
    m, r = _calc([Phase("Pose", poser=["B"]), Phase("Exc", excaver=-5.0, eau={"amont": 0.0, "aval": -5.0})],
                 app, pied=-14.0, eau_amont=0.0, eau_aval=0.0)
    assert r.complet, r.phases[-1].message
    c = fond_de_fouille.charges(m, r.phases[-1])
    dh_av = 5 * 9 / 23
    assert c["dh_aval"] == pytest.approx(dh_av)
    assert c["gradient"] == pytest.approx(dh_av / 9)
    assert c["sigma_v_eff"] == pytest.approx(90.0)       # 9 m × γ' = 10
    assert c["sigma_v_total"] == pytest.approx(180.0)    # + u = 10 × 9
    assert c["u_pied_amont"] == pytest.approx(140.0)     # 10 × 14
    vs = {v.nom: v for v in fond_de_fouille.verifier(m, r, NORMES_TEST)}
    assert vs["Fond de fouille — soulèvement (UPL)"].taux == pytest.approx(1.1 * 140 / (0.9 * 180))
    assert vs["Fond de fouille — boulance (HYD)"].taux == pytest.approx(1.2 * (10 * dh_av) / (0.8 * 90))
    assert vs["Fond de fouille — renard"].taux == pytest.approx((dh_av / 9) / 0.5)


def test_bishop_phi_nul_egal_equilibre_des_moments():
    """φ = 0 : Bishop se réduit à l'équilibre des moments F = c·L_arc·R / Σ W·(xc − x).
    Contrôle par une intégration indépendante très fine de la masse glissante."""
    argile = Couche("Argile", 0.0, gamma=18, gamma_dejauge=8, phi=0.0, c=25.0)
    p = bishop.Profil([argile], 0.0, -4.0, 30.0, None, None, 10.0, [])
    xc, zc, R = 2.0, 6.0, 13.0
    F = bishop.facteur(p, xc, zc, R, n_tranches=400)
    x = np.linspace(xc - R, xc + R, 400001)
    zarc = zc - np.sqrt(np.maximum(R**2 - (x - xc) ** 2, 0))
    h = np.maximum(p.terrain(x) - zarc, 0)
    dx = x[1] - x[0]
    moment = np.sum(18 * h * (xc - x)) * dx
    dans = h > 0
    xa, xb = x[dans].min(), x[dans].max()
    arc = R * (math.asin((xb - xc) / R) - math.asin((xa - xc) / R))
    assert F == pytest.approx(25 * arc * R / moment, rel=1e-2)


def test_bishop_superieur_a_fellenius_et_recherche():
    p = bishop.Profil([SABLE], 0.0, -5.0, 25.0, None, None, 10.0, [])
    F, cercle = bishop.recherche(p, 0.0, -10.0)
    assert cercle is not None and 1.0 < F < 10.0
    # Plus de cohésion -> plus stable
    p2 = bishop.Profil([Couche("S", 0.0, 20, 10, 30, c=10)], 0.0, -5.0, 25.0, None, None, 10.0, [])
    assert bishop.facteur(p2, *cercle) > bishop.facteur(p, *cercle)


def test_deplacements_et_criteres():
    m, r = _calc([Phase("Exc", excaver=-4.0)])
    s = lire_script((RACINE / "exemples" / "fouille_exemple_EI.yaml").read_text(encoding="utf-8")
                    + "criteres: { deplacement_max_mm: 30 }\n")
    v = deplacements.verifier(r, s.criteres)
    assert v[0].taux == pytest.approx(np.abs(r.phases[-1].y).max() * 1e3 / 30)
    assert v[1].etat == "non_verifiable"


def test_equilibre_vertical_butee_verticale_non_mobilisable():
    # δp/φ = 1 et écran sans poids : la butée verticale soulève l'écran -> échec
    sol = Couche("Sable", 0.0, 20, 10, 30, EM=10000, alpha=1 / 3, delta_p_sur_phi=1.0)
    m, r = _calc([Phase("Exc", excaver=-4.0)], couches=[sol])
    v, = equilibre_vertical.verifier(m, r, NORMES_TEST)
    assert v.etat == "non_ok" and "montante" in v.detail


def test_execution_complete_exemple():
    s = lire_script((RACINE / "exemples" / "fouille_exemple.yaml").read_text(encoding="utf-8"))
    ex = executer(s, catalogue_par_defaut(), mod_normes.charger())
    noms = {v.nom for v in ex.verifications}
    assert {"Mobilisation de la butée", "Stabilité générale (Bishop)", "Fond de fouille — boulance (HYD)"} <= noms
    assert all(v.etat == "non_verifiable" for v in ex.verifications if v.categorie == "geotechnique")
    assert all(v.manquants for v in ex.verifications if v.etat == "non_verifiable" and "critère" not in v.detail)
