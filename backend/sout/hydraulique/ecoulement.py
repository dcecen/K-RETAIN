"""Modèles d'eau autour de l'écran, à trois niveaux :

- `Hydrostatique` : nappes amont et aval indépendantes, u = γw·(z_nappe − z)
  (régime existant, conservé pour la non-régression) ;
- `Simplifie` : perte de charge Δh = h_amont − h_aval répartie uniformément le long
  du cheminement amont -> pied -> fouille (Bligh ; longueur pondérée de Lane pour les
  parcours horizontaux d'un bouchon) ; pressions sur l'écran en conséquence ;
- `DifferencesFinies` : écoulement 2D sur la coupe (sout.hydraulique.grille),
  couches anisotropes (k_h, k_v), écran imperméable, substratum, bouchon.

Tous fournissent : pression(cote, z), gradient_sortie_max, debit (par mètre d'écran),
charge_le_long(z, xs) et une sérialisation pour l'affichage.
Hypothèses : régime permanent, nappe amont horizontale maintenue (recharge),
fouille symétrique (flux nul à mi-largeur), substratum imperméable, écran
imperméable sur toute sa hauteur.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..sol.couches import Couche, indice_couche, trier
from .bouchons import Bouchon
from .grille import Grille, isolignes, resoudre_grille


class ErreurHydraulique(Exception):
    pass


@dataclass
class ResultatEcoulement:
    """Résultat commun des modèles d'eau pour une phase."""
    regime: str
    h_amont: float | None
    h_aval: float | None
    z_fond: float
    z_pied: float
    gamma_w: float
    # champ 2D (différences finies) ; None sinon
    xc: np.ndarray | None = None
    zc: np.ndarray | None = None
    h: np.ndarray | None = None
    # profils de pression sur l'écran : fonctions z -> u (kPa)
    _u_amont: object = None
    _u_aval: object = None
    gradient_sortie_max: float = 0.0
    gradient_sortie_moyen: float = 0.0
    gradient_sortie_x: np.ndarray = field(default_factory=lambda: np.zeros(0))
    gradient_sortie: np.ndarray = field(default_factory=lambda: np.zeros(0))
    debit: float = 0.0            # m³/s par mètre d'écran, entrant dans la fouille
    charge_base_prisme: float = 0.0   # excès de charge moyen à la base du prisme de Terzaghi (m)
    bouchon: Bouchon | None = None
    charge_base_bouchon: float | None = None   # m, charge moyenne sous le bouchon
    gradient_bouchon: float | None = None      # -, gradient hydraulique à travers le bouchon
    avertissements: list[str] = field(default_factory=list)
    etancheite: str = "etanche"                # état d'étanchéité de l'écran pris en compte (parois.etancheite)
    debit_paroi: float = 0.0                   # m³/s par mètre d'écran traversant l'écran (compté dans `debit`)
    aval_ferme: bool = True                    # enceinte fermée : flux nul au vis-à-vis (fouille symétrique)

    def pression(self, cote: str, z: np.ndarray) -> np.ndarray:
        f = self._u_amont if cote == "amont" else self._u_aval
        return np.maximum(f(np.asarray(z, float)), 0.0)

    def charge_le_long(self, z: float, xs: np.ndarray) -> np.ndarray:
        if self.h is None:
            raise ErreurHydraulique("pas de champ de charges (régime sans écoulement 2D)")
        # interpolation linéaire en x sur la ligne de cellules la plus proche de z
        j = int(np.argmin(np.abs(self.zc - z)))
        ligne = self.h[:, j]
        ok = ~np.isnan(ligne)
        return np.interp(np.asarray(xs, float), self.xc[ok], ligne[ok])

    def serialiser(self, n_max: int = 160) -> dict:
        d = {"regime": self.regime, "h_amont": self.h_amont, "h_aval": self.h_aval,
             "gradient_sortie_max": float(self.gradient_sortie_max), "gradient_sortie_moyen": float(self.gradient_sortie_moyen),
             "debit_m3_s_m": float(self.debit), "debit_m3_h_m": float(self.debit * 3600),
             "charge_base_prisme": float(self.charge_base_prisme),
             "gradient_sortie_x": self.gradient_sortie_x.round(3).tolist(), "gradient_sortie": self.gradient_sortie.round(4).tolist(),
             "bouchon": None if self.bouchon is None else {"type": self.bouchon.type, "toit": self.bouchon.toit, "base": self.bouchon.base,
                                                           "k": self.bouchon.k, "epaisseur": self.bouchon.epaisseur},
             "charge_base_bouchon": self.charge_base_bouchon, "gradient_bouchon": self.gradient_bouchon,
             "avertissements": self.avertissements, "etancheite": self.etancheite,
             "debit_paroi_m3_h_m": float(self.debit_paroi * 3600), "aval_ferme": self.aval_ferme}
        if self.h is not None:
            pas_x = max(1, int(np.ceil(len(self.xc) / n_max)))
            pas_z = max(1, int(np.ceil(len(self.zc) / n_max)))
            hs = self.h[::pas_x, ::pas_z]
            d["x"] = self.xc[::pas_x].round(3).tolist()
            d["z"] = self.zc[::pas_z].round(3).tolist()
            d["h"] = [[None if np.isnan(v) else round(float(v), 3) for v in ligne] for ligne in hs]
            lo, hi = np.nanmin(self.h), np.nanmax(self.h)
            if hi - lo > 1e-6:
                niveaux = np.linspace(lo, hi, 13)[1:-1].round(3).tolist()
                d["equipotentielles"] = isolignes(self.xc, self.zc, self.h, niveaux)
            # charge à la cote du fond (surface piézométrique sous la fouille) et à mi-fiche
            for nom, zz in (("charge_fond", self.z_fond - 1e-6), ("charge_mi_fiche", 0.5 * (self.z_fond + self.z_pied))):
                j = int(np.argmin(np.abs(self.zc - zz)))
                d[nom] = {"x": self.xc.round(3).tolist(), "h": [None if np.isnan(v) else round(float(v), 3) for v in self.h[:, j]]}
        return d


