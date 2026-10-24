import { useEffect, useState } from 'react'
import { MESSAGE_INJOIGNABLE, messageErreur } from '../lib/api'
import { IconeAlerte } from '../lib/icones'

type Ligne = Record<string, string | number | null>

const TABLES: Record<string, string> = {
  profiles: 'Profilés', palplanches: 'Palplanches', butons: 'Butons modulaires',
  armatures: 'Armatures de tirants', aciers: 'Aciers', betons: 'Bétons',
}

/** Consultation de la base matériaux et import de catalogues (CSV ou Excel). */
export function Materiaux({ surImport }: { surImport: () => void }) {
  const [donnees, setDonnees] = useState<Record<string, Ligne[]>>({})
  const [table, setTable] = useState('profiles')
  const [message, setMessage] = useState<string | null>(null)

  const charger = () => fetch('/api/materiaux')
    .then((r) => { if (!r.ok) throw new Error(`erreur ${r.status}`); return r.json() })
    .then((d) => setDonnees(d && typeof d === 'object' ? d : {}))
    .catch((e) => setMessage(`Base matériaux indisponible : ${messageErreur(e)}`))
  useEffect(() => { void charger() }, [])

  const importer = async (f: File | undefined, champ: HTMLInputElement | null) => {
    if (!f) return
    const corps = new FormData()
    corps.append('fichier', f)
    try {
      let r: Response
      try { r = await fetch('/api/materiaux/import', { method: 'POST', body: corps }) } catch { throw new Error(MESSAGE_INJOIGNABLE) }
      const d = (await r.json().catch(() => null)) as { lignes?: Record<string, number>; detail?: unknown; erreurs?: { message?: string }[] } | null
      if (r.ok && d?.lignes) {
        setMessage(`Import réussi : ${Object.entries(d.lignes).map(([t, n]) => `${t} ${n}`).join(', ')}`)
        void charger()
        surImport()
      } else {
        const detail = typeof d?.detail === 'string' ? d.detail
          : Array.isArray(d?.detail) ? d.detail.map((x) => (typeof x === 'string' ? x : (x as { msg?: string }).msg ?? JSON.stringify(x))).join(' ; ')
          : d?.erreurs?.[0]?.message ?? `erreur ${r.status}`
        setMessage(`Import refusé : ${detail}`)
      }
    } catch (e) {
      setMessage(`Import impossible : ${messageErreur(e)}`)
    } finally {
      if (champ) champ.value = ''   // permet de réimporter le même fichier après correction
    }
  }

  const lignes = donnees[table] ?? []
  const colonnes = lignes.length ? Object.keys(lignes[0]).filter((c) => c !== 'demo') : []
  const fmt = (v: string | number | null) => (typeof v === 'number' ? (Number.isInteger(v) ? v : v.toPrecision(5)) : v ?? '')
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="barre-outils">
        <label className="btn">
          Importer un catalogue (CSV / Excel)
          <input type="file" accept=".csv,.xlsx" hidden onChange={(e) => void importer(e.target.files?.[0], e.target)} />
        </label>
        <span className="note">En-têtes modèles : docs/catalogues/modele_*.csv. CSV : le nom du fichier commence par la table ; Excel : une feuille par table.</span>
        <span className="espace" />
        <div className="puces-choix">
          {Object.entries(TABLES).map(([t, nom]) => (
            <button key={t} className={`puce-choix ${t === table ? 'actif' : ''}`} onClick={() => setTable(t)}>{nom} ({donnees[t]?.length ?? 0})</button>
          ))}
        </div>
      </div>
      <div style={{ flex: 1, overflow: 'auto' }}>
        {message && <div className="alerte info" style={{ margin: 8 }}>{message}</div>}
        {lignes.some((l) => l.demo) && (
          <div className="alerte orange" style={{ margin: 8 }}><IconeAlerte />Lignes DEMO (fond teinté) : valeurs d'illustration, à remplacer par les catalogues fournisseurs avant tout usage.</div>
        )}
        <table className="tableau">
          <thead><tr>{colonnes.map((c) => <th key={c}>{c}</th>)}</tr></thead>
          <tbody>
            {lignes.map((l, i) => (
              <tr key={i} style={l.demo ? { background: 'var(--orange-doux)' } : undefined}>
                {colonnes.map((c) => <td key={c} className={typeof l[c] === 'number' ? 'num' : ''}>{fmt(l[c])}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
