"""Mise en forme des résultats pour l'interface : phases, enveloppes et phase
dimensionnante. Conventions rappelées dans `conventions`."""
from __future__ import annotations

import math

import numpy as np

from .appuis.raideurs import effort_axial
from .noyau.modele import Modele
from .noyau.phasage import ErreurModele, ResultatCalcul
from .sol.kerisel_absi import TableAbsente
from .sol.terrain import ErreurTerrain

CONVENTIONS = {
    "deplacement": "y positif vers la fouille (mm)",
    "moment": "M positif quand la face côté fouille est tendue (kN·m/m)",
    "tranchant": "V = dM/dz, z vers le haut (kN/m)",
    "pression": "pressions effectives horizontales des terres (kPa), eau à part",
    "effort_appui": "positif quand l'appui retient l'écran (buton comprimé, tirant tendu)",
}


def _l(a) -> list:
    return [None if (isinstance(v, float) and not math.isfinite(v)) else v for v in np.asarray(a, float).tolist()]


def actions_phase(ph_modele, modele: Modele) -> list[dict]:
    """Actions d'une phase du modèle, pour l'affichage (frise des phases)."""
    a = []
    if ph_modele.excaver is not None:
        a.append({"type": "excavation", "texte": f"excavation à {ph_modele.excaver:.2f} m"})
    for cote, z in (("amont", ph_modele.remblayer_amont), ("aval", ph_modele.remblayer_aval)):
        if z is not None:
            a.append({"type": "remblai", "texte": f"remblai {cote} à {z:.2f} m"})
    for nom in ph_modele.poser:
        t = modele.appuis[nom].type if nom in modele.appuis else "appui"
        a.append({"type": "radier" if t == "dalle" else "pose", "texte": f"pose de {nom} ({t})"})
    for nom in ph_modele.deposer:
        a.append({"type": "depose", "texte": f"dépose de {nom}"})
    for cote, z in ph_modele.eau.items():
        a.append({"type": "eau", "texte": f"nappe {cote} : {'aucune' if z is None else f'{z:.2f} m'}"})
    terrain_ajout = sorted({sc.nom.split(":")[1] for sc in ph_modele.ajouter_surcharges if sc.nom.startswith("~terrain:")})
    terrain_retrait = sorted({n.split(":")[1] for n in ph_modele.retirer_surcharges if n.startswith("~terrain:")})
    for sc in ph_modele.ajouter_surcharges:
        if not sc.nom.startswith("~terrain:"):
            a.append({"type": "surcharge", "texte": f"ajout de la surcharge {sc.nom}"})
    for nom in ph_modele.retirer_surcharges:
        if not nom.startswith("~terrain:"):
            a.append({"type": "surcharge", "texte": f"retrait de la surcharge {nom}"})
    for nom in terrain_ajout:
        a.append({"type": "remblai", "texte": f"mise en place de {nom} (surcharge équivalente)"})
    for nom in terrain_retrait:
        a.append({"type": "excavation", "texte": f"terrassement de {nom}"})
    return a


def _butee_valeurs(ph) -> tuple[float | None, float | None]:
    """(Bm, Bt) en kN/m côté fouille : résultante des pressions mobilisées et des pressions limites
    de butée (valeurs caractéristiques, intégrées sur la fiche)."""
    av = ph.pressions.get("aval")
    if not av or len(av["z"]) == 0:
        return None, None
    return float(np.sum(av["L"] * av["p"])), float(np.sum(av["L"] * av["pp"]))


def _fonds_par_zone(modele: Modele, res: ResultatCalcul, k: int, ph) -> dict | None:
    """Fond de fouille par zone (geometrie.fouille.zones) à la phase k : la zone par défaut est celle du calcul
    (terrain aval de la phase), les autres suivent le bloc excaver des phases jouées jusqu'à k (chaîne des parents)."""
    geo = getattr(modele, "geometrie", None)
    if geo is None or not getattr(geo, "zones_fond", ()):
        return None
    from .geometrie.derivation import fonds_par_zone
    chaine: list[int] = []
    j = k
    while j and j > 0:
        chaine.append(j)
        j = res.phases[j].parent if res.phases[j].parent is not None else j - 1
    excavers = [modele.excaver_zones[i - 1] for i in reversed(chaine) if 0 < i <= len(modele.excaver_zones)]
    fonds = fonds_par_zone(geo, excavers, modele.terrain_aval if modele.terrain_aval is not None else modele.terrain_amont)
    fonds["defaut"] = float(ph.terrain_aval)
    return fonds


