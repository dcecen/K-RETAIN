import type { Resultats } from '../lib/api'
import { couleurEtat, etatHydraulique } from '../lib/verifs'
import type { Selection } from '../lib/etat'
import { cote, nb, pourcent, uniteCote } from '../lib/format'
import { IconeAlerte, IconeFermer, IconeInfo } from '../lib/icones'
import type { Modele } from '../lib/scriptDoc'
import { COULEURS_SOL } from '../lib/theme'

/** Panneau droit : la phase active, ou l'élément sélectionné (couche, appui, phase). */
export function Inspecteur({ res, phase, selection, modele, onSelection }: {
  res: Resultats | null
  phase: number
  selection: Selection
  modele: Modele
  onSelection: (s: Selection) => void
}) {
  return (
    <aside className="panneau" aria-label="Phase et résultats">
      <div className="panneau-entete">
        Phase et résultats
        <span className="espace" />
        {selection && (
          <button className="btn icone discret" title="Revenir à la phase active" onClick={() => onSelection(null)}>
            <IconeFermer taille={14} />
          </button>
        )}
      </div>
      <div className="panneau-corps">
        {selection?.type === 'couche' ? <Couche modele={modele} index={selection.index} />
          : selection?.type === 'appui' ? <Appui res={res} modele={modele} nom={selection.nom} phase={phase} />
          : <PhaseActive res={res} phase={selection?.type === 'phase' ? selection.index + 1 : phase} onSelection={onSelection} />}
      </div>
    </aside>
  )
}

