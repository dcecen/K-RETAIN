"""Vérifications structurelles élément par élément.

Hypothèses simplificatrices signalées dans chaque détail (à confronter aux
extraits de norme fournis lors de la relecture croisée) :
- butons et bracons : longueur de flambement = longueur de l'appui (articulé aux
  deux extrémités) ; interaction compression-flexion linéaire
  N/Nb,Rd + M/M,Rd ≤ 1 avec moment de poids propre qL²/8 amplifié par 1/(1 − N/Ncr) ;
- liernes : poutre continue sur deux travées (cas défavorable des poutres continues
  courantes), M = q·e²/8, V = 0,625·q·e ; flexion bi-axiale linéaire ; sections de classe 1 ou 2 ;
- sections de classe 4 (tubes, âmes ou ailes élancées) : refusées, la section efficace
  n'étant pas implémentée (limites lues dans docs/normes/ec3.yaml → classification) ;
- palplanches : propriétés réduites par la corrosion au prorata de l'épaisseur
  ((t − perte)/t) ; une âme par largeur de palplanche pour le cisaillement ;
- paroi moulée : flexion simple (effort normal négligé, du côté de la sécurité en flexion composée).
"""
from __future__ import annotations

import math
import re

import numpy as np

from ..verifs import Lecteur, Verif, resultat
from . import ec2, ec3

G = 9.81  # m/s²
SRC_EC3 = "EN 1993-1-1 (§ 6.2, 6.3) — coefficients : docs/normes/ec3.yaml"
SRC_EC35 = "EN 1993-5 — coefficients : docs/normes/ec3.yaml"
SRC_EC2 = "EN 1992-1-1 (§ 3.1.7, 6.1, 6.2.2) — coefficients : docs/normes/ec2.yaml"


def _classe_section(valeur) -> int | None:
    """Classe de section (1 à 4) telle que lue dans le script ou dans un catalogue (entier, réel ou texte « 2 », « 2.0 »)."""
    if valeur in (None, ""):
        return None
    try:
        return int(round(float(str(valeur).strip().replace(",", "."))))
    except ValueError:
        return None


def _cle_combinaison(jeu: str | None) -> str:
    return "ELU_accidentel" if jeu and re.search("except|accid", jeu, re.I) else "ELU_fondamental"


# ---------------------------------------------------------------------------
# Sections des appuis
# ---------------------------------------------------------------------------
def section_element(ref: str, acier: str | None, catalogue) -> dict:
    """Caractéristiques d'un élément (buton modulaire ou profilé) pour le flambement."""
    el = catalogue.element(ref)
    nuance = acier or el.get("acier")
    if nuance is None:
        raise KeyError(f"nuance d'acier de l'élément {ref}")
    ac = catalogue.acier(nuance)
    if el["categorie"] == "butons":
        L_el = el.get("longueur_m") or 1.0
        return {"ref": ref, "A_cm2": el.get("A_cm2"), "I_cm4": el.get("I_cm4"), "W_cm3": el.get("W_cm3"),
                "masse_kg_m": (el.get("masse_kg") or 0) / L_el, "N_Rd_kN": el.get("N_Rd_kN"),
                "fy": ac["fy_MPa"], "E": el.get("E_MPa") or ac["E_MPa"], "courbe": "tube",
                "D_mm": el.get("D_mm"), "t_mm": el.get("t_mm"),
                "demo": bool(el.get("demo") or ac.get("demo"))}
    if el["categorie"] == "profiles":
        tube = el.get("famille") == "tube"
        return {"ref": ref, "A_cm2": el["A_cm2"], "I_cm4": min(el["Iy_cm4"], el["Iz_cm4"]),
                "W_cm3": el["Wel_y_cm3"], "masse_kg_m": el.get("masse_kg_m") or 0, "N_Rd_kN": None,
                "fy": ac["fy_MPa"], "E": ac["E_MPa"], "courbe": "tube" if tube else "i",
                "D_mm": el.get("D_mm"), "t_mm": el.get("t_mm"), "h_mm": el.get("h_mm"), "b_mm": el.get("b_mm"),
                "tw_mm": el.get("tw_mm"), "tf_mm": el.get("tf_mm"), "r_mm": el.get("r_mm") or 0.0,
                "demo": bool(el.get("demo") or ac.get("demo"))}
    raise KeyError(f"{ref} n'est ni un buton ni un profilé")


def classe_compression(sec: dict, lect: Lecteur) -> str | None:
    """Contrôle de classe 4 d'une section comprimée (EN 1993-1-1 tableau 5.2).

    Les limites d'élancement (coefficients de ε² pour les tubes, de ε pour les parois
    planes) sont lues dans docs/normes/ec3.yaml → classification ; ε² = 235/fy.
    Renvoie un message si la section est de classe 4 (section efficace non
    implémentée), None sinon."""
    eps2 = 235.0 / sec["fy"]
    if sec.get("courbe") == "tube":
        if not (sec.get("D_mm") and sec.get("t_mm")):
            lect.manquants.append(f"base matériaux : D et t de {sec['ref']} (classification)")
            return None
        lim = lect.v("ec3", "classification.tube_classe3")
        if lim is not None and sec["D_mm"] / sec["t_mm"] > lim * eps2:
            return (f"section de classe 4 (d/t = {sec['D_mm'] / sec['t_mm']:.0f} > {lim * eps2:.0f}) : "
                    "calcul de la section efficace non implémenté")
        return None
    dims = [sec.get(k) for k in ("h_mm", "b_mm", "tw_mm", "tf_mm")]
    if not all(dims):
        lect.manquants.append(f"base matériaux : dimensions de {sec['ref']} (classification)")
        return None
    h, b, tw, tf = dims
    r = sec.get("r_mm") or 0.0
    eps = eps2 ** 0.5
    lim_aile = lect.v("ec3", "classification.aile_classe3")
    lim_ame = lect.v("ec3", "classification.ame_comprimee_classe3")
    if lim_aile is None or lim_ame is None:
        return None
    c_aile = (b - tw - 2 * r) / 2
    c_ame = h - 2 * tf - 2 * r
    if c_aile / tf > lim_aile * eps or c_ame / tw > lim_ame * eps:
        return (f"section de classe 4 (aile c/t = {c_aile / tf:.1f}, âme c/t = {c_ame / tw:.1f}) : "
                "calcul de la section efficace non implémenté")
    return None


