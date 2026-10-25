// État d'affichage : vue courante, phase active, sélections, thème, repli des panneaux, ancre d'URL.
import { useCallback, useEffect, useRef, useState } from 'react'
import type { ProjetCoupes, Resultats } from './api'
import type { Selection, Vue } from './etat'
import type { SectionAide } from '../vues/Aide'
import type { AideChampInfo } from '../vues/saisie'
import { ETAT_3D_INITIAL, type EtatVue3D } from '../vue3d/etat3d'
import { appliquerTheme, choisirTheme, themeInitial, type Theme } from './theme'
import { decoderAncre, encoderAncre } from '../vue3d/navigation'

export function useAffichage() {
  const [vue, setVueBrute] = useState<Vue>('synthese')
  const [phase, setPhase] = useState(0)
  const [selection, setSelection] = useState<Selection>(null)
  const [selection3d, setSelection3d] = useState<string | null>(null)   // objet sélectionné dans la maquette
  const [prereglage, setPrereglage] = useState<string | null>(null)       // dernier préréglage de calques appliqué
  const [origine3d, setOrigine3d] = useState(false)                       // vue ouverte depuis la maquette (lien de retour)
  const [theme, setTheme] = useState<Theme>(themeInitial)
  const [navRepliee, setNavRepliee] = useState(false)
  const [tiroirNav, setTiroirNav] = useState(false)
  const [tiroirInsp, setTiroirInsp] = useState(false)
  const [ligneCible, setLigneCible] = useState<{ ligne: number; n: number } | null>(null)
  const [sectionAide, setSectionAide] = useState<SectionAide | null>(null)
  const [aideChamp, setAideChamp] = useState<AideChampInfo | null>(null)   // champ de saisie focalisé (panneau droit)
  const [ongletVerifs, setOngletVerifs] = useState<string | null>(null)    // famille ouverte dans la vue Vérifications
  const [etat3d, setEtat3dBrut] = useState<EtatVue3D>(ETAT_3D_INITIAL)      // maquette 3D : plan de coupe, panneau, courbes en un point
  const setEtat3d = useCallback((e: Partial<EtatVue3D>) => setEtat3dBrut((s) => ({ ...s, ...e })), [])
  const compteurCible = useRef(0)

  useEffect(() => { appliquerTheme(theme) }, [theme])

  const basculerTheme = useCallback(() => {
    setTheme((t) => { const n: Theme = t === 'sombre' ? 'clair' : 'sombre'; choisirTheme(n); return n })
  }, [])

  /** Changement de vue par la navigation : ferme le tiroir, oublie l'origine 3D. */
  const setVue = useCallback((v: Vue, sel: Selection = null) => {
    setVueBrute(v)
    setSelection(sel)
    setOrigine3d(false)
    setTiroirNav(false)
    setTiroirInsp(false)
    setAideChamp(null)
  }, [])

  /** Ouverture d'une vue depuis la maquette 3D : lien de retour et filtre sur la sélection. */
  const ouvrirDepuis3d = useCallback((v: Vue) => {
    setVueBrute(v)
    setOrigine3d(true)
  }, [])

  /** Ouvre la vue Aide sur une section (menu Aide). */
  const ouvrirAide = useCallback((s: SectionAide) => { setVue('aide'); setSectionAide(s) }, [setVue])

  /** Place le curseur de l'éditeur sur une ligne (chaque demande est distincte : recliquer la même erreur agit). */
  const viserLigne = useCallback((l: number | null | undefined) => {
    if (l) setLigneCible({ ligne: l, n: ++compteurCible.current })
  }, [])

  /** Sélection depuis la maquette : « appui:B1 » -> inspecteur de l'appui, « couche:1 » -> couche. */
  const selectionner3d = useCallback((id: string | null) => {
    setSelection3d(id)
    if (id?.startsWith('appui:')) setSelection({ type: 'appui', nom: id.slice(6) })
    else if (id?.startsWith('couche:')) setSelection({ type: 'couche', index: Number(id.slice(7)) || 0 })
    else setSelection(null)
  }, [])

  /** Sélection depuis l'inspecteur ou les tableaux : répercutée sur la maquette. */
  const selectionner = useCallback((sel: Selection) => {
    setSelection(sel)
    setSelection3d(sel?.type === 'appui' ? `appui:${sel.nom}` : sel?.type === 'couche' ? `couche:${sel.index}` : null)
  }, [])

  return {
    vue, setVue, ouvrirDepuis3d, origine3d, phase, setPhase, selection, selectionner, setSelection,
    selection3d, selectionner3d, prereglage, setPrereglage, theme, basculerTheme,
    navRepliee, setNavRepliee, tiroirNav, setTiroirNav, tiroirInsp, setTiroirInsp,
    ligneCible, viserLigne, sectionAide, ouvrirAide, aideChamp, setAideChamp, etat3d, setEtat3d,
    ongletVerifs, setOngletVerifs,
  }
}

export type Affichage = ReturnType<typeof useAffichage>

/** Ancre d'URL partageable (coupe, phase, sélection, préréglage de calques) : écrite à chaque changement,
 *  lue une fois au premier calcul. */
export function useAncre(a: Affichage, res: Resultats | null, projet: ProjetCoupes | null, coupeActive: number,
  changerCoupe: (i: number) => void) {
  const ancreInitiale = useRef(decoderAncre(window.location.hash))
  useEffect(() => {
    if (!res) return
    const h = encoderAncre({ coupe: coupeActive, phase: a.phase, selection: a.selection3d, prereglage: a.prereglage })
    if (window.location.hash !== h) window.history.replaceState(null, '', h)
  }, [res, coupeActive, a.phase, a.selection3d, a.prereglage])
  useEffect(() => {
    const an = ancreInitiale.current
    if (!an || !res || !projet) return
    ancreInitiale.current = null
    if (an.coupe > 0 && an.coupe < projet.coupes.length) changerCoupe(an.coupe)
    const cible = (projet.coupes[an.coupe]?.resultats ?? res)
    a.setPhase(Math.min(an.phase, cible.phases.length - 1))
    if (an.selection) a.selectionner3d(an.selection)
    if (an.prereglage) a.setPrereglage(an.prereglage)
    a.setVue('3d')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [res, projet])
  return ancreInitiale
}