def _bilan_forces(ph) -> dict:
    """Bilan des forces horizontales sur l'écran à la fin de la phase : pressions des terres des deux faces,
    pressions d'eau et efforts d'appui (statique : la somme doit être nulle). `relatif` rapporte le résidu à la
    somme des valeurs absolues (échelle des forces en jeu)."""
    am, av = ph.pressions["amont"], ph.pressions["aval"]
    e = ph.eau
    L = np.repeat(np.diff(ph.z) / 2, 2)
    appuis = sum(a["effort"] for a in ph.appuis)
    F = float(np.sum(am["L"] * am["p"]) - np.sum(av["L"] * av["p"]) + np.sum((e["u_amont"] - e["u_aval"]) * L) - appuis)
    brut = float(np.sum(am["L"] * np.abs(am["p"])) + np.sum(av["L"] * np.abs(av["p"]))
                 + np.sum(np.abs(e["u_amont"] - e["u_aval"]) * L) + sum(abs(a["effort"]) for a in ph.appuis))
    return {"residu_kN_m": F, "echelle_kN_m": brut, "relatif": F / max(brut, 1e-12)}


def _butee_mobilisee(ph) -> float | None:
    """Bm/Bt : butée mobilisée rapportée à la butée limite, côté fouille (valeur caractéristique)."""
    Bm, Bt = _butee_valeurs(ph)
    return Bm / Bt if Bm is not None and Bt is not None and Bt > 0 else None


def _complement_appui(da, effort: float, catalogue, normes) -> dict:
    """Effort de calcul (ELU) et flèches d'un appui à une phase, d'après le module de vérification
    (`verifs_struct.elements`) : rien n'est calculé dans la vue 3D. Valeurs absentes si l'élément
    n'est pas dans la base ou si le coefficient de norme manque."""
    from .verifs import Lecteur
    from .verifs_struct.elements import fleche_barre, fleche_lierne, section_element

    inf = da.infos
    esp = inf.get("espacement", 1.0)
    ang = inf.get("angle", 0.0)
    N = effort_axial(effort, esp, ang)
    out: dict = {"effort_elu_kN": None, "effort_elu_kN_m": None, "fleche_mm": None, "fleche_poids_propre_mm": None,
                 "raccourcissement_mm": None, "N_cr_kN": None, "fleche_lierne_mm": None}
    if normes is not None:
        g = Lecteur(normes).v("nf_p94_282", "combinaisons.ELU_fondamental.gamma_effets")
        if g is not None:
            out["effort_elu_kN"] = g * N
            out["effort_elu_kN_m"] = g * effort
    if catalogue is None:
        return out
    if da.type in ("buton", "bracon") and inf.get("element") and inf.get("longueur"):
        try:
            sec = section_element(inf["element"], inf.get("acier"), catalogue)
            if sec.get("I_cm4") and sec.get("A_cm2"):
                f = fleche_barre(sec, N, inf["longueur"], ang)
                out.update({"fleche_mm": f["fleche_m"] * 1e3 if math.isfinite(f["fleche_m"]) else None,
                            "fleche_poids_propre_mm": f["fleche_poids_propre_m"] * 1e3,
                            "raccourcissement_mm": f["raccourcissement_m"] * 1e3, "N_cr_kN": f["N_cr_kN"]})
        except KeyError:
            pass
    if inf.get("lierne") and da.type != "dalle":
        try:
            pr = catalogue.profil(inf["lierne"])
            if pr.get("Iy_cm4"):
                out["fleche_lierne_mm"] = fleche_lierne(pr, effort, esp)["fleche_m"] * 1e3
        except KeyError:
            pass
    return out


