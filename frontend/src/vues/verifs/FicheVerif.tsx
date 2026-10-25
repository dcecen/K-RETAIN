import type { Verif } from '../../lib/api'
import { pourcent } from '../../lib/format'
import { LIBELLE_ETAT } from '../../lib/verifs'
import { schemaSvg, valeurFiche } from './coupeSvg'

function origineLisible(o: string): string {
  if (o.startsWith('norme:')) {
    const [, fichier, cle] = o.split(':')
    return `docs/normes/${fichier}.yaml (${cle})`
  }
  return { calcul: 'calcul', script: 'script', 'base matériaux': 'base matériaux' }[o] ?? o
}

/** Fiche détaillée d'une vérification : principe, données (avec origine), étapes du calcul, résultat, schéma, source. */
export function FicheVerif({ v, id }: { v: Verif; id: string }) {
  const svg = schemaSvg(v.schema)
  const normes = v.donnees.filter((d) => d.origine.startsWith('norme:'))
  const autres = v.donnees.filter((d) => !d.origine.startsWith('norme:'))
  return (
    <section className={`fiche-verif etat-${v.etat}`} id={id}>
      <header className="fiche-entete">
        <div>
          <h3>{v.nom.replace(' [pseudo-3D]', '')}{v.nom.endsWith(' [pseudo-3D]') && <span className="mention"> (pseudo-3D)</span>}</h3>
          <div className="doux">{v.element}{v.phase ? ` · ${v.phase}` : ''}</div>
        </div>
        <div className={`fiche-statut statut ${v.etat}`}>
          {LIBELLE_ETAT[v.etat]}{v.taux !== null && <span className="num"> · taux {pourcent(v.taux)}</span>}
        </div>
      </header>
      <div className="fiche-corps">
        <div className="fiche-texte">
          <p className="fiche-principe">{v.principe || <span className="doux">Fiche non détaillée pour cette vérification. Détail du calcul : {v.detail}</span>}</p>
          {v.principe && <p className="doux fiche-detail">Résumé : {v.detail}</p>}
          {autres.length > 0 && (
            <table className="tableau compact fiche-donnees">
              <thead><tr><th>Symbole</th><th>Donnée</th><th className="num">Valeur</th><th>Unité</th><th>Origine</th></tr></thead>
              <tbody>
                {autres.map((d, i) => (
                  <tr key={i}><td className="mono">{d.symbole}</td><td>{d.libelle}</td><td className="num">{valeurFiche(d.valeur)}</td><td className="doux">{d.unite}</td><td className="doux">{origineLisible(d.origine)}</td></tr>
                ))}
              </tbody>
            </table>
          )}
          {normes.length > 0 && (
            <div className="fiche-normes">
              <div className="insp-titre">Valeurs normatives utilisées</div>
              <ul>
                {normes.map((d, i) => <li key={i}><span className="mono">{d.symbole}</span> = {valeurFiche(d.valeur)} <span className="doux">({origineLisible(d.origine)})</span></li>)}
              </ul>
            </div>
          )}
          {v.etapes.length > 0 && (
            <div className="fiche-etapes">
              <div className="insp-titre">Calcul</div>
              <ol>{v.etapes.map((e, i) => <li key={i}>{e}</li>)}</ol>
            </div>
          )}
          {v.manquants.length > 0 && <div className="alerte orange">Valeurs manquantes : {v.manquants.join(' ; ')}</div>}
          <p className="doux fiche-source">Référence : {v.source}</p>
        </div>
        {svg && <div className="fiche-schema" dangerouslySetInnerHTML={{ __html: svg }} />}
      </div>
    </section>
  )
}
