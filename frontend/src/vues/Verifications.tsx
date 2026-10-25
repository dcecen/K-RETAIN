import { useEffect, useMemo } from 'react'
import type { ProjetCoupes, Resultats, Verif } from '../lib/api'
import { analyserSelection, verifsPour } from '../vue3d/navigation'
import { pourcent } from '../lib/format'
import { famillesPresentes, LIBELLE_ETAT, libelleFamille, pire, sourceCourte, valeurs } from '../lib/verifs'
import { FicheVerif } from './verifs/FicheVerif'

/** Vue Vérifications : synthèse (tableau par famille, synthèse projet) puis sous-onglets par famille ouvrant les
 *  fiches détaillées (principe, données, étapes, schéma). Un clic sur une ligne de la synthèse ouvre sa fiche. */
export function Verifications({ res, projet, filtre, onRetour, onglet, onOnglet }: {
  res: Resultats; projet?: ProjetCoupes | null; filtre?: string | null; onRetour?: () => void
  onglet: string | null; onOnglet: (famille: string | null) => void
}) {
  const sel = analyserSelection(filtre)
  const vs = useMemo(() => (sel ? verifsPour(sel, res, res.maquette?.assemblages ?? {}) : res.verifications ?? []), [sel, res])
  const familles = useMemo(() => famillesPresentes(vs), [vs])
  const actif = onglet && familles.includes(onglet) ? onglet : familles[0] ?? null
  useEffect(() => { if (actif !== onglet) onOnglet(actif) }, [actif, onglet, onOnglet])
  if (!vs.length) return <div className="vide-centre">Aucune vérification demandée.<span className="note">Les vérifications à mener se choisissent dans le bloc « Vérifications demandées » de l'arborescence.</span></div>
  const groupes = new Map<string, Verif[]>()
  for (const f of familles) groupes.set(f, vs.filter((v) => (v.famille || 'structure') === f))
  const nOk = vs.filter((v) => v.etat === 'ok' || v.etat === 'attention').length
  const nNonOk = vs.filter((v) => v.etat === 'non_ok').length
  const nNonVerifiable = vs.filter((v) => v.etat === 'non_verifiable').length
  const idFiche = (v: Verif) => `fiche-${(res.verifications ?? []).indexOf(v)}`
  const ouvrirFiche = (v: Verif) => {
    onOnglet(v.famille || 'structure')
    setTimeout(() => document.getElementById(idFiche(v))?.scrollIntoView({ block: 'start', behavior: 'smooth' }), 50)
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="barre-outils">
        {sel && onRetour && <button className="btn" onClick={onRetour} title="Revenir à la maquette 3D">Maquette 3D</button>}
        {sel && <span className="doux">Filtre : <b>{filtre}</b></span>}
        <span>Vérifications : {vs.length} ; vérifiées : {nOk} ; non vérifiées : {nNonOk}{nNonVerifiable > 0 && ` ; non vérifiables (valeur de norme manquante) : ${nNonVerifiable}`}</span>
        <span className="espace" />
        <span className="legende-signes">Taux de travail = valeur de calcul / valeur limite. Vérifié si taux ≤ 100 %. Cliquez une ligne pour ouvrir sa fiche.</span>
      </div>
      <div style={{ flex: 1, overflow: 'auto' }}>
        {projet && !projet.unique && projet.coupes.length > 1 && (
          <section className="synthese-projet">
            <h3>Synthèse projet : coupe la plus défavorable par vérification ({projet.coupes.length} coupes)</h3>
            <table className="tableau">
              <thead><tr><th>Vérification</th><th>Élément</th><th>Coupe la plus défavorable</th><th className="num">Taux</th><th>Statut</th></tr></thead>
              <tbody>
                {projet.synthese.verifications.map((v, i) => (
                  <tr key={i} className={`etat-${v.etat}`}>
                    <td>{v.nom}</td><td>{v.element}</td><td>{v.coupe}</td>
                    <td className="num">{v.taux === null ? '—' : pourcent(v.taux)}</td><td className={`statut ${v.etat}`}>{LIBELLE_ETAT[v.etat]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {projet.avertissements.length > 0 && <ul className="doux" style={{ margin: '6px 0 0', paddingLeft: 18 }}>{projet.avertissements.map((a, i) => <li key={i}>{a}</li>)}</ul>}
          </section>
        )}
        <table className="tableau synthese-verifs">
          <thead>
            <tr><th>Vérification</th><th>Élément</th><th>Phase</th><th>Valeur de calcul</th><th>Valeur limite</th><th className="num">Taux</th><th>Statut</th><th>Référence</th></tr>
          </thead>
          <tbody>
            {[...groupes.entries()].map(([famille, liste]) => (
              <Groupe key={famille} nom={libelleFamille(famille)} liste={liste} onOuvrir={ouvrirFiche} />
            ))}
          </tbody>
        </table>
        {res.suggestions && res.suggestions.length > 0 && (
          <div style={{ padding: '10px 12px' }}>
            <div className="insp-titre">Élément de la base matériaux le plus léger satisfaisant la vérification</div>
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {res.suggestions.map((s) => (
                <li key={s.appui}><b>{s.appui}</b> : {s.element ?? '—'} {s.taux !== null && `(taux ${pourcent(s.taux)})`} <span className="doux">{s.message}</span></li>
              ))}
            </ul>
          </div>
        )}
        <div className="onglets-verifs" role="tablist" aria-label="Détail par famille de vérification">
          {familles.map((f) => {
            const liste = groupes.get(f) ?? []
            const etat = pire(liste.map((v) => v.etat))
            return (
              <button key={f} role="tab" aria-selected={f === actif} className={`onglet-verif ${f === actif ? 'actif' : ''} etat-${etat ?? 'ok'}`} onClick={() => onOnglet(f)}>
                {libelleFamille(f)} <span className="compte">{liste.length}</span>
              </button>
            )
          })}
        </div>
        <div className="fiches-verifs">
          {(groupes.get(actif ?? '') ?? []).map((v) => <FicheVerif key={idFiche(v)} v={v} id={idFiche(v)} />)}
        </div>
      </div>
    </div>
  )
}

function Groupe({ nom, liste, onOuvrir }: { nom: string; liste: Verif[]; onOuvrir: (v: Verif) => void }) {
  return (
    <>
      <tr className="groupe"><td colSpan={8}>{nom}</td></tr>
      {liste.map((v, i) => {
        const [calc, lim] = valeurs(v)
        const aConfirmer = /simplifi|confirm|hypoth|supposé/i.test(v.source + v.detail)
        return (
          <tr key={i} className={`etat-${v.etat} cliquable`} title={v.detail + (v.manquants.length ? '\nValeurs manquantes : ' + v.manquants.join(', ') : '') + '\nCliquer : fiche détaillée'}
            onClick={() => onOuvrir(v)} tabIndex={0} onKeyDown={(e) => { if (e.key === 'Enter') onOuvrir(v) }}>
            <td>{v.nom.replace(' [pseudo-3D]', '')}{v.nom.endsWith(' [pseudo-3D]') && <> <span className="mention" title="Efforts de la plaque pseudo-3D (moment vertical, horizontal, tranchant, appuis réels)">(pseudo-3D)</span></>}{aConfirmer && <> <span className="mention">(hypothèse à confirmer)</span></>}</td>
            <td>{v.element}</td>
            <td className="doux">{v.phase ?? '—'}</td>
            <td className="calc">{calc}</td>
            <td className="calc">{lim || (v.manquants.length ? <span className="faible">valeur de norme manquante : {v.manquants.join(', ')}</span> : '')}</td>
            <td className="num">{v.taux === null ? '—' : pourcent(v.taux)}</td>
            <td className={`statut ${v.etat}`}>{LIBELLE_ETAT[v.etat]}</td>
            <td className="doux" style={{ fontSize: 11, maxWidth: 260 }} title={v.source}>{sourceCourte(v.source)}</td>
          </tr>
        )
      })}
    </>
  )
}
