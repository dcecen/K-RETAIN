import { describe, expect, it } from 'vitest'
import { CLES_APPUIS as APPUIS, CLES_EAU as EAU, CLES_ECRAN as ECRAN, CLES_PHASES as PHASES, CLES_PROJET as PROJET, CLES_SOLS as SOLS, CLES_SURCHARGES as SURCHARGES, CLES_VERIFS as VERIFS } from '../cles'

/** Clés du script éditables par les formulaires avant la refonte (figées) : aucune ne doit disparaître. */
const AVANT = [
  'projet', 'calcul.coefficients', 'calcul.kh', 'calcul.mode', 'calcul.pas', 'calcul.gamma_w', 'calcul.largeur_fouille', 'calcul.jeu_eau',
  'criteres.deplacement_max_mm', 'criteres.deplacement_tete_mm',
  'sol.nom', 'sol.toit', 'sol.gamma', 'sol.gamma_dejauge', 'sol.c', 'sol.phi', 'sol.delta_a_sur_phi', 'sol.delta_p_sur_phi', 'sol.EM', 'sol.alpha', 'sol.pl', 'sol.kh', 'sol.k_h', 'sol.k_v', 'sol.cu',
  'paroi.type', 'paroi.tete', 'paroi.pied', 'paroi.EI', 'paroi.profil', 'paroi.acier', 'paroi.classe_section', 'paroi.beta_D', 'paroi.perte_epaisseur', 'paroi.beton', 'paroi.epaisseur',
  'paroi.diametre', 'paroi.entraxe', 'paroi.profil_armature', 'paroi.primaires_armes', 'paroi.rapport_EI_fissure', 'paroi.enrobage', 'paroi.armatures_fouille', 'paroi.armatures_terre',
  'paroi.armatures_pieu', 'paroi.largeur_reaction_fiche', 'paroi.blindage.epaisseur', 'paroi.blindage.materiau', 'paroi.blindage.resistance',
  'eau.amont', 'eau.aval', 'hydraulique.regime', 'hydraulique.substratum', 'hydraulique.largeur_amont', 'hydraulique.largeur_fouille', 'hydraulique.pas', 'hydraulique.sol_lane',
  'hydraulique.bouchon.type', 'hydraulique.bouchon.toit', 'hydraulique.bouchon.base', 'hydraulique.bouchon.k', 'hydraulique.bouchon.gamma', 'hydraulique.bouchon.phase', 'hydraulique.bouchon.lest',
  'terrain.amont', 'terrain.aval',
  'surcharges.nom', 'surcharges.type', 'surcharges.q', 'surcharges.distance', 'surcharges.largeur', 'surcharges.cote_ecran',
  'appuis.type', 'appuis.cote', 'appuis.element', 'appuis.acier', 'appuis.beton', 'appuis.E', 'appuis.A', 'appuis.longueur', 'appuis.espacement', 'appuis.angle', 'appuis.precharge',
  'appuis.pied_bracon', 'appuis.longueur_libre', 'appuis.longueur_scellee', 'appuis.diametre_forage', 'appuis.qs', 'appuis.nombre', 'appuis.epaisseur', 'appuis.raideur', 'appuis.symetrique', 'appuis.lierne',
  'phases.nom', 'phases.depuis', 'phases.excaver', 'phases.poser', 'phases.deposer', 'phases.eau.aval', 'phases.eau.amont', 'phases.remblayer.aval', 'phases.remblayer.amont', 'phases.retirer_surcharges',
  'verifications',
]

describe('clés du script couvertes par les formulaires', () => {
  const toutes = new Set([...PROJET, ...SOLS, ...ECRAN, ...EAU, ...SURCHARGES, ...APPUIS, ...PHASES, ...VERIFS])

  it('conserve toutes les clés éditables avant la refonte', () => {
    const manquantes = AVANT.filter((k) => !toutes.has(k))
    expect(manquantes).toEqual([])
  })

  it('ajoute les clés qui n’avaient pas de formulaire', () => {
    for (const k of ['paroi.armatures_horizontales', 'paroi.longueur_panneau', 'surcharges.position', 'surcharges.emprise', 'surcharges.phases', 'appuis.unilateral', 'appuis.longueur_elastique', 'sol.qc', 'sol.K0']) {
      expect(toutes.has(k), k).toBe(true)
    }
  })
})