def _pp_sans_terrain(modele: Modele, res: ResultatCalcul) -> list:
    """Butée limite aval sans l'effet des risbermes/talus/gradins (méthode de la surcharge équivalente),
    par phase : pp − Kph(z) × Δσv des bandes équivalentes actives. None si aucun objet côté fouille."""
    from .noyau.phasage import _coefficients_couche
    from .sol.couches import indice_couche, trier
    from .plan.geometrie import cote_concerne
    from .sol.terrain import CoupeCalcul, PREFIXE_TERRAIN, effet_butee

    coupe = CoupeCalcul.depuis_dict(modele.coupe)
    objets = [o for o in modele.terrain_objets
              if o.face == "aval" and o.methode == "surcharge_equivalente" and cote_concerne(o.cotes_paroi, coupe)]
    if not objets:
        return [None] * len(res.phases)
    couches = trier(modele.couches)
    kph = [_coefficients_couche(c, modele.coefficients)[1] for c in couches]
    out = []
    for k, ph in enumerate(res.phases):
        if not ph.ok:
            out.append(None)
            continue
        # objets actifs à la phase k (k = 0 : état initial, k ≥ 1 : phases[k-1])
        actifs = [o for o in objets if (o.phase_debut or 0) <= k <= (o.phase_fin if o.phase_fin is not None else len(res.phases))]
        if not actifs:
            out.append(None)
            continue
        z = np.asarray(ph.pressions["aval"]["z"], float)
        kph_z = np.array([kph[indice_couche(couches, zz)] for zz in z])
        try:
            sup = effet_butee(actifs, kph_z, z, ph.terrain_aval, coupe)
        except (ErreurTerrain, ValueError, KeyError, IndexError):   # objet inapplicable à cette phase : courbe absente
            out.append(None)
            continue
        out.append(_l(np.asarray(ph.pressions["aval"]["pp"], float) - sup))
    _ = PREFIXE_TERRAIN
    return out


def _couches(modele: Modele) -> list[dict]:
    """Couches triées du haut vers le bas avec les coefficients utilisés par le calcul (Kah, Kph, K0, kh)."""
    from .noyau.phasage import _coefficients_couche, _kh_couche

    out = []
    methode_k = {"coulomb": "Coulomb (Rankine si δ = 0)", "kerisel_absi": "tables de Kérisel-Absi"}.get(modele.coefficients, modele.coefficients)
    for c in sorted(modele.couches, key=lambda c: -c.toit):
        if c.kh is not None:
            methode_kh = "kh imposé"
        elif c.EM is None and c.qc is not None:
            methode_kh = "Schmitt, EM par corrélation CPT (EM = qc × EM/qc)"
        else:
            methode_kh = "Schmitt (EM, α, EI)"
        d = {"nom": c.nom, "toit": c.toit, "kah": None, "kph": None, "k0": None, "kh": None,
             "methode_k": methode_k, "methode_kh": methode_kh,
             "k0_source": "saisi" if c.K0 is not None else "Jaky (1 − sin φ')",
             "phi": c.phi, "c": c.c, "delta_a_sur_phi": c.delta_a_sur_phi, "delta_p_sur_phi": c.delta_p_sur_phi}
        try:
            kah, kph, k0, _, _, _ = _coefficients_couche(c, modele.coefficients)
            d.update({"kah": kah, "kph": kph, "k0": k0})
        except (ErreurModele, ValueError, TableAbsente):   # coefficients refusés (butée hors domaine, tables absentes) : « — »
            pass
        try:
            EI = float(np.asarray(modele.ecran.EI_en(np.array([c.toit - 0.5])))[0])
            d["kh"] = _kh_couche(c, EI)
        except (ErreurModele, ValueError, TypeError):   # EM/alpha absents ou kh non calculable : « — »
            pass
        out.append(d)
    return out


