import { describe, expect, it } from 'vitest'
import { nomProjet, titreScript } from '../format'

describe('titre lisible d’un script (menu Fichier)', () => {
  it('lit projet: texte, bloc avec nom, forme en accolades, et retombe sur le nom de fichier', () => {
    expect(titreScript('# commentaire\nprojet: Fouille exemple\nsol: []\n', 'f')).toBe('Fouille exemple')
    expect(titreScript('projet: "Quai nord"\n', 'f')).toBe('Quai nord')
    expect(titreScript('projet:\n  nom: Berlinoise A\n  affaire: 12\nsol: []\n', 'f')).toBe('Berlinoise A')
    expect(titreScript('projet: { nom: Fouille B, client: X }\n', 'f')).toBe('Fouille B')
    expect(titreScript('projet:\n  affaire: 12\n', 'fichier')).toBe('fichier')
    expect(titreScript('sol: []\n', 'fichier')).toBe('fichier')
  })
})

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
