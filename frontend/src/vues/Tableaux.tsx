import type { Resultats, Verif } from '../lib/api'

const f = (v: number | undefined | null, d = 1) => (v === undefined || v === null ? '—' : v.toFixed(d))

/** Efforts d'appui par phase (kN/m et effort axial par appui). */
export function TableauAppuis({ res, phaseActive }: { res: Resultats; phaseActive: number }) {
  if (!res.appuis.length) return <p>Aucun appui défini.</p>
  return (
    <div className="tableau-defile">
      <table className="tableau">
        <thead>
          <tr>
            <th>Phase</th>
            {res.appuis.map((a) => (
              <th key={a.nom}>
                {a.nom} ({a.type}, z = {a.cote} m)
                <br />
                <small>kN/m · kN axial</small>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {res.phases.map((p, i) => (
            <tr key={i} className={i === phaseActive ? 'actif' : ''}>
              <td>{p.nom}</td>
              {res.appuis.map((a) => {
                const ap = p.appuis?.find((x) => x.nom === a.nom)
                return (
                  <td key={a.nom} className={ap && !ap.actif ? 'inactif' : ''}>
                    {ap ? `${f(ap.effort_kN_m)} · ${f(ap.effort_axial_kN, 0)}` : ''}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <td>Maximum (phase)</td>
            {res.appuis.map((a) => {
              const d = res.dimensionnant.appuis?.[a.nom]
              return <td key={a.nom}>{d ? `${f(d.effort_kN_m)} · ${f(d.effort_axial_kN, 0)} (${d.phase})` : ''}</td>
            })}
          </tr>
        </tfoot>
      </table>
      <p className="note">Effort positif : l'appui retient l'écran (buton comprimé, tirant tendu). Grisé : appui décollé.</p>
    </div>
  )
}

/** Synthèse par phase. */
export function Synthese({ res, phaseActive, choisir }: { res: Resultats; phaseActive: number; choisir: (i: number) => void }) {
  const d = res.dimensionnant
  return (
    <div>
      <div className="cartes">
        <div className="carte"><span>Déplacement max</span><b>{f(d.deplacement?.valeur_mm)} mm</b><small>{d.deplacement?.phase}</small></div>
        <div className="carte"><span>Moment positif max</span><b>{f(d.moment_positif?.valeur, 0)} kN·m/m</b><small>{d.moment_positif?.phase}</small></div>
        <div className="carte"><span>Moment négatif min</span><b>{f(d.moment_negatif?.valeur, 0)} kN·m/m</b><small>{d.moment_negatif?.phase}</small></div>
        <div className="carte"><span>Tranchant max</span><b>{f(d.tranchant?.valeur, 0)} kN/m</b><small>{d.tranchant?.phase}</small></div>
      </div>
      <table className="tableau">
        <thead>
          <tr><th>Phase</th><th>Fond (m)</th><th>y max (mm)</th><th>à z (m)</th><th>y tête (mm)</th><th>M max</th><th>M min</th><th>|V| max</th><th>État</th></tr>
        </thead>
        <tbody>
          {res.phases.map((p, i) => (
            <tr key={i} className={i === phaseActive ? 'actif' : ''} onClick={() => choisir(i)}>
              <td>{p.nom}</td>
              <td>{f(p.terrain_aval, 2)}</td>
              <td>{f(p.synthese?.y_max_mm)}</td>
              <td>{f(p.synthese?.z_y_max, 2)}</td>
              <td>{f(p.synthese?.y_tete_mm)}</td>
              <td>{f(p.synthese?.M_max, 0)}</td>
              <td>{f(p.synthese?.M_min, 0)}</td>
              <td>{f(p.synthese?.V_absmax, 0)}</td>
              <td>{p.ok ? 'calculée' : <span className="rouge">{p.message}</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <ul className="note">
        {Object.entries(res.conventions).map(([k, v]) => (
          <li key={k}><b>{k}</b> : {v}</li>
        ))}
      </ul>
    </div>
  )
}

const LIBELLE_ETAT: Record<Verif['etat'], string> = {
  ok: 'vérifié',
  attention: 'limite',
  non_ok: 'non vérifié',
  non_verifiable: 'non vérifiable',
}

/** Taux de travail des vérifications (vert, orange, rouge, gris si données manquantes). */
export function Verifications({ res }: { res: Resultats }) {
  const v = res.verifications ?? []
  if (!v.length) return <p>Aucune vérification demandée (mot-clé « verifications » du script).</p>
  return (
    <div className="tableau-defile">
      <table className="tableau">
        <thead>
          <tr><th>Vérification</th><th>Élément</th><th>Phase</th><th>Taux</th><th>État</th><th>Détail</th><th>Source</th></tr>
        </thead>
        <tbody>
          {v.map((x, i) => (
            <tr key={i}>
              <td>{x.nom}</td>
              <td>{x.element}</td>
              <td>{x.phase ?? '—'}</td>
              <td className={`etat-${x.etat}`}>{x.taux === null ? '—' : `${(x.taux * 100).toFixed(0)} %`}</td>
              <td className={`etat-${x.etat}`}>{LIBELLE_ETAT[x.etat]}</td>
              <td>
                {x.detail}
                {x.manquants.length > 0 && (
                  <div className="manquants">Valeurs manquantes : {x.manquants.join(', ')}</div>
                )}
              </td>
              <td className="source">{x.source}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {res.suggestions && res.suggestions.length > 0 && (
        <>
          <h3>Élément le plus léger qui passe</h3>
          <ul>
            {res.suggestions.map((s) => (
              <li key={s.appui}>
                <b>{s.appui}</b> : {s.element ?? '—'} {s.taux !== null && `(taux ${(s.taux * 100).toFixed(0)} %)`} {s.message}
              </li>
            ))}
          </ul>
        </>
      )}
      <p className="note">
        Taux = sollicitation / résistance de calcul. Vert ≤ 90 %, orange 90 à 100 %, rouge &gt; 100 %. « Non vérifiable » :
        une valeur de norme manque dans docs/normes (règle : aucune valeur inventée).
      </p>
    </div>
  )
}
