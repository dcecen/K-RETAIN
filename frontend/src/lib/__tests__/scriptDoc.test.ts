import { describe, expect, it } from 'vitest'
import { ajouter, deplacer, fixer, lire, renommerAppui, supprimer } from '../scriptDoc'

const SCRIPT = `# Exemple
projet: Fouille test
paroi:
  type: palplanche
  EI: 1.50e5   # kN·m²/m
  tete: 0.0
  pied: -12.0
sol:
  - { nom: Sable, toit: 0.0, gamma: 20, phi: 30 }
appuis:
  B1: { type: buton, cote: -1.5, espacement: 6.0, longueur: 18.0 }
phases:
  - { nom: Terrassement, excaver: -2.0 }
  - { nom: Pose, poser: B1 }
  - { nom: Dépose, deposer: [B1] }
assemblages:
  A1: { type: platine_about, appui: B1 }
plan:
  contour: [[0, 0], [20, 0], [20, 12], [0, 12]]
  appuis:
    - { appui: B1, de: [0, 6], a: [20, 6] }
`

describe('lecture du script', () => {
  it('rend le modèle et aucune erreur pour un script valide', () => {
    const r = lire(SCRIPT)
    expect(r.erreur).toBeNull()
    expect(r.modele.projet).toBe('Fouille test')
    expect(r.modele.appuis.B1.cote).toBe(-1.5)
  })
  it('signale une erreur de syntaxe sans lever', () => {
    const r = lire('paroi: [\n  type: x')
    expect(r.doc).toBeNull()
    expect(r.erreur).toBeTruthy()
  })
  it("ne plante pas sur un alias YAML non défini (écran blanc auparavant)", () => {
    const r = lire('projet: a\nsol: *inconnu\n')
    expect(r.modele).toBeNull()
    expect(r.erreur).toBeTruthy()
  })
})

describe('fixer : remplacement en place', () => {
  it('ne change que les caractères de la valeur, commentaires et alignements intacts', () => {
    const t = fixer(SCRIPT, ['paroi', 'tete'], 0.5)
    expect(t).toContain('  tete: 0.5\n')
    expect(t).toContain('  EI: 1.50e5   # kN·m²/m')
    expect(t.split('\n').length).toBe(SCRIPT.split('\n').length)
  })
  it('conserve les fins de ligne Windows', () => {
    const crlf = SCRIPT.replace(/\n/g, '\r\n')
    const t = fixer(crlf, ['paroi', 'pied'], -13)
    expect(t).toContain('pied: -13\r\n')
    expect(t.includes('\n') && !t.replace(/\r\n/g, '').includes('\n')).toBe(true)
  })
  it('une valeur vide supprime la clé ; une clé nouvelle est ajoutée', () => {
    expect(fixer(SCRIPT, ['paroi', 'pied'], '')).not.toContain('pied:')
    expect(fixer(SCRIPT, ['paroi', 'acier'], 'S355')).toContain('acier: S355')
  })
  it('écrit le nom dans un bloc projet sans écraser les autres clés', () => {
    const bloc = SCRIPT.replace('projet: Fouille test', 'projet:\n  nom: Fouille test\n  affaire: A-1')
    const t = fixer(bloc, ['projet', 'nom'], 'Chantier')
    expect(t).toContain('nom: Chantier')
    expect(t).toContain('affaire: A-1')
  })
  it('laisse le texte intact si le YAML est invalide', () => {
    const casse = 'paroi: [\n  type: x'
    expect(fixer(casse, ['paroi', 'tete'], 1)).toBe(casse)
  })
})

describe('renommerAppui', () => {
  it('met à jour les phases, les assemblages et le plan', () => {
    const t = renommerAppui(SCRIPT, 'B1', 'BUT1')
    const m = lire(t).modele
    expect(m.appuis.BUT1).toBeDefined()
    expect(m.appuis.B1).toBeUndefined()
    expect(m.phases[1].poser).toBe('BUT1')
    expect(m.phases[2].deposer).toEqual(['BUT1'])
    expect(m.assemblages.A1.appui).toBe('BUT1')
    expect(m.plan.appuis[0].appui).toBe('BUT1')
  })
  it('ne fait rien si le nouveau nom existe déjà', () => {
    const t = ajouter(SCRIPT, ['x'], 1)
    expect(renommerAppui(t, 'B1', 'B1')).toBe(t)
  })
})

describe('listes', () => {
  it('deplacer hors bornes laisse la liste intacte', () => {
    expect(lire(deplacer(SCRIPT, ['phases'], 0, 5)).modele.phases[0].nom).toBe('Terrassement')
    expect(lire(deplacer(SCRIPT, ['phases'], 7, 0)).modele.phases[0].nom).toBe('Terrassement')
    expect(lire(deplacer(SCRIPT, ['phases'], 0, 1)).modele.phases[0].nom).toBe('Pose')
  })
  it('supprimer retire un élément et garde le reste', () => {
    const m = lire(supprimer(SCRIPT, ['phases', 1])).modele
    expect(m.phases.map((p: { nom: string }) => p.nom)).toEqual(['Terrassement', 'Dépose'])
  })
})
