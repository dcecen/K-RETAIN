import { useState, type ReactNode } from 'react'
import type { ErreurScript } from '../lib/api'
import type { Onglet, Section, Selection } from '../lib/etat'
import { nb } from '../lib/format'
import {
  IconeAppui, IconeChevronB, IconeChevronD, IconeCoupe, IconeCube, IconeEau, IconeFichier, IconeParoi, IconePhases, IconeProjet, IconeSol,
  IconeSurcharge, IconeTableau, IconeVerif,
} from '../lib/icones'
import type { Modele } from '../lib/scriptDoc'
import { COULEURS_SOL } from '../lib/theme'

const NOMS_PAROI: Record<string, string> = {
  palplanche: 'Palplanches', paroi_moulee: 'Paroi moulée', pieux_secants: 'Pieux sécants',
  pieux_disjoints: 'Pieux disjoints', berlinoise: 'Berlinoise',
}

/** Onglets de résultats accessibles depuis l'arborescence. */
const RESULTATS: { cle: Onglet; libelle: string }[] = [
  { cle: 'coupe', libelle: 'Coupe et diagrammes' },
  { cle: 'efforts', libelle: "Efforts d'appui" },
  { cle: 'verifications', libelle: 'Vérifications' },
  { cle: 'hypotheses', libelle: 'Hypothèses et référentiel' },
  { cle: '3d', libelle: 'Maquette 3D' },
]

/** Arborescence du projet : données d'entrée (un clic ouvre le formulaire de saisie) et résultats (un clic ouvre l'onglet). */
export function Navigation({ modele, erreurs, section, selection, onglet, resultats, onChoisir, onOnglet }: {
  modele: Modele
  erreurs: ErreurScript[]
  section: Section | null
  selection: Selection
  onglet: Onglet
  resultats: boolean
  onChoisir: (s: Section, sel?: Selection) => void
  onOnglet: (o: Onglet) => void
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
    <nav className="panneau" aria-label="Projet">
      <div className="panneau-entete">Données</div>
      <div className="panneau-corps">
        <ul className="arbre">
          {groupe('projet', <IconeProjet />, 'Projet', null)}
          {groupe('sol', <IconeSol />, 'Sols', String(sol.length), sol.map((c, i) => (
            <li key={i}>
              <button className={`noeud enfant ${selection?.type === 'couche' && selection.index === i ? 'actif' : ''}`}
                onClick={() => onChoisir('sol', { type: 'couche', index: i })}>
                <span className="puce-sol" style={{ background: COULEURS_SOL[i % COULEURS_SOL.length] }} />
                <span className="libelle">{c?.nom ?? `Couche ${i + 1}`}</span>
                <span className="meta">{typeof c?.toit === 'number' ? nb(c.toit, 2) : ''}</span>
              </button>
            </li>
          )))}
          {groupe('paroi', <IconeParoi />, 'Écran', NOMS_PAROI[m.paroi?.type] ?? null)}
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
          {groupe('verifications', <IconeVerif />, 'Vérifications demandées', String(Array.isArray(m.verifications) ? m.verifications.length : 0))}
        </ul>
      </div>
      <div className="panneau-entete">Résultats</div>
      <div className="panneau-corps" style={{ flex: '0 0 auto' }}>
        <ul className="arbre">
          {RESULTATS.map((r) => (
            <li key={r.cle}>
              <button className={`noeud ${onglet === r.cle && section === null ? 'actif' : ''}`} onClick={() => onOnglet(r.cle)}
                disabled={!resultats} title={resultats ? undefined : 'Disponible après le calcul'}>
                <span className="chevron" />
                {r.cle === 'coupe' ? <IconeCoupe /> : r.cle === 'efforts' ? <IconeTableau /> : r.cle === 'verifications' ? <IconeVerif /> : r.cle === 'hypotheses' ? <IconeFichier /> : <IconeCube />}
                <span className="libelle">{r.libelle}</span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </nav>
  )
}
