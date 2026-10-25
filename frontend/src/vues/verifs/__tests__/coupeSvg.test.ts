import { describe, expect, it } from 'vitest'
import { cadre, HAUTEUR, LARGEUR, schemaSvg, TYPES_SCHEMA, valeurFiche } from '../coupeSvg'

const SEP = ' '   // séparateur de milliers français (espace fine insécable)

const BUTEE = { type: 'butee', phase: 'Terrassement final', fond: -6.5, pied: -14, tete: 0, terrain_amont: 0, nappe_amont: -2, nappe_aval: -7, z: [-14, -12, -10, -8, -6.5], p: [300, 250, 150, 60, 0], pp: [900, 700, 450, 200, 0] }
const KRANZ = { type: 'kranz', phase: 'P3', tete: 0, pied: -12, terrain_amont: 0, fond: -6, nappe_amont: null, cote_tirant: -1.5, angle: 0, B: [0, -7.2], A: [-11, -1.5],
  longueur_libre: 8, longueur_scellee: 6, forces: { W: 1800, P1: 215, T: 150, T_max: 640, R: 1500, Fh: 300, Fv: 0 } }
const FOND = { type: 'fond_de_fouille', phase: 'P2', nappe_amont: 0, nappe_aval: -5, fond: -5, pied: -14, terrain_amont: 0, L_amont: 14, L_aval: 9, dh: 5, dh_aval: 1.957 }
const CERCLE = { type: 'cercle', phase: 'P1', xc: 0, zc: 9.8, R: 29.9, z_amont: 0, z_aval: -4, largeur: 30, tete: 0, pied: -10, nappe_amont: null, nappe_aval: null, F: 1.91, cercle_calcul: [0.5, 9.0, 28.0] }
const PROFIL = { type: 'profil', phase: 'P3', quoi: 'maximal', z: [-12, -8, -4, 0], y_mm: [0, 6, 12, 17.6], limite_mm: 30, tete: 0, pied: -12 }
const FORCES = { type: 'forces_verticales', phase: 'P3', montants: 120, descendants: 340, W: 60 }
const BARRE = { type: 'barre', L: 16, angle: 0, N_Ed: 1200, N_cr: 4838, N_b_Rd: 3683, lambda: 1.195, chi: 0.533, ref: 'tube 508x12.5' }
const BETON = { type: 'section_beton', h: 0.6, d: 0.53, As: 20, As_requis: 12.3, M_Ed: 300, M_Rd: 442, face: 'face fouille', phase: 'P3' }
const ACIER = { type: 'section_acier', profil: 'AZ 26-700', M_Ed: 141, M_Rd: 925, V_Ed: 89, V_Rd: 1200, W: 2600, fy: 355, phase: 'P3' }
const POUTRE = { type: 'poutre_continue', e: 4, q: 57, My: 155, V: 193, profil: 'HEB 400', pseudo3d: false }

describe('schémas SVG des fiches de vérification', () => {
  it('chaque type connu rend un SVG autonome avec ses grandeurs', () => {
    const cas: Record<string, [Record<string, unknown>, string[]]> = {
      butee: [BUTEE, ['Bm', 'Bt', 'fond']], kranz: [KRANZ, ['W = 1', 'T = 150', 'P1 = 215']],
      fond_de_fouille: [FOND, ['L_amont = 14', 'L_aval = 9', 'Δh = 5']], cercle: [CERCLE, ['<ellipse', 'R = 29,9', 'F = 1,91']],
      profil: [PROFIL, ['<polyline', 'admissible 30 mm']], forces_verticales: [FORCES, ['340', '120', 'montants / descendants']],
      barre: [BARRE, ['L = 16,00 m', 'χ = 0,533', `N_b,Rd = 3${SEP}683`]], section_beton: [BETON, ['d = 0,530 m', 'M_Rd = 442', 'As requis 12,3']],
      section_acier: [ACIER, ['AZ 26-700', 'M_c,Rd = 925', `Vpl,Rd = 1${SEP}200`]], poutre_continue: [POUTRE, ['q = 57,0', 'q·e²/8', 'HEB 400']],
    }
    expect(Object.keys(cas).sort()).toEqual([...TYPES_SCHEMA].sort())
    for (const [type, [schema, attendus]] of Object.entries(cas)) {
      const svg = schemaSvg(schema)
      expect(svg, type).not.toBeNull()
      expect(svg!.startsWith('<svg xmlns="http://www.w3.org/2000/svg"')).toBe(true)
      expect(svg).toContain(`viewBox="0 0 ${LARGEUR} ${HAUTEUR}"`)
      for (const a of attendus) expect(svg, `${type} : ${a}`).toContain(a)
      expect(svg!.includes('NaN')).toBe(false)
    }
  })

  it('refuse les types inconnus et les schémas vides', () => {
    expect(schemaSvg(null)).toBeNull()
    expect(schemaSvg(undefined)).toBeNull()
    expect(schemaSvg({ type: 'inconnu' })).toBeNull()
    expect(schemaSvg({ type: 'butee' })).toBeNull()          // données absentes : pas d'exception, pas de SVG
  })

  it('le repère de la coupe met l’écran en x = 0 et z croissant vers le haut', () => {
    const k = cadre(-10, 10, -14, 2)
    expect(k.x(0)).toBeGreaterThan(k.x(-10))
    expect(k.x(10)).toBeGreaterThan(k.x(0))
    expect(k.z(2)).toBeLessThan(k.z(-14))                   // z haut = pixels petits
    expect(k.x(10) - k.x(-10)).toBeCloseTo(LARGEUR - 60, 6)
    expect(k.H).toBe(16)
  })

  it('les nappes et la fiche de fond de fouille se dessinent avec des cotes en virgule', () => {
    const svg = schemaSvg(FOND)!
    expect(svg).toContain('nappe 0,00')
    expect(svg).toContain('nappe -5,00')
    expect(svg).toContain('pied -14,00 m')
  })

  it('les valeurs des fiches s’affichent avec des décimales adaptées', () => {
    expect(valeurFiche(1470.2)).toBe(`1${SEP}470`)
    expect(valeurFiche(12.345)).toBe('12,3')
    expect(valeurFiche(1.2345)).toBe('1,23')
    expect(valeurFiche(0.2174)).toBe('0,217')
    expect(valeurFiche('Terrassement')).toBe('Terrassement')
    expect(valeurFiche(null)).toBe('—')
  })
})
