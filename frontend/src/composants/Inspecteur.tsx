import type { Resultats } from '../lib/api'
import type { Selection } from '../lib/etat'
import { cote, nb, pourcent } from '../lib/format'
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
    <aside className="panneau" aria-label="Inspecteur">
      <div className="panneau-entete">
        Inspecteur
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
    return <div className="insp-section doux">Aucun résultat. Lancez le calcul (Recalculer ou Ctrl+Entrée).</div>
  }
  const ph = res.phases[Math.min(phase, res.phases.length - 1)]
  const s = ph.synthese
  const butons = (ph.appuis ?? []).filter((a) => a.type === 'buton' || a.type === 'bracon')
  const maxButon = butons.reduce<null | (typeof butons)[number]>((m, a) => (!m || a.effort_axial_kN > m.effort_axial_kN ? a : m), null)
  const Mabs = s ? (Math.abs(s.M_max) >= Math.abs(s.M_min) ? s.M_max : s.M_min) : null
  const alertes = (res.verifications ?? []).filter((v) => v.etat === 'non_ok' || (v.taux !== null && v.taux > 0.9))
  return (
    <>
      <div className="insp-section">
        <div className="insp-titre">Phase {phase + 1} / {res.phases.length}</div>
        <div className="insp-nom">{ph.nom}</div>
        <dl className="lignes-cle">
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
          <div className="insp-titre">Chiffres clés</div>
          <div className="chiffres">
            <div className="chiffre"><div className="lib">Déplacement max</div>
              <div className="val">{nb(s?.y_max_mm)}<small>mm</small></div><div className="sous">à {nb(s?.z_y_max, 2)} m</div></div>
            <div className="chiffre"><div className="lib">Moment max</div>
              <div className="val">{nb(Mabs, 0)}<small>kN·m/m</small></div><div className="sous">{Mabs !== null && Mabs >= 0 ? 'face fouille tendue' : 'face terre tendue'}</div></div>
            <div className="chiffre"><div className="lib">Effort max par buton</div>
              <div className="val">{maxButon ? nb(maxButon.effort_axial_kN, 0) : '—'}<small>{maxButon ? 'kN' : ''}</small></div>
              <div className="sous">{maxButon ? maxButon.nom : 'aucun buton posé'}</div></div>
            <div className="chiffre"><div className="lib">Butée mobilisée</div>
              <div className="val">{pourcent(s?.butee_mobilisee)}</div><div className="sous">Bm/Bt caractéristique</div></div>
            {ph.hydro && ph.hydro.regime !== 'hydrostatique' && (
              <>
                <div className="chiffre"><div className="lib">Gradient de sortie</div>
                  <div className="val" style={{ color: ph.hydro.gradient_sortie_max >= 0.9 ? 'var(--rouge)' : undefined }}>{nb(ph.hydro.gradient_sortie_max, 3)}</div>
                  <div className="sous">{ph.hydro.bouchon ? `bouchon ${ph.hydro.bouchon.type} : i = ${nb(ph.hydro.gradient_bouchon, 2)}` : 'au fond de fouille, contre l’écran'}</div></div>
                <div className="chiffre"><div className="lib">Débit de pompage</div>
                  <div className="val">{nb(ph.hydro.debit_m3_h_m, 3)}<small>m³/h/m</small></div><div className="sous">{ph.hydro.regime === 'differences_finies' ? 'réseau d’écoulement 2D' : 'régime simplifié'}</div></div>
              </>
            )}
          </div>
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
        <div className="insp-titre">Alertes</div>
        {res.avertissements.map((a, i) => <div key={i} className="alerte orange"><IconeAlerte />{a}</div>)}
        {alertes.map((v, i) => (
          <div key={`v${i}`} className={`alerte ${v.etat === 'non_ok' ? 'rouge' : 'orange'}`}><IconeAlerte />
            <span>{v.nom} — {v.element} : {v.taux !== null ? pourcent(v.taux) : 'non vérifié'}</span></div>
        ))}
        {res.avertissements.length === 0 && alertes.length === 0 && (
          <div className="alerte info"><IconeInfo />Aucune vérification au-delà de 90 %.
            {(res.verifications ?? []).some((v) => v.etat === 'non_verifiable') && ' Certaines sont non vérifiables (valeurs de norme manquantes).'}</div>
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
        {ligne('Toit', c.toit, 'm')}{ligne('γ', c.gamma, 'kN/m³')}{ligne('γ′', c.gamma_dejauge, 'kN/m³')}
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
          {ligne('Élément', a?.element)}{ligne('Cote', a?.cote, 'm')}{ligne('Espacement', a?.espacement ?? 1, 'm')}
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