function PhaseActive({ res, phase, onSelection }: { res: Resultats | null; phase: number; onSelection: (s: Selection) => void }) {
  if (!res) {
    return <div className="insp-section doux">Aucun calcul. Calcul : bouton « Calculer » ou Ctrl+Entrée.</div>
  }
  const ph = res.phases[Math.min(phase, res.phases.length - 1)]
  const s = ph.synthese
  const butons = (ph.appuis ?? []).filter((a) => a.type === 'buton' || a.type === 'bracon')
  const maxButon = butons.reduce<null | (typeof butons)[number]>((m, a) => (!m || a.effort_axial_kN > m.effort_axial_kN ? a : m), null)
  const alertes = (res.verifications ?? []).filter((v) => v.etat === 'non_ok' || v.etat === 'attention')   // états fixés par le calcul
  return (
    <>
      <div className="insp-section">
        <div className="insp-titre">Phase {phase + 1} / {res.phases.length}</div>
        <div className="insp-nom">{ph.nom}</div>
        <dl className="lignes-cle">
          {ph.parent !== null && ph.parent !== phase - 1 && <><dt>Phase de départ</dt><dd style={{ fontFamily: 'inherit' }}>{res.phases[ph.parent]?.nom}</dd></>}
          <dt>Fond de fouille</dt><dd>{cote(ph.terrain_aval)}</dd>
          <dt>Terrain amont</dt><dd>{cote(ph.terrain_amont)}</dd>
          <dt>Nappe amont</dt><dd>{cote(ph.eau_amont)}</dd>
          <dt>Nappe aval</dt><dd>{cote(ph.eau_aval)}</dd>
        </dl>
        {ph.actions.length > 0 && <div className="note" style={{ marginTop: 6 }}>{ph.actions.map((a) => a.texte).join(' · ')}</div>}
      </div>
      {!ph.ok ? (
        <div className="insp-section"><div className="alerte rouge"><IconeAlerte />{ph.message}</div></div>
      ) : (
        <div className="insp-section">
          <div className="insp-titre">Résultats de la phase</div>
          <dl className="lignes-cle">
            <dt>Déplacement max</dt><dd>{nb(s?.y_max_mm)} mm à {nb(s?.z_y_max, 2)} m</dd>
            <dt>Moment max</dt><dd>{nb(s?.M_max, 0)} kN·m/m</dd>
            <dt>Moment min</dt><dd>{nb(s?.M_min, 0)} kN·m/m</dd>
            <dt>Tranchant max</dt><dd>{nb(s?.V_absmax, 0)} kN/m</dd>
            <dt title="Bm / Bt, valeurs caractéristiques">Butée mobilisée Bm/Bt</dt><dd>{pourcent(s?.butee_mobilisee)}</dd>
            {maxButon && <><dt>Effort max par buton</dt><dd>{nb(maxButon.effort_axial_kN, 0)} kN ({maxButon.nom})</dd></>}
            {ph.hydro && ph.hydro.regime !== 'hydrostatique' && (
              <>
                <dt>Gradient de sortie max</dt>
                <dd style={{ color: couleurEtat(etatHydraulique(res, ph.nom)) }}>{nb(ph.hydro.gradient_sortie_max, 3)}{ph.hydro.bouchon ? ` (bouchon ${ph.hydro.bouchon.type} : i = ${nb(ph.hydro.gradient_bouchon, 2)})` : ''}</dd>
                <dt>Débit de pompage</dt><dd>{nb(ph.hydro.debit_m3_h_m, 3)} m³/h/m ({ph.hydro.regime === 'differences_finies' ? 'écoulement 2D' : 'régime simplifié'})</dd>
              </>
            )}
          </dl>
          <div className="note" style={{ marginTop: 6 }}>Signes : y positif vers la fouille ; M positif quand la face côté fouille est tendue.</div>
        </div>
      )}
      <div className="insp-section">
        <div className="insp-titre">Appuis actifs</div>
        {(ph.appuis ?? []).length === 0 ? <div className="note">Aucun appui posé dans cette phase.</div> : (
          <ul className="liste-appuis">
            {(ph.appuis ?? []).map((a) => (
              <li key={a.nom} className={a.actif ? '' : 'inactif'} onClick={() => onSelection({ type: 'appui', nom: a.nom })}
                title={a.actif ? 'Afficher l’appui' : 'Appui décollé'}>
                <span style={{ fontWeight: 500, minWidth: 34 }}>{a.nom}</span>
                <span className="doux">{a.type}</span>
                <span className="espace" />
                <span className="num">{nb(a.effort_kN_m)} <span className="faible">kN/m</span></span>
                <span className="num" style={{ minWidth: 70 }}>{nb(a.effort_axial_kN, 0)} <span className="faible">kN</span></span>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="insp-section">
        <div className="insp-titre">Avertissements et vérifications à taux ≥ 90 %</div>
        {res.avertissements.map((a, i) => <div key={i} className="alerte orange"><IconeAlerte />{a}</div>)}
        {alertes.map((v, i) => (
          <div key={`v${i}`} className={`alerte ${v.etat === 'non_ok' ? 'rouge' : 'orange'}`}><IconeAlerte />
            <span>{v.nom}, {v.element} : {v.taux !== null ? `taux ${pourcent(v.taux)}` : 'non vérifiable'}{v.etat === 'non_ok' ? ', non vérifié' : ''}</span></div>
        ))}
        {res.avertissements.length === 0 && alertes.length === 0 && (
          <div className="alerte info"><IconeInfo />Aucun avertissement ; toutes les vérifications ont un taux inférieur à 90 %.
            {(res.verifications ?? []).some((v) => v.etat === 'non_verifiable') && ' Certaines sont non vérifiables (valeur de norme manquante).'}</div>
        )}
      </div>
    </>
  )
}

function Couche({ modele, index }: { modele: Modele; index: number }) {
  const c = modele?.sol?.[index]
  if (!c) return <div className="insp-section doux">Couche introuvable.</div>
  const ligne = (t: string, v: unknown, u = '') => (v === undefined || v === null ? null : <><dt>{t}</dt><dd>{typeof v === 'number' ? nb(v, Number.isInteger(v) ? 0 : 2) : String(v)} {u}</dd></>)
  return (
    <div className="insp-section">
      <div className="insp-titre"><span className="puce-sol" style={{ background: COULEURS_SOL[index % COULEURS_SOL.length] }} /> Couche {index + 1}</div>
      <div className="insp-nom">{c.nom}</div>
      <dl className="lignes-cle">
        {ligne('Cote du toit', c.toit, uniteCote(modele))}{ligne('γ', c.gamma, 'kN/m³')}{ligne('γ′', c.gamma_dejauge, 'kN/m³')}
        {ligne('φ′', c.phi, '°')}{ligne('c′', c.c ?? 0, 'kPa')}{ligne('EM', c.EM, 'kPa')}{ligne('α', c.alpha)}
        {ligne('pl', c.pl, 'kPa')}{ligne('qc', c.qc, 'kPa')}{ligne('kh imposé', c.kh, 'kN/m³')}
        {ligne('δa/φ′', c.delta_a_sur_phi ?? 0)}{ligne('δp/φ′', c.delta_p_sur_phi ?? 0)}{ligne('K0', c.K0)}
      </dl>
    </div>
  )
}

function Appui({ res, modele, nom, phase }: { res: Resultats | null; modele: Modele; nom: string; phase: number }) {
  const a = modele?.appuis?.[nom]
  const def = res?.appuis.find((x) => x.nom === nom)
  const dim = res?.dimensionnant.appuis?.[nom]
  const ligne = (t: string, v: unknown, u = '') => (v === undefined || v === null ? null : <><dt>{t}</dt><dd>{typeof v === 'number' ? nb(v, Number.isInteger(v) ? 0 : 2) : String(v)} {u}</dd></>)
  return (
    <>
      <div className="insp-section">
        <div className="insp-titre">Appui</div>
        <div className="insp-nom">{nom} <span className="doux" style={{ fontWeight: 400 }}>{a?.type}</span></div>
        <dl className="lignes-cle">
          {ligne('Élément', a?.element)}{ligne('Cote', a?.cote, uniteCote(modele))}{ligne('Espacement', a?.espacement ?? 1, 'm')}
          {ligne('Longueur', a?.longueur, 'm')}{ligne('Angle', a?.angle ?? 0, '°')}{ligne('Précharge', a?.precharge ?? 0, 'kN')}
          {ligne('Lierne', a?.lierne)}{ligne('Raideur', def ? Math.round(def.raideur) : null, 'kN/m/m')}
        </dl>
      </div>
      {res && (
        <div className="insp-section">
          <div className="insp-titre">Effort par phase</div>
          <table className="tableau">
            <thead><tr><th>Phase</th><th className="num">kN/m</th><th className="num">kN</th></tr></thead>
            <tbody>
              {res.phases.map((p, i) => {
                const e = p.appuis?.find((x) => x.nom === nom)
                return e ? (
                  <tr key={i} className={i === phase ? 'actif' : ''}>
                    <td>{i + 1}. {p.nom}</td><td className="num">{nb(e.effort_kN_m)}</td><td className="num">{nb(e.effort_axial_kN, 0)}</td>
                  </tr>
                ) : null
              })}
            </tbody>
          </table>
          {dim && <div className="note" style={{ marginTop: 6 }}>Maximum : {nb(dim.effort_axial_kN, 0)} kN ({dim.phase})</div>}
        </div>
      )}
    </>
  )
}
