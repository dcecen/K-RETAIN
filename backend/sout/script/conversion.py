"""Script validé -> modèle de calcul (sout.noyau.modele.Modele)."""
from __future__ import annotations

import math

from ..appuis.construction import ErreurAppui, construire_appui
from ..noyau.modele import Modele, Phase
from ..parois import ErreurParoi, construire_ecran
from ..sol.couches import Couche
from ..sol.surcharges import Surcharge
from ..sol.terrain import ErreurTerrain, ObjetTerrain, SurchargePlan, bandes_equivalentes, profil_gradins, profil_risberme
from .schema import Script


class ErreurConversion(Exception):
    pass


def _surcharge(s, nom_defaut: str):
    """Surcharge du moteur : forme historique (répartie, bande, linéique au droit de la coupe) quand aucun
    champ de plan n'est utilisé, sinon surcharge étendue rapportée à la coupe (sol.terrain)."""
    etendue = (s.type in ("uniforme", "rectangulaire", "ponctuelle", "lineaire", "convoi") or s.cote_paroi is not None
               or s.emprise is not None or s.position is not None or s.trace is not None or s.profondeur)
    if not etendue:
        return Surcharge(nom=s.nom or nom_defaut, type=s.type, q=s.q, distance=s.distance,
                         largeur=s.largeur or 0.0, cote=s.cote, cote_ecran=s.cote_ecran)
    cp = s.cote_paroi
    cotes = None if cp is None or cp == "toutes" else tuple(f"#{c}" if isinstance(c, int) else str(c) for c in ([cp] if isinstance(cp, (str, int)) else cp))
    emprise = None
    if isinstance(s.emprise, dict):
        emprise = (float(s.emprise.get("de", 0.0)), float(s.emprise.get("a", 0.0)))
    elif isinstance(s.emprise, list) and len(s.emprise) == 2:
        emprise = (float(s.emprise[0]), float(s.emprise[1]))
    return SurchargePlan(nom=s.nom or nom_defaut, type=s.type, q=s.q, distance=s.distance, largeur=s.largeur, emprise=emprise,
                         position=tuple(s.position) if s.position else None,
                         trace=((s.trace.de[0], s.trace.de[1]), (s.trace.a[0], s.trace.a[1])) if s.trace else None,
                         profondeur=s.profondeur, cote=s.cote, cote_ecran=s.cote_ecran, cotes_paroi=cotes, modele=s.modele,
                         infos={"niveaux": s.niveaux})


def _indice_phase(ref, noms: list[str]) -> int:
    """Numéro de phase (1 = première) depuis un numéro ou un nom."""
    if isinstance(ref, str):
        return noms.index(ref) + 1
    return int(ref)


def _liste(v) -> list[str]:
    return [v] if isinstance(v, str) else list(v or [])


def _hydraulique(s: Script) -> dict | None:
    """Bloc hydraulique du modèle ; la phase d'activation d'un bouchon donnée par son nom est
    convertie en indice (1 = première phase) : le bouchon est actif à partir de cette phase."""
    if s.hydraulique is None:
        return None
    h = s.hydraulique.model_dump()
    b = h.get("bouchon")
    if b and isinstance(b.get("phase"), str):
        noms = [p.nom for p in s.phases]
        if b["phase"] not in noms:
            raise ErreurConversion(f"bouchon : phase « {b['phase']} » inconnue")
        b["phase"] = noms.index(b["phase"]) + 1
    return h


