import type * as THREE from 'three'
import { describe, expect, it } from 'vitest'
import { definirMode, definirReglage, definirVisible, etatInitial, versScene } from '../calques'
import { FABRIQUES_CHANTIER } from '../elements'
import { legendes, noteDeformee } from '../legendes'
import { classeTaux, couleurPalette, PALETTES } from '../palettes'
import { amplificationAuto, bornes, COULEUR_HORS_MODELE, extremes, FABRIQUES_RESULTATS_PAROI, horsModele, NZ, profilValeur, tauxParoi } from '../resultats'
import { champPseudo3D } from '../sourceResultats'
import { indicePhase, jeu, nouvelleScene } from './outils'
import { Color } from 'three'

const TOUT = [...FABRIQUES_CHANTIER, ...FABRIQUES_RESULTATS_PAROI]

function surface(sc: ReturnType<typeof nouvelleScene>['sc'], k = 0) {
  return sc.elements.get(`resultats.surface.${k}`)!.objet.children[0] as THREE.Mesh
}

describe('résultats de la paroi en 3D', () => {
  it('à la phase dimensionnante, la couleur à la cote du déplacement maximal est la borne haute de la palette', () => {
    const { sc } = nouvelleScene(TOUT)
    const res = jeu('exemple')
    sc.charger(res)
    sc.appliquerCalques(versScene(definirVisible(etatInitial(), 'resultats.deplacement', true)))
    const i = indicePhase(res, res.dimensionnant.deplacement!.phase)
    sc.phase(i)
    const m = surface(sc)
    const g = m.geometry
    const zMax = res.phases[i].synthese!.z_y_max
    const p = res.maquette!.paroi
    const j = Math.round(((zMax - p.pied) / (p.tete - p.pied)) * (NZ - 1))
    const col = g.attributes.color as THREE.BufferAttribute
    const fin = PALETTES.divergente[PALETTES.divergente.length - 1].map((v) => v / 255)
    const mid = Math.floor(g.attributes.position.count / NZ / 2) * NZ + j     // colonne du milieu de l'arête
    expect(col.getX(mid)).toBeCloseTo(fin[0], 1)
    expect(col.getY(mid)).toBeCloseTo(fin[1], 1)
    expect(col.getZ(mid)).toBeCloseTo(fin[2], 1)
    // en tête de paroi (petit déplacement) : couleur différente
    const tete = mid - j + NZ - 1
    expect(Math.abs(col.getX(tete) - fin[0]) + Math.abs(col.getZ(tete) - fin[2])).toBeGreaterThan(0.2)
  })

  it('l\'amplification « auto » donne 2 m de flèche visuelle', () => {
    const res = jeu('exemple')
    const amp = amplificationAuto(res)
    expect((amp * res.dimensionnant.deplacement!.valeur_mm) / 1000).toBeCloseTo(2, 6)
    const { sc } = nouvelleScene(TOUT)
    sc.charger(res)
    sc.appliquerCalques(versScene(definirVisible(etatInitial(), 'resultats.deformee', true)))
    sc.phase(indicePhase(res, res.dimensionnant.deplacement!.phase))
    const pos = surface(sc).geometry.attributes.position as THREE.BufferAttribute
    const fant = (sc.elements.get('resultats.surface.0')!.objet.children[1] as THREE.Mesh).geometry.attributes.position as THREE.BufferAttribute
    let dmax = 0
    for (let k = 0; k < pos.count; k++) dmax = Math.max(dmax, Math.hypot(pos.getX(k) - fant.getX(k), pos.getZ(k) - fant.getZ(k)))
    expect(dmax).toBeGreaterThan(1.9)
    expect(dmax).toBeLessThan(2.05)
  })

  it('les ailettes du moment ont le signe par couleur', () => {
    const { sc } = nouvelleScene(TOUT)
    const res = jeu('exemple')
    sc.charger(res)
    let e = definirVisible(etatInitial(), 'resultats.moment', true)
    e = definirMode(e, 'resultats.moment', 'ailettes')
    sc.appliquerCalques(versScene(e))
    const i = indicePhase(res, 'Terrassement final et pompage')
    sc.phase(i)
    const el = sc.elements.get('resultats.ailette.M.0')!
    expect(el.objet.visible).toBe(true)
    const g = (el.objet as THREE.Mesh).geometry
    const col = g.attributes.color as THREE.BufferAttribute
    const f = profilValeur(res, i, 'M', 0)!
    const p = res.maquette!.paroi
    const n = g.attributes.position.count / 2
    let pos = 0
    let neg = 0
    for (let j = 0; j < n; j++) {
      const z = p.pied + ((p.tete - p.pied) * j) / (n - 1)
      const r = col.getX(2 * j)
      const b = col.getZ(2 * j)
      if (f(z) > 1) { expect(r).toBeGreaterThan(b); pos++ }
      if (f(z) < -1) { expect(b).toBeGreaterThan(r); neg++ }
    }
    expect(pos).toBeGreaterThan(0)
    expect(neg).toBeGreaterThan(0)
    // en mode couleur, les ailettes disparaissent et la surface se colore
    sc.appliquerCalques(versScene(definirMode(e, 'resultats.moment', 'couleur')))
    expect(el.objet.visible).toBe(false)
    expect(sc.elements.get('resultats.surface.0')!.objet.visible).toBe(true)
  })

  it('classe les taux de travail et grise la paroi non vérifiable', () => {
    expect(classeTaux(0.5)).toBe('vert')
    expect(classeTaux(0.9)).toBe('orange')
    expect(classeTaux(0.999)).toBe('orange')
    expect(classeTaux(1.0)).toBe('rouge')
    expect(classeTaux(null)).toBe('gris')
    const res = jeu('exemple')
    const t = tauxParoi(res.verifications)
    expect(t.verifiable).toBe(false)             // palplanches non vérifiables (coefficients manquants)
    expect(t.fiche).toBeCloseTo(1.181, 2)         // mobilisation de la butée
    const { sc } = nouvelleScene(TOUT)
    sc.charger(res)
    sc.appliquerCalques(versScene(definirVisible(etatInitial(), 'resultats.taux', true)))
    sc.phase(indicePhase(res, 'Terrassement final et pompage'))
    const col = surface(sc).geometry.attributes.color as THREE.BufferAttribute
    const gris = new Color(0x9aa2ad)
    const rouge = new Color(0xc7362c)
    expect(col.getX(NZ - 1)).toBeCloseTo(gris.r, 2)      // tête : gris
    expect(col.getX(0)).toBeCloseTo(rouge.r, 2)          // pied (fiche) : rouge
    const b = jeu('berlinoise')
    const tb = tauxParoi(b.verifications)
    expect(tb.verifiable).toBe(true)
    expect(tb.courant).toBeCloseTo(2.609, 2)             // blindage non vérifié (mise en charge au vérin du tirant, 23/10/2026)
  })

  it('profil et bornes : champ pseudo-3D utilisé quand il existe', () => {
    const res = jeu('p3d')
    const i = res.phases.length - 1
    const f = profilValeur(res, i, 'y', res.pseudo3d!.s[Math.floor(res.pseudo3d!.s.length / 2)])!
    const z = res.pseudo3d!.z
    const p3 = res.pseudo3d!.phases[i].y_mm![Math.floor(res.pseudo3d!.s.length / 2)]
    expect(f(z[10])).toBeCloseTo(p3[10], 6)
    const b = bornes(res, 'yabs', null)
    expect(b.min).toBe(0)
    expect(b.max).toBeCloseTo(Math.max(...res.pseudo3d!.phases.filter((p) => p.ok).flatMap((p) => p.y_mm!.flat().map(Math.abs))), 6)
  })

  it('étiquettes d\'extrêmes : déplacement, moments, appuis avec cote et phase', () => {
    const res = jeu('exemple')
    const e = extremes(res)
    expect(e.find((x) => x.id === 'y')!.texte).toContain('17,6 mm')
    expect(e.find((x) => x.id === 'y')!.z).toBeCloseTo(-5.5, 6)
    expect(e.find((x) => x.id === 'appui.B1')!.texte).toContain('142 kN/m')
    expect(e.find((x) => x.id === 'appui.B1')!.texte).toContain('853 kN')
    const { sc } = nouvelleScene(TOUT)
    sc.charger(res)
    sc.appliquerCalques(versScene(definirVisible(etatInitial(), 'resultats.extremes', true)))
    sc.phase(3)
    expect(sc.etiquettesCourantes.filter((x) => x.id.startsWith('extreme.')).length).toBe(4)
  })

  it('légendes : une par calque de couleur actif, bornes et unité', () => {
    const res = jeu('exemple')
    let e = definirVisible(etatInitial(), 'resultats.deplacement', true)
    e = definirVisible(e, 'resultats.pressions', true)
    const l = legendes(res, versScene(e), 3)
    const d = l.find((x) => x.id === 'deplacement')!
    expect(d.type).toBe('continue')
    if (d.type === 'continue') {
      expect(d.unite).toBe('mm')
      expect(d.min).toBe(0)
      expect(d.max).toBeCloseTo(17.65, 1)
      expect(d.phase).toBe('toutes phases')
    }
    expect(l.some((x) => x.id === 'pressions')).toBe(true)
    e = definirReglage(e, 'resultats.deplacement', 'echelle', 'phase')
    const l2 = legendes(res, versScene(e), 1)
    const d2 = l2.find((x) => x.id === 'deplacement')!
    if (d2.type === 'continue') { expect(d2.max).toBeCloseTo(3.56, 1); expect(d2.phase).toBe('Terrassement à -2,0') }
  })

  it('les calques de résultats restent stables en mémoire et sans allocation au changement de phase', () => {
    const { sc } = nouvelleScene(TOUT)
    const res = jeu('ecoulement')
    sc.charger(res)
    let e = etatInitial()
    for (const id of ['resultats.deformee', 'resultats.deplacement', 'resultats.pressions', 'resultats.enveloppes', 'resultats.extremes']) e = definirVisible(e, id, true)
    e = definirMode(e, 'resultats.tranchant', 'ailettes')
    e = definirVisible(e, 'resultats.tranchant', true)
    sc.appliquerCalques(versScene(e))
    for (let i = 0; i < res.phases.length; i++) sc.phase(i)
    const c0 = sc.fab.creations
    const g0 = sc.fab.geometries.size
    for (let k = 0; k < 30; k++) sc.phase(k % res.phases.length)
    sc.charger(jeu('ecoulement'))
    expect(sc.fab.creations).toBe(c0)
    expect(sc.fab.geometries.size).toBe(g0)
    const t = new Color()
    couleurPalette(0.5, 'divergente', t)
    expect(t.r).toBeGreaterThan(0.9)
  })

  it('pseudo-3D paroi droite : au-delà de la longueur modélisée, la paroi reste grise et non déformée', () => {
    const res = jeu('p3d')                                      // paroi droite de 48 m sur un contour de 96 m
    const L = res.pseudo3d!.s[res.pseudo3d!.s.length - 1]
    const derniere = res.phases.length - 1
    expect(horsModele(res, L - 1)).toBe(false)
    expect(horsModele(res, L + 5)).toBe(true)
    expect(profilValeur(res, derniere, 'y', L - 1)).not.toBeNull()
    expect(profilValeur(res, derniere, 'y', L + 5)).toBeNull()
    expect(champPseudo3D(res)!.courbes(L + 5, derniere)).toBeNull()
    expect(noteDeformee(res)).toContain('hors longueur modélisée')
    const { sc } = nouvelleScene(TOUT)
    sc.charger(res)
    let e = definirVisible(etatInitial(), 'resultats.deplacement', true)
    e = definirVisible(e, 'resultats.deformee', true)
    sc.appliquerCalques(versScene(e))
    sc.phase(derniere)
    const gris = new Color(COULEUR_HORS_MODELE)
    const ecart = (k: number, surf: THREE.Mesh, fant: THREE.Mesh) => {
      const p = surf.geometry.attributes.position as THREE.BufferAttribute
      const f = fant.geometry.attributes.position as THREE.BufferAttribute
      return Math.hypot(p.getX(k) - f.getX(k), p.getZ(k) - f.getZ(k))
    }
    // arête 2 (s de 48 à 72 m) : à partir de la deuxième colonne (s > 48), gris et confondue avec la paroi initiale
    const m2 = surface(sc, 2)
    const fant2 = sc.elements.get('resultats.surface.2')!.objet.children[1] as THREE.Mesh
    const col = m2.geometry.attributes.color as THREE.BufferAttribute
    let dmax = 0
    for (let k = NZ; k < col.count; k++) {
      expect(col.getX(k)).toBeCloseTo(gris.r, 5)
      expect(col.getZ(k)).toBeCloseTo(gris.b, 5)
      dmax = Math.max(dmax, ecart(k, m2, fant2))
    }
    expect(dmax).toBeLessThan(1e-9)
    // arête 0 (s de 0 à 24 m) : dans le modèle, déformée et colorée par le champ
    const m0 = surface(sc, 0)
    const fant0 = sc.elements.get('resultats.surface.0')!.objet.children[1] as THREE.Mesh
    let d0 = 0
    for (let k = 0; k < (m0.geometry.attributes.position as THREE.BufferAttribute).count; k++) d0 = Math.max(d0, ecart(k, m0, fant0))
    expect(d0).toBeGreaterThan(0.1)
  })
})
