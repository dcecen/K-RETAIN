import { useEffect, useRef, useState, useSyncExternalStore } from 'react'
import { demandeCourante, lireValeurs, repondre, sAbonner, type Demande } from '../lib/dialogue'

/** Boîte de dialogue de l'application : une seule à la fois, Entrée valide, Échap annule. */
export function Dialogue() {
  const d = useSyncExternalStore(sAbonner, demandeCourante)
  if (!d) return null
  return <Boite cle={String(Date.now())} d={d} />
}

function Boite({ d }: { cle: string; d: Demande }) {
  const [brut, setBrut] = useState<Record<string, string>>(() => (d.genre === 'saisir' ? Object.fromEntries(d.champs.map((c) => [c.cle, c.defaut === undefined ? '' : String(c.defaut)])) : {}))
  const [erreurs, setErreurs] = useState<Record<string, string>>({})
  const premier = useRef<HTMLInputElement | HTMLButtonElement>(null)
  useEffect(() => { premier.current?.focus() }, [])

  const annuler = () => repondre(d.genre === 'confirmer' ? false : null)
  const valider = () => {
    if (d.genre === 'confirmer') return repondre(true)
    if (d.genre === 'informer') return repondre(undefined)
    const r = lireValeurs(d.champs, brut)
    if (Object.keys(r.erreurs).length) { setErreurs(r.erreurs); return }
    repondre(r.valeurs)
  }
  const touche = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') { e.preventDefault(); annuler() }
    if (e.key === 'Enter' && d.genre !== 'saisir') { e.preventDefault(); valider() }
    if (e.key === 'Enter' && d.genre === 'saisir' && (e.target as HTMLElement).tagName === 'INPUT') { e.preventDefault(); valider() }
  }
  const titre = d.titre ?? (d.genre === 'confirmer' ? 'Confirmation' : d.genre === 'informer' ? 'Information' : undefined)
  return (
    <div className="dialogue-voile" onKeyDown={touche}>
      <div className="dialogue" role="dialog" aria-modal="true" aria-label={titre}>
        {titre && <div className="dialogue-titre">{titre}</div>}
        {d.texte && <p className="dialogue-texte">{d.texte}</p>}
        {d.genre === 'saisir' && (
          <div className="dialogue-champs">
            {d.champs.map((c, i) => (
              <label key={c.cle}>{c.libelle}
                <input ref={i === 0 ? (premier as React.RefObject<HTMLInputElement>) : undefined} className={`champ champ-bloc ${c.type === 'number' ? 'num' : ''} ${erreurs[c.cle] ? 'en-erreur' : ''}`}
                  value={brut[c.cle] ?? ''} inputMode={c.type === 'number' ? 'decimal' : undefined} title={erreurs[c.cle]}
                  onChange={(e) => { setBrut({ ...brut, [c.cle]: e.target.value }); if (erreurs[c.cle]) setErreurs({ ...erreurs, [c.cle]: '' }) }} />
                {erreurs[c.cle] && <span className="message-erreur">{erreurs[c.cle]}</span>}
              </label>
            ))}
          </div>
        )}
        <div className="dialogue-boutons">
          {d.genre !== 'informer' && <button className="btn" onClick={annuler}>Annuler</button>}
          <button ref={d.genre === 'saisir' ? undefined : (premier as React.RefObject<HTMLButtonElement>)} className="btn principal" onClick={valider}>
            {d.genre === 'informer' ? 'Fermer' : d.ok}
          </button>
        </div>
      </div>
    </div>
  )
}
