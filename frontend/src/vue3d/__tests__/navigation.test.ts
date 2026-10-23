import { describe, expect, it } from 'vitest'
import { definirVisible, etatInitial, versScene } from '../calques'
import { FABRIQUES_CHANTIER } from '../elements'
import { analyserSelection, decoderAncre, encoderAncre, filAriane, pointsAttention, titreFiltre, verifsPour } from '../navigation'
import { FABRIQUES_REPERES } from '../reperes'
import { jeu, jeuProjet, nouvelleScene } from './outils'

describe('navigation depuis la maquette', () => {
  it('cliquer B1 filtre le panneau sur B1 : effort de la phase et ses vérifications', () => {
    const res = jeu('exemple')
    const sel = analyserSelection('appui:B1')!
    expect(sel).toEqual({ type: 'appui', nom: 'B1' })
    const a = res.phases[3].appuis!.find((x) => x.nom === 'B1')!
    expect(a.effort_kN_m).toBeCloseTo(142.19, 1)
    const vs = verifsPour(sel, res, res.maquette!.assemblages)
    expect(vs.map((v) => v.nom)).toContain('Buton — flambement et flexion')
    expect(vs.some((v) => v.element.startsWith('A1'))).toBe(true)          // assemblages de B1
    expect(vs.some((v) => v.nom.startsWith('Mobilisation'))).toBe(false)
    const paroi = verifsPour(analyserSelection('paroi:0'), res, {})
    expect(paroi.some((v) => v.nom.startsWith('Mobilisation'))).toBe(true)
    expect(paroi.some((v) => v.nom.startsWith('Fond de fouille'))).toBe(false)
    expect(verifsPour(analyserSelection('fond'), res, {}).every((v) => v.nom.startsWith('Fond de fouille'))).toBe(true)
    expect(verifsPour(analyserSelection('assemblage:A3'), res, res.maquette!.assemblages).every((v) => v.element.startsWith('A3'))).toBe(true)
    expect(verifsPour(null, res, {}).length).toBe(res.verifications!.length)
    expect(analyserSelection('inconnu:x')).toBeNull()
    expect(titreFiltre(sel, 'C1 — long côté sud', 7)).toBe('B1 · coupe C1 · phase 8')
  })

  it('le fil d’Ariane reflète la sélection et la coupe', () => {
    const { projet } = jeuProjet('coupes')
    const m = filAriane(analyserSelection('appui:B1'), projet, 1, { A1: { appui: 'B1' } })
    expect(m.map((x) => x.libelle)).toEqual(['Projet', 'C2', 'Appuis', 'B1'])
    expect(m[1].selection).toBe(`coupe:${projet.coupes[1].nom}`)
    const a = filAriane(analyserSelection('assemblage:A1'), null, 0, { A1: { appui: 'B1' } })
    expect(a.map((x) => x.libelle)).toEqual(['Projet', 'Appuis', 'B1', 'A1'])
    expect(filAriane(null, null, 0).map((x) => x.libelle)).toEqual(['Projet'])
  })

  it("l'ancre d'URL encode coupe, phase, sélection et préréglage, et se décode", () => {
    const h = encoderAncre({ coupe: 0, phase: 7, selection: 'appui:B2', prereglage: 'structure' })
    expect(h).toBe('#c1-p8-s_appui%3AB2-l_structure')
    expect(decoderAncre(h)).toEqual({ coupe: 0, phase: 7, selection: 'appui:B2', prereglage: 'structure' })
    expect(decoderAncre('#c2-p3')).toEqual({ coupe: 1, phase: 2, selection: null, prereglage: null })
    expect(decoderAncre('#autre')).toBeNull()
    expect(decoderAncre('')).toBeNull()
  })

  it('les points d’attention listent les éléments à 90 % et plus, triés par taux décroissant', () => {
    const res = jeu('ecoulement')
    const p = pointsAttention(res, res.maquette!.assemblages)
    expect(p.length).toBeGreaterThan(3)
    for (let i = 1; i < p.length; i++) expect((p[i - 1].taux ?? -1) >= (p[i].taux ?? -1)).toBe(true)
    expect(p[0].selection).toBe('appui:B2')                                // flambement de B2 : 9 900 %
    expect(p.some((x) => x.selection === 'lierne:B2')).toBe(true)
    expect(p.some((x) => x.selection === 'fond')).toBe(true)               // renard — Lane : 170 %
    expect(p.some((x) => x.selection === 'paroi:0')).toBe(true)            // mobilisation de la butée
  })

  it('le curseur de cote et les marqueurs d’alerte apparaissent dans la scène', () => {
    const { sc } = nouvelleScene([...FABRIQUES_CHANTIER, ...FABRIQUES_REPERES])
    const res = jeu('ecoulement')
    sc.charger(res)
    sc.phase(5)
    const el = sc.elements.get('annotations.repere')!
    expect(el.objet.visible).toBe(false)
    sc.definirRepere({ k: 0, z: -5.5 })
    expect(el.objet.visible).toBe(true)
    expect(el.objet.position.y).toBeCloseTo(-5.5, 6)
    expect(sc.etiquettesCourantes.find((x) => x.id === 'repere.cote')!.texte).toContain('−5,50'.replace('−', '-'))
    sc.definirRepere(null)
    expect(el.objet.visible).toBe(false)
    const alertes = sc.etiquettesCourantes.filter((x) => x.id.startsWith('alerte.'))
    expect(alertes.some((x) => x.selection === 'appui:B2' && x.classe?.includes('rouge'))).toBe(true)
    sc.appliquerCalques(versScene(definirVisible(etatInitial(), 'resultats.alertes', false)))
    expect(sc.etiquettesCourantes.some((x) => x.id.startsWith('alerte.'))).toBe(false)
  })
})
