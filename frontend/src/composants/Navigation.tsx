import { useState, type ReactNode } from 'react'
import type { ErreurScript } from '../lib/api'
import type { Selection, Vue } from '../lib/etat'
import { nb } from '../lib/format'
import {
  IconeAppui, IconeBase, IconeChevronB, IconeChevronD, IconeCoupe, IconeCube, IconeEau, IconeFichier, IconeInfo, IconePanneauG, IconeParoi,
  IconePhases, IconePlaque, IconeProjet, IconeScript, IconeSol, IconeSurcharge, IconeTableau, IconeVerif,
} from '../lib/icones'
import type { Modele } from '../lib/scriptDoc'
import { COULEURS_SOL } from '../lib/theme'
import { vueDisponible, vuesDuGroupe, type DefVue } from '../lib/vues'

const NOMS_PAROI: Record<string, string> = {
  palplanche: 'Palplanches', paroi_moulee: 'Paroi moulée', pieux_secants: 'Pieux sécants',
  pieux_disjoints: 'Pieux disjoints', berlinoise: 'Berlinoise',
}

const ICONES: Record<Vue, ReactNode> = {
  projet: <IconeProjet />, sol: <IconeSol />, ecran: <IconeParoi />, eau: <IconeEau />, surcharges: <IconeSurcharge />,
  appuis: <IconeAppui />, phases: <IconePhases />, verifs_demandees: <IconeVerif />,
  synthese: <IconeFichier />, diagrammes: <IconeCoupe />, efforts: <IconeTableau />, verifications: <IconeVerif />,
  '3d': <IconeCube />, hypotheses: <IconeFichier />, pseudo3d: <IconePlaque />,
  script: <IconeScript />, assemblages: <IconeAppui />, materiaux: <IconeBase />, aide: <IconeInfo />,
}