def serialiser(res: ResultatCalcul, modele: Modele, projet: str = "", catalogue=None, normes=None) -> dict:
    pp_sans = _pp_sans_terrain(modele, res)
    phases = []
    for k, ph in enumerate(res.phases):
        d = {
            "nom": ph.nom, "ok": ph.ok, "message": ph.message,
            "terrain_amont": ph.terrain_amont, "terrain_aval": ph.terrain_aval,
            "eau_amont": ph.eau_amont, "eau_aval": ph.eau_aval,
            "actions": ([{"type": "initial", "texte": "état initial, sol au repos"}] if k == 0
                        else actions_phase(modele.phases[k - 1], modele) if k - 1 < len(modele.phases) else []),
            "parent": ph.parent,
            "enfants": [j for j, q in enumerate(res.phases) if q.parent == k],
            "depuis": (modele.phases[k - 1].depuis if 0 < k <= len(modele.phases) else None),
            "fonds": _fonds_par_zone(modele, res, k, ph),
        }
        if ph.ok:
            y_mm = ph.y * 1e3
            i = int(np.argmax(np.abs(y_mm)))
            d.update({
                "z": _l(ph.z), "y_mm": _l(y_mm), "z_diag": _l(ph.z_diag), "M": _l(ph.M), "V": _l(ph.V),
                "pressions": {c: {k: _l(v) for k, v in ph.pressions[c].items() if k in ("z", "p", "pa", "pp", "p0")}
                              for c in ("amont", "aval")},
                **({"pp_sans_terrain": pp_sans[k]} if pp_sans[k] is not None else {}),
                "eau": {k: _l(v) for k, v in ph.eau.items()},
                "hydro": ph.hydro,
                "iterations": int(ph.iterations),
                "appuis": [],
                "synthese": {
                    "y_max_mm": float(y_mm[i]), "z_y_max": float(ph.z[i]),
                    "y_tete_mm": float(y_mm[-1]),
                    "M_max": float(ph.M.max()), "M_min": float(ph.M.min()),
                    "V_absmax": float(np.abs(ph.V).max()),
                    "butee_mobilisee": _butee_mobilisee(ph),
                    "Bm_kN_m": _butee_valeurs(ph)[0], "Bt_kN_m": _butee_valeurs(ph)[1],
                    "bilan": _bilan_forces(ph),
                },
            })
            for a in ph.appuis:
                da = modele.appuis[a["nom"]]
                esp = da.infos.get("espacement", 1.0)
                ang = da.infos.get("angle", 0.0)
                d["appuis"].append({**a, "effort_kN_m": a["effort"],
                                    "effort_axial_kN": effort_axial(a["effort"], esp, ang),
                                    **_complement_appui(da, a["effort"], catalogue, normes)})
        phases.append(d)

    ok = [p for p in res.phases if p.ok and p.nom != "État initial"] or [p for p in res.phases if p.ok]
    env, dim = {}, {}
    if ok:
        Y = np.array([p.y for p in ok]) * 1e3
        Mx = np.array([p.M for p in ok])
        Vx = np.array([p.V for p in ok])
        env = {"z": _l(res.z), "y_min_mm": _l(Y.min(0)), "y_max_mm": _l(Y.max(0)),
               "z_diag": _l(ok[0].z_diag), "M_min": _l(Mx.min(0)), "M_max": _l(Mx.max(0)),
               "V_min": _l(Vx.min(0)), "V_max": _l(Vx.max(0))}

        def _arg(vals, f):
            k = int(f(vals))
            return k

        iy = _arg([np.abs(p.y).max() for p in ok], np.argmax)
        ip = _arg([p.M.max() for p in ok], np.argmax)
        im = _arg([p.M.min() for p in ok], np.argmin)
        iv = _arg([np.abs(p.V).max() for p in ok], np.argmax)
        dim = {
            "deplacement": {"valeur_mm": float(np.abs(ok[iy].y).max() * 1e3), "phase": ok[iy].nom},
            "moment_positif": {"valeur": float(ok[ip].M.max()), "phase": ok[ip].nom},
            "moment_negatif": {"valeur": float(ok[im].M.min()), "phase": ok[im].nom},
            "tranchant": {"valeur": float(np.abs(ok[iv].V).max()), "phase": ok[iv].nom},
            "appuis": {},
        }
        for p in ok:
            for a in p.appuis:
                cur = dim["appuis"].get(a["nom"])
                if cur is None or a["effort"] > cur["effort_kN_m"]:
                    da = modele.appuis[a["nom"]]
                    dim["appuis"][a["nom"]] = {
                        "effort_kN_m": a["effort"], "phase": p.nom,
                        "effort_axial_kN": effort_axial(a["effort"], da.infos.get("espacement", 1.0),
                                                        da.infos.get("angle", 0.0)),
                    }
    return {
        "projet": projet,
        "complet": res.complet,
        "avertissements": res.avertissements,
        "conventions": CONVENTIONS,
        "paroi": {"tete": modele.ecran.tete, "pied": modele.ecran.pied, **modele.ecran.infos},
        "couches": _couches(modele),
        "hydraulique": modele.hydraulique,
        "appuis": [{"nom": a.nom, "cote": a.cote, "type": a.type, "angle": a.infos.get("angle", 0.0),
                    "element": a.infos.get("element"), "espacement": a.infos.get("espacement", 1.0),
                    "precharge": a.infos.get("precharge", 0.0), "lierne": a.infos.get("lierne"),
                    "longueur": a.infos.get("longueur"), "raideur": a.raideur, "unilateral": a.unilateral}
                   for a in modele.appuis.values()],
        "phases": phases,
        "enveloppes": env,
        "dimensionnant": dim,
    }