# ---------------------------------------------------------------------------
def _hydro(gw: float, zn: float | None):
    if zn is None:
        return lambda z: np.zeros_like(np.asarray(z, float))
    return lambda z: gw * (zn - np.asarray(z, float))


class Hydrostatique:
    def __init__(self, z_fond: float, z_pied: float, h_amont: float | None, h_aval: float | None, gamma_w: float):
        self.args = (z_fond, z_pied, h_amont, h_aval, gamma_w)

    def resoudre(self) -> ResultatEcoulement:
        z_fond, z_pied, ha, hv, gw = self.args
        return ResultatEcoulement("hydrostatique", ha, hv, z_fond, z_pied, gw, _u_amont=_hydro(gw, ha), _u_aval=_hydro(gw, hv))


class Simplifie:
    """Perte de charge uniforme le long du cheminement (Bligh), pondérée selon Lane si bouchon."""

    def __init__(self, z_terrain_amont: float, z_fond: float, z_pied: float, h_amont: float | None, h_aval: float | None,
                 gamma_w: float, bouchon: Bouchon | None = None, largeur_fouille: float | None = None):
        self.z_t, self.z_fond, self.z_pied, self.ha, self.hv, self.gw = z_terrain_amont, z_fond, z_pied, h_amont, h_aval, gamma_w
        self.bouchon, self.largeur_fouille = bouchon, largeur_fouille

    def resoudre(self) -> ResultatEcoulement:
        z_fond, z_pied, ha, hv, gw = self.z_fond, self.z_pied, self.ha, self.hv, self.gw
        r = ResultatEcoulement("simplifie", ha, hv, z_fond, z_pied, gw, bouchon=self.bouchon)
        hv_eff = hv if hv is not None else z_fond
        if ha is None or ha - max(hv_eff, z_pied) <= 0 or z_fond <= z_pied:
            r._u_amont, r._u_aval = _hydro(gw, ha), _hydro(gw, hv)
            return r
        dh = ha - hv_eff
        haut = min(ha, self.z_t)
        L_am = haut - z_pied
        # côté fouille : sous un bouchon, le parcours horizontal sous le bouchon (jusqu'à mi-largeur) compte 1/3 (Lane)
        b = self.bouchon
        if b is not None and b.k is None and self.largeur_fouille:
            L_av = (z_fond - z_pied) + (self.largeur_fouille / 2) / 3.0
        else:
            L_av = z_fond - z_pied
        L_tot = L_am + L_av
        i = dh / L_tot

        def u_amont(z):
            z = np.asarray(z, float)
            h = ha - i * np.clip(haut - z, 0.0, None)          # charge décroît en descendant
            return gw * (h - z)

        def u_aval(z):
            z = np.asarray(z, float)
            h = hv_eff + i * np.clip(z_fond - z, 0.0, None)   # charge croît en descendant vers le pied
            return gw * (h - z)

        r._u_amont, r._u_aval = u_amont, u_aval
        r.gradient_sortie_max = r.gradient_sortie_moyen = i
        r.charge_base_prisme = i * (z_fond - z_pied)   # excès de charge au pied
        r.gradient_sortie_x = np.array([0.0])
        r.gradient_sortie = np.array([i])
        if b is not None:
            r.charge_base_bouchon = hv_eff + i * (z_fond - b.base)
            r.gradient_bouchon = i
        r.avertissements.append("Régime simplifié (perte de charge uniforme) : gradient de sortie et débit non calculés "
                                "par un réseau d'écoulement ; préférez le régime differences_finies.")
        return r


