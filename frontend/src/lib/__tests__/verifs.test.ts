import { describe, expect, it } from 'vitest'
import { resumeEtat } from '../verifs'

describe('résumé court d’un résultat de vérification', () => {
  it('n’écrit jamais « non vérifiable » et « non vérifié » ensemble', () => {
    expect(resumeEtat(0.85, 'ok')).toBe('taux 85 %')
    expect(resumeEtat(1.2, 'non_ok')).toBe('taux 120 %, non vérifié')
    expect(resumeEtat(null, 'non_ok')).toBe('non vérifié')               // rupture du calcul : pas de taux
    expect(resumeEtat(null, 'non_verifiable')).toBe('non vérifiable')     // valeur de norme manquante
    for (const t of [resumeEtat(null, 'non_ok'), resumeEtat(null, 'non_verifiable')]) {
      expect(t.includes('non vérifiable') && t.includes('non vérifié,')).toBe(false)
    }
  })
})
