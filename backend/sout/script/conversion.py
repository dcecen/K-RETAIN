"""Script validé -> modèle de calcul (sout.noyau.modele.Modele).

La géométrie (ouvrages en plan, terrain côté terre, terrassements, positions des surcharges) est lue par
`sout.geometrie.normaliser` (bloc `geometrie`, ou forme ancienne plan / fouille / terrain convertie) puis rapportée
à la coupe de calcul par `sout.geometrie.derivation` : une coupe 2D ne reçoit que les zones, objets et positions
qui la concernent (côté et tronçon) ; en pseudo-3D fouille fermée, tout est gardé et chaque ligne verticale filtre
elle-même ses bandes (sol.terrain, bandes SurchargePlan) ; le fond par zone est alors traité par la plaque.
"""
from __future__ import annotations

import math

from ..appuis.construction import ErreurAppui, construire_appui
from ..geometrie import derivation, normaliser
from ..noyau.modele import Modele, Phase
from ..parois import ErreurParoi, construire_ecran
from ..sol.couches import Couche
from ..sol.surcharges import Surcharge
from ..sol.terrain import CoupeCalcul, ErreurTerrain, ObjetTerrain, SurchargePlan, bandes_equivalentes, profil_gradins, profil_risberme
from .schema import Script


class ErreurConversion(Exception):
    pass


def _surcharge(s, nom_defaut: str, pos=None):
    """Surcharge du moteur : forme historique (répartie, bande, linéique au droit de la coupe) quand aucun
    champ de plan n'est utilisé, sinon surcharge étendue rapportée à la coupe (sol.terrain). `pos` : position
    en plan donnée par le bloc geometrie.surcharges (prioritaire sur les clés de plan de la surcharge)."""
    etendue = (s.type in ("uniforme", "rectangulaire", "ponctuelle", "lineaire", "convoi") or s.cote_paroi is not None
               or s.emprise is not None or s.position is not None or s.trace is not None or s.profondeur or pos is not None)
    if not etendue:
        return Surcharge(nom=s.nom or nom_defaut, type=s.type, q=s.q, distance=s.distance,
                         largeur=s.largeur or 0.0, cote=s.cote, cote_ecran=s.cote_ecran)
    cotes = normaliser._cotes(s.cote_paroi)
    emprise = None
    if isinstance(s.emprise, dict):
        emprise = (float(s.emprise.get("de", 0.0)), float(s.emprise.get("a", 0.0)))
    elif isinstance(s.emprise, list) and len(s.emprise) == 2:
        emprise = (float(s.emprise[0]), float(s.emprise[1]))
    position = tuple(s.position) if s.position else None
    trace = ((s.trace.de[0], s.trace.de[1]), (s.trace.a[0], s.trace.a[1])) if s.trace else None
    if pos is not None:
        if pos.etendue.cotes is not None:
            cotes = pos.etendue.cotes
        if pos.etendue.de is not None and pos.etendue.a is not None and s.type in ("bande", "uniforme", "repartie"):
            emprise = (float(pos.etendue.de), float(pos.etendue.a))
        if pos.position is not None:
            position = pos.position
        if pos.emprise is not None:
            emprise = pos.emprise
        if pos.trace is not None:
            trace = pos.trace
    return SurchargePlan(nom=s.nom or nom_defaut, type=s.type, q=s.q, distance=s.distance, largeur=s.largeur, emprise=emprise,
                         position=position, trace=trace, profondeur=s.profondeur, cote=s.cote, cote_ecran=s.cote_ecran,
                         cotes_paroi=cotes, modele=s.modele, infos={"niveaux": s.niveaux})


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


def _objet_terrain(o, debut: int | None, fin: int | None, fond_fn, gamma_a) -> ObjetTerrain:
    """ObjetTerrain (profil construit) d'un objet de la géométrie ; `fond_fn(k)` : fond de fouille à la phase k."""
    if o.type == "gradins":
        pied = o.cote_pied if o.cote_pied is not None else fond_fn(debut)
        profil = profil_gradins([tuple(m) for m in o.marches], pied)
        crete = max(m[0] for m in o.marches)
    else:
        profil = profil_risberme(o.cote_crete, o.largeur_crete, o.pente, o.cote_pied)
        pied, crete = o.cote_pied, o.cote_crete
    return ObjetTerrain(nom=o.nom, type=o.type, face="aval", profil=profil, base=pied, gamma=gamma_a(0.5 * (pied + crete)),
                        methode=o.methode, phase_debut=debut, phase_fin=fin, cotes_paroi=o.etendue.cotes,
                        cote_equivalente=o.cote_equivalente, troncon=o.etendue.troncon)


