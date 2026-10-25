import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, messageErreur, type Resultats, type Verif } from '../lib/api'
import type { ParamDef, Schema, TypeAssemblage } from '../lib/assemblages'
import { confirmer } from '../lib/dialogue'
import { nb, pourcent } from '../lib/format'
import { lireNombre } from '../lib/saisie'
import type { Modele } from '../lib/scriptDoc'
import type { Theme } from '../lib/theme'
import { Detail3D } from './Detail3D'
import { SchemaSvg } from './SchemaSvg'

type Params = Record<string, number | string>
const LIBELLE: Record<string, string> = { ok: 'Vérifié', attention: 'Vérifié', non_ok: 'Non vérifié', non_verifiable: 'Non vérifiable' }

/** Champ numérique validé à la sortie (Entrée ou perte de focus) : on peut taper « 0,5 » ou « -12 » sans que la
 *  valeur soit convertie à chaque frappe ; une saisie non numérique est annulée. */
function ChampNombre({ valeur, onValide, commun }: { valeur: number | string; onValide: (v: number | '') => void; commun: Record<string, () => void> }) {
  const [brut, setBrut] = useState(String(valeur))
  useEffect(() => { setBrut(String(valeur)) }, [valeur])
  const valider = () => {
    const t = brut.trim()
    if (t === '') { onValide(''); return }
    const n = lireNombre(t)
    if (n === null) setBrut(String(valeur))
    else if (n !== valeur) onValide(n)
  }
  return <input className="champ champ-bloc num" value={brut} inputMode="decimal" onMouseEnter={commun.onMouseEnter} onMouseLeave={commun.onMouseLeave}
    onFocus={commun.onFocus} onBlur={() => { valider(); commun.onBlur?.() }} onChange={(e) => setBrut(e.target.value)}
    onKeyDown={(e) => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur() }} />
}

/** Efforts d'un appui calculé : N axial max (kN), V (inclinaison), M et V de lierne (deux travées). */
function effortsAppui(res: Resultats | null, nom: string): Record<string, number> {
  const e: Record<string, number> = { N: 0, V: 0, M: 0, T: 0 }
  if (!res) return e
  const def = res.appuis.find((a) => a.nom === nom)
  const dim = res.dimensionnant.appuis?.[nom]
  if (!def || !dim) return e
  const ang = (def.angle * Math.PI) / 180
  const r1 = (v: number) => Math.round(v * 10) / 10
  e.N = e.T = r1(dim.effort_axial_kN)
  e.V = r1(Math.abs(dim.effort_axial_kN * Math.sin(ang)))
  e.M = r1(0.125 * dim.effort_kN_m * def.espacement ** 2)
  e.V_lierne = r1(0.625 * dim.effort_kN_m * def.espacement)
  return e
}

/** Paramètres d'un type : valeurs par défaut, puis celles de l'appui choisi, puis celles d'un bloc existant du script. */
function parametresPour(type: TypeAssemblage, app: Modele, references: Record<string, string[]>, bloc: Modele): Params {
  const d: Params = Object.fromEntries(type.parametres.map((p) => [p.cle, p.defaut]))
  d.lierne = bloc?.lierne ?? app?.lierne ?? (references.profiles?.[0] ?? '')
  d.buton = bloc?.buton ?? app?.element ?? ''
  d.acier = bloc?.acier ?? app?.acier ?? 'S355'
  if (app && typeof app.angle === 'number' && 'angle' in d) d.angle = app.angle
  if (bloc?.parametres && typeof bloc.parametres === 'object') Object.assign(d, bloc.parametres)
  return d
}

