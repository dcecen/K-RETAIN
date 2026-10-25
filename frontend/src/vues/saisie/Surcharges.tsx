import { useState } from 'react'
import { confirmer } from '../../lib/dialogue'
import { IconeCorbeille, IconePlus } from '../../lib/icones'
import type { Modele } from '../../lib/scriptDoc'
import { Champ, ChampPaire, Choix, ErreursBloc, Th } from './champs'
import { enumDe, type Ctx } from './outils'

const LIBELLES_TYPE: Record<string, string> = {
  repartie: 'Répartie (uniforme)', uniforme: 'Uniforme', bande: 'Bande parallèle à l’écran', rectangulaire: 'Rectangulaire (en plan)',
  ponctuelle: 'Ponctuelle (en plan)', lineique: 'Linéique', lineaire: 'Linéaire (tracé en plan)', convoi: 'Convoi (modèle à fournir)',
}
const UNITE_Q: Record<string, string> = { ponctuelle: 'kN', lineique: 'kN/m', lineaire: 'kN/m' }
const EN_BANDE = (t: string) => t === 'bande' || t === 'lineique'
const EN_PLAN = (t: string) => t === 'rectangulaire' || t === 'ponctuelle'

export function Surcharges({ ctx }: { ctx: Ctx }) {
  const liste: Modele[] = Array.isArray(ctx.modele.surcharges) ? ctx.modele.surcharges : []
  const types = liste.map((s) => String(s?.type ?? 'repartie'))
  const colBande = types.some(EN_BANDE)
  const colPlan = types.some(EN_PLAN)
  const phasesUtilisees = liste.some((s) => s?.phase !== undefined || s?.phases !== undefined)
  const [phases, setPhases] = useState(false)
  const voirPhases = phases || phasesUtilisees
  const enPlan = !!ctx.modele.plan
  return (
    <div className="saisie">
      <p className="aide">Charges derrière l'écran : répartie sur tout le terrain, bande parallèle à l'écran (Boussinesq) ou linéique (Flamant), définies par leur distance à l'écran ; charges en plan (rectangulaire, ponctuelle) définies par leur centre [x ; y] et leur emprise, qui exigent le bloc <span className="mono">plan</span> du script et peuvent aussi être tracées dans la maquette 3D. Une surcharge s'applique dès le début, ou à partir d'une phase (colonnes « Phases »).</p>
      <div className="bloc">
        <div className="bloc-titre">Surcharges
          <span className="espace" />
          <label className="doux" style={{ fontWeight: 400, display: 'inline-flex', gap: 5, alignItems: 'center' }}>
            <input type="checkbox" checked={voirPhases} disabled={phasesUtilisees} onChange={(e) => setPhases(e.target.checked)} /> phases d'application
          </label>
        </div>
        <table className="tableau">
          <thead><tr>
            <Th t="Nom" /><Th t="Type" /><Th t="q" u="kPa, kN ou kN/m" /><Th t="Face" titre="amont = côté terre, aval = côté fouille" />
            {colBande && <><Th t="Distance à l'écran" u="m" /><Th t="Largeur" u="m" /></>}
            {colPlan && <><Th t="Centre x ; y" u="m" /><Th t="Emprise lx ; ly" u="m" /><Th t="Profondeur" u="m" /></>}
            {voirPhases && <><Th t="Dès la phase" titre="numéro ou nom ; vide = dès le début" /><Th t="Phases [1re ; dernière]" /></>}
            <th />
          </tr></thead>
          <tbody>
            {liste.map((s, i) => {
              const t = String(s?.type ?? 'repartie')
              return (
                <tr key={i}>
                  <td><Champ ctx={ctx} chemin={['surcharges', i, 'nom']} valeur={s?.nom} type="text" placeholder={`S${i + 1}`} bloc="Surcharge" cle="nom" libelle="Nom" /></td>
                  <td><Choix ctx={ctx} chemin={['surcharges', i, 'type']} valeur={s?.type} options={enumDe(ctx.schema, 'Surcharge', 'type')} libelles={LIBELLES_TYPE} bloc="Surcharge" cle="type" libelle="Type de surcharge" /></td>
                  <td><Champ ctx={ctx} chemin={['surcharges', i, 'q']} valeur={s?.q} bloc="Surcharge" cle="q" libelle={`q (${UNITE_Q[t] ?? 'kPa'})`} placeholder={UNITE_Q[t] ?? 'kPa'} /></td>
                  <td><Choix ctx={ctx} chemin={['surcharges', i, 'cote_ecran']} valeur={s?.cote_ecran ?? 'amont'} options={['amont', 'aval']} libelles={{ amont: 'amont (terre)', aval: 'aval (fouille)' }} bloc="Surcharge" cle="cote_ecran" libelle="Face chargée" /></td>
                  {colBande && (EN_BANDE(t) ? <>
                    <td><Champ ctx={ctx} chemin={['surcharges', i, 'distance']} valeur={s?.distance} placeholder="0" bloc="Surcharge" cle="distance" libelle="Distance à l'écran" /></td>
                    <td><Champ ctx={ctx} chemin={['surcharges', i, 'largeur']} valeur={s?.largeur} bloc="Surcharge" cle="largeur" libelle="Largeur de la bande" placeholder={t === 'bande' ? 'requise' : '—'} /></td>
                  </> : <td colSpan={2} className="faible" />)}
                  {colPlan && (EN_PLAN(t) ? <>
                    <td><ChampPaire ctx={ctx} chemin={['surcharges', i, 'position']} valeur={s?.position} bloc="Surcharge" cle="position" libelle="Centre en plan" /></td>
                    <td><ChampPaire ctx={ctx} chemin={['surcharges', i, 'emprise']} valeur={s?.emprise} bloc="Surcharge" cle="emprise" libelle="Emprise" placeholder="lx ; ly" /></td>
                    <td><Champ ctx={ctx} chemin={['surcharges', i, 'profondeur']} valeur={s?.profondeur} placeholder="0" bloc="Surcharge" cle="profondeur" libelle="Profondeur d'application" /></td>
                  </> : <td colSpan={3} className="faible">{t === 'lineaire' || t === 'convoi' ? 'tracé / modèle : dans le script' : ''}</td>)}
                  {voirPhases && <>
                    <td><Champ ctx={ctx} chemin={['surcharges', i, 'phase']} valeur={s?.phase} type="text" placeholder="début" bloc="Surcharge" cle="phase" libelle="Phase d'application" /></td>
                    <td><ChampPaire ctx={ctx} chemin={['surcharges', i, 'phases']} valeur={s?.phases} bloc="Surcharge" cle="phases" libelle="Phases d'existence" placeholder="1re ; dernière" /></td>
                  </>}
                  <td><button className="btn icone discret" title="Supprimer" onClick={() => void confirmer(`Supprimer la surcharge « ${s?.nom ?? `S${i + 1}`} » du script ?`, { ok: 'Supprimer' }).then((ok) => { if (ok) ctx.actions.supprimer(['surcharges', i]) })}><IconeCorbeille taille={14} /></button></td>
                </tr>
              )
            })}
            {liste.length === 0 && <tr><td colSpan={12} className="doux">Aucune surcharge.</td></tr>}
          </tbody>
        </table>
      </div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <button className="btn" onClick={() => ctx.actions.ajouter(['surcharges'], { type: 'repartie', q: 10 })}><IconePlus /> Ajouter une surcharge répartie</button>
        <button className="btn" onClick={() => ctx.actions.ajouter(['surcharges'], { type: 'bande', q: 10, distance: 1, largeur: 2 })}><IconePlus /> Ajouter une bande</button>
        {enPlan && <button className="btn" onClick={() => ctx.actions.ajouter(['surcharges'], { nom: `S${liste.length + 1}`, type: 'rectangulaire', q: 10, position: [0, 0], emprise: [2, 2] })}><IconePlus /> Ajouter une charge en plan</button>}
      </div>
      <ErreursBloc ctx={ctx} prefixe="surcharges" />
    </div>
  )
}
