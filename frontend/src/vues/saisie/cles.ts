// Constantes des formulaires de saisie (clés du script couvertes, colonnes, champs par type) : sans composant,
// pour que chaque fichier de composant n'exporte que des composants (rechargement à chaud) et pour les tests.

// --- Projet
/** Clés du bloc `projet:` reprises dans le cartouche de la note de calcul. */
export const CARTOUCHE: [string, string][] = [
  ['affaire', 'Affaire'], ['client', 'Client'], ['lieu', 'Lieu'], ['indice', 'Indice'], ['redacteur', 'Rédacteur'], ['verificateur', 'Vérificateur'],
  ['date', 'Date (vide : date du jour)'], ['systeme_cotes', 'Système de cotes (vide : NGF)'],
]

// --- Projet
export const CLES_CALCUL = ['coefficients', 'kh', 'mode', 'pas', 'gamma_w', 'largeur_fouille', 'jeu_eau']

// --- Projet
export const CLES_PROJET = ['projet', 'projet.nom', ...CARTOUCHE.map(([k]) => `projet.${k}`), ...CLES_CALCUL.map((k) => `calcul.${k}`)]

// --- Sols
/** Colonnes saisies : clé du script, en-tête, unité (COTE = unité des cotes du projet). */
export const COLS_BASE: [string, string, string][] = [
  ['nom', 'Nom', ''], ['toit', 'Cote du toit', 'COTE'], ['gamma', 'γ', 'kN/m³'], ['gamma_dejauge', "γ'", 'kN/m³'], ['c', "c'", 'kPa'], ['phi', "φ'", '°'],
  ['EM', 'EM', 'kPa'], ['alpha', 'α', '-'],
]

// --- Sols
export const COLS_AVANCEES: [string, string, string][] = [
  ['delta_a_sur_phi', "δa/φ'", '-'], ['delta_p_sur_phi', "δp/φ'", '-'], ['pl', 'pl', 'kPa'], ['qc', 'qc', 'kPa'], ['kh', 'kh imposé', 'kN/m³'], ['K0', 'K0', '-'],
  ['k_h', 'k_h', 'm/s'], ['k_v', 'k_v', 'm/s'], ['cu', 'cu', 'kPa'],
]

// --- Sols
export const CLES_SOLS = [...COLS_BASE, ...COLS_AVANCEES].map(([k]) => `sol.${k}`).concat(['terrain.amont', 'terrain.aval'])

// --- Ecran
/** Clés avancées (hors géométrie et section de base), par famille de type. */
export const CLES_AVANCEES_ECRAN = ['EI', 'rapport_EI_fissure', 'enrobage', 'armatures_fouille', 'armatures_terre', 'armatures_pieu', 'classe_section', 'beta_D', 'perte_epaisseur',
  'armatures_horizontales', 'enrobage_horizontal', 'longueur_panneau', 'origine_panneaux']

// --- Ecran
export const CLES_ECRAN = ['paroi.type', 'paroi.tete', 'paroi.pied', 'paroi.etancheite', 'paroi.k_paroi', 'paroi.epaisseur_hydraulique',
  'paroi.forme', 'paroi.rayon', 'paroi.epaisseur_anneau', 'paroi.tolerance_verticalite',
  'paroi.profil', 'paroi.acier', 'paroi.beton', 'paroi.epaisseur', 'paroi.diametre', 'paroi.entraxe', 'paroi.profil_armature',
  'paroi.primaires_armes', 'paroi.largeur_reaction_fiche', 'paroi.blindage.epaisseur', 'paroi.blindage.materiau', 'paroi.blindage.resistance', ...CLES_AVANCEES_ECRAN.map((k) => `paroi.${k}`)]

// --- Geometrie
/** Colonnes des objets de terrain (clé, en-tête, unité ; COTE = unité des cotes). */
export const COLS_OBJET: [string, string, string][] = [
  ['nom', 'Nom', ''], ['type', 'Type', ''], ['de', 'De', 'm'], ['a', 'À', 'm'], ['phases', 'Phases [1re ; dernière]', ''],
  ['cote_crete', 'Crête', 'COTE'], ['largeur_crete', 'Largeur crête', 'm'], ['pente', 'Pente h/v', '-'], ['cote_pied', 'Pied', 'COTE'],
  ['methode', 'Méthode', ''], ['cote_equivalente', 'Cote équivalente', 'COTE'],
]

// --- Geometrie
export const LIBELLES_METHODE_OBJET: Record<string, string> = { surcharge_equivalente: 'surcharge équivalente', fond_equivalent: 'fond équivalent', coin_de_rupture: 'coin de rupture (à fournir)' }

