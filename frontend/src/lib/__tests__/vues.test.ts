import { describe, expect, it } from 'vitest'
import { avecFrise, avecInspecteur, estSaisie, ligneBloc, VUES, vueDisponible, vuesDuGroupe } from '../vues'

describe('table des vues', () => {
  // Neuf étapes depuis le 25/10/2026 (étape 4 « Géométrie », bloc geometrie, entre Écran et Eau : les côtés nommés
  // doivent exister avant les surcharges et les appuis) ; changement de spécification délibéré, pas de valeur de calcul.
  it('numérote les neuf étapes de saisie de 1 à 9, dans l’ordre du script', () => {
    const d = vuesDuGroupe('donnees')
    expect(d.map((v) => v.numero)).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9])
    expect(d.map((v) => v.bloc)).toEqual(['projet', 'sol', 'paroi', 'geometrie', 'eau', 'surcharges', 'appuis', 'phases', 'verifications'])
  })

  it('a des clés uniques et un libellé par vue', () => {
    const cles = VUES.map((v) => v.cle)
    expect(new Set(cles).size).toBe(cles.length)
    for (const v of VUES) expect(v.libelle.length).toBeGreaterThan(0)
  })

  it('n’emploie pas « Paroi » comme libellé de navigation (vocabulaire : « Écran »)', () => {
    for (const v of VUES) expect(v.libelle).not.toMatch(/^Paroi/)
  })

  it('distingue saisie, frise et inspecteur', () => {
    expect(estSaisie('sol')).toBe(true)
    expect(estSaisie('efforts')).toBe(false)
    expect(avecFrise('phases')).toBe(true)
    expect(avecFrise('diagrammes')).toBe(true)
    expect(avecFrise('script')).toBe(false)
    expect(avecInspecteur('efforts')).toBe(true)
    expect(avecInspecteur('3d')).toBe(false)
    expect(avecInspecteur('sol')).toBe(false)
  })

  it('grise les résultats avant le calcul, sauf la synthèse (premiers pas)', () => {
    expect(vueDisponible('efforts', { resultats: false, pseudo3d: false })).toBe(false)
    expect(vueDisponible('synthese', { resultats: false, pseudo3d: false })).toBe(true)
    expect(vueDisponible('pseudo3d', { resultats: true, pseudo3d: false })).toBe(false)
    expect(vueDisponible('sol', { resultats: false, pseudo3d: false })).toBe(true)
  })

  it('retrouve la ligne d’un bloc du script', () => {
    const t = 'projet: Essai\ncalcul:\n  kh: schmitt\nsol:\n  - nom: A\n'
    expect(ligneBloc(t, 'sol')).toBe(4)
    expect(ligneBloc(t, 'projet')).toBe(1)
    expect(ligneBloc(t, 'phases')).toBeNull()
  })
})