def vers_modele(s: Script, catalogue=None, normes=None, jeu: str | None = None) -> Modele:
    """Modèle de calcul ; `jeu` choisit le jeu de niveaux d'eau (défaut : calcul.jeu_eau ou le premier)."""
    try:
        ecran = construire_ecran(s.paroi, catalogue, normes)
        appuis = {nom: construire_appui(nom, a, catalogue) for nom, a in s.appuis.items()}
    except (ErreurParoi, ErreurAppui, KeyError) as e:
        raise ErreurConversion(str(e).strip("'\"")) from None

    couches = [Couche(**c.model_dump()) for c in s.sol]
    noms_phases_tmp = [p.nom for p in s.phases]
    remblai_phase = None
    if s.terrain.remblai is not None:
        # remblai côté terre : couche ajoutée (propriétés d'une couche existante) et remontée du terrain à la phase
        src = next((c for c in s.sol if c.nom == s.terrain.remblai.materiau), s.sol[0])
        couches.insert(0, Couche(**{**src.model_dump(), "nom": f"Remblai ({src.nom})", "toit": s.terrain.remblai.cote}))
        remblai_phase = _indice_phase(s.terrain.remblai.phase, noms_phases_tmp)
    jeu = jeu or s.calcul.jeu_eau or (next(iter(s.eau)) if s.eau else None)
    eau0 = s.eau[jeu] if jeu else None

    # surcharges initiales ; celles qui portent une phase d'application sont ajoutées (et retirées) dans les phases
    noms_phases = [p.nom for p in s.phases]
    surcharges = []
    ajouts_par_phase: dict[int, list] = {}
    retraits_par_phase: dict[int, list[str]] = {}
    n_s = 0
    for i, sc in enumerate(s.surcharges):
        n_s += 1
        obj = _surcharge(sc, f"S{i + 1}")
        debut = fin = None
        if sc.phases:
            debut, fin = _indice_phase(sc.phases[0], noms_phases), _indice_phase(sc.phases[1], noms_phases)
        elif sc.phase is not None:
            debut = _indice_phase(sc.phase, noms_phases)
        if isinstance(obj, SurchargePlan):
            obj = SurchargePlan(**{**obj.__dict__, "phase_debut": debut, "phase_fin": fin})
        if debut is None:
            surcharges.append(obj)
        else:
            ajouts_par_phase.setdefault(debut, []).append(obj)
        if fin is not None and fin + 1 <= len(s.phases):
            retraits_par_phase.setdefault(fin + 1, []).append(obj.nom)
    # objets de terrain (risbermes, talus, gradins côté fouille ; profil côté terre) -> bandes équivalentes phasées
    objets: list[ObjetTerrain] = []
    terrassements: dict[str, int] = {}
    for k_ph, ph in enumerate(s.phases, start=1):
        tr = ph.terrasser_risberme
        for nom in ([tr] if isinstance(tr, str) else tr or []):
            terrassements[nom] = k_ph
    sol_trie = sorted(couches, key=lambda c: -c.toit)

    def _gamma_a(z: float) -> float:
        for c in sol_trie:
            if z <= c.toit + 1e-9:
                return c.gamma
        return sol_trie[-1].gamma

    def _cotes(cp):
        return None if cp is None or cp == "toutes" else tuple(f"#{c}" if isinstance(c, int) else str(c) for c in ([cp] if isinstance(cp, (str, int)) else cp))

    def _fond_a_la_phase(k: int) -> float:
        fond = s.terrain.aval if s.terrain.aval is not None else (s.terrain.amont if s.terrain.amont is not None else s.sol[0].toit)
        for p in s.phases[:k]:
            if p.excaver is not None:
                fond = p.excaver
            if p.remblayer and p.remblayer.aval is not None:
                fond = p.remblayer.aval
        return fond

    try:
        for famille, liste in (("risberme", s.fouille.risbermes), ("talus", s.fouille.talus), ("gradins", s.fouille.gradins)):
            for i, o in enumerate(liste):
                nom = o.nom or f"{famille.capitalize()}{i + 1}"
                debut, fin = _indice_phase(o.phases[0], noms_phases_tmp), _indice_phase(o.phases[1], noms_phases_tmp)
                if nom in terrassements:
                    fin = min(fin, terrassements[nom] - 1)
                if famille == "gradins":
                    pied = o.cote_pied if o.cote_pied is not None else _fond_a_la_phase(debut)
                    profil = profil_gradins([tuple(m) for m in o.marches], pied)
                    crete = max(m[0] for m in o.marches)
                else:
                    largeur = o.largeur_banquette if (famille == "talus" and o.largeur_banquette is not None) else o.largeur_crete
                    profil = profil_risberme(o.cote_crete, largeur, o.pente, o.cote_pied)
                    pied, crete = o.cote_pied, o.cote_crete
                if _fond_a_la_phase(debut) > pied + 1e-6:
                    raise ErreurConversion(f"{famille} « {nom} » : le fond de fouille à la phase {debut} ({_fond_a_la_phase(debut)} m) "
                                           f"est au-dessus du pied {pied} m (excavez d'abord au fond général)")
                objets.append(ObjetTerrain(nom=nom, type=famille, face="aval", profil=profil, base=pied, gamma=_gamma_a(0.5 * (pied + crete)),
                                           methode=o.methode, phase_debut=debut, phase_fin=fin, cotes_paroi=_cotes(o.cote_paroi),
                                           cote_equivalente=getattr(o, "cote_equivalente", None)))
        t = s.terrain
        z_amont = t.amont if t.amont is not None else s.sol[0].toit
        if t.profil is not None and t.methode_pente == "surcharge_equivalente":
            pts = tuple((float(d), float(z)) for d, z in t.profil)
            if any(z > z_amont + 1e-6 for _, z in pts):
                objets.append(ObjetTerrain(nom="Terrain en pente", type="pente", face="amont", profil=pts, base=z_amont,
                                           gamma=_gamma_a(z_amont), methode="surcharge_equivalente", cotes_paroi=_cotes(t.cote_paroi)))
    except ErreurTerrain as e:
        raise ErreurConversion(str(e)) from None
    beta = None
    if t.pente_beta is not None or (t.profil is not None and t.methode_pente == "coulomb_beta"):
        if t.pente_beta is not None:
            beta = t.pente_beta
        else:
            (d0, z0), (d1, z1) = t.profil[0], t.profil[-1]
            beta = math.degrees(math.atan2(z1 - z0, d1 - d0))
    cc = s.coupe_calcul
    from ..plan.geometrie import cote_concerne
    for o in objets:
        # objet rattaché à certains côtés : ignoré par les coupes des autres côtés
        if not cote_concerne(o.cotes_paroi, cc):
            continue
        if o.methode == "coin_de_rupture":
            raise ErreurConversion(f"{o.type} « {o.nom} » : méthode du coin de rupture non disponible — TODO-NORME : "
                                   "publication à fournir dans docs/normes (surcharges_et_terrain.risberme_coin_de_rupture)")
        if o.methode == "fond_equivalent":
            continue
        bandes = bandes_equivalentes(o)
        if o.phase_debut is None:
            surcharges += bandes
        else:
            ajouts_par_phase.setdefault(o.phase_debut, []).extend(bandes)
            if o.phase_fin is not None and o.phase_fin + 1 <= len(s.phases):
                retraits_par_phase.setdefault(o.phase_fin + 1, []).extend(b.nom for b in bandes)
    phases = []
    for k_ph, ph in enumerate(s.phases, start=1):
        ajout = list(ajouts_par_phase.get(k_ph, []))
        for sc in ph.ajouter_surcharges or []:
            n_s += 1
            ajout.append(_surcharge(sc, f"S{n_s}"))
        eau = {}
        if ph.eau is not None:
            for cle in ph.eau.model_fields_set:
                eau[cle] = getattr(ph.eau, cle)
        excaver = ph.excaver
        for o in objets:   # méthode du fond équivalent : fond relevé à la cote choisie pendant la vie de l'objet
            if o.methode == "fond_equivalent" and o.phase_debut == k_ph and o.cote_equivalente is not None:
                excaver = o.cote_equivalente
            if o.methode == "fond_equivalent" and o.phase_fin is not None and o.phase_fin + 1 == k_ph and (excaver is None or excaver > o.base):
                excaver = o.base
        remblai_amont = ph.remblayer.amont if ph.remblayer else None
        if remblai_phase == k_ph and s.terrain.remblai is not None:
            remblai_amont = s.terrain.remblai.cote
        phases.append(Phase(
            nom=ph.nom, excaver=excaver,
            remblayer_amont=remblai_amont,
            remblayer_aval=ph.remblayer.aval if ph.remblayer else None,
            poser=_liste(ph.poser), deposer=_liste(ph.deposer), eau=eau,
            ajouter_surcharges=ajout, retirer_surcharges=list(ph.retirer_surcharges or []) + retraits_par_phase.get(k_ph, []),
            depuis=ph.depuis,
        ))
    return Modele(
        ecran=ecran, couches=couches, phases=phases, appuis=appuis,
        terrain_amont=s.terrain.amont if s.terrain.amont is not None else (s.sol[0].toit if remblai_phase is not None else None),
        terrain_aval=s.terrain.aval,
        eau_amont=eau0.amont if eau0 else None, eau_aval=eau0.aval if eau0 else None,
        surcharges=surcharges, gamma_w=s.calcul.gamma_w, coefficients=s.calcul.coefficients,
        pas=s.calcul.pas,
        hydraulique=_hydraulique(s),
        coupe=s.coupe_calcul.model_dump() if s.coupe_calcul is not None else None,
        beta_amont=beta, terrain_objets=objets,
    )
