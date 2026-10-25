// Lecture des vérifications renvoyées par le serveur pour l'affichage : l'état (ok / attention / non_ok) vient
// du calcul (sout.verifs). Le seul seuil côté interface, SEUIL_ATTENTION (fin de fichier), reprend celui du serveur
// et ne sert qu'aux textes, aux points d'attention et aux couleurs de la maquette.
import type { Resultats, Verif } from './api'

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

/** Référence courte de la source (premier article cité) ; le texte complet reste au survol. */
export function sourceCourte(s: string): string {
  const premier = s.split(/\s*;\s*/)[0] ?? s
  return premier.replace(/\s*—\s*de mémoire, à confirmer/i, '').replace(/\s*\(coefficients\s*:.*\)$/i, '').trim()
}

/** Seuil d'attention (taux de travail à partir duquel une vérification est signalée) : même valeur que
 *  `sout/verifs.py: SEUIL_ATTENTION`. Les états (ok, attention, non_ok) sont fixés par le serveur ; cette
 *  constante ne sert qu'aux textes, aux points d'attention et aux couleurs de la maquette. */
export const SEUIL_ATTENTION = 0.9
export const TEXTE_SEUIL_ATTENTION = `${Math.round(SEUIL_ATTENTION * 100)} %`
