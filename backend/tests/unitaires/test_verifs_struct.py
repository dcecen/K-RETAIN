"""J6 — vérifications structurelles.

Les coefficients de ce fichier sont des VALEURS DE TEST : ils servent à vérifier
les formules contre des calculs manuels ou des valeurs de tableaux publiés ; ce ne
sont pas des valeurs de norme pour RetainWall (qui ne lit que docs/normes).
"""
import math
from pathlib import Path

import pytest

from sout import normes as mod_normes
from sout.materiaux.base import catalogue_par_defaut
from sout.normes import Normes
from sout.script.lecteur import lire_script
from sout.verifications import executer
from sout.verifs_struct import ec2, ec3

RACINE = Path(__file__).resolve().parents[3]
V = lambda x: {"valeur": x, "source": "valeur de test"}  # noqa: E731


@pytest.mark.parametrize("lam,alpha,attendu", [
    (1.0, 0.21, 0.6656),   # tableau EN 1993-1-1 : courbe a, λ̄ = 1,0
    (1.0, 0.34, 0.5970),   # courbe b
    (1.0, 0.49, 0.5399),   # courbe c
    (0.1, 0.34, 1.0),      # palier
])
def test_chi_contre_tableau_publie(lam, alpha, attendu):
    assert ec3.chi(lam, alpha, 0.2) == pytest.approx(attendu, abs=5e-4)


def test_euler_calcul_manuel():
    # Tube 508×12,5 : I = 59 755 cm⁴, L = 18 m : Ncr = π²·2,1e8·5,9755e-4 / 324 = 3 823 kN
    assert ec3.n_cr(210000, 59755, 18.0) == pytest.approx(math.pi**2 * 2.1e8 * 5.9755e-4 / 324)
    f = ec3.flambement(194.6, 59755, 355, 210000, 18.0, 0.21, 0.2, 1.0)
    assert f["lambda"] == pytest.approx(math.sqrt(194.6e-4 * 355e3 / f["N_cr"]))
    assert f["N_b_Rd"] == pytest.approx(f["chi"] * 194.6e-4 * 355e3)


MAT = ec2.Materiaux(fck=30, fyk=500, gamma_c=1.5, gamma_s=1.15, alpha_cc=1.0, lam=0.8, eta=1.0, eps_cu3=3.5, Es=200000)


def test_flexion_rectangulaire_calcul_manuel():
    # M = 300 kN·m, b = 1 m, d = 0,55 m, fcd = 20 MPa, fyd = 434,8 MPa :
    # μ = 0,3/(0,3025×20) = 0,04959 ; λx = d(1 − √(1 − 2μ)) = 0,02798 m ; As = 20×0,02798/434,8 = 12,87 cm²
    f = ec2.flexion_rectangulaire(300, 1.0, 0.55, MAT)
    assert f["mu"] == pytest.approx(0.3 / (0.3025 * 20))
    assert f["As_cm2"] == pytest.approx(12.87, abs=0.01)
    assert ec2.m_rd_rectangulaire(f["As_cm2"], 1.0, 0.55, MAT) == pytest.approx(300, rel=1e-6)


def test_section_circulaire_coherente():
    D, rs = 0.8, 0.33
    assert ec2.m_rd_circulaire(D, 1e-6, rs, MAT) == pytest.approx(0.0, abs=1.0)
    m1, m2 = ec2.m_rd_circulaire(D, 40, rs, MAT), ec2.m_rd_circulaire(D, 80, rs, MAT)
    assert 0 < m1 < m2
    As = ec2.as_circulaire(500, D, rs, MAT)
    assert ec2.m_rd_circulaire(D, As, rs, MAT) == pytest.approx(500, rel=1e-3)
    # Ordre de grandeur : bras de levier entre 0,5 et 0,9 fois le diamètre du cercle d'armatures
    z = 500 / (As * 1e-4 * MAT.fyd * 1e3 / 2)
    assert 0.5 * 2 * rs < z < 0.9 * 2 * rs + 0.2


def test_vrdc_calcul_manuel():
    # k = 1 + √(200/550) = 1,603 ; ρ = 12,87e-4/0,55 ; v_min = 0,035·k^1,5·√30 = 0,389 MPa > v -> 214 kN
    VR = ec2.v_rd_c(1.0, 0.55, 12.87, 30, 1.5, 0.12, 0.035, 2.0, 0.02)
    k = 1 + math.sqrt(200 / 550)
    assert VR == pytest.approx(0.035 * k**1.5 * math.sqrt(30) * 0.55 * 1e3, rel=1e-6)


NORMES_TEST = Normes({
    "nf_p94_282": {"combinaisons": {"ELU_fondamental": {"gamma_effets": V(1.35)}},
                   "tirants": {"gamma_armature": V(1.1)}},
    "ec3": {"gamma_M0": V(1.0), "gamma_M1": V(1.0),
            "flambement": {"alpha": {"a": V(0.21), "b": V(0.34), "c": V(0.49)}, "lambda_0": V(0.2),
                           "courbe_tube": V("a"), "courbe_profil_i_axe_faible": V("c")},
            "temperature": {"alpha_T": V(1.2e-5), "delta_T": V(10.0), "coefficient_bridage": V(0.5)},
            "palplanches": {"gamma_M0": V(1.0), "beta_B": V(1.0)},
            "cisaillement": {"rapport_reduction": V(0.5)}},
})


