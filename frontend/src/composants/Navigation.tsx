import { useState, type ReactNode } from 'react'
import type { ErreurScript } from '../lib/api'
import type { Section, Selection } from '../lib/etat'
import { nb } from '../lib/format'
import {
  IconeAppui, IconeChevronB, IconeChevronD, IconeEau, IconeParoi, IconePhases, IconeProjet, IconeSol,
  IconeSurcharge, IconeVerif,
} from '../lib/icones'
import type { Modele } from '../lib/scriptDoc'
import { COULEURS_SOL } from '../lib/theme'

const NOMS_PAROI: Record<string, string> = {
  palplanche: 'Palplanches', paroi_moulee: 'Paroi moulée', pieux_secants: 'Pieux sécants',
  pieux_disjoints: 'Pieux disjoints', berlinoise: 'Berlinoise',
}

/** Arborescence du modèle ; un clic ouvre le formulaire de saisie correspondant. */
export function Navigation({ modele, erreurs, section, selection, onChoisir }: {
  modele: Modele
  erreurs: ErreurScript[]
  section: Section | null
  selection: Selection
  onChoisir: (s: Section, sel?: Selection) => void
}) {
  const [replies, setReplies] = useState<Record<string, boolean>>({})
  const m = modele ?? {}
  const sol: Modele[] = Array.isArray(m.sol) ? m.sol : []
  const appuis: [string, Modele][] = m.appuis && typeof m.appuis === 'object' ? Object.entries(m.appuis) : []
  const phases: Modele[] = Array.isArray(m.phases) ? m.phases : []
  const enErreur = (prefixe: string) => erreurs.some((e) => e.chemin.startsWith(prefixe))

  const groupe = (cle: Section, icone: ReactNode, libelle: string, meta: string | null, enfants?: ReactNode) => {
    const replie = replies[cle]
    return (
      <li>
        <button className={`noeud ${section === cle && !selection ? 'actif' : ''}`} onClick={() => onChoisir(cle, null)}>
          <span className="chevron" onClick={(e) => { if (enfants) { e.stopPropagation(); setReplies({ ...replies, [cle]: !replie }) } }}>
            {enfants ? (replie ? <IconeChevronD taille={12} /> : <IconeChevronB taille={12} />) : null}
          </span>
          {icone}
          <span className="libelle">{libelle}</span>
          {enErreur(cle) && <span className="erreur-puce" title="Erreur dans ce bloc" />}
          {meta && <span className="meta">{meta}</span>}
        </button>
        {enfants && !replie && <ul className="arbre" style={{ padding: 0 }}>{enfants}</ul>}
      </li>
    )
  }

  return (
    <nav className="panneau" aria-label="Modèle">
      <div className="panneau-entete">Modèle</div>
      <div className="panneau-corps">
        <ul className="arbre">
          {groupe('projet', <IconeProjet />, 'Projet', null)}
          {groupe('sol', <IconeSol />, 'Sol', String(sol.length), sol.map((c, i) => (
            <li key={i}>
              <button className={`noeud enfant ${selection?.type === 'couche' && selection.index === i ? 'actif' : ''}`}
                onClick={() => onChoisir('sol', { type: 'couche', index: i })}>
                <span className="puce-sol" style={{ background: COULEURS_SOL[i % COULEURS_SOL.length] }} />
                <span className="libelle">{c?.nom ?? `Couche ${i + 1}`}</span>
                <span className="meta">{typeof c?.toit === 'number' ? nb(c.toit, 2) : ''}</span>
              </button>
            </li>
          )))}
          {groupe('paroi', <IconeParoi />, 'Paroi', NOMS_PAROI[m.paroi?.type] ?? null)}
          {groupe('eau', <IconeEau />, 'Eau', m.hydraulique?.regime && m.hydraulique.regime !== 'hydrostatique' ? (m.hydraulique.regime === 'differences_finies' ? 'écoulement 2D' : 'simplifié') : (m.eau ? String(Object.keys(m.eau).length) : '0'))}
          {groupe('surcharges', <IconeSurcharge />, 'Surcharges', String(Array.isArray(m.surcharges) ? m.surcharges.length : 0))}
          {groupe('appuis', <IconeAppui />, 'Appuis', String(appuis.length), appuis.map(([nom, a]) => (
            <li key={nom}>
              <button className={`noeud enfant ${selection?.type === 'appui' && selection.nom === nom ? 'actif' : ''}`}
                onClick={() => onChoisir('appuis', { type: 'appui', nom })}>
                <span className="libelle">{nom}</span>
                <span className="meta">{a?.type ?? ''}</span>
              </button>
            </li>
          )))}
          {groupe('phases', <IconePhases />, 'Phases', String(phases.length), phases.map((ph, i) => (
            <li key={i}>
              <button className={`noeud enfant ${selection?.type === 'phase' && selection.index === i ? 'actif' : ''}`}
                onClick={() => onChoisir('phases', { type: 'phase', index: i })}>
                <span className="meta">{i + 1}</span>
                <span className="libelle">{ph?.nom ?? `Phase ${i + 1}`}</span>
              </button>
            </li>
          )))}
          {groupe('verifications', <IconeVerif />, 'Vérifications', String(Array.isArray(m.verifications) ? m.verifications.length : 0))}
        </ul>
      </div>
    </nav>
  )
}
