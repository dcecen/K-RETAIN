"""Étanchéité hydraulique des écrans (parois/etancheite.py, hydraulique/ecoulement.py, hydraulique/grille.py).

Références : loi de Darcy et résistances hydrauliques en série (Cedergren, Seepage, Drainage and Flow Nets, ch. 3 ;
Bear 1972) ; hypothèses d'étanchéité par type de paroi documentées dans parois/etancheite.py (hypothèse de projet).
"""
import numpy as np
import pytest

from sout.hydraulique import ecoulement
from sout.hydraulique.grille import Grille, resoudre_grille
from sout.noyau.modele import DefAppui, Ecran, Modele, Phase
from sout.noyau.phasage import calculer
from sout.script.conversion import vers_modele
from sout.script.lecteur import ScriptInvalide, lire_script
from sout.sol.couches import Couche

SABLE = Couche("Sable", 0.0, 20, 10, 32, EM=12000, alpha=1 / 3, k_h=1e-5, k_v=1e-5)


def _reseau(etancheite="etanche", R=None, aval_ferme=True, **kw):
    args = dict(couches=[SABLE], z_terrain_amont=0.0, z_fond=-5.0, z_pied=-12.0, z_tete=0.0, h_amont=-1.0, h_aval=None,
                largeur_amont=30.0, largeur_aval=10.0, z_substratum=-30.0, pas=0.5, gamma_w=10.0)
    args.update(kw)
    return ecoulement.DifferencesFinies(**args, etancheite=etancheite, resistance_paroi=R, aval_ferme=aval_ferme).resoudre()


# --------------------------------------------------------------------------- 1. Darcy 1D à travers une paroi (exact)
def test_darcy_1d_resistances_en_serie_a_travers_une_paroi():
    """Rangée horizontale de 20 cellules (dx = 0,5 m, k = 1e-5 m/s, longueur L = 10 m) entre deux réservoirs : charges
    10 m et 0 m imposées sur les faces verticales extrêmes, paroi de résistance R = e/k_p = 0,5/1e-7 = 5e6 s sur la face
    entre les cellules 9 et 10. Darcy, résistances en série : v = Δh / (L/k + R) ; charge linéaire dans le sol de part
    et d'autre, saut v·R à la traversée de la paroi (exact à la précision machine)."""
    n, dx, k, R = 20, 0.5, 1e-5, 0.5 / 1e-7
    g = Grille(x=np.arange(n + 1) * dx, z=np.array([0.0, 1.0]))
    kx = np.full(g.forme, k); kz = kx.copy()
    fixe = np.full(g.forme, np.nan)
    faces = np.full((n + 1, 1), np.nan); faces[0, 0], faces[n, 0] = 10.0, 0.0
    res = np.full((n + 1, 1), np.nan); res[10, 0] = R
    h = resoudre_grille(g, kx, kz, fixe, resistance_x=res, charge_face_x=faces)[:, 0]
    v = 10.0 / (n * dx / k + R)
    attendu = np.array([10.0 - v * ((i + 0.5) * dx / k + (R if i >= 10 else 0.0)) for i in range(n)])
    np.testing.assert_allclose(h, attendu, rtol=1e-9, atol=1e-9)
    assert h[9] - h[10] == pytest.approx(v * (dx / k + R), rel=1e-9)
    # sans résistance : charge linéaire de 10 à 0 (écran transparent)
    h0 = resoudre_grille(g, kx, kz, fixe, charge_face_x=faces)[:, 0]
    np.testing.assert_allclose(h0, 10.0 * (1 - (np.arange(n) + 0.5) / n), rtol=1e-9, atol=1e-9)


# --------------------------------------------------------------------------- 2. non-régression : étanche = comportement antérieur
def test_ecran_etanche_par_defaut_inchange():
    base = ecoulement.DifferencesFinies([SABLE], 0.0, -5.0, -12.0, 0.0, -1.0, None, 30.0, 10.0, -30.0, 0.5, 10.0).resoudre()
    r = _reseau("etanche")
    np.testing.assert_allclose(r.h, base.h, rtol=1e-12, equal_nan=True)
    assert r.debit == pytest.approx(base.debit, rel=1e-12) and r.debit_paroi == 0.0 and r.etancheite == "etanche"