def test_execution_structure_exemple_avec_coefficients_de_test():
    texte = (RACINE / "exemples" / "fouille_exemple.yaml").read_text(encoding="utf-8")
    texte = texte.replace("precharge: 50 }", "precharge: 50, lierne: HEB 300 }")
    s = lire_script(texte)
    ex = executer(s, catalogue_par_defaut(), NORMES_TEST)
    vs = {v.nom: v for v in ex.verifications if v.categorie == "structure"}
    pal = vs["Palplanches — flexion et cisaillement"]
    assert pal.taux is not None and 0 < pal.taux < 2
    # M_Ed / M_c,Rd attendu : W élastique (classe non renseignée) 2 600 cm³/m, fy 355 MPa
    Mk = max(abs(p.M).max() for p in ex.resultat.phases if p.ok)
    assert pal.taux >= 1.35 * Mk / (2600e-6 * 355e3) - 1e-9
    assert vs["Buton — flambement et flexion"].taux > 0
    assert vs["Buton — résistance fabricant"].taux == pytest.approx(
        1.35 * max(a["effort"] for p in ex.resultat.phases if p.ok for a in p.appuis) * 6 / 2000)
    assert vs["Lierne — flexion bi-axiale et cisaillement"].taux > 0
    assert vs["Lierne — raidisseurs"].etat == "non_verifiable"
    sug = ex.suggestions[0]
    assert sug["appui"] == "B1" and sug["element"] is not None and sug["taux"] <= 1.0


def test_structure_sans_normes_non_verifiable():
    texte = (RACINE / "exemples" / "fouille_exemple.yaml").read_text(encoding="utf-8")
    ex = executer(lire_script(texte), catalogue_par_defaut(), mod_normes.charger())
    for v in ex.verifications:
        if v.categorie == "structure":
            assert v.etat == "non_verifiable"
    assert "non déterminable" in ex.suggestions[0]["message"]


NORMES_TEST_EC2 = Normes({
    **NORMES_TEST.donnees,
    "ec2": {"gamma_c": V(1.5), "gamma_s": V(1.15), "alpha_cc": V(1.0), "fyk_armatures": V(500), "Es": V(200000),
            "diagramme_rectangulaire": {"lambda": V(0.8), "eta": V(1.0), "epsilon_cu3": V(3.5)},
            "tranchant": {"C_Rd_c": V(0.12), "coef_v_min": V(0.035), "k_max": V(2.0), "rho_l_max": V(0.02)}},
})

GABARIT = """projet: essai structure
paroi:
{paroi}
  tete: 0.0
  pied: -12.0
sol:
  - {{ nom: Sable, toit: 0.0, gamma: 20, gamma_dejauge: 10, phi: 33, EM: 12000, alpha: 0.33 }}
appuis:
  B1: {{ type: buton, element: modulaire_A, cote: -1.0, espacement: 5.0, longueur: 16.0 }}
phases:
  - {{ nom: Exc1, excaver: -2.0 }}
  - {{ nom: Buton, poser: B1 }}
  - {{ nom: Exc2, excaver: -5.0 }}
verifications: [structure]
"""


@pytest.mark.parametrize("paroi,attendus", [
    ("  type: paroi_moulee\n  epaisseur: 0.6\n  beton: C30/37\n  enrobage: 0.07\n  armatures_fouille: 20\n  armatures_terre: 10",
     ["Paroi moulée — flexion (face fouille)", "Paroi moulée — flexion (face terre)",
      "Paroi moulée — effort tranchant sans armatures"]),
    ("  type: pieux_disjoints\n  diametre: 0.8\n  entraxe: 1.6\n  beton: C30/37\n  largeur_reaction_fiche: 1.2\n"
     "  enrobage: 0.08\n  armatures_pieu: 60", ["Pieux — flexion (section circulaire)"]),
    ("  type: berlinoise\n  profil: HEB 300\n  acier: S355\n  entraxe: 2.0\n  largeur_reaction_fiche: 0.9\n"
     "  blindage: { epaisseur: 0.08, materiau: bois, resistance: 10 }",
     ["Profilés de berlinoise — flexion et cisaillement", "Blindage entre profilés — flexion"]),
])
def test_parois_beton_et_berlinoise(paroi, attendus):
    s = lire_script(GABARIT.format(paroi=paroi))
    ex = executer(s, catalogue_par_defaut(), NORMES_TEST_EC2)
    vs = {v.nom: v for v in ex.verifications}
    for nom in attendus:
        assert vs[nom].taux is not None and vs[nom].taux > 0, (nom, vs[nom].detail, vs[nom].manquants)