def _barre(sec: dict, N_k: float, L: float, angle: float, normes, cle: str) -> tuple[float | None, str, Lecteur]:
    """Buton ou bracon : flambement + flexion sous poids propre + température (EC3).

    N_b,Rd avec γM1 (EN 1993-1-1 § 6.3.1.1), M_c,Rd = W·fy/γM0 (§ 6.2.5) ; interaction linéaire
    N_Ed/N_b,Rd + M_Ed/M_c,Rd simplifiée (les formules 6.61-6.62 du § 6.3.3 avec k_yy de l'annexe B
    ne sont pas implémentées : TODO-NORME). Flambement autour de l'axe faible (I = min(Iy, Iz),
    barre bi-articulée), flexion du poids propre autour de l'axe fort (âme verticale)."""
    lect = Lecteur(normes)
    g = lect.v("nf_p94_282", f"combinaisons.{cle}.gamma_effets")
    gM0 = lect.v("ec3", "gamma_M0")
    gM1 = lect.v("ec3", "gamma_M1")
    lam0 = lect.v("ec3", "flambement.lambda_0")
    courbe = lect.v("ec3", "flambement.courbe_tube" if sec["courbe"] == "tube" else "flambement.courbe_profil_i_axe_faible")
    alpha = lect.v("ec3", f"flambement.alpha.{courbe}") if courbe else None
    aT = lect.v("ec3", "temperature.alpha_T")
    dT = lect.v("ec3", "temperature.delta_T")
    cb = lect.v("ec3", "temperature.coefficient_bridage")
    if not sec.get("I_cm4") or not sec.get("A_cm2"):
        lect.manquants.append(f"base matériaux : section ou inertie de {sec['ref']}")
    classe4 = classe_compression(sec, lect)
    if classe4:
        lect.manquants.append(classe4)
    detail_k = f"N caractéristique = {N_k:.0f} kN, L = {L:.2f} m, élément {sec['ref']}"
    if lect.manquants:
        return None, detail_k, lect
    dN_T = cb * aT * dT * sec["E"] * 1e3 * sec["A_cm2"] * 1e-4
    N_Ed = g * (N_k + dN_T)
    fl = ec3.flambement(sec["A_cm2"], sec["I_cm4"], sec["fy"], sec["E"], L, alpha, lam0, gM1)
    q = sec["masse_kg_m"] * G / 1000 * math.cos(math.radians(angle))
    if N_Ed >= fl["N_cr"]:
        return math.inf, detail_k + f" — N_Ed = {N_Ed:.0f} kN ≥ N_cr = {fl['N_cr']:.0f} kN : flambement (instabilité)", lect
    M_Ed = g * q * L**2 / 8 * ec3.amplification(N_Ed, fl["N_cr"])
    W = sec.get("W_cm3") or 0
    M_Rd = ec3.m_rd(W, sec["fy"], gM0) if W else math.inf
    taux = N_Ed / fl["N_b_Rd"] + (M_Ed / M_Rd if M_Rd else 0)
    detail = (f"N_Ed = {N_Ed:.0f} kN (dont température {g * dN_T:.0f}), λ̄ = {fl['lambda']:.2f}, χ = {fl['chi']:.2f}, "
              f"N_b,Rd = {fl['N_b_Rd']:.0f} kN ; M poids propre = {M_Ed:.1f} kN·m ; {sec['ref']}"
              + (" (DEMO)" if sec.get("demo") else ""))
    return taux, detail, lect


def _efforts_appuis(m, r) -> dict:
    """{nom: (H max kN/m, N axial max kN, phase)}."""
    sortie = {}
    for ph in r.phases:
        if not ph.ok:
            continue
        for a in ph.appuis:
            d = m.appuis[a["nom"]]
            esp, ang = d.infos.get("espacement", 1.0), d.infos.get("angle", 0.0)
            N = a["effort"] * esp / math.cos(math.radians(ang))
            if a["nom"] not in sortie or a["effort"] > sortie[a["nom"]][0]:
                sortie[a["nom"]] = (a["effort"], N, ph.nom)
    return sortie


def _efforts_appuis_3d(m, res3d) -> dict:
    """{nom: (H kN/m équivalent, N axial kN, phase)} depuis les appuis réels du pseudo-3D : l'effort
    d'un point est déjà en kN par appui (pas de multiplication par l'espacement) ; le maximum sur
    les phases et les points de même nom est retenu."""
    sortie = {}
    for ph in res3d.phases:
        if not ph.ok:
            continue
        for a in ph.appuis:
            d = m.appuis[a["nom"]]
            esp, ang = d.infos.get("espacement", 1.0) or 1.0, d.infos.get("angle", 0.0) or 0.0
            if d.type == "dalle":
                esp = 1.0
            N = a["effort"] / math.cos(math.radians(ang))
            if a["nom"] not in sortie or N > sortie[a["nom"]][1]:
                sortie[a["nom"]] = (a["effort"] / esp, N, ph.nom)
    return sortie


