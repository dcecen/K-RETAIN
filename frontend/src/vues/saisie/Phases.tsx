import { useState, type ReactNode } from 'react'
import type { Resultats } from '../../lib/api'
import { ArbrePhases } from '../../composants/ArbrePhases'
import { confirmer } from '../../lib/dialogue'
import type { Selection } from '../../lib/etat'
import { uniteCote } from '../../lib/format'
import { IconeCorbeille, IconeDepose, IconeDescendre, IconeEau, IconeExcavation, IconeInitial, IconeMonter, IconePlus, IconePose, IconeRemblai, IconeSurcharge } from '../../lib/icones'
import { resumePhase } from '../../lib/phases'
import type { Modele } from '../../lib/scriptDoc'
import { Avance, Cases, Champ, ErreursBloc } from './champs'
import { type Ctx } from './outils'

const ICONES: Record<string, ReactNode> = {
  initial: <IconeInitial />, excavation: <IconeExcavation />, pose: <IconePose />, depose: <IconeDepose />,
  eau: <IconeEau />, remblai: <IconeRemblai />, surcharge: <IconeSurcharge />,
}

/** Liste simple des phases (sans variante) : ordre, résumé, insertion, déplacement, suppression. */
function ListePhases({ phases, res, actif, selection, onChoisir, onInserer, onDeplacer, onSupprimer }: {
  phases: Modele[]; res: Resultats | null; actif: number; selection: number | null
  onChoisir: (i: number) => void; onInserer: (apres: number) => void; onDeplacer: (i: number, j: number) => void; onSupprimer: (i: number) => void
}) {
  const ligne = (i: number, nom: string, resume: { type: string; texte: string }[], r: Resultats['phases'][number] | undefined) => (
    <div key={i} className={`ligne-phase ${i === selection ? 'sel' : ''} ${i + 1 === actif ? 'act' : ''}`} style={{ height: 34 }} onClick={() => onChoisir(i)}>
      <span className="mono faible" style={{ width: 22, textAlign: 'right' }}>{i + 1}</span>
      <span style={{ fontWeight: i === selection || i + 1 === actif ? 600 : 400, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>{nom}</span>
      <span className="doux" style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 11.5, minWidth: 0 }}>
        {resume.map((a, k) => <span key={k} title={a.texte} style={{ display: 'inline-flex', alignItems: 'center', gap: 3 }}>{ICONES[a.type]}<span className="masquer-etroit">{a.texte}</span></span>)}
      </span>
      {r && !r.ok && <span className="statut non_ok" title={r.message}>rupture</span>}
      <span style={{ display: 'flex', gap: 2 }} onClick={(e) => e.stopPropagation()}>
        {i >= 0 && <button className="btn icone discret" title="Monter" disabled={i === 0} onClick={() => onDeplacer(i, i - 1)}><IconeMonter taille={14} /></button>}
        {i >= 0 && <button className="btn icone discret" title="Descendre" disabled={i === phases.length - 1} onClick={() => onDeplacer(i, i + 1)}><IconeDescendre taille={14} /></button>}
        <button className="btn icone discret" title="Insérer une phase après celle-ci" onClick={() => onInserer(i)}><IconePlus taille={14} /></button>
        {i >= 0 && <button className="btn icone discret" title="Supprimer la phase" onClick={() => onSupprimer(i)}><IconeCorbeille taille={14} /></button>}
      </span>
    </div>
  )
  return (
    <div className="arbre-phases">
      <div className="ligne-phase" style={{ height: 34, cursor: 'default' }}>
        <span className="mono faible" style={{ width: 22, textAlign: 'right' }}>0</span>
        <span style={{ flex: 1 }}>État initial</span>
        <span className="doux" style={{ fontSize: 11.5, display: 'inline-flex', gap: 3, alignItems: 'center' }}>{ICONES.initial}<span className="masquer-etroit">sol au repos</span></span>
        <span style={{ display: 'flex', gap: 2 }}><button className="btn icone discret" title="Insérer une première phase" onClick={() => onInserer(-1)}><IconePlus taille={14} /></button></span>
      </div>
      {phases.map((p, i) => ligne(i, String(p?.nom ?? `Phase ${i + 1}`), resumePhase(p), res?.phases[i + 1]))}
    </div>
  )
}

