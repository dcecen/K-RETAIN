// Lecture des vérifications renvoyées par le serveur pour l'affichage : l'état (ok / attention / non_ok) vient
// du calcul (sout.verifs). Le seul seuil côté interface, SEUIL_ATTENTION (fin de fichier), reprend celui du serveur
// et ne sert qu'aux textes, aux points d'attention et aux couleurs de la maquette.
import type { Resultats, Verif } from './api'
import { pourcent } from './format'

/** Résumé court d'un résultat pour les alertes : « taux 85 % », « taux 120 %, non vérifié », « non vérifié » quand
 *  aucun taux n'existe (rupture du calcul, instabilité) ou « non vérifiable » (valeur de norme manquante) ; jamais
 *  « non vérifiable » et « non vérifié » ensemble. */
export function resumeEtat(taux: number | null, etat: Verif['etat']): string {
  if (taux !== null) return `taux ${pourcent(taux)}${etat === 'non_ok' ? ', non vérifié' : ''}`
  return etat === 'non_ok' ? 'non vérifié' : 'non vérifiable'
}

const GRAVITE: Record<Verif['etat'], number> = { non_ok: 3, attention: 2, ok: 1, non_verifiable: 0 }

/** État le plus grave parmi des vérifications. */
export function pire(etats: Verif['etat'][]): Verif['etat'] | null {
  let p: Verif['etat'] | null = null
  for (const e of etats) if (p === null || GRAVITE[e] > GRAVITE[p]) p = e
  return p
}

/** État des vérifications hydrauliques (boulance, renard, soulèvement, gradient) rattachées à une phase. */
export function etatHydraulique(res: Resultats, nomPhase: string): Verif['etat'] | null {
  const vs = (res.verifications ?? []).filter((v) => /boulance|renard|soul[èe]vement|gradient/i.test(v.nom)
    && (v.phase === null || v.phase === undefined || v.phase.startsWith(nomPhase)))
  return pire(vs.map((v) => v.etat))
}

/** Couleur CSS d'un état (undefined : couleur par défaut). */
export function couleurEtat(etat: Verif['etat'] | null): string | undefined {
  if (etat === 'non_ok') return 'var(--rouge)'
  if (etat === 'attention') return 'var(--orange)'
  return undefined
}

/** Extraction « valeur de calcul / valeur limite » depuis le détail, quand il les contient. */
export function valeurs(v: Verif): [string, string] {
  const d = v.detail
  const m = d.match(/([A-Za-zÀ-ÿ_,.' ]*?= ?[-\d.,]+ ?[^;,(]*?)\s+pour\s+([^;,(]+)/) ?? d.match(/([^;]*?= ?[-\d.,]+ ?[kKMPa·Nm/°%]*)[^;]*?;\s*([^;]*?Rd[^;]*)/)
  if (m) return [m[1].trim(), m[2].trim()]
  const premier = d.split(';')[0].trim()
  return [premier, '']
}

/** Référence courte : la source de la méthode (dernier segment, après les sources des coefficients lus) ;
 *  le texte complet reste au survol. */
export function sourceCourte(s: string): string {
  const segments = s.split(/\s*;\s*/).map((x) => x.trim()).filter(Boolean)
  const methode = segments.find((x) => !/de mémoire|docs\/normes\/\w+\.yaml/i.test(x)) ?? segments[segments.length - 1] ?? s
  return methode.replace(/\s*—\s*de mémoire, à confirmer/i, '').replace(/\s*\(coefficients\s*:.*\)$/i, '').trim()
}

/** Libellé des statuts (ok et attention s'affichent « Vérifié » ; l'attention reste listée dans les points d'attention). */
export const LIBELLE_ETAT: Record<Verif['etat'], string> = { ok: 'Vérifié', attention: 'Vérifié', non_ok: 'Non vérifié', non_verifiable: 'Non vérifiable' }

/** Familles de vérifications (sous-onglets), dans l'ordre d'affichage ; `famille` est donnée par le serveur. */
export const FAMILLES: { cle: string; libelle: string }[] = [
  { cle: 'butee', libelle: 'Butée' }, { cle: 'equilibre_vertical', libelle: 'Équilibre vertical' },
  { cle: 'massif_ancrage', libelle: "Massif d'ancrage" }, { cle: 'fond_de_fouille', libelle: 'Fond de fouille' },
  { cle: 'hydraulique', libelle: 'Hydraulique' }, { cle: 'stabilite_generale', libelle: 'Stabilité générale' },
  { cle: 'deplacements', libelle: 'Déplacements (ELS)' }, { cle: 'ecran', libelle: 'Écran' }, { cle: 'anneau', libelle: 'Anneau' },
  { cle: 'appuis', libelle: 'Appuis' }, { cle: 'liernes', libelle: 'Liernes' }, { cle: 'assemblages', libelle: 'Assemblages' },
  { cle: 'calcul', libelle: 'Calcul' }, { cle: 'geotechnique', libelle: 'Géotechnique' }, { cle: 'structure', libelle: 'Structure' },
]

export function libelleFamille(cle: string): string {
  return FAMILLES.find((f) => f.cle === cle)?.libelle ?? cle
}

/** Familles présentes dans une liste de vérifications, dans l'ordre des sous-onglets. */
export function famillesPresentes(vs: Verif[]): string[] {
  const presentes = new Set(vs.map((v) => v.famille || 'structure'))
  const ordre = FAMILLES.map((f) => f.cle).filter((c) => presentes.has(c))
  for (const p of presentes) if (!ordre.includes(p)) ordre.push(p)
  return ordre
}

/** Seuil d'attention (taux de travail à partir duquel une vérification est signalée) : même valeur que
 *  `sout/verifs.py: SEUIL_ATTENTION`. Les états (ok, attention, non_ok) sont fixés par le serveur ; cette
 *  constante ne sert qu'aux textes, aux points d'attention et aux couleurs de la maquette. */
export const SEUIL_ATTENTION = 0.9
export const TEXTE_SEUIL_ATTENTION = `${Math.round(SEUIL_ATTENTION * 100)} %`
