import { useEffect, useState } from 'react'

type Ligne = Record<string, string | number | null>

const TABLES: Record<string, string> = {
  profiles: 'Profilés',
  palplanches: 'Palplanches',
  butons: 'Butons modulaires',
  armatures: 'Armatures de tirants',
  aciers: 'Aciers',
  betons: 'Bétons',
}

/** Consultation de la base matériaux et import de catalogues (CSV ou Excel). */
export function Materiaux({ surImport }: { surImport: () => void }) {
  const [donnees, setDonnees] = useState<Record<string, Ligne[]>>({})
  const [table, setTable] = useState('profiles')
  const [message, setMessage] = useState<string | null>(null)

  const charger = () =>
    fetch('/api/materiaux')
      .then((r) => r.json())
      .then(setDonnees)
      .catch(() => setMessage('base matériaux injoignable'))

  useEffect(() => {
    void charger()
  }, [])

  const importer = async (f: File | undefined) => {
    if (!f) return
    const corps = new FormData()
    corps.append('fichier', f)
    const r = await fetch('/api/materiaux/import', { method: 'POST', body: corps })
    const d = await r.json()
    if (r.ok) {
      setMessage(`Import réussi : ${Object.entries(d.lignes).map(([t, n]) => `${t} ${n}`).join(', ')}`)
      void charger()
      surImport()
    } else setMessage(`Import refusé : ${d.detail}`)
  }

  const lignes = donnees[table] ?? []
  const colonnes = lignes.length ? Object.keys(lignes[0]).filter((c) => c !== 'demo') : []
  const fmt = (v: string | number | null) => (typeof v === 'number' ? (Number.isInteger(v) ? v : v.toPrecision(5)) : v ?? '')

  return (
    <div>
      <div className="barre">
        <label className="bouton">
          Importer un catalogue (CSV / Excel)
          <input type="file" accept=".csv,.xlsx" hidden onChange={(e) => void importer(e.target.files?.[0])} />
        </label>
        <span className="note">
          Modèles d'en-têtes : docs/catalogues/modele_*.csv. CSV : le nom du fichier commence par la table ; Excel : une
          feuille par table.
        </span>
      </div>
      {message && <div className="alerte">{message}</div>}
      <nav className="onglets">
        {Object.entries(TABLES).map(([t, nom]) => (
          <button key={t} className={t === table ? 'actif' : ''} onClick={() => setTable(t)}>
            {nom} ({donnees[t]?.length ?? 0})
          </button>
        ))}
      </nav>
      <div className="contenu-onglet tableau-defile">
        {lignes.some((l) => l.demo) && (
          <div className="alerte">
            Lignes DEMO (fond jaune) : valeurs d'illustration, à remplacer par les catalogues fournisseurs avant tout usage.
          </div>
        )}
        <table className="tableau">
          <thead>
            <tr>{colonnes.map((c) => <th key={c}>{c}</th>)}</tr>
          </thead>
          <tbody>
            {lignes.map((l, i) => (
              <tr key={i} style={l.demo ? { background: '#fffbe6' } : undefined}>
                {colonnes.map((c) => <td key={c}>{fmt(l[c])}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