class DifferencesFinies:
    def __init__(self, couches: list[Couche], z_terrain_amont: float, z_fond: float, z_pied: float, z_tete: float,
                 h_amont: float | None, h_aval: float | None, largeur_amont: float, largeur_aval: float,
                 z_substratum: float, pas: float, gamma_w: float, bouchon: Bouchon | None = None,
                 nappe_aval_sol: float | None = None, etancheite: str = "etanche", resistance_paroi: float | None = None,
                 aval_ferme: bool = True):
        """etancheite : etanche (faces de l'écran coupées), non_etanche (écran transparent, face de suintement vers la
        fouille au-dessus du fond) ou partielle (résistance R = e_p/k_p en série, loi de Darcy) ; aval_ferme : enceinte
        fermée (flux nul au vis-à-vis, fouille symétrique), sinon paroi ouverte (charge côté fouille imposée au loin)."""
        self.couches = trier(couches)
        for c in self.couches:
            if c.k_h is None:
                raise ErreurHydraulique(f"couche « {c.nom} » : perméabilité k_h (m/s) nécessaire au calcul d'écoulement")
        if etancheite not in ("etanche", "non_etanche", "partielle"):
            raise ErreurHydraulique(f"étanchéité de l'écran inconnue : {etancheite}")
        if etancheite == "partielle" and not (resistance_paroi and resistance_paroi > 0):
            raise ErreurHydraulique("étanchéité partielle : résistance hydraulique de l'écran e_p/k_p inconnue (paroi.k_paroi, paroi.epaisseur_hydraulique)")
        self.z_t, self.z_fond, self.z_pied, self.z_tete = z_terrain_amont, z_fond, z_pied, z_tete
        self.ha, self.hv, self.gw = h_amont, h_aval, gamma_w
        self.La, self.Lv, self.z_sub, self.pas, self.bouchon = largeur_amont, largeur_aval, z_substratum, pas, bouchon
        self.etancheite, self.resistance_paroi, self.aval_ferme = etancheite, resistance_paroi, aval_ferme

    def resoudre(self) -> ResultatEcoulement:
        ha, hv, gw = self.ha, self.hv, self.gw
        z_fond, z_pied = self.z_fond, self.z_pied
        r = ResultatEcoulement("differences_finies", ha, hv, z_fond, z_pied, gw, bouchon=self.bouchon)
        hv_eff = hv if hv is not None else z_fond
        if ha is None:
            r._u_amont, r._u_aval = _hydro(gw, ha), _hydro(gw, hv)
            return r
        z_haut = max(ha, z_fond, hv_eff)
        if z_haut - self.z_sub < 2 * self.pas:
            raise ErreurHydraulique("domaine d'écoulement trop mince : abaissez le substratum")
        # grille : x = 0 est une face ; pas uniforme
        nxa = max(2, int(round(self.La / self.pas)))
        nxv = max(2, int(round(self.Lv / self.pas)))
        x = np.concatenate([np.linspace(-self.La, 0.0, nxa + 1), np.linspace(0.0, self.Lv, nxv + 1)[1:]])
        nz = max(4, int(round((z_haut - self.z_sub) / self.pas)))
        z = np.linspace(self.z_sub, z_haut, nz + 1)
        g = Grille(x, z)
        nx, nz = g.forme
        kx = np.zeros((nx, nz)); kz = np.zeros((nx, nz))
        for j, zc in enumerate(g.zc):
            c = self.couches[indice_couche(self.couches, zc)]
            kx[:, j] = c.k_h
            kz[:, j] = c.k_v if c.k_v is not None else c.k_h
        amont = g.xc < 0
        actif = np.ones((nx, nz), bool)
        fixe = np.full((nx, nz), np.nan)
        face_sup = np.full(nx, np.nan)
        # amont : sol actif sous la nappe et sous le terrain ; charge de la nappe imposée sur la face supérieure
        for i in np.where(amont)[0]:
            actif[i] = g.zc < min(ha, self.z_t)
            face_sup[i] = ha
        # aval : actif sous le fond ; charge imposée au fond (eau dans la fouille ou fond drainé/pompé)
        for i in np.where(~amont)[0]:
            actif[i] = g.zc < z_fond
            face_sup[i] = hv_eff
        # bouchon : perméabilité réduite (ou imperméable : cellules inactives, charge imposée sous le bouchon = face sup de la cellule dessous)
        b = self.bouchon
        if b is not None and b.toit > b.base and b.type == "substratum":
            pass  # bouchon naturel : la couche porte déjà sa perméabilité ; seules les vérifications changent
        elif b is not None and b.toit > b.base:
            dans = (~amont)[:, None] & (g.zc[None, :] <= b.toit) & (g.zc[None, :] > b.base)
            if b.k is None:
                actif &= ~dans
                for i in np.where(~amont)[0]:
                    face_sup[i] = np.nan  # face supérieure de la dernière cellule active : flux nul (bouchon étanche)
            else:
                kx[dans] = b.k; kz[dans] = b.k
        # paroi ouverte (pas de vis-à-vis) : charge côté fouille imposée sur la colonne la plus lointaine, plus de symétrie
        if not self.aval_ferme:
            fixe[nx - 1, actif[nx - 1]] = hv_eff
        # écran en x = 0 entre pied et tête : étanche (faces coupées), partiellement étanche (résistance e_p/k_p en série
        # avec le sol, loi de Darcy) ou non étanche (faces ordinaires). Écran perméable au-dessus du fond : l'eau suinte
        # vers la fouille, charge imposée sur la face = max(z, eau dans la fouille), soit u = 0 à l'air libre.
        iface = int(np.argmin(np.abs(g.x)))
        zone = (g.zc >= z_pied) & (g.zc <= self.z_tete)
        etanches = np.zeros((nx + 1, nz), bool)
        resistance = charge_face = None
        if self.etancheite == "etanche":
            etanches[iface, zone] = True
        else:
            if self.etancheite == "partielle":
                resistance = np.zeros((nx + 1, nz))
                resistance[iface, zone] = self.resistance_paroi
            charge_face = np.full((nx + 1, nz), np.nan)
            suinte = zone & (g.zc > z_fond) & actif[iface - 1] & ~actif[iface]
            charge_face[iface, suinte] = np.maximum(g.zc[suinte], hv_eff)
        h = resoudre_grille(g, kx, kz, fixe, actif, etanches, face_sup, resistance_x=resistance, charge_face_x=charge_face)
        r.xc, r.zc, r.h = g.xc, g.zc, h
        r.etancheite, r.aval_ferme = self.etancheite, self.aval_ferme

        # pressions sur l'écran : colonnes adjacentes de part et d'autre (interpolation en z). Écran perméable : charge
        # ramenée à la face de l'écran (chute de charge dans la demi-cellule et à travers l'écran, flux v = Δh / ΣR) et
        # débit traversant l'écran, compté dans le débit de pompage.
        ia, iv = iface - 1, iface
        h_face = {ia: h[ia].copy(), iv: h[iv].copy()}
        if self.etancheite != "etanche":
            R = self.resistance_paroi if self.etancheite == "partielle" else 0.0
            q_paroi = 0.0
            for j in np.where(zone)[0]:
                ra, rv = 0.5 * g.dx[ia] / kx[ia, j], 0.5 * g.dx[iv] / kx[iv, j]
                if actif[ia, j] and actif[iv, j]:
                    v = (h[ia, j] - h[iv, j]) / (ra + R + rv)
                    h_face[ia][j] = h[ia, j] - v * ra
                    h_face[iv][j] = h[iv, j] + v * rv
                    q_paroi += v * g.dz[j]
                elif actif[ia, j] and charge_face is not None and not np.isnan(charge_face[iface, j]):
                    v = (h[ia, j] - charge_face[iface, j]) / (ra + R)
                    h_face[ia][j] = charge_face[iface, j]
                    q_paroi += max(v, 0.0) * g.dz[j]
            r.debit_paroi = float(q_paroi)

        def profil(i, z_nappe):
            zz, hh = g.zc[actif[i]], h_face[i][actif[i]]
            def u(zq):
                zq = np.asarray(zq, float)
                hq = np.interp(zq, zz, hh, left=hh[0] if len(hh) else 0.0, right=np.nan)
                # au-dessus de la dernière cellule active : charge de la face (nappe / fond)
                hq = np.where(np.isnan(hq), z_nappe if z_nappe is not None else zq, hq)
                return gw * (hq - zq)
            return u
        r._u_amont = profil(ia, ha)
        r._u_aval = profil(iv, hv_eff if hv is not None else None)
        if hv is None:
            # fouille drainée au fond : au-dessus du fond, pas d'eau
            base_aval = r._u_aval
            r._u_aval = lambda zq: np.where(np.asarray(zq, float) < z_fond, base_aval(zq), 0.0)

        # gradient de sortie au fond de fouille (cellules aval dont la face sup est le fond) ;
        # avec un bouchon perméable : gradient dans le sol sous le bouchon et gradient à travers le bouchon
        js = [np.where(actif[i])[0] for i in range(nx)]
        xs, grads, flux, grads_b = [], [], 0.0, []
        j_base = None
        if b is not None and (b.k is not None or b.type == "substratum") and b.toit > b.base:
            j_base = int(np.argmin(np.abs(g.zc - (b.base - 0.5 * self.pas))))   # première cellule de sol sous le bouchon
        for i in np.where(~amont)[0]:
            if len(js[i]) == 0 or np.isnan(face_sup[i]):
                continue
            j = js[i][-1]
            i_s = (h[i, j] - face_sup[i]) / (0.5 * g.dz[j])
            flux += kz[i, j] * max(i_s, 0.0) * g.dx[i]
            if j_base is not None and j_base >= 1:
                j_toit = int(np.argmin(np.abs(g.zc - (min(b.toit, z_fond) - 0.5 * self.pas))))
                h_toit = face_sup[i] if b.type != "substratum" or j_toit >= j else h[i, j_toit]
                grads_b.append(max((h[i, j_base] - h_toit) / max(min(b.toit, z_fond) - b.base, 1e-9), 0.0))
                if b.type != "substratum":
                    i_s = (h[i, j_base - 1] - h[i, j_base]) / g.dz[j_base]
            xs.append(g.xc[i]); grads.append(max(i_s, 0.0))
        r.gradient_bouchon = float(np.max(grads_b)) if grads_b else None
        r.gradient_sortie_x = np.array(xs)
        r.gradient_sortie = np.array(grads)
        r.gradient_sortie_max = float(np.max(grads)) if grads else 0.0
        r.gradient_sortie_moyen = float(np.mean(grads)) if grads else 0.0
        r.debit = float(flux) + r.debit_paroi
        # excès de charge moyen à la base du prisme de Terzaghi (largeur D/2, profondeur D sous le fond)
        D = z_fond - z_pied
        if D > 0:
            j = int(np.argmin(np.abs(g.zc - z_pied)))
            sel = (~amont) & (g.xc <= D / 2)
            vals = h[sel, j]
            vals = vals[~np.isnan(vals)]
            r.charge_base_prisme = float(np.mean(vals) - hv_eff) if len(vals) else 0.0
        if b is not None:
            j = int(np.argmin(np.abs(g.zc - (b.base - 0.5 * self.pas))))
            vals = h[~amont, j]
            vals = vals[~np.isnan(vals)]
            r.charge_base_bouchon = float(np.mean(vals)) if len(vals) else None
        return r


