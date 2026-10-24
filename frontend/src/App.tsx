import { useCallback, useEffect } from 'react'
import { api, messageErreur } from './lib/api'
import { exporterImage, imprimerNote, telechargerNote, telechargerTexte } from './lib/exporter'
import { nomProjet } from './lib/format'
import type { Chemin } from './lib/scriptDoc'
import { useAffichage, useAncre } from './lib/useAffichage'
import { useProjet } from './lib/useProjet'
import { avecFrise, avecInspecteur, defVue, VUE_APRES_CALCUL } from './lib/vues'
import { BarreTitre } from './composants/BarreTitre'
import { Disposition } from './composants/Disposition'
import { FrisePhases } from './composants/FrisePhases'
import { Inspecteur } from './composants/Inspecteur'
import { Navigation } from './composants/Navigation'
import { VueCentrale } from './composants/VueCentrale'

export default function App() {
  const p = useProjet()
  const a = useAffichage()
  const { res, projet } = p

  /** Change de coupe de calcul en conservant la phase (même nom, sinon correspondance). */
  const changerCoupe = useCallback((i: number) => {
    const j = p.changerCoupe(i, a.phase)
    if (j !== null) a.setPhase(j)
  }, [p, a])

  useAncre(a, res, projet, p.coupeActive, changerCoupe)

  /** Calcul puis affichage : dernière phase ; synthèse si on vient d'une vue de saisie ou d'outils. */
  const calculer = useCallback(async () => {
    const r = await p.calculer()
    if (!r) return
    a.setPhase(Math.max(0, r.phases.length - 1))
    if (defVue(a.vue).groupe !== 'resultats') a.setVue(VUE_APRES_CALCUL)
  }, [p, a])

  // Raccourcis : Ctrl+Entrée, flèches de phase, chiffres pour la coupe (hors champs de saisie)
  useEffect(() => {
    const touche = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); void calculer(); return }
      const cible = e.target as HTMLElement
      if (cible?.closest?.('input, textarea, select, .monaco-editor')) return
      if (!res) return
      if (e.key === 'ArrowLeft') a.setPhase((ph) => res.phases[ph]?.parent ?? Math.max(0, ph - 1))
      if (e.key === 'ArrowRight') a.setPhase((ph) => res.phases[ph]?.enfants?.[0] ?? Math.min(res.phases.length - 1, ph + 1))
      if (/^[1-9]$/.test(e.key) && p.plusieursCoupes && Number(e.key) <= projet!.coupes.length) changerCoupe(Number(e.key) - 1)
    }
    window.addEventListener('keydown', touche)
    return () => window.removeEventListener('keydown', touche)
  }, [calculer, res, projet, p.plusieursCoupes, changerCoupe, a])

  const changerPhase = useCallback((i: number) => {
    if (i < 0) a.setPhase((ph) => (res ? (res.phases[ph]?.enfants?.[0] ?? Math.min(res.phases.length - 1, ph + 1)) : ph))
    else a.setPhase(i)
  }, [res, a])

  const allerErreur = () => { a.setVue('script'); a.viserLigne(p.erreurs[0]?.ligne ?? p.etat.ligne) }
  const exporterMaquette = async () => {
    try { telechargerTexte(await api.maquette(p.texteCalcule()), 'maquette_retainwall.html', 'text/html') } catch (e) { p.setEtat({ genre: 'erreur', texte: `Export de la maquette impossible : ${messageErreur(e)}` }) }
  }
  /** Ajout depuis la maquette : refusé si le script n'est pas lisible (sinon l'ajout serait perdu en silence). */
  const ajouterDepuis3d = (chemin: Chemin, valeur: unknown, message: string) => {
    if (p.erreurYaml) { p.setEtat({ genre: 'erreur', texte: `Script YAML illisible (${p.erreurYaml}) : corrigez-le avant d'ajouter depuis la maquette` }); return }
    p.actions.ajouter(chemin, valeur)
    p.setEtat({ genre: 'modifie', texte: message })
  }

  const nNonOk = res?.verifications?.filter((v) => v.etat === 'non_ok').length ?? 0
  const modele = p.erreurYaml ? null : p.modele

  return (
    <Disposition
      navRepliee={a.navRepliee} tiroirNav={a.tiroirNav} tiroirInsp={a.tiroirInsp}
      onRouvrirNav={() => a.setNavRepliee(false)} onFermerTiroirs={() => { a.setTiroirNav(false); a.setTiroirInsp(false) }}
      titre={
        <BarreTitre projet={nomProjet(p.modele?.projet)} etat={p.etat} enCours={p.enCours} exemples={p.exemples} theme={a.theme}
          imagePossible={!!res && (a.vue === 'diagrammes' || a.vue === '3d')} resultatsDisponibles={!!res}
          onRecalculer={() => void calculer()} onExemple={(t) => { p.charger(t, 'Exemple chargé, non calculé'); a.setVue('synthese') }}
          onOuvrir={(f) => void f.text().then((t) => { p.charger(t); a.setVue('synthese') })} onEnregistrer={p.enregistrer}
          onRido={(f) => void p.importerRido(f).then((ok) => { if (ok) a.setVue('script') })}
          onImage={exporterImage} onNote={() => res && void imprimerNote(res, modele, p.serveur)} onNoteFichier={() => res && void telechargerNote(res, modele, p.serveur)}
          onMaquette={() => void exporterMaquette()} onTheme={a.basculerTheme} onAllerErreur={allerErreur}
          onTiroirNav={() => a.setTiroirNav(!a.tiroirNav)} onTiroirInsp={() => a.setTiroirInsp(!a.tiroirInsp)} />
      }
      nav={
        <Navigation modele={p.modele} erreurs={p.erreurs} vue={a.vue} selection={a.selection} resultats={!!res} pseudo3d={!!res?.pseudo3d}
          nNonOk={nNonOk} nErreurs={p.erreurs.length} onVue={a.setVue} onReplier={() => a.setNavRepliee(true)} />
      }
      centre={<VueCentrale p={p} a={a} onCalculer={() => void calculer()} changerCoupe={changerCoupe} ajouterDepuis3d={ajouterDepuis3d} />}
      insp={avecInspecteur(a.vue) || a.tiroirInsp ? <Inspecteur res={res} phase={a.phase} selection={a.selection} modele={p.modele} onSelection={a.selectionner} /> : null}
      frise={avecFrise(a.vue) && res ? <FrisePhases res={res} phase={a.phase} onPhase={changerPhase} /> : null}
    />
  )
}
