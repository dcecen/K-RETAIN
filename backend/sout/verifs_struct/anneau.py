"""Vérifications de l'anneau comprimé d'une paroi circulaire (famille « anneau »).

- Anneau — compression : effort normal circonférentiel de calcul N_Ed(z) = γ_effets·N_θ(z), N_θ = E·t·w/R
  (sout.parois.anneau, Timoshenko & Woinowsky-Krieger § 114), comparé à la résistance du béton seul
  N_Rd(z) = t(z)·fcd, fcd = αcc·fck/γc (EN 1992-1-1 § 3.1.6 (1)P, compression centrée ; armatures négligées,
  du côté de la sécurité). Le joint des pieux sécants peut être en béton non armé : l'EN 1992-1-1 ch. 12 donne
  alors αcc,pl, absent de docs/normes (TODO-NORME) : la valeur αcc de la section armée est employée et la fiche
  le signale. Une traction circonférentielle (w vers le terrain) n'est pas reprise par le béton : vérification
  « non vérifiable » avec la cote et la valeur.
- Anneau — stabilité de forme (indicatif) : pression critique d'un tube long sous pression extérieure uniforme
  p_cr = E·t³/(4·R³) (ν = 0, borne inférieure ; Timoshenko & Gere, Theory of Elastic Stability, ch. 7) comparée à
  la pression reprise par l'anneau p = N_θ/R. Aucun coefficient de sécurité n'existe dans docs/normes pour ce
  mode : la vérification est « non vérifiable » et affiche le rapport p/p_cr.
Coefficients : docs/normes/nf_p94_282.yaml (combinaisons.*.gamma_effets) et docs/normes/ec2.yaml (alpha_cc, gamma_c).
"""
from __future__ import annotations

import numpy as np

from ..parois.anneau import pression_critique_tube
from ..verifs import Lecteur, Verif, donnee, resultat

SRC_ANNEAU = ("Timoshenko & Woinowsky-Krieger, Theory of Plates and Shells, ch. 15 § 114 (N_θ = E·t·w/R) ; "
              "EN 1992-1-1 § 3.1.6 (fcd) — coefficients : docs/normes/ec2.yaml, nf_p94_282.yaml")
SRC_FORME = "Timoshenko & Gere, Theory of Elastic Stability, ch. 7 (anneau sous pression uniforme, q_cr = 3·E·I/R³)"
PRINCIPE_COMPRESSION = (
    "Paroi circulaire chargée de façon axisymétrique : la flèche radiale w (vers la fouille) raccourcit la circonférence, "
    "l'anneau se comprime. Effort normal circonférentiel N_θ = E·t·w/R par mètre de hauteur (coque cylindrique, Timoshenko "
    "§ 114), compression positive. Effort de calcul N_Ed = γ_effets·N_θ (effets caractéristiques pondérés, NF P 94-282 "
    "§ 9.1). Résistance du béton en compression centrée N_Rd = t·fcd, fcd = αcc·fck/γc (EN 1992-1-1 § 3.1.6), armatures "
    "négligées. Pieux sécants : t est la largeur du joint √(D² − e²), plus faible que l'épaisseur courante.")
PRINCIPE_FORME = (
    "Un anneau mince comprimé par une pression extérieure uniforme peut flamber en ovalisant. Pression critique d'un tube "
    "long p_cr = 3·D/R³ avec D = E·t³/(12·(1 − ν²)), prise ici avec ν = 0 (borne inférieure) : p_cr = E·t³/(4·R³). Le "
    "sol qui entoure la paroi s'oppose à l'ovalisation (effet favorable non compté). Aucun coefficient de sécurité "
    "n'est fourni pour ce mode : rapport p/p_cr indicatif.")


def _profil(r) -> list[tuple[str, np.ndarray, np.ndarray, np.ndarray]]:
    """(phase, z, t, N) de chaque phase calculée de l'écran circulaire."""
    return [(ph.nom, ph.anneau["z"], ph.anneau["t"], ph.anneau["N"]) for ph in r.phases if ph.ok and ph.anneau is not None]


