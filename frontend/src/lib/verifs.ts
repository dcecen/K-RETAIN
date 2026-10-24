// Lecture des vérifications renvoyées par le serveur pour l'affichage : aucun seuil numérique n'est fixé ici,
// l'état (ok / attention / non_ok) vient du calcul (sout.verifs, seuil d'affichage documenté côté serveur).
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

