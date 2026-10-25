"""Stabilité du massif d'ancrage par la méthode de Kranz.

Kranz E. (1953), *Über die Verankerung von Spundwänden*, Ernst & Sohn ;
principe repris par la NF P 94-282 (stabilité du massif d'ancrage).

Massif étudié (par mètre linéaire) : sol limité par l'écran (de la surface au
point B), la droite de rupture BA, et un écran fictif vertical passant par A
(milieu du scellement), jusqu'à la surface.
- B : premier point d'effort tranchant nul sous le fond de fouille (à défaut, le pied).
- Efforts sur le massif : poids W (+ surcharges réparties sur le massif),
  action de l'écran (opposée à la poussée calculée au-dessus de B, inclinée de δa),
  poussée active P1 sur l'écran fictif (δ = 0, coefficient de Rankine/Coulomb du
  calcul), réaction R sur BA inclinée de φ' sur la normale (cohésion négligée,
  du côté de la sécurité ; φ' le plus faible des couches traversées), effort d'ancrage
  T selon l'axe du tirant.
- T_max résout l'équilibre des forces (2 équations, inconnues T_max et R).
Critère : gamma_effet · T ≤ T_max / gamma_R (docs/normes/nf_p94_282.yaml -> kranz).
Hypothèses : contraintes effectives (γ' sous la nappe amont, pas de poussée d'eau
sur les limites du massif), surcharges en bande non prises en compte sur P1,
surcharges réparties initiales seules (comptées dans le poids du massif), chaque
lit de tirants étudié séparément (pas de massif combiné pour plusieurs lits).
"""
from __future__ import annotations

import math

import numpy as np

from ..noyau.modele import Modele
from ..noyau.phasage import ResultatCalcul
from ..sol import coefficients as coef
from ..sol.couches import indice_couche, trier
from ..verifs import Lecteur, Verif, donnee, resultat
from .surcharges_stabilite import mention, q_uniforme_amont

SOURCE = "Kranz (1953), NF P 94-282 — stabilité du massif d'ancrage"
PRINCIPE = ("Méthode de Kranz : on isole le massif de sol limité par l'écran jusqu'au point B (premier effort tranchant "
            "nul sous le fond de fouille), la droite BA et un écran fictif vertical passant par A, milieu du scellement. Le "
            "massif est soumis à son poids W, à l'action de l'écran au-dessus de B (Fh, Fv), à la poussée P1 sur l'écran "
            "fictif, à la réaction R du sol sur BA (inclinée de φ' sur la normale) et à l'effort d'ancrage T. L'équilibre "
            "des forces donne l'effort d'ancrage maximal T_max ; la NF P 94-282 impose γ_effet·T ≤ T_max/γ_R. Chaque lit "
            "de tirants est étudié séparément ; les surcharges autres qu'uniformes sont listées et non comptées.")


def point_B(ph) -> float:
    """Cote du premier effort tranchant nul sous le fond de fouille (sinon le pied)."""
    zf = ph.terrain_aval
    z, V = ph.z_diag, ph.V
    ordre = np.argsort(-z)
    z, V = z[ordre], V[ordre]
    sous = z < zf
    zs, Vs = z[sous], V[sous]
    for k in range(1, len(zs)):
        if Vs[k - 1] == 0.0:
            return float(zs[k - 1])
        if np.sign(Vs[k]) != np.sign(Vs[k - 1]) and Vs[k] != 0.0:
            t = Vs[k - 1] / (Vs[k - 1] - Vs[k])
            return float(zs[k - 1] + t * (zs[k] - zs[k - 1]))
    return float(z.min())


def _poids_volumique(couches, z: float, z_nappe: float | None) -> float:
    c = couches[indice_couche(couches, z)]
    return c.gamma_dejauge if (z_nappe is not None and z < z_nappe) else c.gamma