def vers_modele(s: Script, catalogue=None, normes=None, jeu: str | None = None) -> Modele:
    """Modèle de calcul ; `jeu` choisit le jeu de niveaux d'eau (défaut : calcul.jeu_eau ou le premier)."""
    try:
        ecran = construire_ecran(s.paroi, catalogue, normes)
        appuis = {nom: construire_appui(nom, a, catalogue) for nom, a in s.appuis.items()}
    except (ErreurParoi, ErreurAppui, KeyError) as e:
        raise ErreurConversion(str(e).strip("'\"")) from None

    couches = [Couche(**c.model_dump()) for c in s.sol]
    noms_phases = [p.nom for p in s.phases]
    geo = normaliser.depuis_script(s)
    remblai_phase = None
    if geo.remblai is not None:
        # remblai côté terre : couche ajoutée (propriétés d'une couche existante) et remontée du terrain à la phase
        src = next((c for c in s.sol if c.nom == geo.remblai.get("materiau")), s.sol[0])
        couches.insert(0, Couche(**{**src.model_dump(), "nom": f"Remblai ({src.nom})", "toit": geo.remblai["cote"]}))
        remblai_phase = _indice_phase(geo.remblai["phase"], noms_phases)
    jeu = jeu or s.calcul.jeu_eau or (next(iter(s.eau)) if s.eau else None)
    eau0 = s.eau[jeu] if jeu else None

    # Pseudo-3D en fouille fermée : la plaque porte tous les côtés du contour ; les zones, objets et positions
    # restreints à un côté sont gardés et filtrés ligne par ligne. Coupe 2D : seules les données qui la concernent.
    fermee_p3d = (s.calcul.mode == "pseudo3d" and s.pseudo3d is not None and s.pseudo3d.longueur is None
                  and s.plan is not None)
    cc = CoupeCalcul.depuis_dict(s.coupe_calcul.model_dump()) if s.coupe_calcul is not None else None
    loc = derivation.locale(geo, None if fermee_p3d else cc, tous_objets=fermee_p3d)

    # surcharges initiales ; celles qui portent une phase d'application sont ajoutées (et retirées) dans les phases
    surcharges = []
    ajouts_par_phase: dict[int, list] = {}
    retraits_par_phase: dict[int, list[str]] = {}
    n_s = 0
    for i, sc in enumerate(s.surcharges):
        n_s += 1
        obj = _surcharge(sc, f"S{i + 1}", loc.positions.get(sc.nom or f"S{i + 1}"))
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

    def _fond_a_la_phase(k: int) -> float:
        fond = loc.fond_initial if loc.fond_initial is not None else (loc.terrain_amont if loc.terrain_amont is not None else s.sol[0].toit)
        for p in s.phases[:k]:
            ex = derivation.excaver_local(p.excaver, loc.zone_fond)
            if ex is not None:
                fond = ex
            if p.remblayer and p.remblayer.aval is not None:
                fond = p.remblayer.aval
        return fond

    objets: list[ObjetTerrain] = []
    tous_objets: list[ObjetTerrain] = []        # pour l'affichage (maquette), sans filtre de côté
    try:
        for o in geo.objets:
            debut, fin = _indice_phase(o.phases[0], noms_phases), _indice_phase(o.phases[1], noms_phases)
            if o.nom in terrassements:
                fin = min(fin, terrassements[o.nom] - 1)
            ot = _objet_terrain(o, debut, fin, _fond_a_la_phase, _gamma_a)
            tous_objets.append(ot)
            if o not in loc.objets:
                continue
            if _fond_a_la_phase(debut) > ot.base + 1e-6:
                raise ErreurConversion(f"{o.type} « {o.nom} » : le fond de fouille à la phase {debut} ({_fond_a_la_phase(debut)} m) "
                                       f"est au-dessus du pied {ot.base} m (excavez d'abord au fond général)")
            objets.append(ot)
        z_amont = loc.terrain_amont if loc.terrain_amont is not None else s.sol[0].toit
        zones_pente = [z for z in geo.zones_terrain if z.profil is not None and z.methode_pente == "surcharge_equivalente"
                       and (fermee_p3d or derivation.etendue_concerne(z.etendue, cc))]
        for z in zones_pente:
            base = z.cote if z.cote is not None else z_amont
            if any(zz > base + 1e-6 for _, zz in z.profil):
                nom = "Terrain en pente" if len(zones_pente) == 1 else f"Terrain en pente ({z.nom})"
                ot = ObjetTerrain(nom=nom, type="pente", face="amont", profil=z.profil, base=base, gamma=_gamma_a(base),
                                  methode="surcharge_equivalente", cotes_paroi=z.etendue.cotes, troncon=z.etendue.troncon)
                objets.append(ot)
                tous_objets.append(ot)
    except ErreurTerrain as e:
        raise ErreurConversion(str(e)) from None
    beta = None
    if fermee_p3d:
        restreintes = [z for z in geo.zones_terrain if not z.etendue.partout
                       and (z.pente_beta is not None or (z.profil is not None and z.methode_pente == "coulomb_beta"))]
        if restreintes:
            raise ErreurConversion("terrain : pente côté terre limitée à certains côtés non disponible en pseudo-3D fouille fermée "
                                   "(coefficients de poussée uniques sur le contour) : retirez la restriction ou utilisez "
                                   "methode_pente: surcharge_equivalente")
    if loc.beta is not None or (loc.profil is not None and loc.methode_pente == "coulomb_beta"):
        if loc.beta is not None:
            beta = loc.beta
        else:
            (d0, z0), (d1, z1) = loc.profil[0], loc.profil[-1]
            beta = math.degrees(math.atan2(z1 - z0, d1 - d0))
    for o in objets:
        if o.methode == "coin_de_rupture":
            raise ErreurConversion(f"{o.type} « {o.nom} » : méthode du coin de rupture non disponible — TODO-NORME : "
                                   "publication à fournir dans docs/normes (surcharges_et_terrain.risberme_coin_de_rupture)")
        if o.methode == "fond_equivalent":
            if fermee_p3d and (o.cotes_paroi is not None or o.troncon is not None):
                raise ErreurConversion(f"{o.type} « {o.nom} » : méthode du fond équivalent limitée à un côté, non disponible en "
                                       "pseudo-3D fouille fermée (fond de fouille unique sur le contour) : utilisez "
                                       "surcharge_equivalente ou décrivez une zone de fond (geometrie.fouille.zones)")
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
            ajout.append(_surcharge(sc, f"S{n_s}", loc.positions.get(sc.nom or f"S{n_s}")))
        eau = {}
        if ph.eau is not None:
            for cle in ph.eau.model_fields_set:
                eau[cle] = getattr(ph.eau, cle)
        excaver = derivation.excaver_local(ph.excaver, loc.zone_fond)
        for o in objets:   # méthode du fond équivalent : fond relevé à la cote choisie pendant la vie de l'objet
            if o.methode != "fond_equivalent":
                continue
            if o.phase_debut == k_ph and o.cote_equivalente is not None:
                excaver = o.cote_equivalente
            if o.phase_fin is not None and o.phase_fin + 1 == k_ph and (excaver is None or excaver > o.base):
                excaver = o.base
        remblai_amont = ph.remblayer.amont if ph.remblayer else None
        if remblai_phase == k_ph and geo.remblai is not None:
            remblai_amont = geo.remblai["cote"]
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
        terrain_amont=loc.terrain_amont if loc.terrain_amont is not None else (s.sol[0].toit if remblai_phase is not None else None),
        terrain_aval=loc.fond_initial,
        eau_amont=eau0.amont if eau0 else None, eau_aval=eau0.aval if eau0 else None,
        surcharges=surcharges, gamma_w=s.calcul.gamma_w, coefficients=s.calcul.coefficients,
        pas=s.calcul.pas,
        hydraulique=_hydraulique(s),
        coupe=s.coupe_calcul.model_dump() if s.coupe_calcul is not None else None,
        beta_amont=beta, terrain_objets=tous_objets, geometrie=geo,
        excaver_zones=[ph.excaver for ph in s.phases],
    )