# --------------------------------------------------------------------------- 3. écran non étanche
def test_ecran_non_etanche_pression_differentielle_nulle_et_debit_plus_fort():
    r, e = _reseau("non_etanche"), _reseau("etanche")
    z = np.linspace(-11.5, -5.5, 25)
    # sous le fond : même charge des deux côtés de l'écran (écran transparent)
    np.testing.assert_allclose(r.pression("amont", z), r.pression("aval", z), atol=1e-6)
    # au-dessus du fond : face de suintement vers la fouille, u = 0 côté terre
    np.testing.assert_allclose(r.pression("amont", np.linspace(-4.5, -1.5, 13)), 0.0, atol=1e-6)
    # l'écran étanche, lui, porte une pression différentielle
    assert np.max(e.pression("amont", z) - e.pression("aval", z)) > 10.0
    assert r.debit_paroi > 0 and r.debit > e.debit
    assert r.etancheite == "non_etanche"


# --------------------------------------------------------------------------- 4. écran partiellement étanche
def test_ecran_partiellement_etanche_entre_les_deux():
    e, n = _reseau("etanche"), _reseau("non_etanche")
    p = _reseau("partielle", R=0.5 / 1e-7)
    assert e.debit < p.debit < n.debit
    z = np.linspace(-11.5, -5.5, 25)
    du_e = np.max(e.pression("amont", z) - e.pression("aval", z))
    du_p = np.max(p.pression("amont", z) - p.pression("aval", z))
    assert 0.0 < du_p < du_e
    # plus l'écran est perméable, plus on se rapproche de l'écran transparent
    p2 = _reseau("partielle", R=0.5 / 1e-5)
    assert p.debit < p2.debit < n.debit
    with pytest.raises(ecoulement.ErreurHydraulique):
        _reseau("partielle", R=None)


# --------------------------------------------------------------------------- 5. paroi ouverte (pas de vis-à-vis)
def test_paroi_ouverte_charge_aval_imposee_au_loin_enceinte_fermee_flux_nul_au_vis_a_vis():
    """Enceinte fermée : flux nul au vis-à-vis (plan de symétrie à mi-largeur), la charge y reste au-dessus du niveau
    de la fouille. Paroi ouverte : pas de vis-à-vis, charge de la fouille imposée en limite lointaine du domaine."""
    ferme = _reseau(largeur_aval=30.0)
    ouvert = _reseau(largeur_aval=30.0, aval_ferme=False)
    zs = np.array([-6.0, -8.0, -12.0, -20.0])
    loin_o = np.array([ouvert.charge_le_long(z=z, xs=np.array([29.75]))[0] for z in zs])
    loin_f = np.array([ferme.charge_le_long(z=z, xs=np.array([29.75]))[0] for z in zs])
    np.testing.assert_allclose(loin_o, -5.0, atol=1e-9)          # charge aval imposée au loin
    assert np.all(loin_f > -5.0 + 1e-3)                         # flux nul : excès de charge au plan de symétrie
    # flux nul au vis-à-vis : gradient horizontal négligeable sur les deux dernières colonnes du domaine fermé
    j = int(np.argmin(np.abs(ferme.zc + 8.0)))
    assert abs(ferme.h[-1, j] - ferme.h[-2, j]) < 0.02 * abs(ferme.h[0, j] - ferme.h[-1, j])
    assert ouvert.aval_ferme is False and ferme.aval_ferme is True
    assert ouvert.debit != pytest.approx(ferme.debit, rel=1e-3)


# --------------------------------------------------------------------------- 6. régime hydrostatique : nappe ramenée
def test_regime_hydrostatique_ecran_non_etanche_nappe_ramenee_au_niveau_aval():
    app = {"B": DefAppui("B", -0.5, 1e5)}
    phases = [Phase("Pose", poser=["B"]), Phase("Exc", excaver=-6.0, eau={"aval": -6.0})]
    base = dict(couches=[SABLE], appuis=app, phases=phases, eau_amont=-1.0, eau_aval=-1.0)
    draine = calculer(Modele(ecran=Ecran(0.0, -14.0, 1e5, infos={"type": "berlinoise", "etancheite": "non_etanche"}), **base))
    etanche = calculer(Modele(ecran=Ecran(0.0, -14.0, 1e5, infos={"type": "palplanche", "etancheite": "etanche"}), **base))
    assert draine.complet and etanche.complet
    ph = draine.phases[-1]
    z = ph.eau["z"]
    # nappe côté terre ramenée à −6 (eau côté fouille) : u identiques des deux côtés, hydrostatiques depuis −6
    np.testing.assert_allclose(ph.eau["u_amont"], ph.eau["u_aval"], atol=1e-9)
    np.testing.assert_allclose(ph.eau["u_amont"], np.where(z < -6.0, 10.0 * (-6.0 - z), 0.0), atol=1e-9)
    assert any("non étanche" in a for a in draine.avertissements)
    # l'écran étanche garde la nappe à −1 côté terre
    phe = etanche.phases[-1]
    assert np.max(phe.eau["u_amont"] - phe.eau["u_aval"]) == pytest.approx(50.0, abs=1e-6)
    assert not any("non étanche" in a for a in etanche.avertissements)


