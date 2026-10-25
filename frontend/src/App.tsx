import { useCallback, useEffect } from 'react'
import { api, messageErreur, type Exemple } from './lib/api'
import { confirmer, informer } from './lib/dialogue'
import { exporterImage, imprimerNote, telechargerNote, telechargerTexte } from './lib/exporter'
import { nomProjet } from './lib/format'
import type { Chemin } from './lib/scriptDoc'
import { useAffichage, useAncre } from './lib/useAffichage'
import { useProjet } from './lib/useProjet'
import { avecFrise, avecInspecteur, defVue, estSaisie, VUE_APRES_CALCUL } from './lib/vues'
import { AideChamp } from './composants/AideChamp'
import { BarreTitre } from './composants/BarreTitre'
import { Dialogue } from './composants/Dialogue'
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
      if (cible?.closest?.('input, textarea, select, .monaco-editor, .dialogue')) return
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

  /** Remplace le script courant (nouveau projet, exemple, fichier) après confirmation s'il a été modifié. */
  const remplacer = async (texte: string, message: string, vue: 'synthese' | 'projet' = 'synthese') => {
    if (p.modifie && !(await confirmer('Le script courant a été modifié depuis son chargement et n’est pas enregistré. Le remplacer ?', { titre: 'Remplacer le script', ok: 'Remplacer' }))) return
    p.charger(texte, message)
    a.setVue(vue)
  }
  const nouveau = () => {
    const g = p.exemples.find((e) => e.groupe === 'Modèles')
    if (g) void remplacer(g.texte, 'Nouveau projet : renseignez les données puis calculez', 'projet')
  }
  const exemple = (e: Exemple) => void remplacer(e.texte, 'Exemple chargé, non calculé')
  const ouvrir = (f: File) => void f.text().then((t) => remplacer(t, `Fichier « ${f.name} » chargé, non calculé`))
  const importerRido = async (f: File) => {
    if (p.modifie && !(await confirmer('Le script courant a été modifié et n’est pas enregistré. Le remplacer par le fichier RIDO converti ?', { titre: 'Importer un fichier RIDO', ok: 'Importer' }))) return
    if (await p.importerRido(f)) a.setVue('script')
  }

  const allerErreur = () => { a.setVue('script'); a.viserLigne(p.erreurs[0]?.ligne ?? p.etat.ligne) }
  const exporterMaquette = async () => {
    try { telechargerTexte(await api.maquette(p.texteCalcule()), 'maquette_retainwall.html', 'text/html') } catch (e) { void informer(`Export de la maquette impossible : ${messageErreur(e)}`) }
  }
  /** Ajout depuis la maquette : refusé si le script n'est pas lisible (sinon l'ajout serait perdu en silence). */
  const ajouterDepuis3d = (chemin: Chemin, valeur: unknown, message: string) => {
    if (p.erreurYaml) { void informer(`Script YAML illisible (${p.erreurYaml}) : corrigez-le avant d'ajouter depuis la maquette.`); return }
    p.actions.ajouter(chemin, valeur)
    p.setEtat({ genre: 'modifie', texte: message })
  }
  const aPropos = () => void informer(`RetainWall ${p.serveur} : calcul d'écrans de soutènement par coefficients de réaction (NF P 94-282, EC2, EC3). Version non validée : aucun résultat ne doit servir à un projet réel avant comparaison à K-Réa ou RIDO sur plusieurs cas et visa d'un ingénieur.`, 'À propos')

  const nNonOk = res?.verifications?.filter((v) => v.etat === 'non_ok').length ?? 0
  const modele = p.erreurYaml ? null : p.modele

  return (
    <>
      <Disposition
        navRepliee={a.navRepliee} tiroirNav={a.tiroirNav} tiroirInsp={a.tiroirInsp}
        onRouvrirNav={() => a.setNavRepliee(false)} onFermerTiroirs={() => { a.setTiroirNav(false); a.setTiroirInsp(false) }}
        titre={
          <BarreTitre projet={nomProjet(p.modele?.projet)} etat={p.etat} enCours={p.enCours} exemples={p.exemples} theme={a.theme} version={p.serveur}
            imagePossible={!!res && (a.vue === 'diagrammes' || a.vue === '3d')} resultatsDisponibles={!!res}
            onRecalculer={() => void calculer()} onNouveau={nouveau} onExemple={exemple} onOuvrir={ouvrir} onEnregistrer={p.enregistrer}
            onRido={(f) => void importerRido(f)}
            onImage={exporterImage} onNote={() => res && void imprimerNote(res, modele, p.serveur)} onNoteFichier={() => res && void telechargerNote(res, modele, p.serveur)}
            onMaquette={() => void exporterMaquette()} onTheme={a.basculerTheme} onAllerErreur={allerErreur}
            onAide={a.ouvrirAide} onAPropos={aPropos}
            onTiroirNav={() => a.setTiroirNav(!a.tiroirNav)} onTiroirInsp={() => a.setTiroirInsp(!a.tiroirInsp)} />
        }
        nav={
          <Navigation modele={p.modele} erreurs={p.erreurs} vue={a.vue} selection={a.selection} resultats={!!res} pseudo3d={!!res?.pseudo3d}
            nNonOk={nNonOk} nErreurs={p.erreurs.length} onVue={a.setVue} onReplier={() => a.setNavRepliee(true)} />
        }
        centre={<VueCentrale p={p} a={a} onCalculer={() => void calculer()} changerCoupe={changerCoupe} ajouterDepuis3d={ajouterDepuis3d} />}
        insp={avecInspecteur(a.vue) || a.tiroirInsp ? <Inspecteur res={res} phase={a.phase} selection={a.selection} modele={p.modele} onSelection={a.selectionner} />
          : estSaisie(a.vue) ? <AideChamp champ={a.aideChamp} schema={p.schema} erreurs={p.erreurs} prefixe={defVue(a.vue).bloc} onLigne={(l) => { a.setVue('script'); a.viserLigne(l) }} /> : null}
        frise={avecFrise(a.vue) && res ? <FrisePhases res={res} phase={a.phase} onPhase={changerPhase} /> : null}
      />
      <Dialogue />
    </>
  )
}
