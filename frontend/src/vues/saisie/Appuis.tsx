import { useEffect, useState } from 'react'
import { confirmer } from '../../lib/dialogue'
import type { Selection } from '../../lib/etat'
import { uniteCote } from '../../lib/format'
import { IconeCorbeille, IconePlus } from '../../lib/icones'
import type { Modele } from '../../lib/scriptDoc'
import { Avance, Case, Champ, Choix, ErreursBloc, Reference } from './champs'
import { enumDe, erreurParmi, renseignes, type Ctx } from './outils'
import { CHAMPS_APPUI } from './cles'

const LIBELLES_TYPE: Record<string, string> = { buton: 'Buton', tirant: 'Tirant', bracon: 'Bracon', dalle: 'Dalle' }

export function Appuis({ ctx, selection, onSelection }: { ctx: Ctx; selection: Selection; onSelection: (s: Selection) => void }) {
  const appuis: Record<string, Modele> = ctx.modele.appuis ?? {}
  const noms = Object.keys(appuis)
  const actif = selection?.type === 'appui' && selection.nom in appuis ? selection.nom : noms[0]
  const a = actif ? appuis[actif] : null
  const unite = uniteCote(ctx.modele)
  const [nom, setNom] = useState(actif ?? '')
  useEffect(() => setNom(actif ?? ''), [actif])
  const nouveau = () => {
    let k = noms.length + 1
    while (`B${k}` in appuis) k++
    ctx.actions.ajouterCle(['appuis'], `B${k}`, { type: 'buton', cote: -1.5, espacement: 5, longueur: 15 })
    onSelection({ type: 'appui', nom: `B${k}` })
  }
  const ch = (k: string) => ['appuis', actif!, k]
  const famille = a?.type === 'tirant' ? ['armatures', 'butons', 'profiles'] : ['butons', 'profiles']
  const avancees = a?.type === 'tirant' ? ['E', 'A', 'raideur', 'unilateral', 'longueur_elastique'] : ['E', 'A', 'raideur', 'symetrique', 'lierne', 'unilateral']
  return (
    <div className="saisie">
      <p className="aide">Butons, tirants, bracons et dalles, posés et déposés dans la vue Phases. La raideur vient de l'élément choisi dans la base matériaux ; une raideur imposée ou une section E, A se donnent sous « Options avancées ». La précharge est l'effort axial par appui, appliqué à la pose (mise en charge au vérin).</p>
      <div className="puces-choix" style={{ marginBottom: 12 }}>
        {noms.map((n) => <button key={n} className={`puce-choix ${n === actif ? 'actif' : ''}`} onClick={() => onSelection({ type: 'appui', nom: n })}>{n} <span style={{ opacity: 0.7 }}>· {LIBELLES_TYPE[appuis[n]?.type] ?? appuis[n]?.type}</span></button>)}
        <button className="puce-choix" onClick={nouveau}><IconePlus taille={12} /> nouvel appui</button>
      </div>
      {a && actif && (
        <>
          <div className="bloc"><div className="bloc-titre">{actif}
            <span className="espace" />
            <button className="btn icone discret" title="Supprimer l'appui" onClick={() => void confirmer(`Supprimer l'appui « ${actif} » du script, ainsi que ses références dans les phases ?`, { ok: 'Supprimer' }).then((ok) => { if (ok) { ctx.actions.supprimer(['appuis', actif]); onSelection(null) } })}><IconeCorbeille taille={14} /></button>
          </div>
            <div className="grille-form">
              <label>Nom<input className="champ champ-bloc" value={nom} onChange={(e) => setNom(e.target.value)}
                onBlur={() => { const n = nom.trim(); if (n && n !== actif && !(n in appuis)) { ctx.actions.renommerAppui(actif, n); onSelection({ type: 'appui', nom: n }) } else setNom(actif) }}
                onKeyDown={(e) => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur() }} /></label>
              <label>Type<Choix ctx={ctx} chemin={ch('type')} valeur={a.type} options={enumDe(ctx.schema, 'Appui', 'type')} libelles={LIBELLES_TYPE} bloc="Appui" cle="type" libelle="Type d'appui" /></label>
              <label>Cote sur l'écran ({unite})<Champ ctx={ctx} chemin={ch('cote')} valeur={a.cote} bloc="Appui" cle="cote" large libelle="Cote de l'appui" /></label>
              <label>Élément (base matériaux)<Reference ctx={ctx} chemin={ch('element')} valeur={a.element} familles={famille} vide="— (donner E et A, options avancées)" bloc="Appui" cle="element" libelle="Élément" /></label>
              {a.type !== 'dalle' && <label>Nuance d'acier<Reference ctx={ctx} chemin={ch('acier')} valeur={a.acier} familles={['aciers']} bloc="Appui" cle="acier" libelle="Nuance d'acier" /></label>}
              {a.type === 'dalle' && <label>Classe de béton<Reference ctx={ctx} chemin={ch('beton')} valeur={a.beton} familles={['betons']} bloc="Appui" cle="beton" libelle="Classe de béton" /></label>}
              {(CHAMPS_APPUI[a.type] ?? CHAMPS_APPUI.buton).map(([k, lib]) => (
                <label key={k}>{lib}<Champ ctx={ctx} chemin={ch(k)} valeur={a[k]} bloc="Appui" cle={k} large libelle={lib} /></label>
              ))}
            </div>
          </div>
          <Avance nb={renseignes(a, avancees)} forcer={erreurParmi(ctx, ['appuis', actif], avancees)}>
            <div className="grille-form">
              <label>E (MPa), si pas d'élément<Champ ctx={ctx} chemin={ch('E')} valeur={a.E} large bloc="Appui" cle="E" libelle="Module E" /></label>
              <label>A (cm²), si pas d'élément<Champ ctx={ctx} chemin={ch('A')} valeur={a.A} large bloc="Appui" cle="A" libelle="Section A" /></label>
              <label>Raideur imposée (kN/m par m)<Champ ctx={ctx} chemin={ch('raideur')} valeur={a.raideur} large bloc="Appui" cle="raideur" libelle="Raideur imposée" /></label>
              {a.type === 'tirant' && <label>Longueur élastique imposée (m)<Champ ctx={ctx} chemin={ch('longueur_elastique')} valeur={a.longueur_elastique} large bloc="Appui" cle="longueur_elastique" libelle="Longueur élastique" /></label>}
              {a.type !== 'tirant' && <label>Symétrique (deux écrans en vis-à-vis, L/2)<div><Case ctx={ctx} chemin={ch('symetrique')} valeur={a.symetrique ?? true} bloc="Appui" cle="symetrique" libelle="Symétrique" /></div></label>}
              <label>Unilatéral (pas d'effort négatif)<div><Case ctx={ctx} chemin={ch('unilateral')} valeur={a.unilateral ?? a.type !== 'dalle'} bloc="Appui" cle="unilateral" libelle="Unilatéral" /></div></label>
              {a.type !== 'tirant' && <label>Lierne (profilé)<Reference ctx={ctx} chemin={ch('lierne')} valeur={a.lierne} familles={['profiles']} vide="aucune" bloc="Appui" cle="lierne" libelle="Lierne" /></label>}
            </div>
          </Avance>
        </>
      )}
      {!a && <div className="note">Aucun appui défini : « nouvel appui » crée un buton à adapter.</div>}
      <ErreursBloc ctx={ctx} prefixe="appuis" />
    </div>
  )
}