// --- Geometrie
export const CLES_GEOMETRIE = [
  'geometrie.ouvrages.contour', 'geometrie.ouvrages.ferme', 'geometrie.ouvrages.cotes', 'geometrie.ouvrages.appuis.appui', 'geometrie.ouvrages.appuis.de', 'geometrie.ouvrages.appuis.a',
  'geometrie.terrain.cote', 'geometrie.terrain.zones.nom', 'geometrie.terrain.zones.cotes', 'geometrie.terrain.zones.de', 'geometrie.terrain.zones.a', 'geometrie.terrain.zones.cote',
  'geometrie.terrain.zones.pente_beta', 'geometrie.terrain.zones.methode_pente',
  'geometrie.fouille.cote_initiale', 'geometrie.fouille.zones.nom', 'geometrie.fouille.zones.cotes', 'geometrie.fouille.zones.de', 'geometrie.fouille.zones.a', 'geometrie.fouille.zones.largeur',
  ...COLS_OBJET.map(([k]) => `geometrie.fouille.objets.${k}`), 'geometrie.fouille.objets.cotes', 'geometrie.fouille.objets.marches',
  'geometrie.surcharges.surcharge', 'geometrie.surcharges.cotes', 'geometrie.surcharges.de', 'geometrie.surcharges.a', 'geometrie.surcharges.position', 'geometrie.surcharges.emprise',
]

// --- Eau
export const CLES_HYDRAULIQUE = ['regime', 'substratum', 'largeur_amont', 'largeur_fouille', 'pas', 'sol_lane']

// --- Eau
export const CLES_BOUCHON = ['type', 'toit', 'base', 'k', 'gamma', 'phase', 'lest']

// --- Eau
export const CLES_EAU = ['eau.amont', 'eau.aval', ...CLES_HYDRAULIQUE.map((k) => `hydraulique.${k}`), ...CLES_BOUCHON.map((k) => `hydraulique.bouchon.${k}`)]

// --- Surcharges
export const CLES_SURCHARGES = ['surcharges.nom', 'surcharges.type', 'surcharges.q', 'surcharges.distance', 'surcharges.largeur', 'surcharges.cote_ecran', 'surcharges.position', 'surcharges.emprise', 'surcharges.profondeur', 'surcharges.phase', 'surcharges.phases']

// --- Appuis
/** Champs essentiels par type (clé du script, libellé). */
export const CHAMPS_APPUI: Record<string, [string, string][]> = {
  buton: [['longueur', 'Longueur (m)'], ['espacement', 'Espacement (m)'], ['angle', 'Angle (°)'], ['precharge', 'Précharge (kN)']],
  bracon: [['longueur', 'Longueur (m)'], ['espacement', 'Espacement (m)'], ['angle', 'Angle (°)'], ['pied_bracon', 'Cote de l’appui en pied (m)'], ['precharge', 'Précharge (kN)']],
  tirant: [['longueur_libre', 'Longueur libre (m)'], ['longueur_scellee', 'Longueur scellée (m)'], ['angle', 'Inclinaison (°)'], ['espacement', 'Espacement (m)'],
    ['precharge', 'Précontrainte (kN)'], ['diametre_forage', 'Diamètre de forage (m)'], ['qs', 'qs du scellement (kPa)'], ['nombre', 'Nombre de torons / barres']],
  dalle: [['epaisseur', 'Épaisseur (m)'], ['longueur', 'Portée (m)']],
}

// --- Appuis
export const CLES_AVANCEES_APPUI = ['E', 'A', 'raideur', 'symetrique', 'lierne', 'unilateral', 'longueur_elastique']

// --- Appuis
export const CLES_APPUIS = ['appuis.type', 'appuis.cote', 'appuis.element', 'appuis.acier', 'appuis.beton', ...new Set(Object.values(CHAMPS_APPUI).flat().map(([k]) => `appuis.${k}`)), ...CLES_AVANCEES_APPUI.map((k) => `appuis.${k}`)]

// --- Phases
export const CLES_PHASES = ['phases.nom', 'phases.depuis', 'phases.excaver', 'phases.poser', 'phases.deposer', 'phases.eau.aval', 'phases.eau.amont', 'phases.remblayer.aval', 'phases.remblayer.amont', 'phases.retirer_surcharges']

// --- Verifs
export const VERIFS: [string, string, string][] = [
  ['butee', 'Mobilisation de la butée', 'Bm/Bt sur la fiche, coefficients de la NF P 94-282'],
  ['equilibre_vertical', 'Équilibre vertical', 'Mobilisation de δp et portance en pied'],
  ['kranz', 'Massif d’ancrage (Kranz)', 'Stabilité du massif ancré par les tirants'],
  ['fond_de_fouille', 'Fond de fouille', 'Soulèvement, boulance, renard'],
  ['stabilite_generale', 'Stabilité générale (Bishop)', 'Cercles de glissement sous le pied'],
  ['deplacements', 'Déplacements aux ELS', 'Comparés aux critères ci-dessous'],
  ['structure', 'Structure (EC3, EC2)', 'Écran, butons, tirants, liernes, dalles, assemblages'],
]

// --- Verifs
export const CLES_VERIFS = ['verifications', 'criteres.deplacement_max_mm', 'criteres.deplacement_tete_mm']
