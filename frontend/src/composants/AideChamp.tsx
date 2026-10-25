import type { ErreurScript } from '../lib/api'
import { IconeAlerte } from '../lib/icones'
import { cheminErreur } from '../lib/scriptDoc'
import type { AideChampInfo } from '../vues/saisie'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Schema = any

/** Description et contraintes d'un champ, lues dans le schéma JSON du serveur (racine « Script » ou un bloc). */
function definition(schema: Schema, bloc: string, cle: string): Schema {
  const d = bloc === 'Script' ? schema?.properties?.[cle] : schema?.$defs?.[bloc]?.properties?.[cle]
  return d ?? null
}

function bornes(def: Schema): string[] {
  if (!def) return []
  const out: string[] = []
  const cand = [def, ...(def.anyOf ?? [])]
  for (const c of cand) {
    if (c.minimum !== undefined) out.push(`minimum ${c.minimum}`)
    if (c.exclusiveMinimum !== undefined) out.push(`> ${c.exclusiveMinimum}`)
    if (c.maximum !== undefined) out.push(`maximum ${c.maximum}`)
    if (c.exclusiveMaximum !== undefined) out.push(`< ${c.exclusiveMaximum}`)
    if (c.enum) out.push(`valeurs : ${c.enum.join(', ')}`)
  }
  if (def.default !== undefined && def.default !== null) out.push(`défaut : ${JSON.stringify(def.default)}`)
  return [...new Set(out)]
}

/** Panneau droit des vues de saisie : aide du champ focalisé et erreurs du bloc, cliquables. */
export function AideChamp({ champ, schema, erreurs, prefixe, onLigne }: {
  champ: AideChampInfo | null
  schema: Schema
  erreurs: ErreurScript[]
  prefixe: string | undefined
  onLigne: (l: number | null | undefined) => void
}) {
  const def = champ ? definition(schema, champ.bloc, champ.cle) : null
  const lignes = prefixe ? erreurs.filter((e) => e.chemin.startsWith(prefixe)) : []
  return (
    <aside className="panneau" aria-label="Aide du champ">
      <div className="panneau-entete">Aide du champ</div>
      <div className="panneau-corps">
        {champ ? (
          <div className="insp-section aide-champ">
            <div className="insp-nom">{champ.libelle ?? champ.cle}</div>
            <p>{def?.description || 'Pas de description dans le schéma pour ce champ.'}</p>
            {bornes(def).length > 0 && <ul className="bornes">{bornes(def).map((b) => <li key={b}>{b}</li>)}</ul>}
            <dl className="lignes-cle" style={{ marginTop: 8 }}>
              <dt>Clé du script</dt><dd style={{ textAlign: 'left' }}>{cheminErreur(champ.chemin)}</dd>
            </dl>
            <p className="note" style={{ marginTop: 8 }}>Entrée ou perte de focus : la valeur est écrite dans le script ; Échap annule la frappe. Virgule ou point décimal acceptés.</p>
          </div>
        ) : (
          <div className="insp-section doux">Cliquez un champ : sa signification, son unité et ses bornes s'affichent ici. Chaque valeur modifiée met à jour la ligne correspondante du script YAML.</div>
        )}
        <div className="insp-section">
          <div className="insp-titre">Erreurs de ce bloc</div>
          {lignes.length === 0 ? <div className="note">Aucune erreur signalée par le serveur dans ce bloc.</div> : lignes.map((e, i) => (
            <div key={i} className="alerte rouge" style={{ cursor: e.ligne ? 'pointer' : undefined }} onClick={() => onLigne(e.ligne)} title={e.ligne ? `Ouvrir le script à la ligne ${e.ligne}` : undefined}>
              <IconeAlerte /><span>{e.chemin ? `${e.chemin} : ` : ''}{e.message}</span>
            </div>
          ))}
        </div>
      </div>
    </aside>
  )
}