def _liernes_3d(res3d) -> dict:
    """{nom: (|M| max kN·m, |V| max kN, phase)} des liernes modélisées en poutre dans la plaque."""
    sortie = {}
    for ph in res3d.phases:
        if not ph.ok:
            continue
        for nom, li in ph.liernes.items():
            M, V = float(np.abs(li["M"]).max()), float(np.abs(li["V"]).max())
            if nom not in sortie or M > sortie[nom][0]:
                sortie[nom] = (M, V, ph.nom)
    return sortie


def verifier_appuis(s, m, r, catalogue, normes, cle: str, suffixe: str, efforts: dict | None = None,
                    liernes3d: dict | None = None, modele: str = "") -> list[Verif]:
    """Vérifications des appuis ; `efforts` : enveloppe 2D par défaut, ou celle du pseudo-3D ;
    `modele` : suffixe ajouté aux noms (« [pseudo-3D] ») pour distinguer les deux séries."""
    sorties: list[Verif] = []
    efforts = _efforts_appuis(m, r) if efforts is None else efforts
    for nom, a in s.appuis.items():
        if nom not in efforts:
            continue
        H, N, phase = efforts[nom]
        phase = phase + suffixe
        if a.type in ("buton", "bracon"):
            if a.element is None:
                sorties.append(resultat(f"{a.type.capitalize()} — flambement et flexion", nom, phase, None, "", SRC_EC3,
                                        categorie="structure",
                                        detail_non_verifiable=f"N = {N:.0f} kN — élément de la base nécessaire (inertie)"))
            else:
                try:
                    sec = section_element(a.element, a.acier, catalogue)
                except KeyError as e:
                    sorties.append(resultat(f"{a.type.capitalize()} — flambement et flexion", nom, phase, None, "",
                                            SRC_EC3, categorie="structure", detail_non_verifiable=str(e)))
                    continue
                taux, detail, lect = _barre(sec, N, a.longueur, a.angle, normes, cle)
                sorties.append(resultat(f"{a.type.capitalize()} — flambement et flexion", nom, phase, taux, detail,
                                        SRC_EC3 + " ; interaction linéaire simplifiée", lect, "structure"))
                if sec.get("N_Rd_kN"):
                    l2 = Lecteur(normes)
                    g = l2.v("nf_p94_282", f"combinaisons.{cle}.gamma_effets")
                    sorties.append(resultat(f"{a.type.capitalize()} — résistance fabricant", nom, phase,
                                            None if l2.manquants else g * N / sec["N_Rd_kN"],
                                            f"N_k = {N:.0f} kN, N_Rd fabricant = {sec['N_Rd_kN']:.0f} kN",
                                            "catalogue fournisseur (base matériaux)", l2, "structure"))
            if a.type == "bracon":
                V = N * math.sin(math.radians(a.angle))
                sorties.append(resultat("Bracon — appui en pied", nom, phase, None, "", "statique", categorie="structure",
                                        detail_non_verifiable=f"efforts caractéristiques en pied : horizontal {N * math.cos(math.radians(a.angle)):.0f} kN, "
                                        f"vertical {V:.0f} kN — massif d'appui à vérifier séparément"))
        elif a.type == "tirant":
            sorties += _tirant(nom, a, N, phase, catalogue, normes, cle)
        elif a.type == "dalle":
            sorties += _dalle(nom, a, H, phase, catalogue, normes, cle)
        if a.lierne:
            sorties += _lierne(nom, a, H, phase, catalogue, normes, cle, (liernes3d or {}).get(nom))
    for v in sorties:
        v.nom += modele
    return sorties


def _tirant(nom, a, N, phase, catalogue, normes, cle) -> list[Verif]:
    titre = "Tirant — armature"
    if a.element is None:
        return [resultat(titre, nom, phase, None, "", "", categorie="structure",
                         detail_non_verifiable=f"T = {N:.0f} kN — armature (element) de la base nécessaire")]
    try:
        el = catalogue.element(a.element)
    except KeyError as e:
        return [resultat(titre, nom, phase, None, "", "", categorie="structure", detail_non_verifiable=str(e))]
    lect = Lecteur(normes)
    g = lect.v("nf_p94_282", f"combinaisons.{cle}.gamma_effets")
    ga = lect.v("nf_p94_282", "tirants.gamma_armature")
    f = el.get("fp01k_MPa") or el.get("fyk_MPa")
    if not f or not el.get("A_cm2"):
        lect.manquants.append(f"base matériaux : section et limite élastique de {a.element}")
    n = a.nombre or 1
    detail = f"T_k = {N:.0f} kN ; {n} × {a.element}"
    taux = None
    if not lect.manquants:
        R = n * el["A_cm2"] * 1e-4 * f * 1e3 / ga
        taux = g * N / R
        detail += f", résistance de calcul {R:.0f} kN" + (" (DEMO)" if el.get("demo") else "")
    return [resultat(titre, nom, phase, taux, detail, "NF P 94-282 — armature de tirant (γ : docs/normes)", lect,
                     "structure")]


