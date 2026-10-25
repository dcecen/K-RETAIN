// Briques communes des formulaires de saisie : champs liés au script YAML, bloc « Options avancées », aide du champ.
import { useEffect, useState, type ReactNode } from 'react'
import type { Chemin } from '../../lib/scriptDoc'
import { doc, erreurDe, type Ctx } from './outils'

/** Champ texte ou numérique, validé à la perte de focus ou à Entrée ; Échap annule. */
export function Champ({ ctx, chemin, valeur, type = 'number', bloc, cle, placeholder, large, libelle }: {
  ctx: Ctx; chemin: Chemin; valeur: unknown; type?: 'number' | 'text'; bloc?: string; cle?: string; placeholder?: string; large?: boolean; libelle?: string
}) {
  const [brut, setBrut] = useState(valeur === undefined || valeur === null ? '' : String(valeur))
  useEffect(() => { setBrut(valeur === undefined || valeur === null ? '' : String(valeur)) }, [valeur])
  const err = erreurDe(ctx, chemin)
  const valider = () => {
    const t = brut.trim()
    const actuel = valeur === undefined || valeur === null ? '' : String(valeur)
    if (t === actuel) return
    if (t === '') return ctx.actions.fixer(chemin, '')
    if (type === 'number') {
      const n = Number(t.replace(',', '.'))
      if (!Number.isFinite(n)) return setBrut(actuel)
      ctx.actions.fixer(chemin, n)
    } else ctx.actions.fixer(chemin, t)
  }
  return (
    <input className={`champ ${type === 'number' ? 'num' : ''} ${err ? 'en-erreur' : ''} ${large ? 'champ-bloc' : ''}`}
      value={brut} placeholder={placeholder} inputMode={type === 'number' ? 'decimal' : undefined}
      title={err ?? (bloc && cle ? doc(ctx.schema, bloc, cle) : undefined)}
      onFocus={() => { if (bloc && cle) ctx.onAide?.({ bloc, cle, chemin, libelle }) }}
      onChange={(e) => setBrut(e.target.value)} onBlur={valider}
      onKeyDown={(e) => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur(); if (e.key === 'Escape') setBrut(valeur === undefined ? '' : String(valeur)) }} />
  )
}

/** Deux nombres dans un seul champ (« x ; y »), écrits comme liste [x, y] dans le script. */
export function ChampPaire({ ctx, chemin, valeur, bloc, cle, placeholder, libelle }: {
  ctx: Ctx; chemin: Chemin; valeur: unknown; bloc?: string; cle?: string; placeholder?: string; libelle?: string
}) {
  const texte = (v: unknown) => (Array.isArray(v) && v.length >= 2 ? `${v[0]} ; ${v[1]}` : v && typeof v === 'object' ? Object.values(v as object).join(' ; ') : '')
  const [brut, setBrut] = useState(texte(valeur))
  useEffect(() => { setBrut(texte(valeur)) }, [valeur])
  const err = erreurDe(ctx, chemin)
  const valider = () => {
    const t = brut.trim()
    if (t === texte(valeur)) return
    if (t === '') return ctx.actions.fixer(chemin, '')
    const parts = t.split(/[;,]\s*|\s+/).filter(Boolean).map((x) => Number(x.replace(',', '.')))
    if (parts.length !== 2 || parts.some((n) => !Number.isFinite(n))) return setBrut(texte(valeur))
    ctx.actions.fixer(chemin, parts)
  }
  return (
    <input className={`champ num ${err ? 'en-erreur' : ''}`} value={brut} placeholder={placeholder ?? 'x ; y'} inputMode="decimal"
      title={err ?? (bloc && cle ? doc(ctx.schema, bloc, cle) : undefined)}
      onFocus={() => { if (bloc && cle) ctx.onAide?.({ bloc, cle, chemin, libelle }) }}
      onChange={(e) => setBrut(e.target.value)} onBlur={valider}
      onKeyDown={(e) => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur(); if (e.key === 'Escape') setBrut(texte(valeur)) }} />
  )
}

export function Choix({ ctx, chemin, valeur, options, vide, bloc, cle, libelle, libelles }: {
  ctx: Ctx; chemin: Chemin; valeur: unknown; options: string[]; vide?: string; bloc?: string; cle?: string; libelle?: string; libelles?: Record<string, string>
}) {
  const err = erreurDe(ctx, chemin)
  return (
    <select className={`champ ${err ? 'en-erreur' : ''}`} value={valeur === undefined || valeur === null ? '' : String(valeur)} title={err ?? undefined}
      onFocus={() => { if (bloc && cle) ctx.onAide?.({ bloc, cle, chemin, libelle }) }}
      onChange={(e) => ctx.actions.fixer(chemin, e.target.value)}>
      {vide !== undefined && <option value="">{vide}</option>}
      {options.map((o) => <option key={o} value={o}>{libelles?.[o] ?? o}</option>)}
    </select>
  )
}