/** Navigation unique : Données (étapes de saisie, avec leurs enfants), Résultats, Outils. */
export function Navigation({ modele, erreurs, vue, selection, resultats, pseudo3d, nNonOk, nErreurs, onVue, onReplier }: {
  modele: Modele
  erreurs: ErreurScript[]
  vue: Vue
  selection: Selection
  resultats: boolean
  pseudo3d: boolean
  /** Vérifications non vérifiées (compteur rouge) et erreurs du script (compteur rouge). */
  nNonOk: number
  nErreurs: number
  onVue: (v: Vue, sel?: Selection) => void
  onReplier: () => void
}) {
  const [replies, setReplies] = useState<Record<string, boolean>>({})
  const m = modele ?? {}
  const sol: Modele[] = Array.isArray(m.sol) ? m.sol : []
  const appuis: [string, Modele][] = m.appuis && typeof m.appuis === 'object' ? Object.entries(m.appuis) : []
  const phases: Modele[] = Array.isArray(m.phases) ? m.phases : []
  const enErreur = (bloc?: string) => !!bloc && erreurs.some((e) => e.chemin.startsWith(bloc))
  const ctx = { resultats, pseudo3d }

  /** Méta affichée à droite d'une étape de saisie (compte, type). */
  const meta = (d: DefVue): string | null => {
    switch (d.cle) {
      case 'sol': return String(sol.length)
      case 'ecran': return NOMS_PAROI[m.paroi?.type] ?? null
      case 'eau': return m.hydraulique?.regime && m.hydraulique.regime !== 'hydrostatique' ? (m.hydraulique.regime === 'differences_finies' ? 'écoulement 2D' : 'simplifié') : (m.eau ? String(Object.keys(m.eau).length) : '0')
      case 'surcharges': return String(Array.isArray(m.surcharges) ? m.surcharges.length : 0)
      case 'appuis': return String(appuis.length)
      case 'phases': return String(phases.length)
      case 'verifs_demandees': return String(Array.isArray(m.verifications) ? m.verifications.length : 0)
      default: return null
    }
  }
  const compteur = (d: DefVue): { texte: string; rouge: boolean } | null => {
    if (d.cle === 'verifications' && nNonOk) return { texte: `${nNonOk} non vérifiée${nNonOk > 1 ? 's' : ''}`, rouge: true }
    if (d.cle === 'script' && nErreurs) return { texte: `${nErreurs} erreur${nErreurs > 1 ? 's' : ''}`, rouge: true }
    return null
  }

  const noeud = (d: DefVue, enfants?: ReactNode) => {
    const replie = replies[d.cle]
    const dispo = vueDisponible(d.cle, ctx)
    const c = compteur(d)
    return (
      <li key={d.cle}>
        <button className={`noeud ${vue === d.cle && !selection ? 'actif' : ''}`} onClick={() => onVue(d.cle)} disabled={!dispo}
          title={dispo ? d.sousTitre : 'Disponible après le calcul'}>
          {enfants ? (
            <span className="chevron" role="button" aria-label={replie ? 'Déplier' : 'Replier'}
              onClick={(e) => { e.stopPropagation(); setReplies({ ...replies, [d.cle]: !replie }) }}>
              {replie ? <IconeChevronD taille={12} /> : <IconeChevronB taille={12} />}
            </span>
          ) : <span className="chevron" />}
          {d.numero ? <span className="numero-etape">{d.numero}</span> : ICONES[d.cle]}
          <span className="libelle">{d.libelle}</span>
          {enErreur(d.bloc) && <span className="erreur-puce" title="Erreur dans ce bloc du script" />}
          {c && <span className={`meta ${c.rouge ? 'rouge' : ''}`}>{c.texte}</span>}
          {!c && meta(d) && <span className="meta">{meta(d)}</span>}
        </button>
        {enfants && !replie && <ul className="arbre" style={{ padding: 0 }}>{enfants}</ul>}
      </li>
    )
  }

  const enfantsDe = (d: DefVue): ReactNode => {
    if (d.cle === 'sol' && sol.length) return sol.map((c, i) => (
      <li key={i}>
        <button className={`noeud enfant ${selection?.type === 'couche' && selection.index === i && vue === 'sol' ? 'actif' : ''}`}
          onClick={() => onVue('sol', { type: 'couche', index: i })}>
          <span className="puce-sol" style={{ background: COULEURS_SOL[i % COULEURS_SOL.length] }} />
          <span className="libelle">{c?.nom ?? `Couche ${i + 1}`}</span>
          <span className="meta">{typeof c?.toit === 'number' ? nb(c.toit, 2) : ''}</span>
        </button>
      </li>
    ))
    if (d.cle === 'appuis' && appuis.length) return appuis.map(([nom, a]) => (
      <li key={nom}>
        <button className={`noeud enfant ${selection?.type === 'appui' && selection.nom === nom && vue === 'appuis' ? 'actif' : ''}`}
          onClick={() => onVue('appuis', { type: 'appui', nom })}>
          <span className="libelle">{nom}</span>
          <span className="meta">{a?.type ?? ''}</span>
        </button>
      </li>
    ))
    if (d.cle === 'phases' && phases.length) return phases.map((ph, i) => (
      <li key={i}>
        <button className={`noeud enfant ${selection?.type === 'phase' && selection.index === i && vue === 'phases' ? 'actif' : ''}`}
          onClick={() => onVue('phases', { type: 'phase', index: i })}>
          <span className="meta">{i + 1}</span>
          <span className="libelle">{ph?.nom ?? `Phase ${i + 1}`}</span>
        </button>
      </li>
    ))
    return undefined
  }

  return (
    <nav className="panneau" aria-label="Navigation">
      <div className="panneau-entete">Données
        <span className="espace" />
        <button className="btn icone discret masquer-etroit" title="Replier la navigation" onClick={onReplier}><IconePanneauG taille={14} /></button>
      </div>
      <div className="panneau-corps">
        <ul className="arbre">{vuesDuGroupe('donnees').map((d) => noeud(d, enfantsDe(d)))}</ul>
        <div className="panneau-entete">Résultats</div>
        <ul className="arbre">{vuesDuGroupe('resultats').filter((d) => d.cle !== 'pseudo3d' || pseudo3d).map((d) => noeud(d))}</ul>
        <div className="panneau-entete">Outils</div>
        <ul className="arbre">{vuesDuGroupe('outils').map((d) => noeud(d))}</ul>
      </div>
    </nav>
  )
}
