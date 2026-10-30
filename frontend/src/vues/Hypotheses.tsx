import { useEffect, useMemo, useState } from 'react'
import { api, type EntreeNorme, type Resultats } from '../lib/api'
import { telechargerTexte } from '../lib/exporter'
import { interp, nb, pourcent, uniteCote } from '../lib/format'
import type { Modele } from '../lib/scriptDoc'

/** Intitulé des fichiers de docs/normes. */
const FICHIERS: Record<string, string> = {
  nf_p94_282: 'NF P 94-282 (écrans de soutènement) et EN 1997-1 (Eurocode 7) avec annexe nationale',
  ec2: 'EN 1992-1-1 (Eurocode 2, béton)',
  ec3: 'EN 1993-1-1 et EN 1993-5 (Eurocode 3, acier et palplanches)',
  ec3_assemblages: 'EN 1993-1-8 (Eurocode 3, assemblages)',
  hydraulique: 'Critères hydrauliques (Terzaghi, Lane, bouchons)',
}

/** Paires (z, v) triées par z croissant, pour interpoler une courbe donnée dans n'importe quel ordre. */
function courbe(z: number[], v: number[]): [number[], number[]] {
  const idx = z.map((_, i) => i).sort((a, b) => z[a] - z[b])
  return [idx.map((i) => z[i]), idx.map((i) => v[i])]
}

function extremum(z: number[] | undefined, v: number[] | undefined, quoi: 'max' | 'min' | 'abs'): { v: number; z: number } | null {
  if (!z || !v || !v.length) return null
  let k = 0
  for (let i = 1; i < v.length; i++) {
    const a = quoi === 'abs' ? Math.abs(v[i]) : v[i], b = quoi === 'abs' ? Math.abs(v[k]) : v[k]
    if (quoi === 'min' ? a < b : a > b) k = i
  }
  return { v: v[k], z: z[k] }
}

/** Onglet « Hypothèses et référentiel » : méthode, normes et coefficients lus, coefficients de sol
 *  utilisés par le calcul, écran, conventions, valeurs intermédiaires de la phase active. */