def verifier_anneau(s, m, r, normes, cle: str, suffixe: str = "") -> list[Verif]:
    an = getattr(m.ecran, "anneau", None)
    if an is None:
        return []
    profils = _profil(r)
    if not profils:
        return []
    sorties: list[Verif] = []
    beton = m.ecran.infos.get("beton") or {}
    fck = beton.get("fck_MPa")
    # ---- compression circonférentielle
    lect = Lecteur(normes)
    g = lect.v("nf_p94_282", f"combinaisons.{cle}.gamma_effets")
    acc = lect.v("ec2", "alpha_cc")
    gc = lect.v("ec2", "gamma_c")
    if fck is None:
        lect.manquants.append(f"base matériaux : fck du béton {beton.get('classe', s.paroi.beton)}")
    ph_c, z_c, t_c, N_c = max(profils, key=lambda x: float(np.max(x[3])))
    i = int(np.argmax(N_c))
    ph_t, z_t, _, N_t = min(profils, key=lambda x: float(np.min(x[3])))
    j = int(np.argmin(N_t))
    donnees = [donnee("R", "rayon de l'axe de la paroi", an.rayon, "m", "script"),
               donnee("E", "module du béton Ecm", an.E / 1e3, "MPa", "base matériaux"),
               donnee("t", f"épaisseur de l'anneau à la cote {z_c[i]:.2f} m ({an.source_epaisseur})", t_c[i], "m"),
               donnee("N_θ", f"effort normal circonférentiel caractéristique maximal (phase « {ph_c} »)", N_c[i], "kN/m"),
               donnee("z", "cote de N_θ maximal", z_c[i], "m"),
               donnee("fck", "résistance caractéristique du béton", fck, "MPa", "base matériaux")]
    detail = f"N_θ max = {N_c[i]:.0f} kN/m à z = {z_c[i]:.2f} m (phase « {ph_c} »), t = {t_c[i]:.3f} m, R = {an.rayon:g} m"
    etapes: list[str] = []
    taux = None
    traction = float(N_t[j]) < -1e-6
    if not lect.manquants:
        fcd = acc * fck / gc * 1e3                                   # kPa
        N_Ed = g * N_c
        N_Rd = t_c * fcd
        with np.errstate(divide="ignore", invalid="ignore"):
            rapports = np.where(N_Rd > 0, np.maximum(N_Ed, 0.0) / N_Rd, np.where(N_Ed > 0, np.inf, 0.0))
        k = int(np.argmax(rapports))
        taux = float(rapports[k])
        donnees += [donnee("fcd", "résistance de calcul en compression αcc·fck/γc", fcd / 1e3, "MPa"),
                    donnee("N_Ed", f"effort de calcul γ_effets·N_θ à la cote la plus sollicitée ({z_c[k]:.2f} m)", N_Ed[k], "kN/m"),
                    donnee("N_Rd", "résistance t·fcd à cette cote", N_Rd[k], "kN/m")]
        etapes = [f"N_θ = E·t·w/R à chaque nœud, maximum {N_c[i]:.1f} kN/m à z = {z_c[i]:.2f} m (phase « {ph_c} »)",
                  f"fcd = αcc·fck/γc = {acc:g} × {fck:g} / {gc:g} = {fcd / 1e3:.2f} MPa",
                  f"cote la plus sollicitée z = {z_c[k]:.2f} m : N_Ed = {g:g} × {N_c[k]:.1f} = {N_Ed[k]:.1f} kN/m ; "
                  f"N_Rd = t·fcd = {t_c[k]:.3f} × {fcd:.0f} = {N_Rd[k]:.0f} kN/m",
                  f"taux = N_Ed/N_Rd = {taux:.3f}",
                  "joint de pieux sécants non armé : αcc,pl de l'EN 1992-1-1 ch. 12 absent de docs/normes (TODO-NORME), αcc employé"]
        detail += f" ; N_Ed = {N_Ed[k]:.0f} kN/m, N_Rd = t·fcd = {N_Rd[k]:.0f} kN/m à z = {z_c[k]:.2f} m"
    if traction:
        lect.manquants.append(f"traction circonférentielle N_θ = {N_t[j]:.1f} kN/m à z = {z_t[j]:.2f} m (phase « {ph_t} ») : "
                              "non reprise par le béton, armatures horizontales à justifier")
    schema = {"type": "anneau", "phase": ph_c, "R": an.rayon, "t": float(t_c[i]),
              "z": [round(float(x), 3) for x in z_c], "N": [round(float(x), 2) for x in N_c],
              "N_Rd": float(t_c[i] * acc * fck / gc * 1e3) if not lect.manquants and fck else None}
    sorties.append(resultat(f"Anneau — compression circonférentielle{suffixe}", "paroi circulaire", ph_c, taux, detail,
                            SRC_ANNEAU, lect, categorie="structure", famille="anneau", principe=PRINCIPE_COMPRESSION,
                            donnees=donnees, etapes=etapes, schema=schema))
    # ---- stabilité de forme (indicatif)
    p = N_c / an.rayon
    with np.errstate(divide="ignore", invalid="ignore"):
        pcr = np.array([pression_critique_tube(an.E, float(t), an.rayon) for t in t_c])
        rap = np.where(pcr > 0, np.maximum(p, 0.0) / pcr, np.inf)
    k = int(np.argmax(rap))
    lect2 = Lecteur(normes)
    lect2.manquants.append("coefficient de sécurité sur le flambement de l'anneau (aucune valeur dans docs/normes) : rapport indicatif")
    sorties.append(resultat(
        f"Anneau — stabilité de forme (indicatif){suffixe}", "paroi circulaire", ph_c, None, "", SRC_FORME, lect2,
        categorie="structure", famille="anneau", principe=PRINCIPE_FORME,
        detail_non_verifiable=(f"p = N_θ/R = {p[k]:.1f} kPa, p_cr = E·t³/(4·R³) = {pcr[k]:.0f} kPa à z = {z_c[k]:.2f} m : "
                               f"p/p_cr = {rap[k]:.3f} (ν = 0, borne inférieure ; appui latéral du sol non compté)"),
        donnees=[donnee("p", "pression reprise par l'anneau N_θ/R", p[k], "kPa"),
                 donnee("p_cr", "pression critique du tube long E·t³/(4·R³)", pcr[k], "kPa"),
                 donnee("t", "épaisseur de l'anneau", t_c[k], "m"), donnee("R", "rayon", an.rayon, "m", "script")],
        etapes=[f"p = N_θ/R = {N_c[k]:.1f} / {an.rayon:g} = {p[k]:.1f} kPa à z = {z_c[k]:.2f} m",
                f"p_cr = E·t³/(4·R³) = {an.E:.0f} × {t_c[k]:.3f}³ / (4 × {an.rayon:g}³) = {pcr[k]:.0f} kPa",
                f"p/p_cr = {rap[k]:.3f}"]))
    return sorties