# --------------------------------------------------------------------------- 7. lecteur et conversion
SCRIPT = """projet: test
calcul: {{ kh: impose }}
paroi: {{ type: {type}, EI: 1.0e5, tete: 0.0, pied: -10.0{extra} }}
sol:
  - {{ nom: Sable, toit: 0.0, gamma: 20, gamma_dejauge: 10, phi: 30, kh: 10000, k_h: 1.0e-5 }}
eau:
  service: {{ amont: -1.0, aval: -1.0 }}
{hydraulique}appuis:
  B1: {{ type: buton, raideur: 100000, cote: -0.5, espacement: 1.0 }}
phases:
  - {{ nom: P1, poser: B1 }}
  - {{ nom: P2, excaver: -4.0, eau: {{ aval: -4.0 }} }}
"""


def _script(type="palplanche", extra="", hydraulique=""):
    return SCRIPT.format(type=type, extra=extra, hydraulique=hydraulique)


def _erreurs(texte: str) -> str:
    with pytest.raises(ScriptInvalide) as exc:
        lire_script(texte)
    return " | ".join(e.message for e in exc.value.erreurs)


def test_lecteur_etancheite_partielle_exige_k_paroi_epaisseur_et_differences_finies():
    assert "k_paroi" in _erreurs(_script(extra=", etancheite: partielle"))
    msg = _erreurs(_script(extra=", etancheite: partielle, k_paroi: 1.0e-7"))
    assert "epaisseur_hydraulique" in msg and "differences_finies" in msg
    assert "sans effet" in _erreurs(_script(extra=", k_paroi: 1.0e-7"))
    s = lire_script(_script(extra=", etancheite: partielle, k_paroi: 1.0e-7, epaisseur_hydraulique: 0.5",
                            hydraulique="hydraulique: { regime: differences_finies, substratum: -30.0 }\n"))
    m = vers_modele(s)
    assert m.ecran.infos["etancheite"] == "partielle"
    assert m.ecran.infos["resistance_hydraulique"] == pytest.approx(0.5 / 1e-7)


def test_defaut_etancheite_par_type_de_paroi_et_calcul_de_bout_en_bout():
    assert vers_modele(lire_script(_script("palplanche"))).ecran.infos["etancheite"] == "etanche"
    m = vers_modele(lire_script(_script("berlinoise", extra=", entraxe: 2.0, largeur_reaction_fiche: 0.3")))
    assert m.ecran.infos["etancheite"] == "non_etanche"
    res = calculer(m)
    assert res.complet and any("non étanche" in a for a in res.avertissements)
    ph = res.phases[-1]
    np.testing.assert_allclose(ph.eau["u_amont"], ph.eau["u_aval"], atol=1e-9)


GEOMETRIE = """geometrie:
  ouvrages:
    contour: [[0, 0], [20, 0], [20, 12], [0, 12]]
    cotes: {{ sud: 0, est: 1, nord: 2, ouest: 3 }}
{ferme}coupe_calcul: {{ x: 10.0, y: 0.0, ni: [0.0, 1.0], t: [1.0, 0.0], k: 0, s: 10.0, cote: sud }}
"""


def test_largeur_de_fouille_deduite_de_la_geometrie_et_paroi_ouverte():
    hyd = "hydraulique: { regime: differences_finies, substratum: -30.0 }\n"
    m = vers_modele(lire_script(_script(hydraulique=hyd + GEOMETRIE.format(ferme=""))))
    assert m.hydraulique["largeur_fouille"] == pytest.approx(12.0)
    assert "vis-à-vis" in m.hydraulique["largeur_fouille_origine"]
    assert m.hydraulique.get("aval_ferme", True) is True
    # largeur donnée dans le script : conservée
    m2 = vers_modele(lire_script(_script(hydraulique="hydraulique: { regime: differences_finies, largeur_fouille: 8.0 }\n" + GEOMETRIE.format(ferme=""))))
    assert m2.hydraulique["largeur_fouille"] == 8.0
    # paroi ouverte (polyligne de trois arêtes : pas de côté 3) : pas de vis-à-vis, domaine côté fouille étendu
    ouverte = GEOMETRIE.format(ferme="    ferme: false\n").replace(", ouest: 3", "")
    assert "ouest" in _erreurs(_script(hydraulique=hyd + GEOMETRIE.format(ferme="    ferme: false\n")))
    m3 = vers_modele(lire_script(_script(hydraulique=hyd + ouverte)))
    assert m3.hydraulique["aval_ferme"] is False and m3.hydraulique.get("largeur_fouille") is None
    res = calculer(m3)
    assert res.complet and res.phases[-1].hydro["aval_ferme"] is False
