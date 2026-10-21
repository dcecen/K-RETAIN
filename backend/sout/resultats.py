"""Mise en forme des résultats pour l'interface : phases, enveloppes et phase
dimensionnante. Conventions rappelées dans `conventions`."""
from __future__ import annotations

import math

import numpy as np

from .appuis.raideurs import effort_axial
from .noyau.modele import Modele
from .noyau.phasage import ResultatCalcul

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
    for sc in ph_modele.ajouter_surcharges:
        a.append({"type": "surcharge", "texte": f"ajout de la surcharge {sc.nom}"})
    for nom in ph_modele.retirer_surcharges:
        a.append({"type": "surcharge", "texte": f"retrait de la surcharge {nom}"})
    return a


def _butee_mobilisee(ph) -> float | None:
    """Bm/Bt : butée mobilisée rapportée à la butée limite, côté fouille (valeur caractéristique)."""
    av = ph.pressions.get("aval")
    if not av or len(av["z"]) == 0:
        return None
    Bt = float(np.sum(av["L"] * av["pp"]))
    return float(np.sum(av["L"] * av["p"])) / Bt if Bt > 0 else None


def serialiser(res: ResultatCalcul, modele: Modele, projet: str = "") -> dict:
    phases = []
    for k, ph in enumerate(res.phases):
        d = {
            "nom": ph.nom, "ok": ph.ok, "message": ph.message,
            "terrain_amont": ph.terrain_amont, "terrain_aval": ph.terrain_aval,
            "eau_amont": ph.eau_amont, "eau_aval": ph.eau_aval,
            "actions": ([{"type": "initial", "texte": "état initial, sol au repos"}] if k == 0
                        else actions_phase(modele.phases[k - 1], modele) if k - 1 < len(modele.phases) else []),
        }
        if ph.ok:
            y_mm = ph.y * 1e3
            i = int(np.argmax(np.abs(y_mm)))
            d.update({
                "z": _l(ph.z), "y_mm": _l(y_mm), "z_diag": _l(ph.z_diag), "M": _l(ph.M), "V": _l(ph.V),
                "pressions": {c: {k: _l(v) for k, v in ph.pressions[c].items() if k in ("z", "p", "pa", "pp", "p0")}
                              for c in ("amont", "aval")},
                "eau": {k: _l(v) for k, v in ph.eau.items()},
                "hydro": ph.hydro,
                "appuis": [],
                "synthese": {
                    "y_max_mm": float(y_mm[i]), "z_y_max": float(ph.z[i]),
                    "y_tete_mm": float(y_mm[-1]),
                    "M_max": float(ph.M.max()), "M_min": float(ph.M.min()),
                    "V_absmax": float(np.abs(ph.V).max()),
                    "butee_mobilisee": _butee_mobilisee(ph),
                },
            })
            for a in ph.appuis:
                da = modele.appuis[a["nom"]]
                esp = da.infos.get("espacement", 1.0)
                ang = da.infos.get("angle", 0.0)
                d["appuis"].append({**a, "effort_kN_m": a["effort"],
                                    "effort_axial_kN": effort_axial(a["effort"], esp, ang)})
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
        "couches": [{"nom": c.nom, "toit": c.toit} for c in sorted(modele.couches, key=lambda c: -c.toit)],
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