def t_max(couches, z_t: float, z_nappe: float | None, z_B: float, x_A: float, z_A: float,
          angle_tirant: float, Fh_ecran: float, Fv_ecran: float, q_reparti: float = 0.0,
          methode_k=coef.kah, n: int = 400) -> tuple[float, dict]:
    """Effort d'ancrage maximal T_max (kN/m, selon l'axe du tirant).

    Repère : écran en x = 0, massif côté amont (x < 0), z vers le haut.
    Fh_ecran, Fv_ecran : poussée horizontale et composante verticale descendante
    exercées par le sol sur l'écran au-dessus de B.
    """
    couches = trier(couches)
    # Poids du massif : bandes horizontales entre B et la surface
    poly = [(0.0, z_t), (0.0, z_B), (x_A, z_A), (x_A, z_t)]
    z_bas = min(z_B, z_A)
    zs = np.linspace(z_bas, z_t, n + 1)
    W = 0.0
    for z0, z1 in zip(zs[:-1], zs[1:]):
        zm = 0.5 * (z0 + z1)
        xs = []
        for (xa, za), (xb, zb) in zip(poly, poly[1:] + poly[:1]):
            if (za - zm) * (zb - zm) < 0 or (za == zm and zb != zm):
                xs.append(xa + (zm - za) / (zb - za) * (xb - xa))
        if len(xs) >= 2:
            W += (max(xs) - min(xs)) * (z1 - z0) * _poids_volumique(couches, zm, z_nappe)
    W += q_reparti * abs(x_A)

    # Poussée active sur l'écran fictif (δ = 0) de la surface à z_A
    zf = np.linspace(z_A, z_t, n + 1)
    P1 = 0.0
    sv = q_reparti
    for z1, z0 in zip(zf[::-1][:-1], zf[::-1][1:]):  # de haut en bas
        zm = 0.5 * (z0 + z1)
        g = _poids_volumique(couches, zm, z_nappe)
        c = couches[indice_couche(couches, zm)]
        sv_m = sv + g * (z1 - zm)
        pa = max(methode_k(c.phi, 0.0) * sv_m - coef.terme_cohesion_poussee(c.phi, c.c, methode_k(c.phi, 0.0)), 0.0)
        P1 += pa * (z1 - z0)
        sv += g * (z1 - z0)

    # Réaction sur BA
    # φ' le plus faible des couches traversées par BA (du côté de la sécurité)
    phi = math.radians(min(couches[indice_couche(couches, z)].phi for z in np.linspace(min(z_B, z_A), max(z_B, z_A), 41)))
    t_up = np.array([x_A - 0.0, z_A - z_B])
    t_up /= np.linalg.norm(t_up)                  # de B vers A
    n_in = np.array([-t_up[1], t_up[0]])          # normale
    if n_in[1] < 0:
        n_in = -n_in                               # vers le haut, dans le massif
    u_R = n_in * math.cos(phi) + t_up * math.sin(phi)
    i = math.radians(angle_tirant)
    u_T = np.array([math.cos(i), math.sin(i)])     # le tirant tire le massif vers la tête
    # Σ forces = 0 : T·u_T + r·u_R = −(W + écran + P1)
    autres = np.array([-Fh_ecran + P1, -W + Fv_ecran])
    Mtx = np.column_stack([u_T, u_R])
    T, r = np.linalg.solve(Mtx, -autres)
    return float(T), {"W": W, "P1": P1, "r": float(r), "z_B": z_B, "phi": math.degrees(phi)}


