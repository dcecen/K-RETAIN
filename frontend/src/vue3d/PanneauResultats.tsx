import { useEffect, useMemo, useRef } from 'react'
import Plotly from 'plotly.js-dist-min'
import type { ProjetCoupes, Resultats, Verif } from '../lib/api'
import { cote, nb, pourcent } from '../lib/format'
import { IconeFermer } from '../lib/icones'
import type { Modele } from '../lib/scriptDoc'
import { couleurs, COULEURS_SOL, type Theme } from '../lib/theme'
import { CoupeDiagrammes } from '../vues/CoupeDiagrammes'
import { Efforts } from '../vues/Efforts'
import { analyserSelection, pointsAttention, titreFiltre, verifsPour } from './navigation'

export type Volet = 'courbes' | 'efforts' | 'verifications'
const LIBELLE: Record<Verif['etat'], string> = { ok: 'Vérifié', attention: 'Vérifié', non_ok: 'Non vérifié', non_verifiable: 'Non vérifiable' }

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Obj = any

/** Petit graphique Plotly aux couleurs du thème. Les tableaux reçus sont souvent recréés à chaque rendu
 *  (survol de la maquette) : le graphique n'est redessiné que si leur contenu change. */
function Mini({ traces, layout, hauteur = 220, theme }: { traces: Obj[]; layout: Obj; hauteur?: number; theme: Theme }) {
  const ref = useRef<HTMLDivElement>(null)
  const cle = JSON.stringify([traces, layout])
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const c = couleurs()
    const axe = { gridcolor: c.filet, linecolor: c.filetFort, tickfont: { size: 10, color: c.doux }, zerolinecolor: c.filetFort }
    void Plotly.react(el, traces, {
      paper_bgcolor: c.fond, plot_bgcolor: c.fond, font: { family: 'IBM Plex Sans, sans-serif', size: 11, color: c.texte },
      margin: { l: 48, r: 10, t: 24, b: 34 }, showlegend: true, legend: { orientation: 'h', y: 1.15, font: { size: 10 } }, separators: ', ',
      ...layout, xaxis: { ...axe, ...(layout.xaxis ?? {}) }, yaxis: { ...axe, ...(layout.yaxis ?? {}) },
    }, { responsive: true, displayModeBar: false, locale: 'fr' })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cle, theme])
  useEffect(() => {
    const el = ref.current
    return () => { if (el) Plotly.purge(el) }
  }, [])
  return <div ref={ref} style={{ width: '100%', height: hauteur }} />
}

