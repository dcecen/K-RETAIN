"""Stabilité du fond de fouille vis-à-vis de l'eau : soulèvement, boulance, renard.

Le calcul d'écoulement n'étant pas encore disponible, la perte de charge est
estimée par la méthode de la longueur de cheminement (Bligh, Lane) : la charge
hydraulique Δh = h_amont − h_aval se dissipe uniformément le long de l'écran,
de la nappe amont (ou du terrain amont s'il est plus bas) jusqu'au pied, puis
du pied jusqu'au fond de fouille. Méthode simplifiée, à remplacer par un
calcul d'écoulement (réseau de Terzaghi ou éléments finis) pour un projet.

- Soulèvement global (UPL, EN 1997-1 § 2.4.7.4) au niveau du pied, hypothèse
  conservatrice : la charge amont est entièrement transmise sous le pied.
  gamma_dst · u_pied ≤ gamma_stb · σv,total (colonne fond -> pied, côté aval).
- Boulance (HYD, EN 1997-1 § 2.4.7.5) sur la colonne aval :
  gamma_dst · Δu ≤ gamma_stb · σ'v, Δu = γw · Δh_aval (surpression au pied).
- Renard : gradient de sortie moyen i = Δh_aval / (fond − pied) ≤ gradient admissible.
Coefficients : docs/normes/nf_p94_282.yaml → fond_de_fouille.
"""
from __future__ import annotations

from ..noyau.modele import Modele
from ..noyau.phasage import ResultatCalcul
from ..sol.couches import contraintes_verticales, trier
from ..verifs import Lecteur, Verif, resultat

SOURCE = "NF P 94-282 / EN 1997-1 (UPL, HYD) — longueur de cheminement (méthode simplifiée)"


def charges(modele: Modele, ph) -> dict | None:
    """Grandeurs hydrauliques de la phase, ou None si pas d'écoulement vers la fouille."""
    h_am, h_av = ph.eau_amont, ph.eau_aval
    if h_am is None:
        return None
    z_p = modele.ecran.pied
    zf = ph.terrain_aval
    h_av_eff = h_av if h_av is not None else zf  # fouille drainée au fond
    dh = h_am - max(h_av_eff, z_p)
    if dh <= 0 or zf <= z_p:
        return None
    haut_amont = min(h_am, ph.terrain_amont)
    L_am = haut_amont - z_p
    L_av = zf - z_p
    dh_av = dh * L_av / (L_am + L_av)
    gw = modele.gamma_w
    couches = trier(modele.couches)
    sv_eff, u_hyd = contraintes_verticales([z_p], zf, h_av_eff, couches, gw)
    u_pied_amont = gw * (h_am - z_p)
    return {
        "dh": dh, "dh_aval": dh_av, "L_aval": L_av,
        "sigma_v_eff": float(sv_eff[0]),
        "sigma_v_total": float(sv_eff[0] + u_hyd[0]),
        "u_pied_amont": u_pied_amont,
        "delta_u": gw * dh_av,
        "gradient": dh_av / L_av,
    }


def verifier(modele: Modele, res: ResultatCalcul, normes) -> list[Verif]:
    cas = [(ph, charges(modele, ph)) for ph in res.phases[1:] if ph.ok]
    cas = [(ph, c) for ph, c in cas if c is not None]
    if not cas:
        return []
    sorties = []
    # Soulèvement
    lect = Lecteur(normes)
    gd = lect.v("nf_p94_282", "fond_de_fouille.soulevement.gamma_dst")
    gs = lect.v("nf_p94_282", "fond_de_fouille.soulevement.gamma_stb")
    ph, c = max(cas, key=lambda t: t[1]["u_pied_amont"] / max(t[1]["sigma_v_total"], 1e-9))
    rk = c["u_pied_amont"] / max(c["sigma_v_total"], 1e-9)
    detail = (f"u au pied (charge amont) = {c['u_pied_amont']:.0f} kPa, σv total fond→pied = "
              f"{c['sigma_v_total']:.0f} kPa, rapport caractéristique {rk:.2f}")
    sorties.append(resultat("Fond de fouille — soulèvement (UPL)", "fond de fouille", ph.nom,
                            None if lect.manquants else gd * c["u_pied_amont"] / (gs * c["sigma_v_total"]),
                            detail, SOURCE, lect))
    # Boulance
    lect = Lecteur(normes)
    gd = lect.v("nf_p94_282", "fond_de_fouille.boulance.gamma_dst")
    gs = lect.v("nf_p94_282", "fond_de_fouille.boulance.gamma_stb")
    ph, c = max(cas, key=lambda t: t[1]["delta_u"] / max(t[1]["sigma_v_eff"], 1e-9))
    rk = c["delta_u"] / max(c["sigma_v_eff"], 1e-9)
    detail = (f"Δh = {c['dh']:.2f} m dont {c['dh_aval']:.2f} m côté fouille ; surpression au pied "
              f"{c['delta_u']:.1f} kPa, σ'v = {c['sigma_v_eff']:.1f} kPa, rapport caractéristique {rk:.2f}")
    sorties.append(resultat("Fond de fouille — boulance (HYD)", "fond de fouille", ph.nom,
                            None if lect.manquants else gd * c["delta_u"] / (gs * c["sigma_v_eff"]),
                            detail, SOURCE, lect))
    # Renard
    lect = Lecteur(normes)
    i_adm = lect.v("nf_p94_282", "fond_de_fouille.renard.gradient_admissible")
    ph, c = max(cas, key=lambda t: t[1]["gradient"])
    detail = f"gradient de sortie moyen i = {c['gradient']:.2f}"
    sorties.append(resultat("Fond de fouille — renard", "fond de fouille", ph.nom,
                            None if lect.manquants else c["gradient"] / i_adm, detail, SOURCE, lect))
    return sorties
