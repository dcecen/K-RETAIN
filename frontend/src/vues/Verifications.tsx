import type { ProjetCoupes, Resultats, Verif } from '../lib/api'
import { pourcent } from '../lib/format'

const LIBELLE: Record<Verif['etat'], string> = { ok: 'Vérifié', attention: 'Limite', non_ok: 'Non vérifié', non_verifiable: 'Prévu' }

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

export function Verifications({ res, projet }: { res: Resultats; projet?: ProjetCoupes | null }) {
  const vs = res.verifications ?? []
  if (!vs.length) return <div className="vide-centre">Aucune vérification demandée.<span className="note">Ajoutez-les dans le bloc « Vérifications » de la navigation.</span></div>
  const groupes = new Map<string, Verif[]>()
  for (const v of vs) groupes.set(famille(v), [...(groupes.get(famille(v)) ?? []), v])
  const nOk = vs.filter((v) => v.etat === 'ok' || v.etat === 'attention').length
  const nPrevu = vs.filter((v) => v.etat === 'non_verifiable').length
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="barre-outils">
        <span><b>{nOk}</b> / {vs.length - nPrevu} vérifications satisfaites</span>
        {nPrevu > 0 && <span className="doux">· {nPrevu} prévue(s), non vérifiables tant que les valeurs de norme manquent</span>}
        <span className="espace" />
        <span className="legende-signes">Vert ≤ 90 % · orange 90 à 100 % · rouge &gt; 100 % · « À confirmer » : hypothèse à valider avec la norme</span>
      </div>
      <div style={{ flex: 1, overflow: 'auto' }}>
        {projet && !projet.unique && projet.coupes.length > 1 && (
          <section className="synthese-projet">
            <h3>Synthèse projet — pire coupe par vérification ({projet.coupes.length} coupes)</h3>
            <table className="tableau">
              <thead><tr><th>Vérification</th><th>Élément</th><th>Coupe la plus défavorable</th><th className="num">Taux</th><th>État</th></tr></thead>
              <tbody>
                {projet.synthese.verifications.map((v, i) => (
                  <tr key={i} className={`etat-${v.etat}`}>
                    <td>{v.nom}</td><td>{v.element}</td><td>{v.coupe}</td>
                    <td className="num">{v.taux === null ? '—' : pourcent(v.taux)}</td><td>{LIBELLE[v.etat]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {projet.avertissements.length > 0 && <ul className="doux" style={{ margin: '6px 0 0', paddingLeft: 18 }}>{projet.avertissements.map((a, i) => <li key={i}>{a}</li>)}</ul>}
          </section>
        )}
        <table className="tableau">
          <thead>
            <tr><th>Vérification</th><th>Élément</th><th>Phase</th><th>Valeur de calcul</th><th>Valeur limite</th><th className="num">Taux</th><th>Statut</th><th>Source</th></tr>
          </thead>
          <tbody>
            {[...groupes.entries()].map(([nom, liste]) => (
              <Groupe key={nom} nom={nom} liste={liste} />
            ))}
          </tbody>
        </table>
        {res.suggestions && res.suggestions.length > 0 && (
          <div style={{ padding: '10px 12px' }}>
            <div className="insp-titre">Élément le plus léger qui passe</div>
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
        const couleur = v.etat === 'non_ok' ? 'var(--rouge)' : v.etat === 'attention' ? 'var(--orange)' : v.etat === 'ok' ? 'var(--vert)' : 'var(--texte-faible)'
        return (
          <tr key={i} title={v.detail + (v.manquants.length ? '\nValeurs manquantes : ' + v.manquants.join(', ') : '')}>
            <td>{v.nom}{aConfirmer && <> <span className="etiquette-confirmer">À confirmer</span></>}</td>
            <td>{v.element}</td>
            <td className="doux">{v.phase ?? '—'}</td>
            <td className="calc">{calc}</td>
            <td className="calc">{lim || (v.manquants.length ? <span className="faible">norme : {v.manquants.length} valeur(s) manquante(s)</span> : '')}</td>
            <td className="num">{v.taux === null ? '—' : pourcent(v.taux)}</td>
            <td>
              <div className="barre-taux">
                <span className={`pastille ${v.etat}`}>{LIBELLE[v.etat]}</span>
                <div className="piste"><div className="remplissage" style={{ width: `${Math.min(110, (v.taux ?? 0) * 100) / 1.1}%`, background: couleur }} /></div>
              </div>
            </td>
            <td className="doux" style={{ fontSize: 11, maxWidth: 260 }}>{v.source}</td>
          </tr>
        )
      })}
    </>
  )
}
