import { lazy, Suspense, type ReactNode } from 'react'
import type { Exemple } from '../lib/api'
import type { Vue } from '../lib/etat'
import { uniteCote } from '../lib/format'
import type { Chemin } from '../lib/scriptDoc'
import type { Affichage } from '../lib/useAffichage'
import type { Projet } from '../lib/useProjet'
import { defVue, estSaisie, ligneBloc, vueDisponible } from '../lib/vues'
import { Assemblages } from '../vues/Assemblages'
import { CoupeDiagrammes } from '../vues/CoupeDiagrammes'
import { Efforts } from '../vues/Efforts'
import { Hypotheses } from '../vues/Hypotheses'
import { Materiaux } from '../vues/Materiaux'
import { Pseudo3D } from '../vues/Pseudo3D'
import { Saisie } from '../vues/saisie'
import { Synthese } from '../vues/Synthese'
import { Verifications } from '../vues/Verifications'
import { Aide } from '../vues/Aide'
import { EnTeteVue } from './EnTeteVue'
import { PremiersPas } from './PremiersPas'

// Éditeur (Monaco) et maquette (three.js) chargés à la demande : la page s'ouvre sans les attendre.
const Editeur = lazy(() => import('../vues/Editeur').then((m) => ({ default: m.Editeur })))
const Onglet3D = lazy(() => import('../vue3d/Onglet3D').then((m) => ({ default: m.Onglet3D })))
const CHARGEMENT = <div className="vide-centre"><span>Chargement…</span></div>