export function Assemblages({ res, modele, references, theme, onEnregistrer, onSupprimer }: {
  res: Resultats | null
  modele: Modele
  references: Record<string, string[]>
  theme: Theme
  /** Écriture dans le script : ajout d'un bloc, ou remplacement d'un bloc existant (`remplacer`). */
  onEnregistrer: (nom: string, bloc: Record<string, unknown>, remplacer: boolean) => void
  onSupprimer: (nom: string) => void
}) {
  const [types, setTypes] = useState<TypeAssemblage[]>([])
  const [vignettes, setVignettes] = useState<Record<string, Schema>>({})
  const [cle, setCle] = useState<string>('platine_about')
  const [params, setParams] = useState<Params>({})
  const [appui, setAppui] = useState<string>('')
  const [efforts, setEfforts] = useState<Record<string, number>>({ N: 500, V: 0, M: 0, T: 500 })
  const [schema, setSchema] = useState<Schema | null>(null)
  const [verifs, setVerifs] = useState<Verif[]>([])
  const [survol, setSurvol] = useState<Set<string>>(new Set())
  const [reperes, setReperes] = useState<Set<number>>(new Set())
  const [vueActive, setVueActive] = useState(0)
  const [erreur, setErreur] = useState<string | null>(null)
  const [nomSauvegarde, setNomSauvegarde] = useState('A1')
  const [existant, setExistant] = useState<string | null>(null)   // bloc du script ouvert pour modification
  const enAttente = useRef<Modele>(null)                          // bloc à appliquer au prochain changement de type
  const minuterie = useRef<number | undefined>(undefined)
  const type = types.find((t) => t.cle === cle)
  const dansScript: Record<string, Modele> = modele?.assemblages && typeof modele.assemblages === 'object' ? modele.assemblages : {}

  useEffect(() => {
    api.assemblagesTypes().then((ts) => {
      setTypes(ts)
      // vignettes : schéma par défaut de chaque type
      ts.forEach((t) => {
        const defauts: Params = Object.fromEntries(t.parametres.map((p) => [p.cle, p.defaut]))
        defauts.lierne = 'HEB 300'; defauts.buton = 'modulaire_A'; defauts.acier = 'S355'
        api.assemblagesSchema({ type: t.cle, parametres: defauts, efforts: { N: 500, V: 20, M: 100, T: 500 } })
          .then((s) => setVignettes((v) => ({ ...v, [t.cle]: s }))).catch(() => {})
      })
    }).catch((e) => setErreur(`Types d'assemblages indisponibles : ${messageErreur(e)}`))
  }, [])

  // changement de type : paramètres par défaut, lierne / buton de l'appui choisi, bloc du script en attente
  useEffect(() => {
    if (!type) return
    const bloc = enAttente.current
    enAttente.current = null
    const app = (bloc?.appui ?? appui) ? modele?.appuis?.[bloc?.appui ?? appui] : null
    setParams(parametresPour(type, app, references, bloc))
    setVueActive(0)
    setReperes(new Set())
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cle, types])

  useEffect(() => {
    if (!appui) return
    const app = modele?.appuis?.[appui]
    setEfforts(effortsAppui(res, appui))
    setParams((p) => ({ ...p, lierne: app?.lierne ?? p.lierne, buton: app?.element ?? p.buton, acier: app?.acier ?? p.acier }))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [appui, res])

  /** Ouvre un assemblage du script pour le modifier. */
  const ouvrir = (nom: string) => {
    const bloc = dansScript[nom]
    if (!bloc || typeof bloc !== 'object') return
    setExistant(nom)
    setNomSauvegarde(nom)
    setAppui(typeof bloc.appui === 'string' ? bloc.appui : '')
    if (bloc.efforts && typeof bloc.efforts === 'object') setEfforts({ N: 0, V: 0, M: 0, T: 0, ...bloc.efforts })
    const t = types.find((x) => x.cle === bloc.type)
    if (!t) { setErreur(`Type d'assemblage inconnu : ${bloc.type}`); return }
    if (t.cle === cle) {
      const app = bloc.appui ? modele?.appuis?.[bloc.appui] : null
      setParams(parametresPour(t, app, references, bloc))
    } else { enAttente.current = bloc; setCle(t.cle) }
  }
  const nouveau = (t: string) => {
    setExistant(null)
    let k = 1
    while (`A${k}` in dansScript) k++
    setNomSauvegarde(`A${k}`)
    if (t !== cle) setCle(t)
  }

  const fck = (res?.paroi as { beton?: { fck_MPa?: number } } | undefined)?.beton?.fck_MPa ?? null
  const recalculer = useCallback(() => {
    if (!type) return
    const e = { ...efforts, V: cle === 'eclisse_lierne' ? (efforts.V_lierne ?? efforts.V) : efforts.V }
    Promise.all([
      api.assemblagesSchema({ type: cle, parametres: params, efforts: e, fck }),
      api.assemblagesVerifier({ type: cle, parametres: params, efforts: e, fck }),
    ]).then(([s, v]) => { setSchema(s); setVerifs(v); setErreur(null) }).catch((err) => setErreur(messageErreur(err)))
  }, [type, cle, params, efforts, fck])

  useEffect(() => {
    window.clearTimeout(minuterie.current)
    minuterie.current = window.setTimeout(recalculer, 250)
  }, [recalculer])

  const familles = useMemo(() => {
    const m = new Map<string, TypeAssemblage[]>()
    for (const t of types) m.set(t.famille, [...(m.get(t.famille) ?? []), t])
    return [...m.entries()]
  }, [types])

  const champ = (p: ParamDef) => {
    const v = params[p.cle] ?? p.defaut
    const commun = { onMouseEnter: () => setSurvol(new Set([p.cle])), onMouseLeave: () => setSurvol(new Set()), onFocus: () => setSurvol(new Set([p.cle])), onBlur: () => setSurvol(new Set()) }
    if (p.genre === 'choix' && p.choix) {
      return <select className="champ champ-bloc" value={String(v)} {...commun} onChange={(e) => setParams({ ...params, [p.cle]: isNaN(Number(e.target.value)) ? e.target.value : Number(e.target.value) })}>
        {p.choix.map((c) => <option key={String(c)} value={String(c)}>{String(c)}</option>)}</select>
    }
    if (p.genre === 'profil' || p.genre === 'tube' || p.genre === 'acier' || p.genre === 'beton') {
      const liste = p.genre === 'profil' ? references.profiles ?? [] : p.genre === 'tube' ? [...(references.butons ?? []), ...(references.profiles ?? [])] : p.genre === 'acier' ? references.aciers ?? [] : references.betons ?? []
      return <select className="champ champ-bloc" value={String(v)} {...commun} onChange={(e) => setParams({ ...params, [p.cle]: e.target.value })}>
        <option value="">—</option>{liste.map((r) => <option key={r} value={r}>{r}</option>)}</select>
    }
    return <ChampNombre valeur={v} commun={commun} onValide={(n) => setParams((q) => ({ ...q, [p.cle]: n }))} />
  }

  const effortsDemandes = type?.efforts ?? ['N']
  const appuis = Object.keys(modele?.appuis ?? {})

  const enregistrer = () => {
    const { acier, lierne, buton, ...reste } = params
    const base: Record<string, unknown> = existant && dansScript[existant] && typeof dansScript[existant] === 'object' ? { ...dansScript[existant] } : {}
    const bloc: Record<string, unknown> = { ...base, type: cle }
    if (appui) { bloc.appui = appui; delete bloc.efforts } else { bloc.efforts = Object.fromEntries(effortsDemandes.map((k) => [k, efforts[k] ?? 0])); delete bloc.appui }
    if (acier) bloc.acier = acier; else delete bloc.acier
    if (lierne) bloc.lierne = lierne; else delete bloc.lierne
    if (buton) bloc.buton = buton; else delete bloc.buton
    const defauts = Object.fromEntries((type?.parametres ?? []).map((p) => [p.cle, p.defaut]))
    const parametres = Object.fromEntries(Object.entries(reste).filter(([k, v]) => v !== '' && v !== defauts[k]))
    if (Object.keys(parametres).length) bloc.parametres = parametres; else delete bloc.parametres
    const nom = nomSauvegarde.trim()
    const remplacer = existant === nom
    onEnregistrer(nom, bloc, remplacer)
    setExistant(nom)
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '240px minmax(0, 1fr) 340px', height: '100%', minHeight: 0 }}>
      {/* --- assemblages du script, puis types avec vignettes */}
      <div style={{ overflow: 'auto', borderRight: '1px solid var(--filet)' }}>
        <div className="panneau-entete">Dans le script</div>
        {Object.keys(dansScript).length === 0 && <div className="note" style={{ padding: '6px 10px' }}>Aucun assemblage enregistré. Choisissez un type ci-dessous, réglez-le, puis « Ajouter au script ».</div>}
        {Object.entries(dansScript).map(([nom, b]) => (
          <button key={nom} className={`noeud ${existant === nom ? 'actif' : ''}`} onClick={() => ouvrir(nom)} title={`Modifier l'assemblage ${nom}`}>
            <span className="chevron" /><span className="libelle">{nom}</span>
            <span className="meta">{types.find((t) => t.cle === b?.type)?.nom ?? b?.type}{b?.appui ? ` · ${b.appui}` : ''}</span>
          </button>
        ))}
        <div className="panneau-entete">Nouveau : types</div>
        {familles.map(([fam, liste]) => (
          <div key={fam}>
            <div className="titre-groupe" style={{ padding: '6px 10px 2px', fontSize: 11, color: 'var(--texte-faible)', textTransform: 'uppercase', letterSpacing: '0.4px' }}>{fam}</div>
            {liste.map((t) => (
              <button key={t.cle} className={`noeud ${t.cle === cle && !existant ? 'actif' : ''}`} style={{ height: 'auto', padding: '6px 8px', display: 'block', textAlign: 'left', whiteSpace: 'normal' }}
                onClick={() => nouveau(t.cle)} title={t.description}>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <div style={{ width: 84, height: 60, flexShrink: 0, border: '1px solid var(--filet)', background: 'var(--panneau)', overflow: 'hidden' }}>
                    {vignettes[t.cle] && <SchemaSvg schema={vignettes[t.cle]} vue={vignettes[t.cle].vues[0]} hauteur={60} compact />}
                  </div>
                  <span style={{ fontSize: 12.5 }}>{t.nom}</span>
                </div>
              </button>
            ))}
          </div>
        ))}
      </div>

      {/* --- schéma */}
      <div style={{ display: 'flex', flexDirection: 'column', minHeight: 0, minWidth: 0 }}>
        <div className="barre-outils">
          <b style={{ whiteSpace: 'nowrap' }}>{existant ? `${existant} : ` : ''}{type?.nom}</b>
          <span className="doux masquer-etroit" style={{ fontSize: 12, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', minWidth: 0 }}>{type?.description}</span>
          <span className="espace" />
          {schema?.vues.map((v, i) => <button key={i} className={`puce-choix ${i === vueActive ? 'actif' : ''}`} onClick={() => setVueActive(i)}>{v.nom}</button>)}
          <button className={`puce-choix ${vueActive === -1 ? 'actif' : ''}`} onClick={() => setVueActive(-1)}>Détail 3D</button>
          <button className={`puce-choix ${vueActive === -2 ? 'actif' : ''}`} onClick={() => setVueActive(-2)}>Toutes les vues</button>
        </div>
        <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
          {erreur && <div className="alerte rouge" style={{ margin: 12 }}>{erreur}</div>}
          {schema?.demo && <div className="alerte orange" style={{ margin: '8px 12px 0' }}>Matériaux du jeu DEMO : valeurs d'illustration.</div>}
          {schema && vueActive >= 0 && <SchemaSvg schema={schema} vue={schema.vues[vueActive]} params={survol} reperes={reperes} hauteur={520} onRepere={(r) => setReperes(new Set([r]))} />}
          {schema && vueActive === -1 && <Detail3D schema={schema} reperes={reperes} theme={theme} hauteur={520} />}
          {schema && vueActive === -2 && schema.vues.map((v, i) => <SchemaSvg key={i} schema={schema} vue={v} params={survol} reperes={reperes} hauteur={360} onRepere={(r) => setReperes(new Set([r]))} />)}
          {schema && (
            <div style={{ padding: '8px 12px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div>
                <div className="insp-titre">Nomenclature</div>
                <table className="tableau">
                  <thead><tr><th>Rep.</th><th>Désignation</th><th>Matériau</th><th className="num">Nb</th></tr></thead>
                  <tbody>
                    {schema.nomenclature.map((n) => (
                      <tr key={n.repere} className={`cliquable ${reperes.has(n.repere) ? 'actif' : ''}`} onClick={() => setReperes(new Set([n.repere]))}>
                        <td className="mono">{n.repere}</td><td>{n.nom}</td><td className="doux">{n.materiau}</td><td className="num">{n.nombre}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div>
                <div className="insp-titre">Notes</div>
                {schema.notes.map((n, i) => <p key={i} className="note" style={{ margin: '0 0 6px' }}>{n}</p>)}
                <p className="note">Cotes en mm, efforts en kN. Symboles de soudure ISO 2553 : triangle = cordon d'angle (gorge a), cercle = contour. Survolez un champ pour surligner sa cote ; cliquez une vérification ou un repère pour surligner la pièce.</p>
              </div>
            </div>
          )}
          <div style={{ padding: '0 12px 16px' }}>
            <div className="insp-titre">Vérifications</div>
            <table className="tableau">
              <thead><tr><th>Vérification</th><th>Élément</th><th className="num">Taux</th><th>Statut</th><th>Détail</th></tr></thead>
              <tbody>
                {verifs.map((v, i) => (
                  <tr key={i} className={`cliquable ${v.reperes.some((r) => reperes.has(r)) ? 'actif' : ''}`} onClick={() => setReperes(new Set(v.reperes))} title={v.source + (v.manquants.length ? '\nValeurs manquantes : ' + v.manquants.join(', ') : '')}>
                    <td>{v.nom}{/simplifi|hypoth|confirm/i.test(v.source + v.detail) && <> <span className="mention">(hypothèse à confirmer)</span></>}</td>
                    <td className="doux">{v.element}</td>
                    <td className="num">{v.taux === null ? '—' : pourcent(v.taux)}</td>
                    <td className={`statut ${v.etat}`}>{LIBELLE[v.etat]}</td>
                    <td className="doux" style={{ fontSize: 11.5 }}>{v.detail}{v.manquants.length > 0 && <div className="manquants faible">manque : {v.manquants.slice(0, 3).join(', ')}{v.manquants.length > 3 ? '…' : ''}</div>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* --- paramètres et efforts */}
      <div style={{ overflow: 'auto', borderLeft: '1px solid var(--filet)' }}>
        <div className="panneau-entete">Efforts</div>
        <div className="grille-form" style={{ gridTemplateColumns: '1fr' }}>
          <label>Appui du calcul (efforts automatiques)
            <select className="champ champ-bloc" value={appui} onChange={(e) => setAppui(e.target.value)}>
              <option value="">— saisie manuelle —</option>
              {appuis.map((a) => <option key={a} value={a}>{a} ({modele?.appuis?.[a]?.type}){res?.dimensionnant.appuis?.[a] ? ` · ${nb(res.dimensionnant.appuis[a].effort_axial_kN, 0)} kN` : ''}</option>)}
            </select>
          </label>
          {effortsDemandes.map((k) => (
            <label key={k}>{k === 'N' ? 'N — effort axial (kN)' : k === 'T' ? 'T — traction du tirant (kN)' : k === 'V' ? 'V — effort transversal (kN)' : 'M — moment dans la lierne (kN·m)'}
              <input className="champ champ-bloc num" value={String(efforts[k] ?? 0)} inputMode="decimal" onChange={(e) => setEfforts({ ...efforts, [k]: Number(e.target.value.replace(',', '.')) || 0 })} /></label>
          ))}
        </div>
        <div className="panneau-entete">Paramètres</div>
        <div className="grille-form" style={{ gridTemplateColumns: '1fr' }}>
          {type?.parametres.map((p) => (
            <label key={p.cle} title={p.cle}>{p.libelle}{p.unite ? ` (${p.unite})` : ''}{champ(p)}</label>
          ))}
        </div>
        <div className="panneau-entete">{existant ? 'Enregistrer dans le script' : 'Ajouter au script'}</div>
        <div className="grille-form" style={{ gridTemplateColumns: '1fr' }}>
          <label>Nom de l'assemblage<input className="champ champ-bloc" value={nomSauvegarde} onChange={(e) => setNomSauvegarde(e.target.value)} /></label>
          <button className="btn principal" disabled={!type || !nomSauvegarde.trim()} onClick={enregistrer}>
            {existant === nomSauvegarde.trim() ? 'Enregistrer les modifications' : nomSauvegarde.trim() in dansScript ? `Remplacer ${nomSauvegarde.trim()}` : 'Ajouter au script'}
          </button>
          {existant && (
            <button className="btn" onClick={() => void confirmer(`Supprimer l'assemblage « ${existant} » du script ?`, { ok: 'Supprimer' }).then((ok) => { if (ok) { onSupprimer(existant); setExistant(null) } })}>Supprimer du script</button>
          )}
          <p className="note">L'assemblage enregistré est revérifié à chaque calcul avec les efforts de l'appui, et apparaît dans la vue Vérifications.</p>
        </div>
      </div>
    </div>
  )
}