function TableVerifs({ liste }: { liste: Verif[] }) {
  if (!liste.length) return <div className="note" style={{ padding: 10 }}>Aucune vérification rattachée à cet objet.</div>
  return (
    <table className="tableau compact">
      <thead><tr><th>Vérification</th><th>Élément</th><th>Phase</th><th className="num">Taux</th><th>État</th></tr></thead>
      <tbody>
        {liste.map((v, i) => (
          <tr key={i} className={`etat-${v.etat}`} title={v.detail}>
            <td>{v.nom}</td><td>{v.element}</td><td className="doux">{v.phase ?? '—'}</td>
            <td className="num">{v.taux === null ? '—' : pourcent(v.taux)}</td><td className={`statut ${v.etat}`}>{LIBELLE[v.etat]}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

/** Panneau de résultats de la maquette : Courbes, Efforts, Vérifications, filtrés sur la sélection. */
export function PanneauResultats({ res, projet, coupeActive, phase, selection, modele, theme, resultatsPour, largeur, curseurZ, volet, onVolet,
  onSelection, onPhase, onOuvrir, onFermer, onCentrer, onSurvolZ, onLargeur }: {
  res: Resultats
  projet: ProjetCoupes | null
  coupeActive: number
  phase: number
  selection: string | null
  modele: Modele
  theme: Theme
  resultatsPour?: (k: number, sl: number, phase: number) => { res: Resultats; phase: number; coupe: string | null }
  largeur: number
  curseurZ: number | null
  volet: Volet
  onVolet: (v: Volet) => void
  onSelection: (id: string | null) => void
  onPhase: (i: number) => void
  onOuvrir: (onglet: 'coupe' | 'efforts' | 'verifications') => void
  onFermer: () => void
  onCentrer: (id: string) => void
  onSurvolZ: (z: number | null) => void
  onLargeur: (l: number) => void
}) {
  const sel = useMemo(() => analyserSelection(selection), [selection])
  const coupe = projet && !projet.unique ? projet.coupes[coupeActive] : null
  const assemblages = useMemo(() => res.maquette?.assemblages ?? {}, [res])
  // résultats « vus » par la sélection (tronçon → coupe)
  const ctxSel = useMemo(() => {
    if (sel?.type === 'paroi' && resultatsPour) {
      const r = resultatsPour(sel.k ?? 0, 1, phase)
      return { res: r.res, phase: r.phase, coupeNom: r.coupe }
    }
    if (sel?.type === 'coupe' && projet && !projet.unique) {
      const i = projet.coupes.findIndex((c) => c.nom === sel.nom)
      if (i >= 0 && projet.coupes[i].resultats) {
        const ip = projet.coupes[coupeActive].correspondance[phase] ?? phase
        let j = 0
        projet.coupes[i].correspondance.forEach((c, k) => { if (c <= ip) j = k })
        return { res: projet.coupes[i].resultats!, phase: j, coupeNom: sel.nom }
      }
    }
    return { res, phase, coupeNom: coupe?.nom ?? null }
  }, [sel, resultatsPour, phase, projet, coupeActive, res, coupe])
  const r = ctxSel.res
  const ph = r.phases[Math.min(ctxSel.phase, r.phases.length - 1)]
  const verifs = useMemo(() => verifsPour(sel, r, assemblages), [sel, r, assemblages])
  const attention = useMemo(() => pointsAttention(res, assemblages), [res, assemblages])

  // redimensionnement par la poignée gauche
  const glisse = useRef<{ x: number; l: number } | null>(null)
  useEffect(() => {
    const bouge = (e: PointerEvent) => { if (glisse.current) onLargeur(Math.min(640, Math.max(320, glisse.current.l + (glisse.current.x - e.clientX)))) }
    const fin = () => { glisse.current = null }
    window.addEventListener('pointermove', bouge)
    window.addEventListener('pointerup', fin)
    return () => { window.removeEventListener('pointermove', bouge); window.removeEventListener('pointerup', fin) }
  }, [onLargeur])

  const nomAppui = sel?.type === 'appui' || sel?.type === 'lierne' ? sel.nom : sel?.type === 'assemblage' ? assemblages[sel.nom]?.appui ?? null : null
  const lignesAppui = nomAppui ? r.phases.map((p, i) => ({ i, p, a: p.appuis?.find((x) => x.nom === nomAppui) })).filter((x) => x.a) : []

  const courbes = () => {
    if (!sel) {
      const syn = projet && !projet.unique && projet.coupes.length > 1 ? projet.synthese : null
      const d = res.dimensionnant
      return (
        <div className="insp-section">
          <div className="insp-titre">Synthèse {syn ? `projet (${projet!.coupes.length} coupes)` : ''}</div>
          <dl className="lignes-cle">
            <dt>Déplacement max</dt><dd>{nb(d.deplacement?.valeur_mm)} mm{syn && (syn.chiffres.deplacement as Obj)?.coupe ? ` · ${String((syn.chiffres.deplacement as Obj).coupe).split(' — ')[0]}` : ''}</dd>
            <dt>Moment max</dt><dd>{nb(d.moment_positif?.valeur, 0)} kN·m/m</dd>
            <dt>Moment min</dt><dd>{nb(d.moment_negatif?.valeur, 0)} kN·m/m</dd>
            <dt>Tranchant max</dt><dd>{nb(d.tranchant?.valeur, 0)} kN/m</dd>
            {Object.entries(d.appuis ?? {}).map(([n, a]) => <span key={n} style={{ display: 'contents' }}><dt>{n} max</dt><dd>{nb(a.effort_kN_m, 0)} kN/m · {nb(a.effort_axial_kN, 0)} kN</dd></span>)}
          </dl>
          <div className="insp-titre" style={{ marginTop: 10 }}>Vérifications non vérifiées ou à taux ≥ 90 %</div>
          {attention.length === 0 ? <div className="note">Aucune : toutes les vérifications ont un taux inférieur à 90 %.</div> : (
            <ul className="points-attention">
              {attention.map((p, i) => (
                <li key={i} className={p.etat === 'non_ok' || (p.taux ?? 0) >= 1 ? 'rouge' : 'orange'} onClick={() => { onSelection(p.selection); onCentrer(p.selection) }} title="Centrer la maquette et ouvrir la vérification">
                  <span className="num">{p.taux === null ? '—' : pourcent(p.taux)}</span> {p.libelle}{p.phase ? <span className="doux"> · {p.phase}</span> : null}
                </li>
              ))}
            </ul>
          )}
        </div>
      )
    }
    if (sel.type === 'paroi' || sel.type === 'coupe' || sel.type === 'coupe_locale') {
      return <div className="courbes-pleines"><CoupeDiagrammes res={r} phase={ctxSel.phase} theme={theme} curseurZ={curseurZ} onSurvolZ={onSurvolZ} /></div>
    }
    if (nomAppui) {
      const x = lignesAppui.map((l) => `${l.i + 1}`)
      const traces: Obj[] = [
        { x, y: lignesAppui.map((l) => l.a!.effort_kN_m), name: 'effort (kN/m)', type: 'scatter', mode: 'lines+markers', line: { color: couleurs().accent } },
        { x, y: lignesAppui.map((l) => l.a!.effort_axial_kN), name: 'effort axial (kN)', type: 'scatter', mode: 'lines+markers', yaxis: 'y2', line: { color: couleurs().orange } },
      ]
      const fleches = lignesAppui.filter((l) => l.a!.fleche_mm != null)
      return (
        <div className="insp-section">
          <div className="insp-titre">{nomAppui} — effort au fil des phases</div>
          <Mini theme={theme} traces={traces} layout={{ xaxis: { title: { text: 'phase', font: { size: 10 } }, type: 'category' }, yaxis: { title: { text: 'kN/m', font: { size: 10 } } }, yaxis2: { overlaying: 'y', side: 'right', title: { text: 'kN', font: { size: 10 } }, tickfont: { size: 10 } },
            shapes: [{ type: 'line', xref: 'x', yref: 'paper', x0: `${ctxSel.phase + 1}`, x1: `${ctxSel.phase + 1}`, y0: 0, y1: 1, line: { color: couleurs().doux, dash: 'dot', width: 1 } }] }} />
          {fleches.length > 0 && (
            <>
              <div className="insp-titre" style={{ marginTop: 8 }}>Flèche (module de vérification)</div>
              <Mini theme={theme} hauteur={180} traces={[{ x: fleches.map((l) => `${l.i + 1}`), y: fleches.map((l) => l.a!.fleche_mm), name: 'flèche (mm)', type: 'bar', marker: { color: couleurs().vert } },
                { x: fleches.map((l) => `${l.i + 1}`), y: fleches.map((l) => l.a!.fleche_poids_propre_mm), name: 'poids propre seul', type: 'scatter', mode: 'markers', marker: { color: couleurs().doux } }]}
                layout={{ xaxis: { type: 'category' }, yaxis: { title: { text: 'mm', font: { size: 10 } } } }} />
            </>
          )}
        </div>
      )
    }
    if (sel.type === 'fond' || sel.type === 'bouchon') {
      const e = ph.eau
      const hy = ph.hydro
      return (
        <div className="insp-section">
          <div className="insp-titre">Pressions d'eau sur la paroi — {ph.nom}</div>
          {e ? <Mini theme={theme} traces={[{ x: e.u_amont, y: e.z, name: 'u amont (kPa)', type: 'scatter', mode: 'lines' }, { x: e.u_aval, y: e.z, name: 'u aval (kPa)', type: 'scatter', mode: 'lines' }]}
            layout={{ xaxis: { title: { text: 'kPa', font: { size: 10 } } }, yaxis: { title: { text: 'cote (m)', font: { size: 10 } } } }} /> : <div className="note">Phase non calculée.</div>}
          {hy && (
            <dl className="lignes-cle" style={{ marginTop: 8 }}>
              <dt>Régime</dt><dd>{hy.regime}</dd>
              <dt>Gradient de sortie max</dt><dd>{nb(hy.gradient_sortie_max, 3)}</dd>
              {hy.bouchon && <><dt>Bouchon</dt><dd>{hy.bouchon.type} · {nb(hy.bouchon.epaisseur, 1)} m</dd><dt>Gradient dans le bouchon</dt><dd>{nb(hy.gradient_bouchon, 2)}</dd></>}
              <dt>Débit</dt><dd>{nb(hy.debit_m3_h_m, 3)} m³/h/m</dd>
            </dl>
          )}
        </div>
      )
    }
    if (sel.type === 'couche') {
      const c = modele?.sol?.[sel.index ?? 0]
      const co = res.couches[sel.index ?? 0] as Obj
      const ligne = (t: string, v: unknown, u = '') => (v === undefined || v === null ? null : <><dt>{t}</dt><dd>{typeof v === 'number' ? nb(v, Number.isInteger(v) ? 0 : 3) : String(v)} {u}</dd></>)
      return (
        <div className="insp-section">
          <div className="insp-titre"><span className="puce-sol" style={{ background: COULEURS_SOL[(sel.index ?? 0) % COULEURS_SOL.length] }} /> {c?.nom ?? co?.nom}</div>
          <dl className="lignes-cle">
            {ligne('Toit', c?.toit ?? co?.toit, 'm')}{ligne('γ', c?.gamma, 'kN/m³')}{ligne('γ′', c?.gamma_dejauge, 'kN/m³')}{ligne('φ′', c?.phi, '°')}{ligne('c′', c?.c ?? 0, 'kPa')}
            {ligne('EM', c?.EM, 'kPa')}{ligne('α', c?.alpha)}
            {ligne('Kah (calcul)', co?.kah)}{ligne('Kph (calcul)', co?.kph)}{ligne('K0', co?.k0)}{ligne('kh', co?.kh != null ? Math.round(co.kh) : null, 'kN/m³')}
          </dl>
          <div className="note">Coefficients tels qu'utilisés par le calcul (méthode du script : Coulomb ou Kérisel-Absi ; kh de Schmitt ou imposé).</div>
        </div>
      )
    }
    if (sel.type === 'surcharge') {
      const sc = res.maquette?.surcharges?.[sel.index ?? 0]
      if (!sc) return <div className="note" style={{ padding: 10 }}>Surcharge introuvable.</div>
      const unite = sc.type === 'ponctuelle' ? 'kN' : sc.type === 'lineaire' || sc.type === 'lineique' ? 'kN/m' : 'kPa'
      const nomPhase = (k: number) => (k <= 0 ? 'état initial' : `${k}. ${res.phases[k]?.nom ?? ''}`)
      return (
        <div className="insp-section">
          <div className="insp-titre">Surcharge {sc.nom} <span className="doux">· {sc.type}</span></div>
          <dl className="lignes-cle">
            <dt>Valeur</dt><dd>{nb(sc.q, 0)} {unite}</dd>
            {sc.position && <><dt>Position</dt><dd>x = {nb(sc.position[0], 1)} m, y = {nb(sc.position[1], 1)} m</dd></>}
            {sc.emprise && (sc.type === 'bande' ? <><dt>Le long du côté</dt><dd>de {nb(sc.emprise[0], 1)} à {nb(sc.emprise[1], 1)} m</dd></> : <><dt>Emprise</dt><dd>{nb(sc.emprise[0], 1)} × {nb(sc.emprise[1], 1)} m</dd></>)}
            {sc.type === 'bande' && <><dt>Bande</dt><dd>de {nb(sc.distance ?? 0, 1)} à {nb((sc.distance ?? 0) + (sc.largeur ?? 0), 1)} m de la paroi</dd></>}
            {!!sc.profondeur && <><dt>Profondeur</dt><dd>{nb(sc.profondeur, 1)} m</dd></>}
            <dt>Application</dt><dd>{nomPhase(sc.phase_debut)}</dd>
            {sc.phase_fin < res.phases.length - 1 && <><dt>Retrait après</dt><dd>{nomPhase(sc.phase_fin)}</dd></>}
            {sc.cotes_paroi && <><dt>Côtés</dt><dd>{sc.cotes_paroi.join(', ')}</dd></>}
          </dl>
          {sc.profil && (
            <>
              <div className="insp-titre" style={{ marginTop: 8 }}>Contrainte verticale induite au droit de la coupe</div>
              <Mini theme={theme} traces={[{ x: sc.profil.dsv, y: sc.profil.z, name: 'Δσv (kPa)', type: 'scatter', mode: 'lines', line: { color: couleurs().orange } }]}
                layout={{ xaxis: { title: { text: 'Δσv (kPa)', font: { size: 10 } } }, yaxis: { title: { text: 'cote (m)', font: { size: 10 } } } }} />
              <div className="note">{sc.profil.methode}. Pression horizontale supplémentaire ≈ Ka × Δσv (côté poussée), telle que le moteur l'applique aux ressorts.</div>
            </>
          )}
        </div>
      )
    }
    if (sel.type === 'terrain') {
      const o = res.maquette?.terrain?.objets.find((x) => x.nom === sel.nom)
      const t = res.maquette?.terrain
      if (!o) {
        return (
          <div className="insp-section">
            <div className="insp-titre">{sel.nom}</div>
            {t?.pente_beta ? <div className="note">Terrain en pente côté terre : β = {nb(t.pente_beta, 1)}°, poussée de Coulomb avec talus (sol/coefficients.py, Ka(β) &gt; Ka horizontal). Kah des couches : voir une couche.</div> : <div className="note">Objet de terrain introuvable.</div>}
          </div>
        )
      }
      const zCrete = Math.max(...o.profil.map((p) => p[1]))
      const methode = o.methode === 'surcharge_equivalente' ? 'surcharge équivalente : le volume est remplacé par son poids (bandes de γ·h appliquées à la cote de base, diffusées par Boussinesq)'
        : o.methode === 'fond_equivalent' ? `fond de fouille équivalent à ${nb(o.cote_equivalente ?? 0, 2)} m (valeur choisie)` : o.methode === 'coulomb_beta' ? 'coefficients de poussée de Coulomb avec talus' : o.methode
      const ppSans = ph.pp_sans_terrain
      return (
        <div className="insp-section">
          <div className="insp-titre">{o.nom} <span className="doux">· {o.type} · {o.face === 'aval' ? 'côté fouille' : 'côté terre'}</span></div>
          <dl className="lignes-cle">
            <dt>Crête</dt><dd>{nb(zCrete, 2)} m</dd>
            <dt>Base</dt><dd>{nb(o.base, 2)} m</dd>
            <dt>Étendue</dt><dd>{nb(o.profil[o.profil.length - 1][0], 1)} m</dd>
            <dt>γ retenu</dt><dd>{nb(o.gamma, 1)} kN/m³</dd>
            <dt>Phases</dt><dd>{o.phase_debut} à {Math.min(o.phase_fin, res.phases.length - 1)}</dd>
            {o.cotes_paroi && <><dt>Côtés</dt><dd>{o.cotes_paroi.join(', ')}</dd></>}
          </dl>
          <div className="note">Méthode : {methode}.</div>
          {o.face === 'aval' && ph.pressions && (
            <>
              <div className="insp-titre" style={{ marginTop: 8 }}>Butée limite — {ph.nom}</div>
              {ppSans ? <Mini theme={theme} traces={[{ x: ppSans, y: ph.pressions.aval.z, name: 'sans la risberme', type: 'scatter', mode: 'lines', line: { color: couleurs().doux, dash: 'dash' } },
                { x: ph.pressions.aval.pp, y: ph.pressions.aval.z, name: 'avec (calcul)', type: 'scatter', mode: 'lines', line: { color: couleurs().vert } }]}
                layout={{ xaxis: { title: { text: 'kPa', font: { size: 10 } } }, yaxis: { title: { text: 'cote (m)', font: { size: 10 } } } }} />
                : <div className="note">L'objet n'agit pas à cette phase (ou méthode sans effet sur la butée limite).</div>}
            </>
          )}
        </div>
      )
    }
    return <div className="note" style={{ padding: 10 }}>Pas de courbe pour cet objet.</div>
  }

  const efforts = () => {
    if (nomAppui) {
      const def = r.appuis.find((x) => x.nom === nomAppui)
      return (
        <div className="insp-section">
          <div className="insp-titre">{nomAppui} {def ? <span className="doux">· {def.type}{def.element ? ` · ${def.element}` : ''} · cote {cote(def.cote)}</span> : null}</div>
          <table className="tableau compact">
            <thead><tr><th>Phase</th><th className="num">kN/m</th><th className="num">kN</th><th className="num">ELU kN</th><th className="num">flèche mm</th></tr></thead>
            <tbody>
              {lignesAppui.map(({ i, p, a }) => (
                <tr key={i} className={`cliquable ${i === ctxSel.phase ? 'actif' : ''} ${a!.actif ? '' : 'inactif'}`} onClick={() => onPhase(i)}>
                  <td>{i + 1}. {p.nom}</td><td className="num">{nb(a!.effort_kN_m)}</td><td className="num">{nb(a!.effort_axial_kN, 0)}</td>
                  <td className="num">{a!.effort_elu_kN != null ? nb(a!.effort_elu_kN, 0) : '—'}</td><td className="num">{a!.fleche_mm != null ? nb(a!.fleche_mm) : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {sel?.type === 'assemblage' && <div className="note" style={{ marginTop: 6 }}>Effort de calcul de l'assemblage {sel.nom} à la phase active : {ph.appuis?.find((x) => x.nom === nomAppui)?.effort_elu_kN != null ? `${nb(ph.appuis!.find((x) => x.nom === nomAppui)!.effort_elu_kN!, 0)} kN (ELU)` : 'ELU non disponible'}.</div>}
        </div>
      )
    }
    if (sel?.type === 'fond' || sel?.type === 'bouchon') return <div className="insp-section"><dl className="lignes-cle"><dt>Débit de pompage</dt><dd>{ph.hydro ? `${nb(ph.hydro.debit_m3_h_m, 3)} m³/h/m` : '—'}</dd></dl></div>
    if (sel?.type === 'couche' || sel?.type === 'surcharge' || sel?.type === 'terrain') return <div className="note" style={{ padding: 10 }}>Pas d'effort d'appui pour cet objet.</div>
    return <div className="efforts-compacts"><Efforts res={r} phase={ctxSel.phase} onPhase={onPhase} onAppui={(n) => onSelection(`appui:${n}`)} /></div>
  }

  const verifications = () => {
    if (!sel && projet && !projet.unique && projet.coupes.length > 1) {
      return (
        <table className="tableau compact">
          <thead><tr><th>Vérification</th><th>Élément</th><th>Pire coupe</th><th className="num">Taux</th><th>État</th></tr></thead>
          <tbody>{projet.synthese.verifications.map((v, i) => (
            <tr key={i} className={`etat-${v.etat}`}><td>{v.nom}</td><td>{v.element}</td><td>{v.coupe.split(' — ')[0]}</td><td className="num">{v.taux === null ? '—' : pourcent(v.taux)}</td><td className={`statut ${v.etat}`}>{LIBELLE[v.etat]}</td></tr>
          ))}</tbody>
        </table>
      )
    }
    return <TableVerifs liste={verifs} />
  }

  const ongletPleinEcran: Record<Volet, 'coupe' | 'efforts' | 'verifications'> = { courbes: 'coupe', efforts: 'efforts', verifications: 'verifications' }
  return (
    <aside className="panneau-resultats" style={{ width: largeur }} aria-label="Résultats de la sélection">
      <div className="poignee-redim" onPointerDown={(e) => { glisse.current = { x: e.clientX, l: largeur }; e.preventDefault() }} title="Redimensionner" />
      <div className="panneau-entete">
        <span className="filtre" title={titreFiltre(sel, ctxSel.coupeNom, ctxSel.phase)}>{titreFiltre(sel, ctxSel.coupeNom, ctxSel.phase)}</span>
        <span className="espace" />
        <button className="btn discret" onClick={() => onOuvrir(ongletPleinEcran[volet])} title="Ouvrir cet onglet en plein écran, filtré sur la sélection">Plein écran</button>
        <button className="btn icone discret" title="Fermer (R)" onClick={onFermer}><IconeFermer taille={14} /></button>
      </div>
      <div className="volets" role="tablist">
        {(['courbes', 'efforts', 'verifications'] as Volet[]).map((v) => (
          <button key={v} role="tab" aria-selected={volet === v} className={`volet ${volet === v ? 'actif' : ''}`} onClick={() => onVolet(v)}>
            {v === 'courbes' ? 'Courbes' : v === 'efforts' ? 'Efforts' : `Vérifications${verifs.length ? ` (${verifs.length})` : ''}`}
          </button>
        ))}
      </div>
      <div className="panneau-corps">
        {volet === 'courbes' ? courbes() : volet === 'efforts' ? efforts() : verifications()}
      </div>
    </aside>
  )
}
