"""J4 — base matériaux et types de paroi."""
import math
from pathlib import Path

import pytest
from openpyxl import Workbook

from sout import normes
from sout.materiaux.base import Catalogue, ReferenceInconnue, catalogue_par_defaut, reconstruire
from sout.materiaux.importer import lire_fichier
from sout.noyau.phasage import calculer
from sout.parois import ErreurParoi
from sout.script.conversion import ErreurConversion, vers_modele
from sout.script.lecteur import lire_script

RACINE = Path(__file__).resolve().parents[3]
CAT = catalogue_par_defaut()
NORMES_VIDES = normes.charger(normes.DOSSIER / 'modeles')  # modèles vides : toutes les valeurs à null


def test_base_demo_et_proprietes_calculees():
    heb = CAT.profil("HEB 300")
    assert heb["demo"] == 1
    # Valeurs du catalogue HEB 300 (EN 10365) : A = 149,1 cm², Iy = 25 170 cm⁴, Wpl,y = 1 869 cm³
    assert heb["A_cm2"] == pytest.approx(149.1, rel=2e-3)
    assert heb["Iy_cm4"] == pytest.approx(25170, rel=2e-3)
    assert heb["Wpl_y_cm3"] == pytest.approx(1869, rel=2e-3)
    t = CAT.profil("TUBE 508x12.5")
    assert t["A_cm2"] == pytest.approx(math.pi / 4 * (508**2 - 483**2) / 100)
    assert CAT.element("modulaire_A")["categorie"] == "butons"
    with pytest.raises(ReferenceInconnue):
        CAT.profil("HEB 9999")


def test_import_csv_et_excel(tmp_path):
    cats = tmp_path / "catalogues"
    cats.mkdir()
    (cats / "profiles_test.csv").write_text(
        "ref;famille;h_mm;b_mm;tw_mm;tf_mm;r_mm\nHEB 300 X;HEB;300;300;11;19;27\n", encoding="utf-8")
    wb = Workbook()
    ws = wb.active
    ws.title = "butons"
    ws.append(["ref", "fabricant", "A_cm2", "N_Rd_kN", "E_MPa"])
    ws.append(["B-TEST", "Essai", 100, 1234, 210000])
    wb.save(cats / "fournisseur.xlsx")
    assert lire_fichier(cats / "fournisseur.xlsx")[0][0] == "butons"
    base = tmp_path / "m.sqlite"
    compte = reconstruire(base, cats)
    assert compte["butons"] >= 3 and compte["profiles"] >= 13
    c = Catalogue(base)
    assert c.element("B-TEST")["N_Rd_kN"] == 1234
    assert c.profil("HEB 300 X")["Iy_cm4"] == pytest.approx(CAT.profil("HEB 300")["Iy_cm4"])
    catalogue_par_defaut.cache_clear()


BASE = """projet: essai
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
"""

PAROIS = {
    "palplanche": "  type: palplanche\n  profil: AZ 26-700\n  acier: S355GP",
    "paroi_moulee": "  type: paroi_moulee\n  epaisseur: 0.6\n  beton: C30/37",
    "pieux_secants": "  type: pieux_secants\n  diametre: 0.8\n  entraxe: 0.65\n  beton: C30/37\n  primaires_armes: false",
    "pieux_disjoints": "  type: pieux_disjoints\n  diametre: 0.8\n  entraxe: 1.6\n  beton: C30/37\n  largeur_reaction_fiche: 1.2",
    "berlinoise": "  type: berlinoise\n  profil: HEB 300\n  acier: S355\n  entraxe: 2.0\n  largeur_reaction_fiche: 0.9\n"
                  "  blindage: { epaisseur: 0.08, materiau: bois }",
}


def _modele(paroi):
    return vers_modele(lire_script(BASE.format(paroi=paroi)), CAT, NORMES_VIDES)


@pytest.mark.parametrize("type_paroi", list(PAROIS))
def test_cinq_types_de_paroi_se_calculent(type_paroi):
    m = _modele(PAROIS[type_paroi])
    res = calculer(m)
    assert res.complet, [p.message for p in res.phases]
    assert res.phases[-1].appuis[0]["effort"] > 0


def test_rigidites_calcul_manuel():
    # Palplanche AZ 26-700 : E = 210 000 MPa, I = 55 510 cm⁴/m -> EI = 2,1e8 × 5,551e-4 = 116 571 kN·m²/m
    assert _modele(PAROIS["palplanche"]).ecran.EI == pytest.approx(2.1e8 * 55510e-8)
    # Paroi moulée e = 0,6 m, Ecm = 33 000 MPa : EI = 3,3e7 × 0,6³/12 = 594 000
    assert _modele(PAROIS["paroi_moulee"]).ecran.EI == pytest.approx(3.3e7 * 0.6**3 / 12)
    # Pieux sécants D = 0,8, primaires non armés, entraxe 0,65 : EI = Ecm·πD⁴/64 / (2 × 0,65)
    assert _modele(PAROIS["pieux_secants"]).ecran.EI == pytest.approx(3.3e7 * math.pi * 0.8**4 / 64 / 1.3)
    # Berlinoise HEB 300 tous les 2 m : EI = 2,1e8 × Iy / 2
    m = _modele(PAROIS["berlinoise"])
    assert m.ecran.EI == pytest.approx(2.1e8 * CAT.profil("HEB 300")["Iy_cm4"] * 1e-8 / 2)
    assert m.ecran.infos["rapport_largeur_fiche"] == pytest.approx(0.45)


def test_fiche_discontinue_sans_largeur_refusee():
    with pytest.raises(ErreurConversion, match="TODO-NORME"):
        _modele(PAROIS["pieux_disjoints"].replace("\n  largeur_reaction_fiche: 1.2", ""))


def test_fiche_discontinue_reduit_la_butee():
    pleine = calculer(_modele(PAROIS["pieux_disjoints"].replace("1.2", "1.6"))).phases[-1]
    reduite = calculer(_modele(PAROIS["pieux_disjoints"])).phases[-1]
    assert abs(reduite.y).max() > abs(pleine.y).max()
    # sous le fond, la butée limite est réduite dans le rapport 1,2 / 1,6
    zf = reduite.terrain_aval
    pp_r = reduite.pressions["aval"]["pp"][reduite.pressions["aval"]["z"] < zf]
    pp_p = pleine.pressions["aval"]["pp"][pleine.pressions["aval"]["z"] < zf]
    assert pp_r == pytest.approx(pp_p * 0.75)


def test_palplanche_en_U_sans_beta_D_refusee():
    with pytest.raises(ErreurConversion, match="β_D"):
        _modele("  type: palplanche\n  profil: U-DEMO-600\n  acier: S355GP")
    m = _modele("  type: palplanche\n  profil: U-DEMO-600\n  acier: S355GP\n  beta_D: 0.7")
    assert m.ecran.EI == pytest.approx(2.1e8 * CAT.palplanche("U-DEMO-600")["I_cm4_m"] * 1e-8 * 0.7)


def test_exemple_du_cahier_des_charges():
    texte = (RACINE / "exemples" / "fouille_exemple.yaml").read_text(encoding="utf-8")
    res = calculer(vers_modele(lire_script(texte), CAT, NORMES_VIDES))
    assert res.complet, [p.message for p in res.phases]


def test_erreur_paroi_sans_donnees():
    with pytest.raises(ErreurConversion, match="obligatoire.*epaisseur"):
        _modele("  type: paroi_moulee")
    assert issubclass(ErreurParoi, Exception)