export function Hypotheses({ res, modele, phase, version }: { res: Resultats; modele: Modele; phase: number; version: string }) {
  const [normes, setNormes] = useState<Record<string, EntreeNorme[]> | null>(null)
  const [erreurNormes, setErreurNormes] = useState<string | null>(null)
  useEffect(() => { api.normes().then((d) => setNormes(d.fichiers)).catch((e) => setErreurNormes(String(e?.message ?? e))) }, [])
  const unite = uniteCote(modele)
  const ph = res.phases[Math.min(phase, res.phases.length - 1)]
  const s = ph.synthese
  const approche = normes?.nf_p94_282?.find((e) => e.cle === 'approche_de_calcul')
  const sol: Modele[] = Array.isArray(modele?.sol) ? modele.sol : []
  const deltas = (nom: string) => sol.find((c) => c?.nom === nom)

  const yMax = extremum(ph.z, ph.y_mm, 'abs')
  const mMax = extremum(ph.z_diag, ph.M, 'max')
  const mMin = extremum(ph.z_diag, ph.M, 'min')
  const vMax = extremum(ph.z_diag, ph.V, 'abs')

  /** Profil des pressions de la phase active sur la grille amont, aval et eau interpolés. */
  const profil = useMemo(() => {
    const p = ph.pressions, e = ph.eau
    if (!p || !e) return []
    const [za, pa] = courbe(p.amont.z, p.amont.pa), [, pm] = courbe(p.amont.z, p.amont.p), [, p0] = courbe(p.amont.z, p.amont.p0)
    const [zv, pp] = courbe(p.aval.z, p.aval.pp), [, pv] = courbe(p.aval.z, p.aval.p)
    const [ze, ua] = courbe(e.z, e.u_amont), [, uv] = courbe(e.z, e.u_aval)
    return za.map((z, i) => ({
      z, p0: p0[i], pa: pa[i], p_amont: pm[i], u_amont: interp(ze, ua, z), pp: interp(zv, pp, z), p_aval: interp(zv, pv, z), u_aval: interp(ze, uv, z),
    })).sort((a, b) => b.z - a.z)
  }, [ph])
  const exporterCsv = () => {
    const lignes = [`cote (${unite});p0 amont (kPa);poussee limite pa (kPa);pression amont mobilisee (kPa);u amont (kPa);butee limite pp (kPa);pression aval mobilisee (kPa);u aval (kPa)`]
    const f = (v: number | null) => (v === null || v === undefined ? '' : String(Math.round(v * 1000) / 1000).replace('.', ','))
    for (const l of profil) lignes.push([l.z, l.p0, l.pa, l.p_amont, l.u_amont, l.pp, l.p_aval, l.u_aval].map((v) => f(v as number | null)).join(';'))
    telechargerTexte(lignes.join('\n'), `pressions_${ph.nom.replace(/[^\w-]+/g, '_')}.csv`, 'text/csv;charset=utf-8')
  }

  return (
    <div className="saisie" style={{ maxWidth: 1400 }}>
      <h2>Hypothèses et référentiel</h2>
      <p className="aide">Valeurs telles qu'utilisées par le calcul affiché. Les coefficients de norme sont lus dans docs/normes ; chaque valeur porte sa source et son statut de relecture.</p>

      <div className="bloc"><div className="bloc-titre">Méthode de calcul</div>
        <dl className="lignes-cle" style={{ padding: '8px 12px', gridTemplateColumns: 'max-content 1fr' }}>
          <dt>Logiciel</dt><dd style={{ textAlign: 'left', fontFamily: 'inherit' }}>K-Retain {version}</dd>
          <dt>Modèle</dt><dd style={{ textAlign: 'left', fontFamily: 'inherit' }}>Écran en poutre d'Euler-Bernoulli sur ressorts élasto-plastiques (méthode aux coefficients de réaction, type MISS), calcul phasé avec mémoire des ressorts.</dd>
          <dt>Approche de calcul</dt><dd style={{ textAlign: 'left', fontFamily: 'inherit' }}>{approche ? <>{String(approche.valeur ?? 'non renseignée')} <span className="doux">({approche.source})</span></> : erreurNormes ? <span className="faible">référentiel indisponible : {erreurNormes}</span> : 'lecture en cours'}</dd>
          <dt>Documents de référence</dt><dd style={{ textAlign: 'left', fontFamily: 'inherit' }}>{Object.keys(normes ?? {}).map((f) => FICHIERS[f] ?? f).join(' ; ') || '—'}</dd>
          <dt>Cotes</dt><dd style={{ textAlign: 'left', fontFamily: 'inherit' }}>{unite}, axe vertical vers le haut.</dd>
          {Object.entries(res.conventions ?? {}).map(([k, v]) => <Convention key={k} cle={k} texte={v} />)}
        </dl>
      </div>

      <div className="bloc"><div className="bloc-titre">Écran</div>
        <dl className="lignes-cle" style={{ padding: '8px 12px', gridTemplateColumns: 'max-content 1fr' }}>
          <dt>Type</dt><dd style={{ textAlign: 'left', fontFamily: 'inherit' }}>{String(res.paroi.type ?? '—')}{res.paroi.profil ? `, ${String(res.paroi.profil)}` : ''}</dd>
          <dt>Tête / pied</dt><dd style={{ textAlign: 'left' }}>{nb(res.paroi.tete, 2)} / {nb(res.paroi.pied, 2)} {unite}</dd>
          {typeof res.paroi.EI === 'number' && <><dt>EI</dt><dd style={{ textAlign: 'left' }}>{nb(res.paroi.EI, 0)} kN·m²/m <span className="doux" style={{ fontFamily: 'var(--police)' }}>({String(res.paroi.EI_source ?? '')})</span></dd></>}
          {typeof res.paroi.rapport_largeur_fiche === 'number' && <><dt>Largeur de réaction sous le fond</dt><dd style={{ textAlign: 'left' }}>{pourcent(res.paroi.rapport_largeur_fiche)} de l'entraxe</dd></>}
        </dl>
      </div>

      <div className="bloc"><div className="bloc-titre">Coefficients de sol utilisés par le calcul</div>
        <table className="tableau">
          <thead><tr><th>Couche</th><th className="num">Toit<span className="unite">{unite}</span></th><th className="num">φ'<span className="unite">°</span></th><th className="num">c'<span className="unite">kPa</span></th>
            <th className="num">δa/φ'</th><th className="num">δp/φ'</th><th className="num">Ka</th><th className="num">Kp</th><th className="num">K0</th><th>Source de K0</th><th className="num">kh<span className="unite">kN/m³</span></th><th>Méthode de kh</th></tr></thead>
          <tbody>
            {res.couches.map((c, i) => {
              const d = deltas(c.nom)
              return (
                <tr key={i}>
                  <td>{c.nom}</td><td className="num">{nb(c.toit, 2)}</td>
                  <td className="num">{nb(c.phi ?? d?.phi, 1)}</td><td className="num">{nb(c.c ?? d?.c ?? 0, 1)}</td>
                  <td className="num">{nb(c.delta_a_sur_phi ?? d?.delta_a_sur_phi ?? 0, 2)}</td><td className="num">{nb(c.delta_p_sur_phi ?? d?.delta_p_sur_phi ?? 0, 2)}</td>
                  <td className="num">{nb(c.kah, 3)}</td><td className="num">{nb(c.kph, 2)}</td><td className="num">{nb(c.k0, 3)}</td><td className="doux">{c.k0_source ?? ''}</td>
                  <td className="num">{nb(c.kh, 0)}</td><td className="doux">{c.methode_kh ?? ''}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
        <p className="note" style={{ padding: '6px 12px' }}>Ka et Kp : coefficients horizontaux de poussée et de butée, {res.couches[0]?.methode_k ?? 'méthode du script'}. La cohésion est prise en compte par les états correspondants (termes 2c√Ka et 2c√Kp). Une valeur « — » signifie que le coefficient n'a pas pu être évalué (domaine de validité, table absente).</p>
      </div>

      <div className="bloc"><div className="bloc-titre">{phase === 0 ? 'État initial' : `Phase ${phase}`} : {ph.nom}</div>
        {!ph.ok ? <div className="alerte rouge" style={{ margin: 8 }}>{ph.message}</div> : (
          <>
            <table className="tableau" style={{ width: 'auto' }}>
              <thead><tr><th>Grandeur</th><th className="num">Valeur</th><th>Unité</th><th className="num">Cote ({unite})</th></tr></thead>
              <tbody>
                <tr><td>Déplacement maximal |y|</td><td className="num">{nb(yMax?.v)}</td><td>mm</td><td className="num">{nb(yMax?.z, 2)}</td></tr>
                <tr><td>Moment maximal (face côté fouille tendue)</td><td className="num">{nb(mMax?.v, 1)}</td><td>kN·m/m</td><td className="num">{nb(mMax?.z, 2)}</td></tr>
                <tr><td>Moment minimal (face côté terre tendue)</td><td className="num">{nb(mMin?.v, 1)}</td><td>kN·m/m</td><td className="num">{nb(mMin?.z, 2)}</td></tr>
                <tr><td>Effort tranchant maximal |V|</td><td className="num">{nb(vMax?.v, 1)}</td><td>kN/m</td><td className="num">{nb(vMax?.z, 2)}</td></tr>
                <tr><td>Butée mobilisée Bm (résultante des pressions aval)</td><td className="num">{nb(s?.Bm_kN_m, 1)}</td><td>kN/m</td><td /></tr>
                <tr><td>Butée limite Bt (résultante des pressions limites aval)</td><td className="num">{nb(s?.Bt_kN_m, 1)}</td><td>kN/m</td><td /></tr>
                <tr><td>Taux de mobilisation Bm/Bt (caractéristique)</td><td className="num">{pourcent(s?.butee_mobilisee, 1)}</td><td /><td /></tr>
                <tr><td>Itérations du solveur</td><td className="num">{ph.iterations ?? '—'}</td><td /><td /></tr>
                {(ph.appuis ?? []).map((a) => (
                  <tr key={a.nom}><td>Effort dans {a.nom} ({a.type}){a.actif ? '' : ', décollé'}</td><td className="num">{nb(a.effort_kN_m, 1)} / {nb(a.effort_axial_kN, 0)}</td><td>kN/m / kN par appui</td><td className="num">{nb(a.cote, 2)}</td></tr>
                ))}
              </tbody>
            </table>
            <div className="bloc-titre" style={{ borderTop: '1px solid var(--filet)' }}>Pressions le long de l'écran (kPa, valeurs caractéristiques)
              <span className="espace" /><button className="btn" onClick={exporterCsv}>Exporter en CSV</button></div>
            <div style={{ maxHeight: 360, overflow: 'auto' }}>
              <table className="tableau compact">
                <thead><tr><th className="num">Cote<span className="unite">{unite}</span></th><th className="num">p0 amont</th><th className="num">Poussée limite pa</th><th className="num">Amont mobilisée</th><th className="num">u amont</th>
                  <th className="num">Butée limite pp</th><th className="num">Aval mobilisée</th><th className="num">u aval</th></tr></thead>
                <tbody>
                  {profil.map((l, i) => (
                    <tr key={i}><td className="num">{nb(l.z, 2)}</td><td className="num">{nb(l.p0)}</td><td className="num">{nb(l.pa)}</td><td className="num">{nb(l.p_amont)}</td><td className="num">{nb(l.u_amont)}</td>
                      <td className="num">{nb(l.pp)}</td><td className="num">{nb(l.p_aval)}</td><td className="num">{nb(l.u_aval)}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="note" style={{ padding: '6px 12px' }}>Pressions effectives horizontales des terres ; eau à part (u). Au-dessus du fond de fouille, les colonnes aval sont vides.</p>
          </>
        )}
      </div>

      <div className="bloc"><div className="bloc-titre">Valeurs normatives lues (docs/normes)</div>
        {!normes ? <div className="note" style={{ padding: 10 }}>{erreurNormes ? `Référentiel indisponible : ${erreurNormes}` : 'Lecture en cours'}</div> : Object.entries(normes).map(([f, entrees]) => (
          <details key={f} open={f === 'nf_p94_282'}>
            <summary style={{ padding: '6px 12px', cursor: 'pointer', fontWeight: 500 }}>{FICHIERS[f] ?? f} <span className="doux">({f}.yaml, {entrees.length} valeurs)</span></summary>
            <table className="tableau compact">
              <thead><tr><th>Clé</th><th className="num">Valeur</th><th>Source et statut</th></tr></thead>
              <tbody>
                {entrees.map((e) => (
                  <tr key={e.cle}>
                    <td className="mono">{e.cle}</td>
                    <td className="num">{e.valeur === null || e.valeur === undefined ? <span className="statut non_verifiable">non renseignée</span> : typeof e.valeur === 'number' ? nb(e.valeur, Number.isInteger(e.valeur) ? 0 : 3) : String(e.valeur)}</td>
                    <td className="doux" style={{ whiteSpace: 'normal' }}>{e.source}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>
        ))}
      </div>
    </div>
  )
}

const CONVENTIONS: Record<string, string> = { deplacement: 'Déplacement', moment: 'Moment', tranchant: 'Effort tranchant', pression: 'Pressions', effort_appui: "Effort d'appui" }

function Convention({ cle, texte }: { cle: string; texte: string }) {
  return <><dt>{CONVENTIONS[cle] ?? cle}</dt><dd style={{ textAlign: 'left', fontFamily: 'inherit' }}>{texte}</dd></>
}
