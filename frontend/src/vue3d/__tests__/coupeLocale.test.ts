import { describe, expect, it } from 'vitest'
import { Contour } from '../geometrie'
import { FABRIQUES_CHANTIER } from '../elements'
import { FABRIQUES_COUPE_LOCALE, positionDepuisPoint } from '../coupeLocale'
import { deriver, entreeYamlCoupe, source2D, sourceChamp, sourcePseudo3D, type ChampPlaque } from '../sourceResultats'
import { jeu, jeuProjet, nouvelleScene } from './outils'
import { Vector3 } from 'three'

describe('coupe locale et source de résultats', () => {
  it('en mode 2D, « Couper ici » sur le tronçon de C1 affiche les courbes de C1 et le dit', () => {
    const { resultats, projet } = jeuProjet('coupes')
    const src = source2D(projet, resultats, 0)
    expect(src.mode).toBe('2d')
    const c1 = src.coupeLocale(0, 12, 3)!
    expect(c1.coupe!.startsWith('C1')).toBe(true)
    expect(c1.res.phases[3].y_mm).toEqual(resultats.phases[3].y_mm)
    expect(c1.origine).toContain('mode 2D')
    const c2 = src.coupeLocale(2, 5, 3)!
    expect(c2.coupe!.startsWith('C2')).toBe(true)
    expect(c2.res.dimensionnant.deplacement!.valeur_mm).toBeGreaterThan(30)
    expect(src.coupeLocale(3, 5, 3)).toBeNull()                    // tronçon orphelin
    // coupe unique : les mêmes résultats partout
    const u = source2D(null, jeu('exemple'), 0).coupeLocale(1, 3, 3)!
    expect(u.res.phases[3].synthese!.y_max_mm).toBeCloseTo(17.76, 1)
  })

  it('avec une source factice de type pseudo-3D, les courbes extraites suivent la fonction à 1 % près', () => {
    const res = jeu('exemple')
    const geo = new Contour(res.maquette!.contour)
    const z = Array.from({ length: 30 }, (_, j) => -14 + (14 * j) / 29)
    // champ analytique : y = 10·(1 + s/20)·(1 + z/14)² mm ; M = 100·cos(π z / 14)·(1 + s/40)
    const champ: ChampPlaque = {
      z,
      courbes: (s, phase) => (phase === 0 ? null : { y_mm: z.map((zz) => 10 * (1 + s / 20) * (1 + zz / 14) ** 2), M: z.map((zz) => 100 * Math.cos((Math.PI * zz) / 14) * (1 + s / 40)) }),
    }
    const src = sourceChamp(res, champ, geo)
    expect(src.mode).toBe('pseudo3d')
    const c = src.coupeLocale(1, 4, 3)!              // arête 1 : s = 20 + 4 = 24 m
    const s = geo.aretes[1].s0 + 4
    const ph = c.res.phases[3]
    expect(ph.ok).toBe(true)
    ph.y_mm!.forEach((v, j) => expect(Math.abs(v - 10 * (1 + s / 20) * (1 + z[j] / 14) ** 2)).toBeLessThanOrEqual(0.01 * 10 * (1 + s / 20) + 1e-9))
    ph.M!.forEach((v, j) => expect(Math.abs(v - 100 * Math.cos((Math.PI * z[j]) / 14) * (1 + s / 40))).toBeLessThanOrEqual(1 + 1e-9))
    // V = dM/dz dérivé numériquement, cohérent avec −100·π/14·sin(πz/14)·(1 + s/40) au milieu
    const V = deriver(z, ph.M!)
    const j = 15
    const attendu = -100 * (Math.PI / 14) * Math.sin((Math.PI * z[j]) / 14) * (1 + s / 40)
    expect(Math.abs(V[j] - attendu) / Math.abs(attendu)).toBeLessThan(0.02)
    expect(c.res.phases[0].ok).toBe(false)           // phase hors champ
    expect(c.origine).toContain('pseudo-3D')
    // champ du serveur : à une abscisse de la grille, la courbe est exactement celle du champ
    const p3 = jeu('p3d')
    const g3 = new Contour(p3.maquette!.contour)
    const s3 = sourcePseudo3D(p3, g3)!
    const i = 7
    const sGrille = p3.pseudo3d!.s[i]
    const k = g3.projeter(g3.point(sGrille).x, g3.point(sGrille).y).k
    const cc = s3.coupeLocale(k, sGrille - g3.aretes[k].s0, p3.phases.length - 1)!
    expect(cc.res.phases[p3.phases.length - 1].y_mm![5]).toBeCloseTo(p3.pseudo3d!.phases[p3.phases.length - 1].y_mm![i][5], 3)
  })

  it('une coupe épinglée crée une entrée YAML correcte', () => {
    const { projet } = jeuProjet('coupes')
    const geo = new Contour(projet.contour)
    const e = entreeYamlCoupe('C4 — milieu du côté sud', geo, 0, 12.5, { long_sud: 0, court_est: 1 })
    expect(e).toEqual({ nom: 'C4 — milieu du côté sud', zone: { paroi: 'long_sud' }, trace: { de: [12.5, -8], a: [12.5, 8] } })
    const e3 = entreeYamlCoupe('C5', geo, 3, 9)
    expect(e3.zone).toEqual({ paroi: 3 })
    expect((e3.trace as { de: number[] }).de[0]).toBeCloseTo(-5.4, 6)   // trace de 5,4 m de part et d'autre
  })

  it('le plan « Couper ici » suit la position et se place depuis un point cliqué', () => {
    const { sc } = nouvelleScene([...FABRIQUES_CHANTIER, ...FABRIQUES_COUPE_LOCALE])
    const res = jeu('exemple')
    sc.charger(res)
    const el = sc.elements.get('coupes.locale')!
    expect(el.objet.visible).toBe(false)
    const geo = sc.d!.geo
    const pos = positionDepuisPoint(geo, new Vector3(7, -3, -0.2))     // point proche du côté 0 (y = 0)
    expect(pos).toEqual({ k: 0, sl: 7 })
    sc.definirCoupeLocale(pos)
    expect(el.objet.visible).toBe(true)
    expect(el.objet.position.x).toBeCloseTo(7, 6)
    expect(sc.etiquettesCourantes.find((x) => x.id === 'coupe.locale')!.texte).toContain('s = 7,0 m')
    const c0 = sc.fab.creations
    sc.definirCoupeLocale({ k: 2, sl: 3 })
    sc.definirCoupeLocale(null)
    expect(el.objet.visible).toBe(false)
    expect(sc.fab.creations).toBe(c0)
  })
})
