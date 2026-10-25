import { describe, expect, it } from 'vitest'
import { aretesContour, bandeSur, cadrage, etendueConcerne, lireCotes, lireGeometrie, tronconSur } from '../geometriePlan'

const RECT: [number, number][] = [[0, 0], [20, 0], [20, 12], [0, 12]]

describe('arêtes du contour', () => {
  it('oriente la normale intérieure vers la fouille pour un contour direct', () => {
    const a = aretesContour(RECT, true, { sud: 0, est: 1, nord: 2, ouest: 3 })
    expect(a).toHaveLength(4)
    expect(a[0].nom).toBe('sud')
    expect(a[0].L).toBe(20)
    expect(a[0].ni).toEqual([-0, 1]) // côté sud : l'intérieur est vers y > 0
    expect(a[2].ni[1]).toBe(-1)
    expect(a[3].s0).toBe(52)
  })
  it('inverse la normale pour un contour indirect', () => {
    const a = aretesContour([...RECT].reverse())
    expect(a[0].ni[1]).toBeCloseTo(-1) // arête (0,12)->(20,12) : l'intérieur est vers y < 12
    expect(a.every((x) => Number.isFinite(x.ni[0]) && Number.isFinite(x.ni[1]))).toBe(true)
  })
  it('ignore l’arête de fermeture d’une polyligne ouverte', () => {
    const a = aretesContour([[0, 0], [10, 0], [10, 5]], false)
    expect(a).toHaveLength(2)
    expect(a.map((x) => x.k)).toEqual([0, 1])
  })
})

describe('étendues', () => {
  const a = aretesContour(RECT, true, { sud: 0, nord: 2 })
  it('lit les côtés comme noms ou numéros', () => {
    expect(lireCotes(undefined)).toBeNull()
    expect(lireCotes('sud')).toEqual(['sud'])
    expect(lireCotes([1, 'nord'])).toEqual(['#1', 'nord'])
  })
  it('concerne par nom ou par numéro ; vide = tous', () => {
    expect(etendueConcerne({ cotes: null, de: null, a: null }, a[1])).toBe(true)
    expect(etendueConcerne({ cotes: ['sud'], de: null, a: null }, a[0])).toBe(true)
    expect(etendueConcerne({ cotes: ['sud'], de: null, a: null }, a[2])).toBe(false)
    expect(etendueConcerne({ cotes: ['#1'], de: null, a: null }, a[1])).toBe(true)
  })
  it('borne le tronçon à la longueur de l’arête', () => {
    expect(tronconSur({ cotes: null, de: 4, a: 26 }, a[0])).toEqual([4, 20])
    expect(tronconSur({ cotes: null, de: null, a: null }, a[1])).toEqual([0, 12])
  })
  it('construit la bande d’un objet côté fouille sur son tronçon', () => {
    const b = bandeSur(a[0], { cotes: ['sud'], de: 4, a: 16 }, 3, 1)
    expect(b).toEqual([[4, 0], [16, 0], [16, 3], [4, 3]])
    const t = bandeSur(a[0], { cotes: ['sud'], de: 4, a: 16 }, 3, -1)
    expect(t[2]).toEqual([16, -3])
  })
})

describe('lecture de la géométrie du script', () => {
  it('lit le bloc geometrie (objets avec étendue, zones, positions)', () => {
    const g = lireGeometrie({
      geometrie: {
        ouvrages: { contour: RECT, cotes: { sud: 0, est: 1 }, appuis: [{ appui: 'B1', de: [6, 0], a: [6, 12] }] },
        fouille: { zones: [{ nom: 'est', cotes: ['est'] }], objets: [{ type: 'risberme', cotes: ['sud'], de: 4, a: 16, phases: [3, 3], cote_crete: -3, largeur_crete: 2, pente: 1.5, cote_pied: -6 }] },
        terrain: { zones: [{ nom: 'nordp', cotes: [2], pente_beta: 10 }] },
        surcharges: [{ surcharge: 'grue', position: [15, -8], emprise: [6, 6] }],
      },
      surcharges: [{ nom: 'grue', type: 'rectangle', q: 50 }],
    })
    expect(g.ancienne).toBe(false)
    expect(g.contour).toHaveLength(4)
    expect(g.appuis[0].appui).toBe('B1')
    expect(g.objets[0].nom).toBe('Risberme1')
    expect(g.objets[0].etendue).toEqual({ cotes: ['sud'], de: 4, a: 16 })
    expect(g.objets[0].largeur).toBeCloseTo(2 + 3 * 1.5)
    expect(g.zonesFond[0].nom).toBe('est')
    expect(g.zonesTerrain[0].etendue.cotes).toEqual(['#2'])
    expect(g.positions[0]).toMatchObject({ surcharge: 'grue', position: [15, -8], emprise: [6, 6], type: 'rectangle' })
  })
  it('lit la forme ancienne (plan, fouille.risbermes, terrain.pente_beta, surcharges.cote_paroi) et la signale', () => {
    const g = lireGeometrie({
      plan: { contour: RECT, cotes: { sud: 0 } },
      fouille: { risbermes: [{ cote_paroi: 'sud', phases: [2, 2], cote_crete: -2, largeur_banquette: 3, pente: 1, cote_pied: -5 }] },
      terrain: { amont: 0, pente_beta: 15, cote_paroi: ['sud'] },
      surcharges: [{ nom: 'q1', type: 'bande', q: 20, cote_paroi: 'sud' }, { nom: 'q2', type: 'uniforme', q: 10 }],
    })
    expect(g.ancienne).toBe(true)
    expect(g.anciens).toEqual(['plan', 'fouille.risbermes', 'terrain.pente_beta', 'terrain.cote_paroi'])
    expect(g.objets[0]).toMatchObject({ nom: 'Risberme1', type: 'risberme', etendue: { cotes: ['sud'], de: null, a: null } })
    expect(g.objets[0].largeur).toBeCloseTo(3 + 3 * 1)
    expect(g.zonesTerrain[0].pente_beta).toBe(15)
    expect(g.positions.map((p) => p.surcharge)).toEqual(['q1'])
  })
  it('sans plan ni geometrie : contour vide, rien d’ancien', () => {
    const g = lireGeometrie({ sol: [] })
    expect(g.contour).toEqual([])
    expect(g.ancienne).toBe(false)
    expect(cadrage(g)).toEqual({ xmin: -1, xmax: 21, ymin: -1, ymax: 13 })
  })
})

describe('cadrage', () => {
  it('englobe le contour et les positions avec une marge', () => {
    const g = lireGeometrie({ geometrie: { ouvrages: { contour: RECT }, surcharges: [{ surcharge: 'g', position: [15, -8] }] }, surcharges: [{ nom: 'g', type: 'ponctuelle' }] })
    const c = cadrage(g)
    expect(c.ymin).toBeLessThan(-8)
    expect(c.xmax).toBeGreaterThan(20)
    expect(c.xmin).toBeLessThan(0)
  })
})