def _dalle(nom, a, H, phase, catalogue, normes, cle) -> list[Verif]:
    lect = Lecteur(normes)
    g = lect.v("nf_p94_282", f"combinaisons.{cle}.gamma_effets")
    gc = lect.v("ec2", "gamma_c")
    acc = lect.v("ec2", "alpha_cc")
    fck = None
    if a.beton:
        try:
            fck = catalogue.beton(a.beton)["fck_MPa"]
        except KeyError:
            pass
    if fck is None or not a.epaisseur:
        lect.manquants.append("script : beton et epaisseur de la dalle")
    detail = f"effort {H:.0f} kN/m"
    taux = None
    if not lect.manquants:
        sigma = g * H / a.epaisseur / 1000  # MPa
        fcd = acc * fck / gc
        taux = sigma / fcd
        detail += f", σ = {sigma:.2f} MPa pour fcd = {fcd:.1f} MPa"
    return [resultat("Dalle — compression", nom, phase, taux, detail, SRC_EC2, lect, "structure")]


def _lierne(nom, a, H, phase, catalogue, normes, cle, efforts_3d: tuple | None = None) -> list[Verif]:
    """Lierne : poutre continue sur deux travées (M = q·e²/8, V = 0,625·q·e) ou, en pseudo-3D,
    moments et tranchants de la lierne modélisée en poutre horizontale continue dans la plaque."""
    titre = "Lierne — flexion bi-axiale et cisaillement"
    try:
        p = catalogue.profil(a.lierne)
        if a.acier is None:
            raise KeyError(f"appui {nom} : nuance d'acier de la lierne (mot-clé acier) obligatoire")
        ac = catalogue.acier(a.acier)
    except KeyError as e:
        return [resultat(titre, f"{nom} ({a.lierne})", phase, None, "", SRC_EC3, categorie="structure",
                         detail_non_verifiable=str(e))]
    lect = Lecteur(normes)
    g = lect.v("nf_p94_282", f"combinaisons.{cle}.gamma_effets")
    gM0 = lect.v("ec3", "gamma_M0")
    e = a.espacement
    q = H
    qv = H * math.tan(math.radians(a.angle)) + (p.get("masse_kg_m") or 0) * G / 1000
    detail = f"q = {q:.0f} kN/m sur des travées de {e:.2f} m ; {a.lierne}" + (" (DEMO)" if p.get("demo") else "")
    sorties = []
    if lect.manquants:
        sorties.append(resultat(titre, f"{nom} ({a.lierne})", phase, None, detail, SRC_EC3, lect, "structure"))
    else:
        My, Mz, V = g * 0.125 * q * e**2, g * 0.125 * qv * e**2, g * 0.625 * q * e
        source_lierne = SRC_EC3 + " ; poutre continue sur deux travées (cas défavorable) M = q·e²/8, V = 0,625·q·e"
        if efforts_3d is not None:
            My, V = g * efforts_3d[0], g * efforts_3d[1]
            source_lierne = SRC_EC3 + " ; moments et tranchants de la lierne modélisée en poutre continue dans la plaque (pseudo-3D)"
        fy = ac["fy_MPa"]
        MyR, MzR = ec3.m_rd(p["Wpl_y_cm3"], fy, gM0), ec3.m_rd(p["Wpl_z_cm3"], fy, gM0)
        VR = ec3.v_pl_rd(p.get("Avz_cm2") or 0, fy, gM0)
        t_flex = My / MyR + Mz / MzR
        t_cis = V / VR if VR else math.inf
        detail += (f" ; My = {My:.0f}, Mz = {Mz:.1f} kN·m (M,Rd {MyR:.0f} / {MzR:.0f}) ; "
                   f"V = {V:.0f} kN (Vpl,Rd {VR:.0f})")
        sorties.append(resultat(titre, f"{nom} ({a.lierne})", phase, max(t_flex, t_cis), detail,
                                source_lierne, lect, "structure"))
    sorties.append(resultat("Lierne — raidisseurs", f"{nom} ({a.lierne})", phase, None, "", "EN 1993-1-5 § 6",
                            categorie="structure",
                            detail_non_verifiable=f"effort concentré au droit de chaque appui ≈ {q * e:.0f} kN (caractéristique) : "
                            "résistance de l'âme et raidisseurs à vérifier (non automatisé)"))
    return sorties


# ---------------------------------------------------------------------------
# Paroi
# ---------------------------------------------------------------------------
def _efforts_paroi(r) -> dict:
    Mp = max(((float(ph.M.max()), ph.nom) for ph in r.phases if ph.ok), default=(0.0, None))
    Mn = min(((float(ph.M.min()), ph.nom) for ph in r.phases if ph.ok), default=(0.0, None))
    V = max(((float(np.abs(ph.V).max()), ph.nom) for ph in r.phases if ph.ok), default=(0.0, None))
    return {"M+": Mp, "M-": Mn, "V": V}


def _efforts_paroi_3d(res3d) -> dict:
    """Enveloppes sur toute la plaque pseudo-3D : Mz max et min (flexion verticale, kN·m/m), |V| max
    (statique des lignes, 2 points par élément), |Ms| max (flexion horizontale, kN·m/m de hauteur)."""
    oks = [ph for ph in res3d.phases if ph.ok]
    Mp = max(((float(ph.Mz.max()), ph.nom) for ph in oks), default=(0.0, None))
    Mn = min(((float(ph.Mz.min()), ph.nom) for ph in oks), default=(0.0, None))
    V = max(((float(np.abs(ph.V_diag).max()), ph.nom) for ph in oks), default=(0.0, None))
    Ms = max(((float(np.abs(ph.Ms).max()), ph.nom) for ph in oks), default=(0.0, None))
    return {"M+": Mp, "M-": Mn, "V": V, "Ms": Ms}


