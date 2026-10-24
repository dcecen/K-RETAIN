import { describe, expect, it } from 'vitest'
import { noteCalcul } from '../note'
import { jeu } from '../../vue3d/__tests__/outils'

const NORMES = {
  nf_p94_282: [
    { cle: 'approche_de_calcul', valeur: 'Approche 2 (test)', source: 'source test' },
    { cle: 'combinaisons.ELU_fondamental.gamma_effets', valeur: 1.35, source: 'source test' },
    { cle: 'butee.gamma_R_e', valeur: 1.4, source: 'source test' },
  ],
}
const MODELE = {
  projet: { nom: 'Berlinoise avec tirants (exemple)', affaire: 'A-2026-017', indice: 'B', redacteur: 'D. C.', verificateur: 'V. V.', date: '25/10/2026', systeme_cotes: 'IGN69' },
  sol: [{ nom: 'Limon', gamma: 19, gamma_dejauge: 9, phi: 27, c: 5, EM: 6000, alpha: 0.5 }],
  eau: { service: { amont: null, aval: null } },
  surcharges: [{ nom: 'chantier', type: 'repartie', q: 10 }],
  calcul: { coefficients: 'coulomb', kh: 'schmitt' },
}

describe('note de calcul', () => {
  const html = noteCalcul(jeu('berlinoise'), { modele: MODELE, normes: NORMES, version: 'v0.1.0' })

  it('suit le plan en huit parties avec un cartouche', () => {
    for (const titre of ['1. Objet', '2. Documents de référence', '3. Hypothèses', '4. Caractéristiques géotechniques', '5. Phasage', '6. Résultats par phase', '7. Vérifications aux ELU et aux ELS', '8. Conclusion']) {
      expect(html).toContain(`<h2>${titre}</h2>`)
    }
    for (const champ of ['A-2026-017', '<td class="">B</td>', '25/10/2026', 'D. C.', 'V. V.', 'RetainWall v0.1.0']) expect(html).toContain(champ)
  })

  it('utilise la virgule décimale, les unités par mètre linéaire et le système de cotes du projet', () => {
    expect(html).toContain('kN.m/ml')
    expect(html).toContain('kN/ml')
    expect(html).toContain('m IGN69')
    expect(html).toMatch(/\d,\d/)
    expect(html).not.toMatch(/<td class="n">\d+\.\d+/)
  })

  it('reprend le référentiel, les coefficients partiels et les statuts sans pastille', () => {
    expect(html).toContain('Approche 2 (test)')
    expect(html).toContain('combinaisons.ELU_fondamental.gamma_effets')
    expect(html).toContain('Non vérifié')
    expect(html).not.toContain('Limite')
    expect(html).not.toContain('Prévu')
    expect(html).not.toMatch(/[✅❌⚠✓]/)
  })

  it('reste lisible sans référentiel (serveur injoignable)', () => {
    const sans = noteCalcul(jeu('berlinoise'), { modele: null, normes: null, version: '' })
    expect(sans).toContain('non renseignée dans docs/normes')
    expect(sans).toContain('m NGF')
  })
})