def verifier(modele: Modele, res: ResultatCalcul, normes) -> list[Verif]:
    sorties = []
    tirants = [a for a in modele.appuis.values() if a.type == "tirant"]
    if not tirants:
        return []
    for d in tirants:
        inf = d.infos
        Ll, Ls = inf.get("longueur_libre"), inf.get("longueur_scellee")
        if not Ll or not Ls:
            sorties.append(resultat("Stabilité du massif d'ancrage (Kranz)", d.nom, None, None,
                                    "longueur_libre et longueur_scellee nécessaires", SOURCE,
                                    detail_non_verifiable="longueur_libre et longueur_scellee du tirant nécessaires"))
            continue
        ang = inf.get("angle", 0.0)
        Lc = Ll + Ls / 2
        x_A = -Lc * math.cos(math.radians(ang))
        z_A = d.cote - Lc * math.sin(math.radians(ang))
        lect = Lecteur(normes)
        ge = lect.v("nf_p94_282", "kranz.gamma_effet")
        gR = lect.v("nf_p94_282", "kranz.gamma_R")
        pire_cas = None
        for ph in res.phases[1:]:
            if not ph.ok:
                continue
            app = next((a for a in ph.appuis if a["nom"] == d.nom), None)
            if app is None:
                continue
            T = app["effort"] / math.cos(math.radians(ang))
            zB = point_B(ph)
            am = ph.pressions["amont"]
            dessus = am["z"] > zB
            Fh = float(np.sum(am["L"][dessus] * am["p"][dessus]))
            Fv = float(np.sum(am["L"][dessus] * am["p"][dessus] * am["tan_delta"][dessus]))
            q, ignorees = q_uniforme_amont(modele)
            Tm, info = t_max(modele.couches, ph.terrain_amont, ph.eau_amont, zB, x_A, z_A, ang, Fh, Fv, q)
            rapport = T / Tm if Tm > 0 else float("inf")
            if pire_cas is None or rapport > pire_cas[0]:
                pire_cas = (rapport, ph.nom, T, Tm, info, ph, Fh, Fv)
        if pire_cas is None:
            continue
        rapport, nom, T, Tm, info, ph, Fh, Fv = pire_cas
        detail = (f"T = {T:.0f} kN/m, T_max = {Tm:.0f} kN/m (B à z = {info['z_B']:.2f} m, "
                  f"poids du massif {info['W']:.0f} kN/m), T/T_max = {rapport:.2f} (caractéristique)"
                  + mention(ignorees))
        taux = None if lect.manquants else ge * gR * rapport
        donnees = [donnee("T", "effort du tirant par mètre d'écran, selon son axe (phase retenue)", T, "kN/m"),
                   donnee("T_max", "effort d'ancrage maximal du massif", Tm, "kN/m"),
                   donnee("T/T_max", "rapport caractéristique", rapport),
                   donnee("z_B", "point B : premier effort tranchant nul sous le fond (sinon le pied)", info["z_B"], "m"),
                   donnee("x_A", "point A (milieu du scellement) : abscisse depuis l'écran", x_A, "m"),
                   donnee("z_A", "point A : cote", z_A, "m"),
                   donnee("W", "poids du massif O-B-A-A' (déjaugé sous la nappe)", info["W"], "kN/m"),
                   donnee("P1", "poussée active sur l'écran fictif passant par A (δ = 0)", info["P1"], "kN/m"),
                   donnee("Fh", "poussée horizontale du sol sur l'écran au-dessus de B", Fh, "kN/m"),
                   donnee("Fv", "composante verticale (frottement) sur l'écran au-dessus de B", Fv, "kN/m"),
                   donnee("R", "réaction du sol sur BA (inclinée de φ' sur la normale)", info["r"], "kN/m"),
                   donnee("φ'", "angle de frottement le plus faible traversé par BA", info["phi"], "°"),
                   donnee("α", "inclinaison du tirant sur l'horizontale", ang, "°", "script"),
                   donnee("L_libre + L_scellée/2", "distance de l'écran au milieu du scellement", Lc, "m", "script")]
        etapes = [f"Point A au milieu du scellement : x_A = −(L_libre + L_scellée/2)·cos α = {x_A:.2f} m, z_A = cote − (L_libre + L_scellée/2)·sin α = {z_A:.2f} m",
                  f"Point B sur l'écran : z_B = {info['z_B']:.2f} m (premier effort tranchant nul sous le fond, phase « {nom} »)",
                  f"Massif O-B-A-A' : poids W = {info['W']:.1f} kN/m ; écran fictif en A : poussée P1 = {info['P1']:.1f} kN/m ; "
                  f"action de l'écran au-dessus de B : Fh = {Fh:.1f} kN/m, Fv = {Fv:.1f} kN/m",
                  f"Équilibre des forces du massif, réaction R inclinée de φ' = {info['phi']:.1f}° sur la normale à BA : "
                  f"T_max = {Tm:.1f} kN/m (R = {info['r']:.1f} kN/m)",
                  f"T = effort du tirant / cos α = {T:.1f} kN/m ; T/T_max = {rapport:.3f}"]
        etapes.append("coefficients partiels manquants : taux non calculable" if taux is None
                      else f"taux = γ_effet·γ_R·T/T_max = {ge:g} × {gR:g} × {rapport:.3f} = {taux:.3f}")
        schema = {"type": "kranz", "phase": nom, "tete": modele.ecran.tete, "pied": modele.ecran.pied,
                  "terrain_amont": ph.terrain_amont, "fond": ph.terrain_aval, "nappe_amont": ph.eau_amont,
                  "cote_tirant": d.cote, "angle": ang, "B": [0.0, info["z_B"]], "A": [x_A, z_A],
                  "longueur_libre": Ll, "longueur_scellee": Ls,
                  "forces": {"W": info["W"], "P1": info["P1"], "T": T, "T_max": Tm, "R": info["r"], "Fh": Fh, "Fv": Fv}}
        sorties.append(resultat("Stabilité du massif d'ancrage (Kranz)", d.nom, nom, taux, detail, SOURCE, lect,
                                famille="massif_ancrage", principe=PRINCIPE, donnees=donnees, etapes=etapes, schema=schema))
    return sorties
