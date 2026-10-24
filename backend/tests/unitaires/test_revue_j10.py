"""Non-régression des corrections issues de la revue croisée J10."""
import math

import numpy as np
import pytest

from sout.appuis.construction import ErreurAppui, construire_appui
from sout.appuis.raideurs import raideur_dalle
from sout.noyau.modele import DefAppui, Ecran, Modele, Phase
from sout.pseudo3d.calcul import MoteurPseudo3D
from sout.script.schema import Appui
from sout.sol import kerisel_absi
from sout.sol.couches import Couche
from sout.verifs_geo import bishop

SABLE = Couche("Sable", 0.0, 20, 10, 30, EM=10000, alpha=1 / 3)


@pytest.mark.lent
def test_bishop_affinage_au_moins_aussi_bon_qu_une_grille_fine():
    p = bishop.Profil([SABLE], 0.0, -5.0, 25.0, None, None, 10.0, [])
    F_affine, _ = bishop.recherche(p, 0.0, -10.0)
    # grille fine de référence (anciennes bornes, n = 40)
    H, meilleur = 10.0, math.inf
    for xc in np.linspace(-1.5 * H, 0.6 * H, 40):
        for zc in np.linspace(0.1 * H, 2.0 * H, 40):
            for zb in np.linspace(-10 - 0.05 * H, -10 - 1.2 * H, 20):
                F = bishop._F(p, -10.0, xc, zc, zb, 1.0, 1.0, 1.0)
                meilleur = min(meilleur, F)
    assert F_affine <= meilleur * 1.003


def test_pseudo3d_appuis_a_leur_espacement_exact():
    app = {"B": DefAppui("B", -1.0, 30000.0, infos={"espacement": 4.0})}
    m = Modele(ecran=Ecran(0.0, -10.0, 1e5), couches=[SABLE], appuis=app, pas=0.5,
               phases=[Phase("Pose", poser=["B"]), Phase("Exc", excaver=-3.0)])
    mot = MoteurPseudo3D(m, 10.0, 0.5)
    pos = mot._positions_appui(4.0)
    assert np.allclose(np.diff(pos), 4.0) and len(pos) == 2
    assert pos[0] == pytest.approx(10.0 - pos[-1])          # centrés
    r = mot.calculer()
    assert r.phases[-1].ok and len(r.phases[-1].appuis) == 2


def test_dalle_raideur_non_divisee_par_l_espacement():
    a = Appui(type="dalle", cote=-1.0, epaisseur=0.3, E=30000, longueur=20.0, espacement=5.0)
    assert construire_appui("D", a).raideur == pytest.approx(raideur_dalle(30000, 0.3, 20.0))


def test_tirant_sans_longueur_message_clair():
    a = Appui(type="tirant", cote=-1.0, E=195000, A=6.0)
    with pytest.raises(ErreurAppui, match="longueur_libre"):
        construire_appui("T", a)


def test_kerisel_absi_interpolation_logarithmique(tmp_path, monkeypatch):
    (tmp_path / "kp.csv").write_text("phi;delta_sur_phi;K\n30;0;3.0\n30;1;6.0\n35;0;3.69\n35;1;8.0\n",
                                     encoding="utf-8")
    monkeypatch.setattr(kerisel_absi, "DOSSIER", tmp_path)
    kerisel_absi._charger.cache_clear()
    try:
        K = kerisel_absi._interpoler("kp", 32.5, 0.0)
        assert K == pytest.approx(math.sqrt(3.0 * 3.69))      # moyenne géométrique à mi-chemin
        assert K < (3.0 + 3.69) / 2                            # plus faible que l'interpolation linéaire
    finally:
        kerisel_absi._charger.cache_clear()
