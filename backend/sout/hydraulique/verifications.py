"""Vérifications hydrauliques du fond de fouille à partir du modèle d'eau de chaque phase.

- Boulance (HYD, EN 1997-1 § 10.3) : par équilibre des pressions sur le prisme de Terzaghi
  (γ_dst·u_excès ≤ γ_stb·σ'v à sa base) et par gradient de sortie (γ_dst·i ≤ γ_stb·i_c, i_c = γ'/γw).
- Renard : Terzaghi (F = γ'·D/(γw·h_a) ≥ F_min), Lane (L_w/H ≥ C_lane), gradient critique
  (i_sortie ≤ i_admissible). Les trois sont affichés ensemble.
- Soulèvement du bouchon (UPL, § 10.2) : γ_dst·u(base) ≤ γ_stb·(γ_b·e + lest) ; épaisseur minimale.
- Gradient à travers le bouchon : i_b ≤ i_admissible (bouchon).
- Débit de pompage : information (m³/h par mètre d'écran).
- Stabilité du fond en argile molle (option, si cu est donné) : F = N_c·cu/(γ·H + q) ≥ F_min,
  N_c selon la géométrie (Bjerrum & Eide 1956), valeur à fournir.
Coefficients : docs/normes/nf_p94_282.yaml (fond_de_fouille) et docs/normes/hydraulique.yaml.
"""
from __future__ import annotations

from ..noyau.modele import Modele
from ..noyau.phasage import ResultatCalcul
from ..sol.couches import contraintes_verticales, indice_couche, trier
from ..verifs import Lecteur, Verif, resultat
from . import bouchons, lane, terzaghi

SRC_HYD = "EN 1997-1 § 10.3 (HYD) / NF P 94-282 — coefficients : docs/normes"
SRC_RENARD = "docs/normes/hydraulique.yaml — Terzaghi (1943) § 97, Lane (1935), gradient critique"
SRC_UPL = "EN 1997-1 § 10.2 (UPL) — bouchon de fond de fouille"


def _gamma_prime_moyen(modele: Modele, z_fond: float, z_pied: float) -> float:
    """γ' moyen entre le fond et le pied (σ'v hydrostatique au pied / D)."""
    D = z_fond - z_pied
    if D <= 0:
        return 0.0
    sv, _ = contraintes_verticales([z_pied], z_fond, z_fond, trier(modele.couches), modele.gamma_w)
    return float(sv[0]) / D