/** Zone centrale : en-tête de la vue puis son contenu. */
export function VueCentrale({ p, a, onCalculer, changerCoupe, ajouterDepuis3d, onExemple }: {
  p: Projet
  a: Affichage
  onCalculer: () => void
  changerCoupe: (i: number) => void
  ajouterDepuis3d: (chemin: Chemin, valeur: unknown, message: string) => void
  onExemple?: (e: Exemple) => void
}) {
  const { vue } = a
  const d = defVue(vue)
  const res = p.res
  const modele = p.erreurYaml ? null : p.modele
  const disponible = vueDisponible(vue, { resultats: !!res, pseudo3d: !!res?.pseudo3d })

  const allerLigne = (l: number | null | undefined) => { a.setVue('script'); a.viserLigne(l) }
  const retour = a.origine3d && vue !== '3d' ? { libelle: 'Maquette 3D', onClick: () => a.setVue('3d') } : null

  // Actions de l'en-tête : coupe de calcul (résultats à plusieurs coupes), lien vers le bloc du script (saisie)
  const actions: ReactNode = (
    <>
      {d.groupe === 'resultats' && p.plusieursCoupes && (
        <label className="doux selecteur-coupe" title="Coupe de calcul affichée (touches 1 à 9)">Coupe de calcul
          <select value={p.coupeActive} onChange={(e) => changerCoupe(Number(e.target.value))} aria-label="Coupe de calcul affichée">
            {p.projet!.coupes.map((c, i) => <option key={c.nom} value={i}>{i + 1}. {c.nom}</option>)}
          </select>
        </label>
      )}
      {estSaisie(vue) && d.bloc && <button className="btn discret" onClick={() => allerLigne(ligneBloc(p.texte, d.bloc!))} title="Ouvrir le script YAML à ce bloc">Voir dans le script</button>}
    </>
  )

  const premiersPas = <PremiersPas etat={p.etat} erreurs={p.erreurs} enCours={p.enCours} onDonnees={() => a.setVue('projet')} onCalculer={onCalculer} onLigne={allerLigne} />

  const contenu = (): ReactNode => {
    if (estSaisie(vue)) {
      return (
        <Saisie modele={modele} erreurs={p.erreurs} schema={p.schema} references={p.references} actions={p.actions} onAide={a.setAideChamp} texte={p.texte}
          section={vue} selection={a.selection} onSelection={a.setSelection} phaseActive={a.phase} onPhaseActive={a.setPhase} res={res} />
      )
    }
    if (d.groupe === 'resultats' && (!res || !disponible)) return premiersPas
    switch (vue) {
      case 'synthese': return <Synthese res={res!} projet={p.projet} onVue={a.setVue} onSelection3d={(id) => { a.selectionner3d(id); a.setTiroirInsp(true) }} />
      case 'diagrammes': return <CoupeDiagrammes res={res!} phase={a.phase} theme={a.theme} unite={uniteCote(p.modele)} />
      case 'efforts': return <Efforts res={res!} phase={a.phase} onPhase={a.setPhase} onAppui={(n) => { a.selectionner({ type: 'appui', nom: n }); a.setTiroirInsp(true) }} />
      case 'verifications': return <Verifications res={res!} projet={p.projet} filtre={a.origine3d ? a.selection3d : null} onRetour={() => a.setVue('3d')} onglet={a.ongletVerifs} onOnglet={a.setOngletVerifs} />
      case 'hypotheses': return <Hypotheses res={res!} modele={modele} phase={a.phase} version={p.serveur} />
      case 'pseudo3d': return <Pseudo3D res={res!} phase={a.phase} theme={a.theme} />
      case '3d':
        return res!.maquette ? (
          <Onglet3D res={res!} texte={p.texteCalcule()} phase={a.phase} theme={a.theme} projet={p.projet} coupeActive={p.coupeActive} cotes={p.cotesPlan}
            onEpingler={(e) => ajouterDepuis3d(['coupes'], e, 'Coupe ajoutée au script : à recalculer')}
            onAjouterSurcharge={(e) => ajouterDepuis3d(['surcharges'], e, 'Surcharge ajoutée au script : à recalculer')}
            onAjouterRisberme={(e) => ajouterDepuis3d(modele?.geometrie ? ['geometrie', 'fouille', 'objets'] : ['fouille', 'risbermes'], e, 'Risberme ajoutée au script : à recalculer')}
            formeGeometrie={!!modele?.geometrie}
            selection={a.selection3d} onSelection={a.selectionner3d} modele={modele} onPhase={a.setPhase}
            onOuvrir={(o) => a.ouvrirDepuis3d(o === 'coupe' ? 'diagrammes' : o)} prereglageInitial={a.prereglage} onPrereglage={a.setPrereglage}
            etat3d={a.etat3d} onEtat3d={a.setEtat3d} unite={uniteCote(p.modele)} />
        ) : <div className="vide-centre"><b>Maquette non disponible</b><span>Le serveur n'a pas renvoyé la géométrie de la maquette pour ce calcul.</span></div>
      case 'assemblages':
        return <Assemblages res={res} modele={modele} references={p.references} theme={a.theme}
          onEnregistrer={(nom, bloc, remplacer) => {
            if (remplacer) p.actions.fixer(['assemblages', nom], bloc); else p.actions.ajouterCle(['assemblages'], nom, bloc)
            p.setEtat({ genre: 'modifie', texte: `Assemblage ${nom} enregistré dans le script : à recalculer` })
          }}
          onSupprimer={(nom) => { p.actions.supprimer(['assemblages', nom]); p.setEtat({ genre: 'modifie', texte: `Assemblage ${nom} retiré du script : à recalculer` }) }} />
      case 'script':
        return (
          <div className="vue-script">
            <div className="editeur">
              <Editeur texte={p.texte} onChange={p.setTexte} erreurs={[...p.erreurs, ...p.avertScript]} schema={p.schema} references={p.references} cible={a.ligneCible} />
            </div>
            {p.rapportRido && (
              <div className="rapport-rido"><b>Rapport de conversion RIDO</b> <button className="btn discret" onClick={() => p.setRapportRido(null)}>Fermer</button>
                <ul style={{ margin: '4px 0 0', paddingLeft: 16 }}>{p.rapportRido.map((l, i) => <li key={i}>{l}</li>)}</ul></div>
            )}
            <div className="liste-erreurs">
              {p.erreurYaml ? <ul><li><b>YAML</b> {p.erreurYaml}</li></ul>
                : p.erreurs.length === 0 && p.avertScript.length === 0 ? <div className="ok">Script valide.</div> : (
                  <ul>
                    {p.erreurs.length === 0 && <li className="ok-ligne">Script calculable ; les avertissements ci-dessous n'empêchent pas le calcul.</li>}
                    {[...p.erreurs, ...p.avertScript].map((e, i) => (
                      <li key={i} className={e.niveau === 'avertissement' ? 'avert' : ''} onClick={() => a.viserLigne(e.ligne)}>
                        <b className="mono">{e.ligne ? `ligne ${e.ligne}` : 'script'}</b><span>{e.chemin ? `${e.chemin} : ` : ''}{e.message}</span>
                      </li>))}
                  </ul>
                )}
            </div>
          </div>
        )
      case 'materiaux': return <Materiaux surImport={() => void p.rechargerReferences()} />
      case 'aide': return <Aide version={p.serveur} section={a.sectionAide} exemples={p.exemples} onExemple={onExemple} />
      default: return null
    }
  }

  return (
    <>
      <EnTeteVue titre={d.libelle} sousTitre={d.sousTitre} retour={retour} enfants={actions} />
      <div className="contenu-vue">
        <Suspense fallback={CHARGEMENT}>{contenu()}</Suspense>
      </div>
    </>
  )
}

export type { Vue }