export function Phases({ ctx, selection, onSelection, phaseActive, onPhaseActive, res }: {
  ctx: Ctx; selection: Selection; onSelection: (s: Selection) => void; phaseActive: number; onPhaseActive: (i: number) => void; res: Resultats | null
}) {
  const phases: Modele[] = Array.isArray(ctx.modele.phases) ? ctx.modele.phases : []
  const appuis = Object.keys(ctx.modele.appuis ?? {})
  /** Zones de fond déclarées dans geometrie.fouille.zones : « excaver » peut alors être un dictionnaire par zone. */
  const zonesFond: string[] = (Array.isArray(ctx.modele.geometrie?.fouille?.zones) ? ctx.modele.geometrie.fouille.zones : []).map((z: Modele, i: number) => String(z?.nom ?? `zone${i + 1}`))
  const surcharges: string[] = (ctx.modele.surcharges ?? []).map((s: Modele, i: number) => String(s?.nom ?? `S${i + 1}`))
  // nom par défaut d'un objet sans clé nom : même règle que le moteur (conversion.py : Risberme1, Talus1, Gradins1)
  const NOM_DEFAUT: Record<string, string> = { risbermes: 'Risberme', talus: 'Talus', gradins: 'Gradins' }
  const objetsTerrain: string[] = ['risbermes', 'talus', 'gradins'].flatMap((k) => (Array.isArray(ctx.modele.fouille?.[k]) ? ctx.modele.fouille[k].map((o: Modele, i: number) => String(o?.nom ?? `${NOM_DEFAUT[k]}${i + 1}`)) : []))
  const sel = selection?.type === 'phase' ? selection.index : null
  const ph = sel !== null ? phases[sel] : null
  const unite = uniteCote(ctx.modele)
  const variantes = phases.some((p) => p?.depuis !== undefined && p?.depuis !== null)
  const [voirArbre, setVoirArbre] = useState(false)
  const arbre = variantes || voirArbre
  const nomLibre = (base: string) => {
    const noms = new Set(phases.map((p) => String(p?.nom ?? '')))
    let n = base, k = 2
    while (noms.has(n)) n = `${base} ${k++}`
    return n
  }
  const choisir = (i: number) => {
    onSelection(i >= 0 ? { type: 'phase', index: i } : null)
    if (res && i + 1 < res.phases.length) onPhaseActive(i + 1)
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
    setVoirArbre(true)
    onSelection({ type: 'phase', index: phases.length })
  }
  const deplacer = (i: number, j: number) => {
    ctx.actions.deplacer(['phases'], i, j)
    onSelection({ type: 'phase', index: j })
  }
  const supprimer = async (i: number) => {
    const nom = String(phases[i]?.nom ?? '')
    const refs = phases.map((p, k) => (p?.depuis === nom ? k + 1 : 0)).filter(Boolean)
    const question = refs.length ? `La phase « ${nom} » est le point de départ des phases ${refs.join(', ')}. La supprimer quand même ?` : `Supprimer la phase « ${nom} » du script ?`
    if (!(await confirmer(question, { ok: 'Supprimer' }))) return
    ctx.actions.supprimer(['phases', i])
    onSelection(null)
  }
  const champPhase = (k: string, lib: string, placeholder: string, chemin = ['phases', sel!, k]) => (
    <label key={k}>{lib}<Champ ctx={ctx} chemin={chemin} valeur={chemin.length === 3 ? ph?.[k] : ph?.[chemin[2]]?.[chemin[3]]} placeholder={placeholder} bloc="Phase" cle={k} large libelle={lib} /></label>
  )
  return (
    <div className="saisie">
      <p className="aide">
        {arbre
          ? <>Explorateur de phases : chaque phase repart de l'état de la précédente, ou de la phase indiquée comme « phase de départ » (variante, comme une branche dans Plaxis). Insérez une phase après une autre, créez une variante à partir d'une phase ; cliquez une phase pour l'éditer et l'afficher dans les résultats.</>
          : <>Chaque phase repart de l'état de la précédente : excavation, pose ou dépose d'appuis, niveaux de nappe, remblais, surcharges. Cliquez une phase pour l'éditer et l'afficher dans les résultats ; les flèches changent l'ordre. « Créer une variante » ouvre l'explorateur à branches (une phase qui repart d'un état antérieur).</>}
      </p>
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(360px, 1fr) minmax(300px, 1fr)', gap: 16, alignItems: 'start' }}>
        <div>
          {arbre ? (
            <ArbrePhases phases={phases} res={res} actif={phaseActive} selection={sel} onChoisir={choisir}
              onInserer={inserer} onBrancher={brancher} onSupprimer={(i) => void supprimer(i)} />
          ) : (
            <ListePhases phases={phases} res={res} actif={phaseActive} selection={sel} onChoisir={choisir}
              onInserer={inserer} onDeplacer={deplacer} onSupprimer={(i) => void supprimer(i)} />
          )}
          <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
            <button className="btn" onClick={() => inserer(phases.length - 1)}><IconePlus /> Ajouter une phase à la fin</button>
            {!arbre && <button className="btn" onClick={() => brancher(phases.length - 1)} title="Nouvelle phase qui repart d'un état antérieur (explorateur à branches)">Créer une variante</button>}
          </div>
        </div>
        <div className="bloc" style={{ margin: 0 }}>
          <div className="bloc-titre">{ph ? `Phase ${sel! + 1} : ${ph.nom ?? ''}` : 'Sélectionnez une phase'}</div>
          {ph && sel !== null && (
            <>
              <div className="grille-form" style={{ gridTemplateColumns: '1fr 1fr' }}>
                <label style={{ gridColumn: '1 / -1' }}>Nom<Champ ctx={ctx} chemin={['phases', sel, 'nom']} valeur={ph.nom} type="text" large bloc="Phase" cle="nom" libelle="Nom de la phase" /></label>
                {arbre && (
                  <label style={{ gridColumn: '1 / -1' }}>Phase de départ (vide = précédente)
                    <select className="champ champ-bloc" value={ph.depuis ?? ''} onChange={(e) => ctx.actions.fixer(['phases', sel, 'depuis'], e.target.value)}>
                      <option value="">— précédente —</option>
                      <option value="État initial">0. État initial</option>
                      {phases.slice(0, sel).map((p, k) => <option key={k} value={String(p?.nom ?? '')}>{k + 1}. {p?.nom}</option>)}
                    </select></label>
                )}
                {ph.excaver && typeof ph.excaver === 'object' ? (
                  <>
                    {champPhase('defaut', `Excaver à, par défaut (${unite})`, '—', ['phases', sel, 'excaver', 'defaut'])}
                    {[...zonesFond, ...Object.keys(ph.excaver).filter((k) => k !== 'defaut' && !zonesFond.includes(k))].map((z) =>
                      champPhase(z, `Excaver la zone ${z} à (${unite})${zonesFond.includes(z) ? '' : ' (zone inconnue)'}`, 'défaut', ['phases', sel, 'excaver', z]))}
                    {zonesFond.length % 2 === 0 && <span />}
                  </>
                ) : (
                  <>
                    {champPhase('excaver', `Excaver à (${unite})`, '—')}
                    {zonesFond.length
                      ? <label>Fond par zone ({zonesFond.join(', ')})<button className="btn" type="button" title="Écrit excaver: { defaut: …, zone: … } pour cette phase" onClick={() => ctx.actions.fixer(['phases', sel, 'excaver'], { defaut: typeof ph.excaver === 'number' ? ph.excaver : 0 })}>Excaver par zone</button></label>
                      : <span />}
                  </>
                )}
                <label>Poser<Cases ctx={ctx} chemin={['phases', sel, 'poser']} valeur={ph.poser} options={appuis} bloc="Phase" cle="poser" libelle="Appuis posés" /></label>
                <label>Déposer<Cases ctx={ctx} chemin={['phases', sel, 'deposer']} valeur={ph.deposer} options={appuis} bloc="Phase" cle="deposer" libelle="Appuis déposés" /></label>
                {champPhase('aval', `Nappe aval, côté fouille (${unite})`, 'inchangée', ['phases', sel, 'eau', 'aval'])}
                {champPhase('amont', `Nappe amont, côté terre (${unite})`, 'inchangée', ['phases', sel, 'eau', 'amont'])}
                {res?.phases[sel + 1] && !res.phases[sel + 1].ok && <div className="alerte rouge" style={{ gridColumn: '1 / -1' }}>{res.phases[sel + 1].message}</div>}
              </div>
              <Avance nb={['remblayer', 'ajouter_surcharges', 'retirer_surcharges', 'terrasser_risberme'].filter((k) => ph[k] !== undefined && ph[k] !== null && ph[k] !== '').length}>
                <div className="grille-form" style={{ gridTemplateColumns: '1fr 1fr' }}>
                  {champPhase('aval', `Remblai aval à (${unite})`, '—', ['phases', sel, 'remblayer', 'aval'])}
                  {champPhase('amont', `Remblai amont à (${unite})`, '—', ['phases', sel, 'remblayer', 'amont'])}
                  {/* ajouter_surcharges attend des blocs de surcharge complets (schéma) : une liste de noms serait refusée au calcul.
                      La phase d'application d'une surcharge se règle dans l'étape Surcharges (colonne Phase). */}
                  <div className="doux" style={{ gridColumn: '1 / -1', fontSize: 12 }}>
                    Surcharges appliquées à partir d'une phase : colonne « Phase » de l'étape Surcharges.
                    {Array.isArray(ph.ajouter_surcharges) && ph.ajouter_surcharges.length > 0 && ` Ce script ajoute ici ${ph.ajouter_surcharges.length} surcharge(s) décrite(s) dans le script (ajouter_surcharges).`}
                  </div>
                  <label style={{ gridColumn: '1 / -1' }}>Retirer des surcharges<Cases ctx={ctx} chemin={['phases', sel, 'retirer_surcharges']} valeur={ph.retirer_surcharges} options={surcharges} bloc="Phase" cle="retirer_surcharges" libelle="Surcharges retirées" /></label>
                  {(objetsTerrain.length > 0 || ph.terrasser_risberme) && <label style={{ gridColumn: '1 / -1' }}>Terrasser (risbermes, talus, gradins)<Cases ctx={ctx} chemin={['phases', sel, 'terrasser_risberme']} valeur={ph.terrasser_risberme} options={objetsTerrain} bloc="Phase" cle="terrasser_risberme" libelle="Objets de terrain terrassés" /></label>}
                </div>
              </Avance>
            </>
          )}
        </div>
      </div>
      <ErreursBloc ctx={ctx} prefixe="phases" />
    </div>
  )
}