def verifier(modele: Modele, res: ResultatCalcul, normes) -> list[Verif]:
    cas = [ph for ph in res.phases if ph.ok and ph.ecoulement is not None and ph.ecoulement.h_amont is not None]
    cas = [ph for ph in cas if (ph.ecoulement.h_amont - (ph.ecoulement.h_aval if ph.ecoulement.h_aval is not None else ph.terrain_aval)) > 0]
    if not cas:
        return []
    gw = modele.gamma_w
    sorties: list[Verif] = []
    cfg = modele.hydraulique or {}

    def pire(cle):
        return max(cas, key=cle)

    # ---- Boulance par équilibre des pressions (prisme de Terzaghi)
    ph = pire(lambda p: p.ecoulement.charge_base_prisme / max(p.terrain_aval - modele.ecran.pied, 1e-9))
    e = ph.ecoulement
    D = ph.terrain_aval - modele.ecran.pied
    gp = _gamma_prime_moyen(modele, ph.terrain_aval, modele.ecran.pied)
    lect = Lecteur(normes)
    gd = lect.v("nf_p94_282", "fond_de_fouille.boulance.gamma_dst")
    gs = lect.v("nf_p94_282", "fond_de_fouille.boulance.gamma_stb")
    u_exces, s_stb = gw * e.charge_base_prisme, gp * D
    detail = (f"prisme de Terzaghi (D = {D:.2f} m, largeur D/2) : excès de charge moyen à la base {e.charge_base_prisme:.2f} m, "
              f"u = {u_exces:.1f} kPa, σ'v = {s_stb:.1f} kPa (rapport caractéristique {u_exces / max(s_stb, 1e-9):.2f})")
    sorties.append(resultat("Boulance — équilibre des pressions (HYD)", "fond de fouille", ph.nom,
                            None if lect.manquants or s_stb <= 0 else gd * u_exces / (gs * s_stb), detail, SRC_HYD, lect))

    # ---- Boulance par gradient de sortie
    ph = pire(lambda p: p.ecoulement.gradient_sortie_max)
    e = ph.ecoulement
    couches = trier(modele.couches)
    c_fond = couches[indice_couche(couches, ph.terrain_aval - 1e-6)]
    i_c = c_fond.gamma_dejauge / gw
    lect = Lecteur(normes)
    gd = lect.v("nf_p94_282", "fond_de_fouille.boulance.gamma_dst")
    gs = lect.v("nf_p94_282", "fond_de_fouille.boulance.gamma_stb")
    detail = (f"gradient de sortie maximal i = {e.gradient_sortie_max:.3f} (moyen {e.gradient_sortie_moyen:.3f}), "
              f"gradient critique i_c = γ'/γw = {i_c:.2f} ({c_fond.nom})")
    sorties.append(resultat("Boulance — gradient de sortie", "fond de fouille", ph.nom,
                            None if lect.manquants else gd * e.gradient_sortie_max / (gs * i_c), detail, SRC_HYD, lect))

    # ---- Renard : Terzaghi
    ph = pire(lambda p: p.ecoulement.charge_base_prisme)
    e = ph.ecoulement
    D = ph.terrain_aval - modele.ecran.pied
    gp = _gamma_prime_moyen(modele, ph.terrain_aval, modele.ecran.pied)
    F = terzaghi.facteur_securite(D, gp, gw, e.charge_base_prisme)
    lect = Lecteur(normes)
    Fmin = lect.v("hydraulique", "terzaghi.F_min")
    sorties.append(resultat("Renard — Terzaghi", "fond de fouille", ph.nom, None if lect.manquants else Fmin / F,
                            f"F = γ'·D/(γw·h_a) = {gp:.1f}·{D:.2f}/({gw:.0f}·{e.charge_base_prisme:.2f}) = {F:.2f}", SRC_RENARD, lect))

    # ---- Renard : Lane
    ph = pire(lambda p: (p.ecoulement.h_amont - (p.ecoulement.h_aval if p.ecoulement.h_aval is not None else p.terrain_aval)))
    e = ph.ecoulement
    hv_eff = e.h_aval if e.h_aval is not None else ph.terrain_aval
    H = e.h_amont - hv_eff
    haut = min(e.h_amont, ph.terrain_amont)
    vert = [haut - modele.ecran.pied, ph.terrain_aval - modele.ecran.pied]
    horiz = []
    if e.bouchon is not None and e.bouchon.k is None and cfg.get("largeur_fouille"):
        horiz.append(cfg["largeur_fouille"] / 2)
    L_w = lane.longueur_ponderee(vert, horiz)
    sol_lane = cfg.get("sol_lane") or c_fond.sol_lane
    lect = Lecteur(normes)
    if sol_lane is None:
        lect.manquants.append("script : sol_lane (type de sol de la table de Lane, bloc hydraulique ou couche)")
        C = None
    else:
        C = lect.v("hydraulique", f"lane.C.{sol_lane}")
    sorties.append(resultat("Renard — Lane", "fond de fouille", ph.nom, None if lect.manquants else lane.taux(L_w, H, C),
                            f"L_w = {L_w:.2f} m (verticaux {sum(vert):.2f} + horizontaux/3), H = {H:.2f} m, L_w/H = {L_w / max(H, 1e-9):.2f}"
                            + (f", C_Lane({sol_lane})" if sol_lane else ""), SRC_RENARD, lect))

    # ---- Renard : gradient critique admissible
    ph = pire(lambda p: p.ecoulement.gradient_sortie_max)
    e = ph.ecoulement
    lect = Lecteur(normes)
    i_adm = lect.v("nf_p94_282", "fond_de_fouille.renard.gradient_admissible")
    sorties.append(resultat("Renard — gradient critique", "fond de fouille", ph.nom,
                            None if lect.manquants else e.gradient_sortie_max / i_adm,
                            f"i_sortie = {e.gradient_sortie_max:.3f}", SRC_RENARD, lect))

    # ---- Bouchon : soulèvement et gradient
    avec_b = [p for p in cas if p.ecoulement.bouchon is not None]
    if avec_b:
        ph = max(avec_b, key=lambda p: (p.ecoulement.charge_base_bouchon or p.ecoulement.h_amont))
        e, b = ph.ecoulement, ph.ecoulement.bouchon
        lect = Lecteur(normes)
        gd = lect.v("nf_p94_282", "fond_de_fouille.soulevement.gamma_dst")
        gs = lect.v("nf_p94_282", "fond_de_fouille.soulevement.gamma_stb")
        h_base = e.charge_base_bouchon if e.charge_base_bouchon is not None else e.h_amont
        u = gw * (h_base - b.base)
        sigma = b.gamma * b.epaisseur + b.lest
        hv_eff = e.h_aval if e.h_aval is not None else ph.terrain_aval
        if hv_eff > b.toit:
            sigma += gw * (hv_eff - b.toit)   # eau au-dessus du bouchon
        detail = f"charge sous le bouchon {h_base:.2f} m, u = {u:.1f} kPa ; poids du bouchon + lest = {sigma:.1f} kPa"
        if not lect.manquants:
            e_min = bouchons.epaisseur_minimale(e.h_amont, b.toit, b.gamma, gw, gd, gs, b.lest + (gw * (hv_eff - b.toit) if hv_eff > b.toit else 0.0))
            detail += f" ; épaisseur minimale (pleine charge amont) {e_min:.2f} m pour {b.epaisseur:.2f} m"
        sorties.append(resultat("Soulèvement du bouchon (UPL)", f"bouchon {b.type}", ph.nom,
                                None if lect.manquants or sigma <= 0 else gd * u / (gs * sigma), detail, SRC_UPL, lect))
        lect = Lecteur(normes)
        i_adm_b = lect.v("hydraulique", "bouchon.gradient_admissible")
        ib = e.gradient_bouchon
        sorties.append(resultat("Gradient à travers le bouchon", f"bouchon {b.type}", ph.nom,
                                None if lect.manquants or ib is None else ib / i_adm_b,
                                f"i_bouchon = {ib:.2f}" if ib is not None else "bouchon imperméable : gradient non défini", SRC_UPL, lect))

    # ---- Débit (information)
    ph = pire(lambda p: p.ecoulement.debit)
    q = ph.ecoulement.debit
    sorties.append(resultat("Débit de pompage", "fouille", ph.nom, None, "", "réseau d'écoulement (par mètre d'écran, fouille symétrique)",
                            detail_non_verifiable=f"Q = {q * 3600:.3f} m³/h par mètre d'écran ({q * 1000:.2f} l/s/m) ; "
                            "à multiplier par le périmètre de la fouille — information, pas un critère"
                            + ("" if ph.ecoulement.regime == "differences_finies" else " ; régime simplifié : débit non calculé")))

    # ---- Stabilité du fond en argile molle (option)
    ph = min(cas, key=lambda p: p.terrain_aval)
    c_fond = couches[indice_couche(couches, ph.terrain_aval - 1e-6)]
    if c_fond.cu is not None:
        lect = Lecteur(normes)
        Nc = lect.v("hydraulique", "fond_argile.N_c")
        Fmin = lect.v("hydraulique", "fond_argile.F_min")
        H_exc = ph.terrain_amont - ph.terrain_aval
        sv_tot, u_h = contraintes_verticales([ph.terrain_aval], ph.terrain_amont, ph.eau_amont, couches, gw)
        q = sum(s.q for s in modele.surcharges if s.type == "repartie" and s.cote_ecran == "amont")
        charge = float(sv_tot[0] + u_h[0]) + q
        detail = f"cu = {c_fond.cu:.0f} kPa ({c_fond.nom}), γ·H + q = {charge:.0f} kPa"
        taux = None
        if not lect.manquants and charge > 0:
            F = Nc * c_fond.cu / charge
            taux = Fmin / F
            detail += f", N_c = {Nc}, F = {F:.2f}"
        sorties.append(resultat("Stabilité du fond en argile (Bjerrum-Eide)", "fond de fouille", ph.nom, taux, detail,
                                "Bjerrum & Eide (1956) — N_c et F_min : docs/normes/hydraulique.yaml", lect))
    return sorties