def _mat_ec2(lect: Lecteur, fck: float | None) -> ec2.Materiaux | None:
    vals = {k: lect.v("ec2", c) for k, c in (
        ("fyk", "fyk_armatures"), ("gamma_c", "gamma_c"), ("gamma_s", "gamma_s"), ("alpha_cc", "alpha_cc"),
        ("lam", "diagramme_rectangulaire.lambda"), ("eta", "diagramme_rectangulaire.eta"),
        ("eps_cu3", "diagramme_rectangulaire.epsilon_cu3"), ("Es", "Es"))}
    if fck is None or any(v is None for v in vals.values()):
        return None
    return ec2.Materiaux(fck=fck, **vals)


def verifier_paroi(s, m, r, catalogue, normes, cle: str, suffixe: str, efforts: dict | None = None,
                    modele: str = "") -> list[Verif]:
    """Vérifications de la paroi ; `efforts` : enveloppe 2D par défaut, ou celle du pseudo-3D
    (_efforts_paroi_3d) ; `modele` : suffixe des noms (« [pseudo-3D] »). Le blindage d'une berlinoise
    (pressions du 2D) n'est vérifié qu'en 2D."""
    p = s.paroi
    inf = m.ecran.infos
    ef = _efforts_paroi(r) if efforts is None else efforts
    (Mp, php), (Mn, phn), (Vk, phv) = ef["M+"], ef["M-"], ef["V"]
    Mk = max(abs(Mp), abs(Mn))
    ph_M = php if abs(Mp) >= abs(Mn) else phn
    sorties: list[Verif] = []
    lect = Lecteur(normes)
    g = lect.v("nf_p94_282", f"combinaisons.{cle}.gamma_effets")
    if p.type == "palplanche" and inf.get("section"):
        sec, fy = inf["section"], inf["acier"]["fy_MPa"]
        gM0 = lect.v("ec3", "palplanches.gamma_M0")
        beta_B = 1.0
        if sec.get("forme") == "U":
            beta_B = lect.v("ec3", "palplanches.beta_B")
        seuil = lect.v("ec3", "cisaillement.rapport_reduction")
        reduc = 1.0
        if p.perte_epaisseur and sec.get("t_mm"):
            reduc = max(0.0, 1 - p.perte_epaisseur / sec["t_mm"])
        classe = _classe_section(p.classe_section or sec.get("classe"))
        if classe is None:
            lect.manquants.append("classe de section de la palplanche (catalogue ou paroi.classe_section)")
        elif classe == 4:
            lect.manquants.append("palplanche de classe 4 : calcul de la section efficace non implémenté")
        plastique = classe in (1, 2) and bool(sec.get("Wpl_cm3_m"))
        W = (sec["Wpl_cm3_m"] if plastique else sec["Wel_cm3_m"]) * reduc
        detail = f"M_k = {Mk:.0f} kN·m/m, V_k = {Vk:.0f} kN/m ; {p.profil}" + (" (DEMO)" if inf.get("demo") else "")
        taux = None
        if not lect.manquants:
            M_Ed, V_Ed = g * Mk, g * Vk
            Av = (sec.get("s_mm") or 0) * ((sec.get("h_mm") or 0) - (sec.get("t_mm") or 0)) / 100 / ((sec.get("largeur_mm") or 1000) / 1000) * reduc
            VR = ec3.v_pl_rd(Av, fy, gM0) if Av else math.inf
            MR = beta_B * ec3.m_rd(W, fy, gM0)
            if V_Ed > seuil * VR:
                rho = (2 * V_Ed / VR - 1) ** 2
                MR *= (1 - rho)
            taux = max(M_Ed / MR, V_Ed / VR)
            detail += (f" ; M_Ed = {M_Ed:.0f} pour M_c,Rd = {MR:.0f} kN·m/m (W {'pl' if plastique else 'él'}"
                       f"{', corrosion' if reduc < 1 else ''}) ; V_Ed = {V_Ed:.0f} pour Vpl,Rd = {VR:.0f} kN/m")
        sorties.append(resultat("Palplanches — flexion et cisaillement", p.profil, ph_M and ph_M + suffixe, taux,
                                detail, SRC_EC35 + " ; Av = une âme par largeur de palplanche (hypothèse, EN 1993-5 § 5.2.2 à confirmer)",
                                lect, "structure"))
    elif p.type == "berlinoise" and inf.get("section"):
        sec, fy, e = inf["section"], inf["acier"]["fy_MPa"], inf["entraxe"]
        gM0 = lect.v("ec3", "gamma_M0")
        detail = f"M_k = {Mk * e:.0f} kN·m, V_k = {Vk * e:.0f} kN par profilé ; {p.profil}" + (" (DEMO)" if inf.get("demo") else "")
        taux = None
        if not lect.manquants:
            MR = ec3.m_rd(sec["Wpl_y_cm3"], fy, gM0)
            VR = ec3.v_pl_rd(sec.get("Avz_cm2") or 0, fy, gM0)
            taux = max(g * Mk * e / MR, g * Vk * e / VR)
            detail += f" ; M,Rd = {MR:.0f} kN·m, Vpl,Rd = {VR:.0f} kN"
        sorties.append(resultat("Profilés de berlinoise — flexion et cisaillement", p.profil, ph_M and ph_M + suffixe,
                                taux, detail, SRC_EC3 + " (classe 1-2 supposée)", lect, "structure"))
        if not modele:
            sorties += _blindage(p, r, inf, normes, cle, suffixe)
    elif p.type in ("paroi_moulee", "pieux_secants", "pieux_disjoints"):
        sorties += _beton(p, inf, r, Mp, Mn, Vk, php, phn, phv, normes, cle, suffixe)
    if modele and "Ms" in ef:
        sorties += _flexion_horizontale(p, inf, ef["Ms"][0], ef["Ms"][1] and ef["Ms"][1] + suffixe, normes, cle)
    for v in sorties:
        v.nom += modele
    return sorties


