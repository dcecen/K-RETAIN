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
Coefficients : docs/normes/nf_p94_282.yaml -> fond_de_fouille.
"""
from __future__ import annotations

from ..noyau.modele import Modele
from ..noyau.phasage import ResultatCalcul
from ..sol.couches import contraintes_verticales, trier
from ..verifs import Lecteur, Verif, donnee, resultat

SOURCE = ("NF P 94-282 / EN 1997-1 (UPL, HYD) — longueur de cheminement (méthode simplifiée, perte de charge "
          "uniforme : peut sous-estimer le gradient de sortie d'une fouille étroite ; à confirmer par un calcul d'écoulement)")


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
        "dh": dh, "dh_aval": dh_av, "L_aval": L_av, "L_amont": L_am,
        "sigma_v_eff": float(sv_eff[0]),
        "sigma_v_total": float(sv_eff[0] + u_hyd[0]),
        "u_pied_amont": u_pied_amont,
        "delta_u": gw * dh_av,
        "gradient": dh_av / L_av,
        "h_amont": h_am, "h_aval": h_av_eff, "z_fond": zf, "z_pied": z_p, "terrain_amont": ph.terrain_amont, "gamma_w": gw,
    }


def _schema(ph, c: dict) -> dict:
    """Géométrie du cheminement (nappes, fond, pied) pour le dessin de la fiche."""
    return {"type": "fond_de_fouille", "phase": ph.nom, "nappe_amont": c["h_amont"], "nappe_aval": c["h_aval"],
            "fond": c["z_fond"], "pied": c["z_pied"], "terrain_amont": c["terrain_amont"], "L_amont": c["L_amont"],
            "L_aval": c["L_aval"], "dh": c["dh"], "dh_aval": c["dh_aval"]}


def _donnees(c: dict) -> list[dict]:
    return [donnee("Δh", "perte de charge totale entre les nappes amont et aval", c["dh"], "m"),
            donnee("L_amont", "cheminement côté terre (nappe ou terrain -> pied)", c["L_amont"], "m"),
            donnee("L_aval", "cheminement côté fouille (pied -> fond)", c["L_aval"], "m"),
            donnee("Δh_aval", "perte de charge côté fouille = Δh·L_aval/(L_amont + L_aval)", c["dh_aval"], "m"),
            donnee("u_pied", "pression d'eau au pied sous la charge amont = γw·(nappe amont − pied)", c["u_pied_amont"], "kPa"),
            donnee("σv", "contrainte verticale totale du sol fond -> pied", c["sigma_v_total"], "kPa"),
            donnee("Δu", "surpression au pied côté fouille = γw·Δh_aval", c["delta_u"], "kPa"),
            donnee("σ'v", "contrainte verticale effective du sol fond -> pied", c["sigma_v_eff"], "kPa"),
            donnee("i", "gradient de sortie moyen = Δh_aval/L_aval", c["gradient"]),
            donnee("γw", "poids volumique de l'eau", c["gamma_w"], "kN/m³", "script")]


PRINCIPE_CHEMINEMENT = ("Méthode simplifiée de la longueur de cheminement (Bligh) : la perte de charge Δh entre la nappe "
                        "amont et le niveau d'eau côté fouille est répartie uniformément le long du trajet contournant "
                        "l'écran (côté terre jusqu'au pied, puis du pied au fond de fouille). ")


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
    detail = (f"u au pied (charge amont) = {c['u_pied_amont']:.0f} kPa, σv total fond->pied = "
              f"{c['sigma_v_total']:.0f} kPa, rapport caractéristique {rk:.2f}")
    taux = None if lect.manquants else gd * c["u_pied_amont"] / (gs * c["sigma_v_total"])
    etapes = [f"u_pied = γw·(nappe amont − pied) = {c['gamma_w']:g} × ({c['h_amont']:.2f} − ({c['z_pied']:.2f})) = {c['u_pied_amont']:.1f} kPa",
              f"σv = poids total de la colonne de sol entre le fond ({c['z_fond']:.2f} m) et le pied ({c['z_pied']:.2f} m) = {c['sigma_v_total']:.1f} kPa",
              f"rapport caractéristique u_pied/σv = {rk:.3f}"]
    etapes.append("coefficients partiels manquants : taux non calculable" if taux is None
                  else f"taux = γ_dst·u_pied / (γ_stb·σv) = {gd:g} × {c['u_pied_amont']:.1f} / ({gs:g} × {c['sigma_v_total']:.1f}) = {taux:.3f}")
    sorties.append(resultat("Fond de fouille — soulèvement (UPL)", "fond de fouille", ph.nom, taux, detail, SOURCE, lect,
                            famille="fond_de_fouille", donnees=_donnees(c), etapes=etapes, schema=_schema(ph, c),
                            principe=("Soulèvement du fond (état limite UPL, EN 1997-1 § 10.2 repris par la NF P 94-282) : la "
                                      "pression d'eau au pied de l'écran, sous la charge de la nappe amont, est comparée au poids "
                                      "total de la colonne de sol comprise entre le fond de fouille et le pied. Critère "
                                      "γ_dst·u_pied ≤ γ_stb·σv.")))
    # Boulance
    lect = Lecteur(normes)
    gd = lect.v("nf_p94_282", "fond_de_fouille.boulance.gamma_dst")
    gs = lect.v("nf_p94_282", "fond_de_fouille.boulance.gamma_stb")
    ph, c = max(cas, key=lambda t: t[1]["delta_u"] / max(t[1]["sigma_v_eff"], 1e-9))
    rk = c["delta_u"] / max(c["sigma_v_eff"], 1e-9)
    detail = (f"Δh = {c['dh']:.2f} m dont {c['dh_aval']:.2f} m côté fouille ; surpression au pied "
              f"{c['delta_u']:.1f} kPa, σ'v = {c['sigma_v_eff']:.1f} kPa, rapport caractéristique {rk:.2f}")
    taux = None if lect.manquants else gd * c["delta_u"] / (gs * c["sigma_v_eff"])
    etapes = [f"Δh = nappe amont − niveau d'eau côté fouille = {c['dh']:.2f} m",
              f"Δh_aval = Δh·L_aval/(L_amont + L_aval) = {c['dh']:.2f} × {c['L_aval']:.2f}/({c['L_amont']:.2f} + {c['L_aval']:.2f}) = {c['dh_aval']:.3f} m",
              f"Δu = γw·Δh_aval = {c['gamma_w']:g} × {c['dh_aval']:.3f} = {c['delta_u']:.2f} kPa",
              f"σ'v = poids déjaugé de la colonne de sol fond -> pied = {c['sigma_v_eff']:.1f} kPa ; rapport caractéristique Δu/σ'v = {rk:.3f}"]
    etapes.append("coefficients partiels manquants : taux non calculable" if taux is None
                  else f"taux = γ_dst·Δu / (γ_stb·σ'v) = {gd:g} × {c['delta_u']:.2f} / ({gs:g} × {c['sigma_v_eff']:.1f}) = {taux:.3f}")
    sorties.append(resultat("Fond de fouille — boulance (HYD)", "fond de fouille", ph.nom, taux, detail, SOURCE, lect,
                            famille="fond_de_fouille", donnees=_donnees(c), etapes=etapes, schema=_schema(ph, c),
                            principe=(PRINCIPE_CHEMINEMENT + "Boulance (état limite HYD, EN 1997-1 § 10.3) : la surpression "
                                      "d'eau au pied côté fouille, due à la perte de charge résiduelle, est comparée au poids "
                                      "déjaugé de la colonne de sol entre le fond et le pied. Critère γ_dst·Δu ≤ γ_stb·σ'v.")))
    # Renard
    lect = Lecteur(normes)
    i_adm = lect.v("nf_p94_282", "fond_de_fouille.renard.gradient_admissible")
    ph, c = max(cas, key=lambda t: t[1]["gradient"])
    detail = f"gradient de sortie moyen i = {c['gradient']:.2f}"
    taux = None if lect.manquants else c["gradient"] / i_adm
    etapes = [f"Δh_aval = {c['dh_aval']:.3f} m sur le trajet pied -> fond L_aval = {c['L_aval']:.2f} m",
              f"i = Δh_aval/L_aval = {c['gradient']:.3f}"]
    etapes.append("gradient admissible manquant dans docs/normes : taux non calculable" if taux is None
                  else f"taux = i / i_adm = {c['gradient']:.3f} / {i_adm:g} = {taux:.3f}")
    sorties.append(resultat("Fond de fouille — renard", "fond de fouille", ph.nom, taux, detail, SOURCE, lect,
                            famille="fond_de_fouille", donnees=_donnees(c), etapes=etapes, schema=_schema(ph, c),
                            principe=(PRINCIPE_CHEMINEMENT + "Renard (érosion régressive) : le gradient hydraulique moyen de "
                                      "sortie dans la fouille, Δh_aval/L_aval, est comparé au gradient admissible fixé par le "
                                      "référentiel (valeur de projet dans docs/normes).")))
    return sorties
