// Table des vues de l'application (navigation unique en trois groupes) : fonctions pures, testées.
import type { Section, Vue } from './etat'

export type Groupe = 'donnees' | 'resultats' | 'outils'

export interface DefVue {
  cle: Vue
  groupe: Groupe
  /** Libellé court de la navigation. */
  libelle: string
  /** Sous-titre affiché dans l'en-tête de la vue. */
  sousTitre: string
  /** Numéro d'étape (vues de saisie). */
  numero?: number
  /** Bloc du script YAML correspondant (bouton « Voir dans le script »). */
  bloc?: string
}

export const VUES: DefVue[] = [
  { cle: 'projet', groupe: 'donnees', numero: 1, libelle: 'Projet', sousTitre: 'Identification, cartouche de la note, options de calcul', bloc: 'projet' },
  { cle: 'sol', groupe: 'donnees', numero: 2, libelle: 'Sols', sousTitre: 'Couches du haut vers le bas, terrain initial', bloc: 'sol' },
  { cle: 'ecran', groupe: 'donnees', numero: 3, libelle: 'Écran', sousTitre: 'Type de paroi, géométrie, matériaux et section', bloc: 'paroi' },
  { cle: 'eau', groupe: 'donnees', numero: 4, libelle: 'Eau', sousTitre: 'Jeux de niveaux de nappe amont et aval, écoulement', bloc: 'eau' },
  { cle: 'surcharges', groupe: 'donnees', numero: 5, libelle: 'Surcharges', sousTitre: 'Charges derrière l’écran et en plan', bloc: 'surcharges' },
  { cle: 'appuis', groupe: 'donnees', numero: 6, libelle: 'Appuis', sousTitre: 'Butons, tirants, bracons, dalles', bloc: 'appuis' },
  { cle: 'phases', groupe: 'donnees', numero: 7, libelle: 'Phases', sousTitre: 'Enchaînement du chantier : excavations, poses, nappes', bloc: 'phases' },
  { cle: 'verifs_demandees', groupe: 'donnees', numero: 8, libelle: 'Vérifications demandées', sousTitre: 'Vérifications à mener et critères de déplacement', bloc: 'verifications' },
  { cle: 'synthese', groupe: 'resultats', libelle: 'Synthèse', sousTitre: 'Valeurs dimensionnantes, vérifications, points d’attention' },
  { cle: 'diagrammes', groupe: 'resultats', libelle: 'Diagrammes', sousTitre: 'Coupe, déplacement, moment, tranchant et pressions de la phase active' },
  { cle: 'efforts', groupe: 'resultats', libelle: 'Efforts d’appui', sousTitre: 'Par phase et par appui' },
  { cle: 'verifications', groupe: 'resultats', libelle: 'Vérifications', sousTitre: 'Taux de travail et statut, par famille' },
  { cle: '3d', groupe: 'resultats', libelle: 'Maquette 3D', sousTitre: 'Chantier, résultats sur la paroi et les appuis, coupes' },
  { cle: 'hypotheses', groupe: 'resultats', libelle: 'Hypothèses et référentiel', sousTitre: 'Méthode, coefficients lus dans docs/normes, conventions' },
  { cle: 'pseudo3d', groupe: 'resultats', libelle: 'Pseudo-3D', sousTitre: 'Plaque sur ressorts : cartes de déplacement et de moments' },
  { cle: 'script', groupe: 'outils', libelle: 'Script YAML', sousTitre: 'Référence du modèle : chaque formulaire le met à jour, et inversement' },
  { cle: 'assemblages', groupe: 'outils', libelle: 'Assemblages', sousTitre: 'Dessin et vérification des assemblages d’appuis' },
  { cle: 'materiaux', groupe: 'outils', libelle: 'Base matériaux', sousTitre: 'Profilés, palplanches, butons, armatures, aciers, bétons' },
  { cle: 'aide', groupe: 'outils', libelle: 'Aide', sousTitre: 'Premiers pas, catalogue des exemples, raccourcis, conventions, guide du script' },
]

/** Vue affichée après un calcul lancé depuis une vue de saisie ou d'outils. */
export const VUE_APRES_CALCUL: Vue = 'synthese'

export function defVue(v: Vue): DefVue {
  return VUES.find((d) => d.cle === v) ?? VUES[0]
}

export function vuesDuGroupe(g: Groupe): DefVue[] {
  return VUES.filter((d) => d.groupe === g)
}

export function estSaisie(v: Vue): v is Section {
  return defVue(v).groupe === 'donnees'
}

/** La frise des phases accompagne les résultats et la saisie des phases. */
export function avecFrise(v: Vue): boolean {
  return defVue(v).groupe === 'resultats' || v === 'phases'
}

/** Le panneau droit (phase active) accompagne les résultats, sauf la maquette 3D qui a son propre panneau. */
export function avecInspecteur(v: Vue): boolean {
  return defVue(v).groupe === 'resultats' && v !== '3d'
}

/** Vue accessible dans l'état courant (résultats disponibles, pseudo-3D présent). */
export function vueDisponible(v: Vue, ctx: { resultats: boolean; pseudo3d: boolean }): boolean {
  const d = defVue(v)
  if (v === 'pseudo3d') return ctx.pseudo3d
  if (d.groupe === 'resultats') return ctx.resultats || v === 'synthese'
  return true
}

/** Numéro de ligne (à partir de 1) du bloc de premier niveau `cle:` du script ; null s'il n'existe pas. */
export function ligneBloc(texte: string, cle: string): number | null {
  const lignes = texte.split('\n')
  const i = lignes.findIndex((l) => l.startsWith(`${cle}:`))
  return i < 0 ? null : i + 1
}