def _flexion_horizontale(p, inf, Ms: float, phase, normes, cle: str) -> list[Verif]:
    """Moment horizontal Ms de la plaque (pseudo-3D). Paroi moulée : flexion simple d'une bande de
    1 m de hauteur, d = e − enrobage_horizontal (EN 1992-1-1 § 6.1), As horizontal requis et M_Rd si
    paroi.armatures_horizontales est donné. Autres parois : la résistance en flexion horizontale des
    serrures (palplanches, EN 1993-5) ou des recouvrements (pieux) n'est pas définie : TODO-NORME."""
    titre = "Flexion horizontale (moment Ms de la plaque)"
    if p.type != "paroi_moulee":
        return [resultat(titre, p.type, phase, None, "", "TODO-NORME : résistance en flexion horizontale des serrures "
                         "(EN 1993-5) ou des recouvrements de pieux non définie", categorie="structure",
                         detail_non_verifiable=f"|Ms| max = {Ms:.0f} kN·m/m de hauteur — non vérifié")]
    lect = Lecteur(normes)
    g = lect.v("nf_p94_282", f"combinaisons.{cle}.gamma_effets")
    fck = (inf.get("beton") or {}).get("fck_MPa")
    if fck is None:
        lect.manquants.append("base matériaux : fck du béton de la paroi")
    mat = _mat_ec2(lect, fck)
    enr = p.enrobage_horizontal if p.enrobage_horizontal is not None else p.enrobage
    if enr is None:
        lect.manquants.append("script : paroi.enrobage_horizontal (ou enrobage)")
    detail = f"|Ms| max = {Ms:.0f} kN·m/m de hauteur"
    taux = None
    det_nv = detail
    if not lect.manquants:
        d = p.epaisseur - enr
        f = ec2.flexion_rectangulaire(g * Ms, 1.0, d, mat)
        detail += f" ; As horizontal requis = {f['As_cm2']:.1f} cm²/m par face, μ = {f['mu']:.3f} (μ lim {f['mu_lim']:.3f})"
        det_nv = detail
        if p.armatures_horizontales:
            MR = ec2.m_rd_rectangulaire(p.armatures_horizontales, 1.0, d, mat)
            taux = g * Ms / MR
            detail += f" ; As fourni {p.armatures_horizontales} cm²/m, M_Rd = {MR:.0f} kN·m/m"
        else:
            det_nv += " — armatures_horizontales absentes"
            if f["mu"] > f["mu_lim"]:
                taux = f["mu"] / f["mu_lim"]
    return [resultat(titre, "paroi", phase, taux, detail, SRC_EC2, lect, "structure", detail_non_verifiable=det_nv)]


def _blindage(p, r, inf, normes, cle, suffixe) -> list[Verif]:
    titre = "Blindage entre profilés — flexion"
    if not p.blindage:
        return [resultat(titre, "blindage", None, None, "", "", categorie="structure",
                         detail_non_verifiable="bloc paroi.blindage absent")]
    b = (inf["section"].get("b_mm") or 0) / 1000
    portee = inf["entraxe"] - b
    pmax, phase = 0.0, None
    for ph in r.phases:
        if not ph.ok:
            continue
        am = ph.pressions["amont"]
        dessus = am["z"] >= ph.terrain_aval
        if dessus.any():
            u = np.interp(am["z"][dessus], ph.eau["z"], ph.eau["u_amont"])
            v = float((am["p"][dessus] + u).max())
            if v > pmax:
                pmax, phase = v, ph.nom
    lect = Lecteur(normes)
    g = lect.v("nf_p94_282", f"combinaisons.{cle}.gamma_effets")
    if p.blindage.resistance is None:
        lect.manquants.append("script : paroi.blindage.resistance (MPa, valeur de calcul)")
    detail = f"pression maximale {pmax:.0f} kPa sur une portée libre de {portee:.2f} m, épaisseur {p.blindage.epaisseur} m"
    taux = None
    if not lect.manquants:
        M = g * pmax * portee**2 / 8           # kN·m par m de hauteur
        sigma = M / (p.blindage.epaisseur**2 / 6) / 1000  # MPa
        taux = sigma / p.blindage.resistance
        detail += f" ; σ = {sigma:.1f} MPa pour {p.blindage.resistance} MPa"
    return [resultat(titre, f"blindage {p.blindage.materiau}", phase and phase + suffixe, taux, detail,
                     "résistance des matériaux (poutre sur deux appuis, M = pL²/8)", lect, "structure")]