def construire(modele, etat: dict, indice_phase: int, nom_phase: str):
    """Modèle d'eau pour l'état de chantier d'une phase, selon modele.hydraulique."""
    cfg = modele.hydraulique or {}
    regime = cfg.get("regime", "hydrostatique")
    z_fond, z_pied = etat["terrain"][+1], modele.ecran.pied
    ha, hv = etat["eau"][-1], etat["eau"][+1]
    b = cfg.get("bouchon")
    bouchon = None
    if b is not None:
        bb = b if isinstance(b, Bouchon) else Bouchon(**b)
        if bb.actif(indice_phase, nom_phase):
            bouchon = bb
    # étanchéité de l'écran (parois.etancheite) : « partielle » n'a de sens qu'avec un réseau d'écoulement ;
    # « non_etanche » hors écoulement 2D est traité par le moteur (nappe côté terre ramenée au niveau côté fouille)
    infos = getattr(modele.ecran, "infos", None) or {}
    etancheite = infos.get("etancheite", "etanche")
    if etancheite == "partielle" and regime != "differences_finies":
        raise ErreurHydraulique("étanchéité partielle de l'écran : seul le régime differences_finies calcule le passage de l'eau "
                                "à travers l'écran (hydraulique.regime)")
    if regime == "hydrostatique":
        return Hydrostatique(z_fond, z_pied, ha, hv, modele.gamma_w).resoudre()
    H = modele.ecran.tete - z_pied
    if regime == "simplifie":
        return Simplifie(etat["terrain"][-1], z_fond, z_pied, ha, hv, modele.gamma_w, bouchon, cfg.get("largeur_fouille")).resoudre()
    if regime == "differences_finies":
        aval_ferme = bool(cfg.get("aval_ferme", True))
        return DifferencesFinies(
            modele.couches, etat["terrain"][-1], z_fond, z_pied, modele.ecran.tete, ha, hv,
            largeur_amont=cfg.get("largeur_amont") or 4 * H,
            largeur_aval=(cfg.get("largeur_fouille") or 2 * H) / 2 if aval_ferme else (cfg.get("largeur_amont") or 4 * H),
            z_substratum=cfg.get("substratum") if cfg.get("substratum") is not None else z_pied - 2 * H,
            pas=cfg.get("pas") or 0.5, gamma_w=modele.gamma_w, bouchon=bouchon,
            etancheite=etancheite, resistance_paroi=infos.get("resistance_hydraulique"), aval_ferme=aval_ferme).resoudre()
    raise ErreurHydraulique(f"régime hydraulique inconnu : {regime}")
