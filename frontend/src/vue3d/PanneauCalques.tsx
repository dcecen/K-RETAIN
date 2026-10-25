import { useMemo, useRef, useState } from 'react'
import { IconeChevronB, IconeChevronD, IconeCiseaux, IconeFermer, IconeIsoler, IconeLoupe, IconeOeil, IconeOeilBarre, IconeVerrou, IconeVerrouOuvert } from '../lib/icones'
import { telechargerTexte } from '../lib/exporter'
import { confirmer, informer, saisir } from '../lib/dialogue'
import {
  ARBRE_CALQUES, basculerIsolation, definirCoupe, definirMode, definirOpacite, definirReglage, definirVerrou, definirVisible, enregistrerPrereglage,
  etatPrereglage, exporterJson, importerJson, PREREGLAGES_LIVRES, rechercher, REGLAGES, visibiliteGroupe,
  type DefCalque, type DefReglage, type EtatCalques, type Prereglage,
} from './calques'

/** Panneau « Calques » : arbre avec visibilité, opacité, verrou, plan de coupe, mode, isolation ; préréglages. */
export function PanneauCalques({ etat, perso, onEtat, onPerso, onFermer, disponibles, onPrereglage }: {
  /** Appelé quand un préréglage est appliqué (ancre d'URL). */
  onPrereglage?: (id: string | null) => void
  etat: EtatCalques
  perso: Prereglage[]
  onEtat: (e: EtatCalques) => void
  onPerso: (p: Prereglage[]) => void
  onFermer: () => void
  /** Feuilles ayant au moins un objet dans la scène (les autres sont estompées). */
  disponibles?: Set<string>
}) {
  const [texte, setTexte] = useState('')
  const [replies, setReplies] = useState<Set<string>>(() => new Set(['environnement', 'coupes', 'annotations', 'outils']))
  const fichier = useRef<HTMLInputElement>(null)
  const filtre = useMemo(() => rechercher(texte), [texte])

  const basculerRepli = (id: string) => setReplies((r) => { const n = new Set(r); if (n.has(id)) n.delete(id); else n.add(id); return n })

  const enregistrer = () => {
    void saisir({ titre: 'Enregistrer un préréglage de calques', champs: [{ cle: 'nom', libelle: 'Nom du préréglage', type: 'text' }], ok: 'Enregistrer' })
      .then((v) => { const nom = v ? String(v.nom).trim() : ''; if (nom) onPerso(enregistrerPrereglage(perso, nom, etat)) })
  }
  const importer = async (f: File) => {
    try {
      const r = importerJson(await f.text())
      onEtat(r.etat)
      if (r.prereglages.length) onPerso([...perso.filter((p) => !r.prereglages.some((q) => q.id === p.id)), ...r.prereglages])
    } catch (e) { void informer(`Fichier de calques illisible : ${e instanceof Error ? e.message : String(e)}`) }
  }

  const reglage = (id: string, r: DefReglage, v: number | string | boolean | undefined) => {
    const val = v ?? r.defaut
    const fixer = (x: number | string | boolean) => onEtat(definirReglage(etat, id, r.cle, x))
    if (r.type === 'bool') return <label key={r.cle}><input type="checkbox" checked={!!val} onChange={(e) => fixer(e.target.checked)} /> {r.nom}</label>
    if (r.type === 'choix') return (
      <label key={r.cle}>{r.nom}
        <select value={String(val)} onChange={(e) => fixer(e.target.value)}>{r.options!.map((o) => <option key={o.id} value={o.id}>{o.nom}</option>)}</select>
      </label>
    )
    const auto = r.auto && (val === 'auto' || val === 0)
    return (
      <label key={r.cle}>{r.nom}
        {r.auto && <input type="checkbox" checked={!!auto} title="automatique" onChange={(e) => fixer(e.target.checked ? 'auto' : (r.min ?? 1) * 10)} />}
        {r.auto && <span>auto</span>}
        <input type="number" min={r.min} max={r.max} step={r.pas} value={auto ? '' : Number(val)} disabled={!!auto}
          onChange={(e) => fixer(Math.min(Math.max(Number(e.target.value) || (r.min ?? 0), r.min ?? -Infinity), r.max ?? Infinity))} />
      </label>
    )
  }

  const ligne = (d: DefCalque, niveau: number) => {
    if (filtre && !filtre.has(d.id)) return null
    const groupe = !!d.enfants
    const vis = visibiliteGroupe(etat, d.id)
    const feuille = groupe ? null : etat.feuilles[d.id]
    const replie = replies.has(d.id) && !filtre
    const isole = etat.isolation?.id === d.id
    const estompe = !groupe && disponibles && !disponibles.has(d.id)
    const premiere = groupe ? etat.feuilles[d.enfants![0].id] : feuille
    return (
      <li key={d.id}>
        <div className={`calque ${groupe ? 'groupe' : 'enfant'} ${isole ? 'epingle' : ''}`} style={niveau > 1 ? { paddingLeft: 26 + 14 * (niveau - 1) } : undefined}>
          {groupe ? (
            <span className="chevron" onClick={() => basculerRepli(d.id)} role="button" aria-label={replie ? 'Déplier' : 'Replier'}>
              {replie ? <IconeChevronD taille={12} /> : <IconeChevronB taille={12} />}
            </span>
          ) : <span className="chevron" />}
          <input type="checkbox" checked={vis === true} ref={(el) => { if (el) el.indeterminate = vis === 'partiel' }}
            onChange={(e) => onEtat(definirVisible(etat, d.id, e.target.checked))} aria-label={`Afficher ${d.nom}`} />
          <span className={`libelle ${estompe ? 'estompe' : ''}`} title={estompe ? `${d.nom} — rien à afficher dans ce projet` : d.nom}>{d.nom}</span>
          {feuille && d.modes && (
            <select value={feuille.mode} onChange={(e) => onEtat(definirMode(etat, d.id, e.target.value))} aria-label={`Mode de ${d.nom}`}>
              {d.modes.map((m) => <option key={m.id} value={m.id}>{m.nom}</option>)}
            </select>
          )}
          <span className="outils">
            <input type="range" min={0} max={100} value={Math.round((premiere?.opacite ?? 1) * 100)} title="Opacité"
              onChange={(e) => onEtat(definirOpacite(etat, d.id, Number(e.target.value) / 100))} aria-label={`Opacité de ${d.nom}`} />
            <button className={`btn icone discret ${premiere?.coupe ? 'actif' : ''}`} title="Le plan de coupe s'applique à ce calque"
              onClick={() => onEtat(definirCoupe(etat, d.id, !premiere?.coupe))}><IconeCiseaux taille={13} /></button>
            <button className={`btn icone discret ${premiere?.verrou ? 'actif' : ''}`} title={premiere?.verrou ? 'Calque verrouillé (non sélectionnable)' : 'Verrouiller la sélection'}
              onClick={() => onEtat(definirVerrou(etat, d.id, !premiere?.verrou))}>{premiere?.verrou ? <IconeVerrou taille={13} /> : <IconeVerrouOuvert taille={13} />}</button>
            <button className={`btn icone discret ${isole ? 'actif' : ''}`} title={isole ? 'Revenir à l\'état précédent' : 'Isoler ce calque'}
              onClick={() => onEtat(basculerIsolation(etat, d.id))}><IconeIsoler taille={13} /></button>
          </span>
        </div>
        {feuille?.visible && REGLAGES[d.id] && (
          <div className="calque-reglages">
            {REGLAGES[d.id].map((r) => reglage(d.id, r, feuille.reglages?.[r.cle]))}
          </div>
        )}
        {groupe && !replie && <ul>{d.enfants!.map((e) => ligne(e, niveau + 1))}</ul>}
      </li>
    )
  }

  return (
    <aside className="panneau-calques" aria-label="Calques">
      <div className="panneau-entete">
        Calques <span className="raccourci">L</span>
        <span className="espace" />
        <button className="btn icone discret" title="Tout afficher" onClick={() => onEtat(ARBRE_CALQUES.reduce((e, d) => definirVisible(e, d.id, true), etat))}><IconeOeil taille={14} /></button>
        <button className="btn icone discret" title="Tout masquer" onClick={() => onEtat(ARBRE_CALQUES.reduce((e, d) => definirVisible(e, d.id, false), etat))}><IconeOeilBarre taille={14} /></button>
        <button className="btn icone discret" title="Fermer" onClick={onFermer}><IconeFermer taille={14} /></button>
      </div>
      <div className="recherche">
        <IconeLoupe taille={14} />
        <input value={texte} onChange={(e) => setTexte(e.target.value)} placeholder="Rechercher un calque…" aria-label="Rechercher un calque" />
        {texte && <button className="btn icone discret" onClick={() => setTexte('')} title="Effacer"><IconeFermer taille={12} /></button>}
      </div>
      <div className="prereglages" title="Préréglages : un clic applique l'état complet des calques">
        {[...PREREGLAGES_LIVRES, ...perso].map((p) => (
          <button key={p.id} className="btn" title={p.description} onClick={() => { const e = etatPrereglage(p.id, perso); if (e) { onEtat(e); onPrereglage?.(p.id) } }}>{p.nom}</button>
        ))}
      </div>
      <ul className="arbre-calques">{ARBRE_CALQUES.map((d) => ligne(d, 0))}</ul>
      <div className="pied">
        <button className="btn" onClick={enregistrer}>Enregistrer un préréglage</button>
        <button className="btn" onClick={() => telechargerTexte(exporterJson(etat, perso), 'calques_retainwall.json', 'application/json')}>Exporter JSON</button>
        <button className="btn" onClick={() => fichier.current?.click()}>Importer</button>
        <input ref={fichier} type="file" accept=".json" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) void importer(f); e.target.value = '' }} />
        {perso.length > 0 && <button className="btn discret" onClick={() => void confirmer('Supprimer vos préréglages de calques enregistrés ?', { ok: 'Supprimer' }).then((ok) => { if (ok) onPerso([]) })}>Supprimer les miens</button>}
      </div>
    </aside>
  )
}