def _beton(p, inf, r, Mp, Mn, Vk, php, phn, phv, normes, cle, suffixe) -> list[Verif]:
    sorties = []
    lect = Lecteur(normes)
    g = lect.v("nf_p94_282", f"combinaisons.{cle}.gamma_effets")
    fck = (inf.get("beton") or {}).get("fck_MPa")
    if fck is None:
        lect.manquants.append("base matériaux : fck du béton de la paroi (EI imposé : classe de béton non lue)")
    mat = _mat_ec2(lect, fck)
    if p.enrobage is None:
        lect.manquants.append("script : paroi.enrobage (m, à l'axe des armatures)")
    if p.type == "paroi_moulee":
        e = p.epaisseur
        for face, Mk, ph, prov in (("face fouille", Mp, php, p.armatures_fouille),
                                   ("face terre", Mn, phn, p.armatures_terre)):
            detail = f"M_k = {Mk:.0f} kN·m/m ({face})"
            taux = None
            det_nv = detail
            if not lect.manquants:
                d = e - p.enrobage
                f = ec2.flexion_rectangulaire(g * Mk, 1.0, d, mat)
                detail += f" ; As requis = {f['As_cm2']:.1f} cm²/m, μ = {f['mu']:.3f} (μ lim {f['mu_lim']:.3f})"
                det_nv = detail
                if prov:
                    MR = ec2.m_rd_rectangulaire(prov, 1.0, d, mat)
                    taux = g * abs(Mk) / MR
                    detail += f" ; As fourni {prov} cm²/m, M_Rd = {MR:.0f} kN·m/m"
                else:
                    det_nv += " — ferraillage fourni absent (armatures_fouille / armatures_terre)"
                    if f["mu"] > f["mu_lim"]:
                        taux = f["mu"] / f["mu_lim"]  # béton insuffisant quel que soit l'acier
            sorties.append(resultat(f"Paroi moulée — flexion ({face})", "paroi", ph and ph + suffixe, taux, detail,
                                    SRC_EC2, lect, "structure", detail_non_verifiable=det_nv))
        l2 = Lecteur(normes)
        g2 = l2.v("nf_p94_282", f"combinaisons.{cle}.gamma_effets")
        crdc = l2.v("ec2", "tranchant.C_Rd_c")
        cvm = l2.v("ec2", "tranchant.coef_v_min")
        kmax = l2.v("ec2", "tranchant.k_max")
        rmax = l2.v("ec2", "tranchant.rho_l_max")
        gc = l2.v("ec2", "gamma_c")
        if p.enrobage is None:
            l2.manquants.append("script : paroi.enrobage")
        As_t = min([x for x in (p.armatures_fouille, p.armatures_terre) if x] or [0.0])
        detail = f"V_k = {Vk:.0f} kN/m"
        taux = None
        if not l2.manquants and fck:
            VR = ec2.v_rd_c(1.0, e - p.enrobage, As_t, fck, gc, crdc, cvm, kmax, rmax)
            taux = g2 * Vk / VR
            detail += f" ; VRd,c = {VR:.0f} kN/m (ρl avec {As_t:.1f} cm²/m)"
        sorties.append(resultat("Paroi moulée — effort tranchant sans armatures", "paroi", phv and phv + suffixe,
                                taux, detail, SRC_EC2, l2, "structure"))
    else:
        D = p.diametre
        e_arm = p.entraxe if (p.type == "pieux_disjoints" or p.primaires_armes) else 2 * p.entraxe
        Mk = max(abs(Mp), abs(Mn))
        ph = php if abs(Mp) >= abs(Mn) else phn
        detail = f"M_k par pieu armé = {Mk * e_arm:.0f} kN·m (entraxe des pieux armés {e_arm:.2f} m)"
        taux = None
        det_nv = detail
        insuffisant = False
        if not lect.manquants:
            r_s = D / 2 - p.enrobage
            As_req = ec2.as_circulaire(g * Mk * e_arm, D, r_s, mat)
            detail += f" ; As requis = {As_req:.0f} cm² par pieu"
            det_nv = detail + " — ferraillage fourni absent (armatures_pieu)"
            if p.armatures_pieu:
                MR = ec2.m_rd_circulaire(D, p.armatures_pieu, r_s, mat)
                taux = g * Mk * e_arm / MR
                detail += f" ; As fourni {p.armatures_pieu} cm², M_Rd = {MR:.0f} kN·m"
            elif math.isinf(As_req):
                insuffisant = True
        if insuffisant:
            sorties.append(Verif("Pieux — flexion (section circulaire)", "structure", "pieux", ph and ph + suffixe,
                                 "non_ok", None, detail + " — section de béton insuffisante : aucun ferraillage de la "
                                 "plage de recherche (borne de calcul, non normative) ne suffit", SRC_EC2, []))
        else:
            sorties.append(resultat("Pieux — flexion (section circulaire)", "pieux", ph and ph + suffixe, taux, detail,
                                    SRC_EC2, lect, "structure", detail_non_verifiable=det_nv))
        sorties.append(resultat("Pieux — effort tranchant", "pieux", phv and phv + suffixe, None, "", SRC_EC2,
                                categorie="structure",
                                detail_non_verifiable=f"V_k par pieu = {Vk * e_arm:.0f} kN — section équivalente "
                                "d'une section circulaire à définir (non automatisé)"))
    return sorties


# ---------------------------------------------------------------------------
# Élément le plus léger qui passe
# ---------------------------------------------------------------------------
def suggestions(s, ex, catalogue, normes) -> list[dict]:
    sorties = []
    for nom, a in s.appuis.items():
        if a.type not in ("buton", "bracon") or not a.longueur:
            continue
        candidats = []
        for t in ("butons", "profiles"):
            if t == "profiles" and a.acier is None:
                continue  # nuance des profilés inconnue : pas de valeur implicite
            for row in catalogue.lister(t):
                try:
                    candidats.append(section_element(row["ref"], a.acier if t == "profiles" else None, catalogue))
                except KeyError:
                    continue
        candidats.sort(key=lambda c: c["masse_kg_m"] or math.inf)
        pire_N, cle_pire = 0.0, "ELU_fondamental"
        for jeu, (m, r) in ex.jeux.items():
            if not r.complet:
                continue
            ef = _efforts_appuis(m, r).get(nom)
            if ef and ef[1] > pire_N:
                pire_N, cle_pire = ef[1], _cle_combinaison(jeu)
        if pire_N <= 0:
            continue
        choix, manque = None, []
        for c in candidats:
            l_classe = Lecteur(normes)
            if classe_compression(c, l_classe):
                continue  # section de classe 4 : écartée
            taux, _, lect = _barre(c, pire_N, a.longueur, a.angle, normes, cle_pire)
            if lect.manquants:
                manque = lect.manquants
                break
            if c.get("N_Rd_kN"):
                g = lect.v("nf_p94_282", f"combinaisons.{cle_pire}.gamma_effets")
                taux = max(taux, g * pire_N / c["N_Rd_kN"])
            if taux <= 1.0:
                choix = (c, taux)
                break
        if manque:
            sorties.append({"appui": nom, "element": None, "taux": None,
                            "message": "non déterminable : valeurs de norme manquantes (" + ", ".join(manque[:3]) + "…)"})
        elif choix:
            c, t = choix
            sorties.append({"appui": nom, "element": c["ref"], "taux": t,
                            "message": f"{c['masse_kg_m']:.0f} kg/m" + (" — élément DEMO" if c.get("demo") else "")})
        else:
            sorties.append({"appui": nom, "element": None, "taux": None, "message": "aucun élément de la base ne passe"})
    return sorties


