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


def serialiser(res: ResultatCalcul, modele: Modele, projet: str = "") -> dict:
    phases = []
    for ph in res.phases:
        d = {
            "nom": ph.nom, "ok": ph.ok, "message": ph.message,
            "terrain_amont": ph.terrain_amont, "terrain_aval": ph.terrain_aval,
            "eau_amont": ph.eau_amont, "eau_aval": ph.eau_aval,
        }
        if ph.ok:
            y_mm = ph.y * 1e3
            i = int(np.argmax(np.abs(y_mm)))
            d.update({
                "z": _l(ph.z), "y_mm": _l(y_mm), "z_diag": _l(ph.z_diag), "M": _l(ph.M), "V": _l(ph.V),
                "pressions": {c: {k: _l(v) for k, v in ph.pressions[c].items() if k in ("z", "p", "pa", "pp", "p0")}
                              for c in ("amont", "aval")},
                "eau": {k: _l(v) for k, v in ph.eau.items()},
                "appuis": [],
                "synthese": {
                    "y_max_mm": float(y_mm[i]), "z_y_max": float(ph.z[i]),
                    "y_tete_mm": float(y_mm[-1]),
                    "M_max": float(ph.M.max()), "M_min": float(ph.M.min()),
                    "V_absmax": float(np.abs(ph.V).max()),
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
        "appuis": [{"nom": a.nom, "cote": a.cote, "type": a.type, "angle": a.infos.get("angle", 0.0)}
                   for a in modele.appuis.values()],
        "phases": phases,
        "enveloppes": env,
        "dimensionnant": dim,
    }
