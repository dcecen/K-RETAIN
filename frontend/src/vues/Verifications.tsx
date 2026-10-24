import type { ProjetCoupes, Resultats, Verif } from '../lib/api'
import { analyserSelection, verifsPour } from '../vue3d/navigation'
import { pourcent } from '../lib/format'

const LIBELLE: Record<Verif['etat'], string> = { ok: 'Vérifié', attention: 'Limite', non_ok: 'Non vérifié', non_verifiable: 'Non vérifiable' }

function famille(v: Verif): string {
  if (v.categorie === 'geotechnique') return 'Géotechnique'
  const n = v.nom.toLowerCase()
  if (n.startsWith('buton') || n.startsWith('bracon')) return 'Butons et bracons'
  if (n.startsWith('lierne')) return 'Liernes'
  if (n.startsWith('tirant')) return 'Tirants'
  if (n.startsWith('dalle')) return 'Dalles'
  return 'Paroi'
}

/** Extraction « valeur de calcul / valeur limite » depuis le détail, quand il les contient. */
function valeurs(v: Verif): [string, string] {
  const d = v.detail
  const m = d.match(/([A-Za-zÀ-ÿ_,.' ]*?= ?[-\d.,]+ ?[^;,(]*?)\s+pour\s+([^;,(]+)/) ?? d.match(/([^;]*?= ?[-\d.,]+ ?[kKMPa·Nm/°%]*)[^;]*?;\s*([^;]*?Rd[^;]*)/)
  if (m) return [m[1].trim(), m[2].trim()]
  const premier = d.split(';')[0].trim()
  return [premier, '']
}

/** Référence courte de la source (premier article cité) ; le texte complet reste au survol. */
function sourceCourte(s: string): string {
  const premier = s.split(/\s*;\s*/)[0] ?? s
  return premier.replace(/\s*—\s*de mémoire, à confirmer/i, '').replace(/\s*\(coefficients\s*:.*\)$/i, '').trim()
}

export function Verifications({ res, projet, filtre, onRetour }: { res: Resultats; projet?: ProjetCoupes | null; filtre?: string | null; onRetour?: () => void }) {
  const sel = analyserSelection(filtre)
  const vs = sel ? verifsPour(sel, res, res.maquette?.assemblages ?? {}) : res.verifications ?? []
  if (!vs.length) return <div className="vide-centre">Aucune vérification demandée.<span className="note">Les vérifications à mener se choisissent dans le bloc « Vérifications demandées » de l'arborescence.</span></div>
  const groupes = new Map<string, Verif[]>()
  for (const v of vs) groupes.set(famille(v), [...(groupes.get(famille(v)) ?? []), v])
  const nOk = vs.filter((v) => v.etat === 'ok' || v.etat === 'attention').length
  const nNonOk = vs.filter((v) => v.etat === 'non_ok').length
  const nNonVerifiable = vs.filter((v) => v.etat === 'non_verifiable').length
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="barre-outils">
        {sel && onRetour && <button className="btn" onClick={onRetour} title="Revenir à la maquette 3D">Maquette 3D</button>}
        {sel && <span className="doux">Filtre : <b>{filtre}</b></span>}
        <span>Vérifications : {vs.length} ; vérifiées : {nOk} ; non vérifiées : {nNonOk}{nNonVerifiable > 0 && ` ; non vérifiables (valeur de norme manquante) : ${nNonVerifiable}`}</span>
        <span className="espace" />
        <span className="legende-signes">Taux de travail = valeur de calcul / valeur limite. Vérifié si taux ≤ 100 %.</span>
      </div>
      <div style={{ flex: 1, overflow: 'auto' }}>
        {projet && !projet.unique && projet.coupes.length > 1 && (
          <section className="synthese-projet">
            <h3>Synthèse projet : coupe la plus défavorable par vérification ({projet.coupes.length} coupes)</h3>
            <table className="tableau">
              <thead><tr><th>Vérification</th><th>Élément</th><th>Coupe la plus défavorable</th><th className="num">Taux</th><th>Statut</th></tr></thead>
              <tbody>
                {projet.synthese.verifications.map((v, i) => (
                  <tr key={i} className={`etat-${v.etat}`}>
                    <td>{v.nom}</td><td>{v.element}</td><td>{v.coupe}</td>
                    <td className="num">{v.taux === null ? '—' : pourcent(v.taux)}</td><td className={`statut ${v.etat}`}>{LIBELLE[v.etat]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {projet.avertissements.length > 0 && <ul className="doux" style={{ margin: '6px 0 0', paddingLeft: 18 }}>{projet.avertissements.map((a, i) => <li key={i}>{a}</li>)}</ul>}
          </section>
        )}
        <table className="tableau">
          <thead>
            <tr><th>Vérification</th><th>Élément</th><th>Phase</th><th>Valeur de calcul</th><th>Valeur limite</th><th className="num">Taux</th><th>Statut</th><th>Référence</th></tr>
          </thead>
          <tbody>
            {[...groupes.entries()].map(([nom, liste]) => (
              <Groupe key={nom} nom={nom} liste={liste} />
            ))}
          </tbody>
        </table>
        {res.suggestions && res.suggestions.length > 0 && (
          <div style={{ padding: '10px 12px' }}>
            <div className="insp-titre">Élément de la base matériaux le plus léger satisfaisant la vérification</div>
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {res.suggestions.map((s) => (
                <li key={s.appui}><b>{s.appui}</b> : {s.element ?? '—'} {s.taux !== null && `(taux ${pourcent(s.taux)})`} <span className="doux">{s.message}</span></li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  )
}

function Groupe({ nom, liste }: { nom: string; liste: Verif[] }) {
  return (
    <>
      <tr className="groupe"><td colSpan={8}>{nom}</td></tr>
      {liste.map((v, i) => {
        const [calc, lim] = valeurs(v)
        const aConfirmer = /simplifi|confirm|hypoth|supposé/i.test(v.source + v.detail)
        return (
          <tr key={i} className={`etat-${v.etat}`} title={v.detail + (v.manquants.length ? '\nValeurs manquantes : ' + v.manquants.join(', ') : '')}>
            <td>{v.nom.replace(' [pseudo-3D]', '')}{v.nom.endsWith(' [pseudo-3D]') && <> <span className="mention" title="Efforts de la plaque pseudo-3D (moment vertical, horizontal, tranchant, appuis réels)">(pseudo-3D)</span></>}{aConfirmer && <> <span className="mention">(hypothèse à confirmer)</span></>}</td>
            <td>{v.element}</td>
            <td className="doux">{v.phase ?? '—'}</td>
            <td className="calc">{calc}</td>
            <td className="calc">{lim || (v.manquants.length ? <span className="faible">valeur de norme manquante : {v.manquants.join(', ')}</span> : '')}</td>
            <td className="num">{v.taux === null ? '—' : pourcent(v.taux)}</td>
            <td className={`statut ${v.etat}`}>{LIBELLE[v.etat]}</td>
            <td className="doux" style={{ fontSize: 11, maxWidth: 260 }} title={v.source}>{sourceCourte(v.source)}</td>
          </tr>
        )
      })}
    </>
  )
}
