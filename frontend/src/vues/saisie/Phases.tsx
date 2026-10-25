import type { Resultats } from '../../lib/api'
import { ArbrePhases } from '../../composants/ArbrePhases'
import { confirmer } from '../../lib/dialogue'
import type { Selection } from '../../lib/etat'
import { uniteCote } from '../../lib/format'
import type { Chemin, Modele } from '../../lib/scriptDoc'
import { Champ, ErreursBloc } from './champs'
import { type Ctx } from './outils'

export function Phases({ ctx, selection, onSelection, phaseActive, onPhaseActive, res }: {
  ctx: Ctx; selection: Selection; onSelection: (s: Selection) => void; phaseActive: number; onPhaseActive: (i: number) => void; res: Resultats | null
}) {
  const phases: Modele[] = Array.isArray(ctx.modele.phases) ? ctx.modele.phases : []
  const appuis = Object.keys(ctx.modele.appuis ?? {})
  const surcharges: string[] = (ctx.modele.surcharges ?? []).map((s: Modele, i: number) => s?.nom ?? `S${i + 1}`)
  const sel = selection?.type === 'phase' ? selection.index : null
  const ph = sel !== null ? phases[sel] : null
  const listeStr = (v: unknown): string => (Array.isArray(v) ? v.join(', ') : v ? String(v) : '')
  const fixerListe = (chemin: Chemin, texte: string) => {
    const l = texte.split(',').map((s) => s.trim()).filter(Boolean)
    ctx.actions.fixer(chemin, l.length === 0 ? '' : l.length === 1 ? l[0] : l)
  }
  const nomLibre = (base: string) => {
    const noms = new Set(phases.map((p) => String(p?.nom ?? '')))
    let n = base, k = 2
    while (noms.has(n)) n = `${base} ${k++}`
    return n
  }
  const inserer = (apres: number) => {
    // nouvelle phase enchaînée après `apres` (−1 = après l'état initial, en tête de liste) ;
    // la phase qui suivait garde son enchaînement sur la nouvelle (parent implicite = précédente de la liste)
    const nom = nomLibre('Nouvelle phase')
    const suivante = phases[apres + 1]
    const valeur: Record<string, unknown> = { nom }
    if (apres >= 0 && phases[apres]?.depuis && suivante && !suivante.depuis) {
      // on insère dans une branche : la nouvelle phase enchaîne sur `apres` et la suivante restait sur `apres`
      valeur.depuis = phases[apres].nom
    }
    ctx.actions.inserer(['phases'], apres + 1, valeur)
    if (suivante && !suivante.depuis && apres >= 0 && phases[apres]?.depuis) ctx.actions.fixer(['phases', apres + 2, 'depuis'], nom)
    onSelection({ type: 'phase', index: apres + 1 })
  }
  const brancher = (depuis: number) => {
    const nom = nomLibre('Variante')
    ctx.actions.ajouter(['phases'], depuis >= 0 ? { nom, depuis: phases[depuis]?.nom } : { nom, depuis: 'État initial' })
    onSelection({ type: 'phase', index: phases.length })
  }
  const supprimer = async (i: number) => {
    const nom = String(phases[i]?.nom ?? '')
    const refs = phases.map((p, k) => (p?.depuis === nom ? k + 1 : 0)).filter(Boolean)
    const question = refs.length ? `La phase « ${nom} » est le point de départ des phases ${refs.join(', ')}. La supprimer quand même ?` : `Supprimer la phase « ${nom} » du script ?`
    if (!(await confirmer(question, { ok: 'Supprimer' }))) return
    ctx.actions.supprimer(['phases', i])
    onSelection(null)
  }
  return (
    <div className="saisie">
      <p className="aide">Explorateur de phases : chaque phase repart de l'état de la précédente, ou de la phase indiquée par <span className="mono">depuis</span> (variante, comme une branche dans Plaxis). Insérez une phase après une autre, ou créez une variante à partir d'une phase ; cliquez une phase pour l'éditer et l'afficher dans les résultats.</p>
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(360px, 1fr) minmax(300px, 1fr)', gap: 16, alignItems: 'start' }}>
        <ArbrePhases phases={phases} res={res} actif={phaseActive} selection={sel}
          onChoisir={(i) => { onSelection(i >= 0 ? { type: 'phase', index: i } : null); if (res && i + 1 < res.phases.length) onPhaseActive(i + 1) }}
          onInserer={inserer} onBrancher={brancher} onSupprimer={(i) => void supprimer(i)} />
        <div className="bloc" style={{ margin: 0 }}>
          <div className="bloc-titre">{ph ? `Phase ${sel! + 1} — ${ph.nom ?? ''}` : 'Sélectionnez une phase'}</div>
          {ph && sel !== null && (
            <div className="grille-form" style={{ gridTemplateColumns: '1fr 1fr' }}>
              <label style={{ gridColumn: '1 / -1' }}>Nom<Champ ctx={ctx} chemin={['phases', sel, 'nom']} valeur={ph.nom} type="text" large /></label>
              <label>Phase de départ (vide = précédente)
                <select className="champ champ-bloc" value={ph.depuis ?? ''} onChange={(e) => ctx.actions.fixer(['phases', sel, 'depuis'], e.target.value)}>
                  <option value="">— précédente —</option>
                  {phases.slice(0, sel).map((p, k) => <option key={k} value={String(p?.nom ?? '')}>{k + 1}. {p?.nom}</option>)}
                </select></label>
              <label>Excaver à ({uniteCote(ctx.modele)})<Champ ctx={ctx} chemin={['phases', sel, 'excaver']} valeur={ph.excaver} placeholder="—" bloc="Phase" cle="excaver" large /></label>
              <label>Poser (appuis, virgules)<input className="champ champ-bloc" key={`p${sel}${listeStr(ph.poser)}`} defaultValue={listeStr(ph.poser)} list="liste-appuis" placeholder="—"
                onBlur={(e) => { if (e.target.value.trim() !== listeStr(ph.poser)) fixerListe(['phases', sel, 'poser'], e.target.value) }} /></label>
              <label>Déposer<input className="champ champ-bloc" key={`d${sel}${listeStr(ph.deposer)}`} defaultValue={listeStr(ph.deposer)} list="liste-appuis" placeholder="—"
                onBlur={(e) => { if (e.target.value.trim() !== listeStr(ph.deposer)) fixerListe(['phases', sel, 'deposer'], e.target.value) }} /></label>
              <label>Nappe aval ({uniteCote(ctx.modele)})<Champ ctx={ctx} chemin={['phases', sel, 'eau', 'aval']} valeur={ph.eau?.aval} placeholder="inchangée" large /></label>
              <label>Nappe amont ({uniteCote(ctx.modele)})<Champ ctx={ctx} chemin={['phases', sel, 'eau', 'amont']} valeur={ph.eau?.amont} placeholder="inchangée" large /></label>
              <label>Remblai aval à (m)<Champ ctx={ctx} chemin={['phases', sel, 'remblayer', 'aval']} valeur={ph.remblayer?.aval} placeholder="—" large /></label>
              <label>Remblai amont à (m)<Champ ctx={ctx} chemin={['phases', sel, 'remblayer', 'amont']} valeur={ph.remblayer?.amont} placeholder="—" large /></label>
              <label style={{ gridColumn: '1 / -1' }}>Retirer des surcharges (noms, virgules){surcharges.length ? ` — définies : ${surcharges.join(', ')}` : ''}
                <input className="champ champ-bloc" key={`r${sel}${listeStr(ph.retirer_surcharges)}`} defaultValue={listeStr(ph.retirer_surcharges)} placeholder="—"
                  onBlur={(e) => { const l = e.target.value.split(',').map((s) => s.trim()).filter(Boolean); if (listeStr(l) !== listeStr(ph.retirer_surcharges)) ctx.actions.fixer(['phases', sel, 'retirer_surcharges'], l.length ? l : '') }} /></label>
              {res?.phases[sel + 1] && !res.phases[sel + 1].ok && <div className="alerte rouge" style={{ gridColumn: '1 / -1' }}>{res.phases[sel + 1].message}</div>}
            </div>
          )}
        </div>
      </div>
      <datalist id="liste-appuis">{appuis.map((a) => <option key={a} value={a} />)}</datalist>
      <ErreursBloc ctx={ctx} prefixe="phases" />
    </div>
  )
}