export function Case({ ctx, chemin, valeur, bloc, cle, libelle }: { ctx: Ctx; chemin: Chemin; valeur: unknown; bloc?: string; cle?: string; libelle?: string }) {
  return <input type="checkbox" checked={!!valeur} onFocus={() => { if (bloc && cle) ctx.onAide?.({ bloc, cle, chemin, libelle }) }}
    onChange={(e) => ctx.actions.fixer(chemin, e.target.checked)} />
}

/** Liste de références de la base matériaux (profilés, aciers, bétons…). */
export function Reference({ ctx, chemin, valeur, familles, vide = '—', bloc, cle, libelle }: {
  ctx: Ctx; chemin: Chemin; valeur: unknown; familles: string[]; vide?: string; bloc?: string; cle?: string; libelle?: string
}) {
  const err = erreurDe(ctx, chemin)
  return (
    <select className={`champ champ-bloc ${err ? 'en-erreur' : ''}`} value={valeur === undefined || valeur === null ? '' : String(valeur)} title={err ?? undefined}
      onFocus={() => { if (bloc && cle) ctx.onAide?.({ bloc, cle, chemin, libelle }) }}
      onChange={(e) => ctx.actions.fixer(chemin, e.target.value)}>
      <option value="">{vide}</option>
      {familles.flatMap((f) => ctx.references[f] ?? []).map((r) => <option key={r} value={r}>{r}</option>)}
    </select>
  )
}

/** Cases à cocher sur une liste d'éléments existants (appuis à poser, surcharges à retirer…), écrites comme
 *  texte unique ou liste dans le script. */
export function Cases({ ctx, chemin, valeur, options, bloc, cle, libelle }: {
  ctx: Ctx; chemin: Chemin; valeur: unknown; options: string[]; bloc?: string; cle?: string; libelle?: string
}) {
  const actuels: string[] = Array.isArray(valeur) ? valeur.map(String) : valeur ? [String(valeur)] : []
  const inconnus = actuels.filter((a) => !options.includes(a))
  const basculer = (o: string) => {
    const l = actuels.includes(o) ? actuels.filter((x) => x !== o) : [...actuels, o]
    ctx.actions.fixer(chemin, l.length === 0 ? '' : l.length === 1 ? l[0] : l)
  }
  if (!options.length && !inconnus.length) return <span className="note">aucun élément défini</span>
  return (
    <div className="cases-choix" onFocus={() => { if (bloc && cle) ctx.onAide?.({ bloc, cle, chemin, libelle }) }}>
      {options.map((o) => (
        <label key={o} className={`case-choix ${actuels.includes(o) ? 'actif' : ''}`}>
          <input type="checkbox" checked={actuels.includes(o)} onChange={() => basculer(o)} /> {o}
        </label>
      ))}
      {inconnus.map((o) => (
        <label key={o} className="case-choix actif inconnu" title="Nom absent de la liste des éléments définis">
          <input type="checkbox" checked onChange={() => basculer(o)} /> {o} ?
        </label>
      ))}
    </div>
  )
}

export const Th = ({ t, u, titre }: { t: ReactNode; u?: string; titre?: string }) => <th title={titre}>{t}{u && <span className="unite">{u}</span>}</th>

/** Bloc replié « Options avancées » : compteur de valeurs renseignées, ouvert d'office si une erreur s'y trouve. */
export function Avance({ titre = 'Options avancées', nb, forcer, children }: { titre?: string; nb: number; forcer?: boolean; children: ReactNode }) {
  const [ouvert, setOuvert] = useState(false)
  return (
    <details className="avance" open={ouvert || forcer || undefined} onToggle={(e) => setOuvert((e.target as HTMLDetailsElement).open)}>
      <summary>{titre}<span className="doux"> {nb > 0 ? `(${nb} renseignée${nb > 1 ? 's' : ''})` : '(aucune renseignée)'}</span></summary>
      <div className="avance-corps">{children}</div>
    </details>
  )
}

/** Erreurs du serveur rattachées à un bloc du script, listées sous le formulaire. */
export function ErreursBloc({ ctx, prefixe }: { ctx: Ctx; prefixe: string }) {
  const liste = ctx.erreurs.filter((e) => e.chemin.startsWith(prefixe))
  if (!liste.length) return null
  return <div style={{ marginTop: 8 }}>{liste.map((e, i) => <div key={i} className="message-erreur">{e.chemin} : {e.message}</div>)}</div>
}