def executer(s, ex, catalogue, normes) -> tuple[list[Verif], list[dict]]:
    verifs: list[Verif] = []
    plusieurs = len(ex.jeux) > 1
    for jeu, (m, r) in ex.jeux.items():
        if not r.complet:
            continue
        cle = _cle_combinaison(jeu)
        if cle == "ELU_accidentel":
            msg = f"Jeu d'eau « {jeu} » : combinaison ELU accidentelle retenue d'après son nom (contient « except » ou « accid »)."
            if msg not in ex.avertissements:
                ex.avertissements.append(msg)
        suffixe = f" [{jeu}]" if plusieurs and jeu else ""
        verifs += verifier_paroi(s, m, r, catalogue, normes, cle, suffixe)
        verifs += verifier_appuis(s, m, r, catalogue, normes, cle, suffixe)
    res3d = getattr(ex, "pseudo3d", None)
    if res3d is not None and res3d.complet:
        # seconde série sur les efforts de la plaque (jeu d'eau principal, branche principale)
        cle = _cle_combinaison(ex.jeu_principal)
        m = ex.modele
        v3 = verifier_paroi(s, m, ex.resultat, catalogue, normes, cle, "", efforts=_efforts_paroi_3d(res3d), modele=" [pseudo-3D]")
        v3 += verifier_appuis(s, m, ex.resultat, catalogue, normes, cle, "", efforts=_efforts_appuis_3d(m, res3d),
                              liernes3d=_liernes_3d(res3d), modele=" [pseudo-3D]")
        if not res3d.appuis_repartis:
            for v in v3:
                v.source += " ; appuis ponctuels sur un nœud (pseudo3d.largeur_appui absente) : Ms et V à leur droit dépendent du maillage"
        verifs += v3
    return verifs, suggestions(s, ex, catalogue, normes)


# ---------------------------------------------------------------------------
# Flèches des butons et des liernes (affichage 3D et contrôle de service)
# ---------------------------------------------------------------------------
def fleche_barre(sec: dict, N_kN: float, L: float, angle: float = 0.0, avec_compression: bool = True) -> dict:
    """Flèche à mi-portée d'un buton ou bracon sous son poids propre (m), en poutre sur
    deux appuis : f = 5·g·L⁴ / (384·E·I), avec g le poids propre par mètre projeté
    perpendiculairement à la barre (q·cos θ). Résistance des matériaux (Timoshenko,
    *Strength of Materials*, poutre simplement appuyée sous charge uniforme).

    Avec `avec_compression`, la flèche est majorée par l'effet du second ordre de la
    compression N : 1 / (1 − N/Ncr) (Timoshenko & Gere, *Theory of Elastic Stability*,
    1961 — même amplification que dans `_barre`). Ncr = charge critique d'Euler.

    Renvoie aussi le raccourcissement axial élastique N·L / (E·A) (m). Unités : N en kN
    (caractéristique, non pondéré), L en m, section en cm², cm⁴, E en MPa, masse en kg/m.
    """
    E_kPa = sec["E"] * 1e3
    I_m4 = sec["I_cm4"] * 1e-8
    A_m2 = sec["A_cm2"] * 1e-4
    g = sec["masse_kg_m"] * G / 1000 * math.cos(math.radians(angle))   # kN/m perpendiculaire à la barre
    f0 = 5.0 * g * L**4 / (384.0 * E_kPa * I_m4)
    N_cr = ec3.n_cr(sec["E"], sec["I_cm4"], L)
    amp = ec3.amplification(max(N_kN, 0.0), N_cr) if avec_compression else 1.0
    return {
        "fleche_poids_propre_m": f0,
        "fleche_m": f0 * amp if math.isfinite(amp) else math.inf,
        "amplification": amp,
        "N_cr_kN": N_cr,
        "raccourcissement_m": N_kN * L / (E_kPa * A_m2),
        "g_kN_m": g,
    }


def fleche_lierne(profil: dict, q_kN_m: float, e: float) -> dict:
    """Flèche d'une lierne entre deux appuis (m) sous la réaction de la paroi q (kN/m),
    valeur approchée : poutre continue à travées égales assimilée à une travée
    bi-encastrée sous charge uniforme, f = q·e⁴ / (384·E·I) (Résistance des matériaux ;
    la travée isostatique donnerait 5 fois plus). Signalée comme approchée.

    Flexion autour de l'axe fort (Iy, l'âme est horizontale : voir choix du module
    assemblages). E en MPa, I en cm⁴.
    """
    E_kPa = (profil.get("E_MPa") or 210000.0) * 1e3
    I_m4 = profil["Iy_cm4"] * 1e-8
    return {"fleche_m": q_kN_m * e**4 / (384.0 * E_kPa * I_m4), "approchee": True}
