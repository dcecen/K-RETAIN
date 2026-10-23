import { describe, expect, it } from 'vitest'
import { nomProjet } from '../format'

describe('nom du projet affiché dans la barre de titre', () => {
  it("n'affiche jamais [object Object]", () => {
    expect(nomProjet('Fouille exemple')).toBe('Fouille exemple')
    expect(nomProjet(12)).toBe('12')
    expect(nomProjet({ nom: 'Projet A', lieu: 'Lyon' })).toBe('Projet A')
    expect(nomProjet({ lieu: 'Lyon' })).toBe('')
    expect(nomProjet(['a'])).toBe('')
    expect(nomProjet(undefined)).toBe('')
    expect(nomProjet(null)).toBe('')
  })
})
