import type { ProjetCoupes, Resultats } from '../lib/api'
import type { Vue } from '../lib/etat'
import { nb, pourcent } from '../lib/format'
import { IconeAlerte, IconeInfo } from '../lib/icones'
import { pointsAttention } from '../vue3d/navigation'
import { TEXTE_SEUIL_ATTENTION } from '../lib/verifs'

/** Synthèse du calcul : état, vérifications, valeurs dimensionnantes sur toutes les phases, efforts d'appui
 *  maximaux, points d'attention. Source unique des maxima (les autres vues renvoient ici). */
export function Synthese({ res, projet, onVue, onSelection3d }: {
  res: Resultats
  projet: ProjetCoupes | null
  onVue: (v: Vue) => void
  onSelection3d: (id: string) => void
}) {
  const d = res.dimensionnant
  const verifs = res.verifications ?? []
  const nOk = verifs.filter((v) => v.etat === 'ok' || v.etat === 'attention').length
  const nNonOk = verifs.filter((v) => v.etat === 'non_ok').length
  const nNonVerifiable = verifs.filter((v) => v.etat === 'non_verifiable').length
  const attention = pointsAttention(res, res.maquette?.assemblages ?? {})
  const rompue = res.phases.find((p) => !p.ok)
  const syn = projet && !projet.unique && projet.coupes.length > 1 ? projet.synthese : null
  const nomPhase = (p: string | null | undefined) => p ?? '—'
  return (
    <div className="synthese">
      <section className="bloc">
        <div className="bloc-titre">Calcul</div>
        <dl className="lignes-cle" style={{ padding: 12 }}>
          <dt>Projet</dt><dd style={{ fontFamily: 'inherit', textAlign: 'left' }}>{res.projet}</dd>
          <dt>Phases</dt><dd>{res.phases.length - 1} après l'état initial</dd>
          <dt>État</dt><dd style={{ fontFamily: 'inherit', textAlign: 'left' }}>{res.complet ? 'terminé, toutes les phases convergées' : <span className="statut non_ok">interrompu à la phase « {rompue?.nom ?? '—'} » : {rompue?.message ?? 'rupture'}</span>}</dd>
          {syn && <><dt>Coupes de calcul</dt><dd>{projet!.coupes.length} (synthèse sur la coupe la plus défavorable)</dd></>}
          <dt>Vérifications</dt>
          <dd style={{ fontFamily: 'inherit', textAlign: 'left' }}>
            {verifs.length === 0 ? 'aucune demandée' : <>{verifs.length} ; vérifiées : {nOk} ; <span className={nNonOk ? 'statut non_ok' : ''}>non vérifiées : {nNonOk}</span>{nNonVerifiable > 0 && <> ; non vérifiables (valeur de norme manquante) : {nNonVerifiable}</>}</>}
          </dd>
        </dl>
      </section>

      <section className="bloc">
        <div className="bloc-titre">Valeurs dimensionnantes (toutes phases{syn ? ', toutes coupes' : ''})</div>
        <table className="tableau" style={{ width: 'auto', minWidth: 520 }}>
          <thead><tr><th>Grandeur</th><th className="num">Valeur</th><th>Unité</th><th>Phase</th></tr></thead>
          <tbody>
            <tr><td>Déplacement maximal |y|</td><td className="num">{nb(d.deplacement?.valeur_mm)}</td><td>mm</td><td className="doux">{nomPhase(d.deplacement?.phase)}</td></tr>
            <tr><td>Moment maximal (face côté fouille tendue)</td><td className="num">{nb(d.moment_positif?.valeur, 0)}</td><td>kN·m/m</td><td className="doux">{nomPhase(d.moment_positif?.phase)}</td></tr>
            <tr><td>Moment minimal (face côté terre tendue)</td><td className="num">{nb(d.moment_negatif?.valeur, 0)}</td><td>kN·m/m</td><td className="doux">{nomPhase(d.moment_negatif?.phase)}</td></tr>
            <tr><td>Effort tranchant maximal |V|</td><td className="num">{nb(d.tranchant?.valeur, 0)}</td><td>kN/m</td><td className="doux">{nomPhase(d.tranchant?.phase)}</td></tr>
            {Object.entries(d.appuis ?? {}).map(([n, a]) => (
              <tr key={n} className="cliquable" onClick={() => onSelection3d(`appui:${n}`)} title="Détail de l'appui dans le panneau de droite">
                <td>Effort maximal dans {n}</td><td className="num">{nb(a.effort_kN_m, 1)} / {nb(a.effort_axial_kN, 0)}</td><td>kN/m / kN par appui</td><td className="doux">{nomPhase(a.phase)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="note" style={{ padding: '6px 12px' }}>Signes : déplacement positif vers la fouille ; moment positif quand la face côté fouille est tendue ; effort d'appui positif quand l'appui retient l'écran. Détail par phase : vues Diagrammes et Efforts d'appui.</p>
      </section>

      <section className="bloc">
        <div className="bloc-titre">Points d'attention <span className="doux" style={{ fontWeight: 400 }}>(vérifications non vérifiées ou à taux ≥ {TEXTE_SEUIL_ATTENTION})</span></div>
        {attention.length === 0 ? (
          <div className="alerte info" style={{ margin: 10 }}><IconeInfo />Aucun : toutes les vérifications ont un taux inférieur à {TEXTE_SEUIL_ATTENTION}.{nNonVerifiable > 0 && ' Certaines sont non vérifiables (valeur de norme manquante) : voir la vue Vérifications.'}</div>
        ) : (
          <ul className="points-attention" style={{ padding: 6 }}>
            {attention.map((p, i) => (
              <li key={i} className={p.etat === 'non_ok' || (p.taux ?? 0) >= 1 ? 'rouge' : 'orange'} onClick={() => { onSelection3d(p.selection); onVue('verifications') }} title="Ouvrir la vérification">
                <span className="num">{p.taux === null ? '—' : pourcent(p.taux)}</span> {p.libelle}{p.phase ? <span className="doux"> · {p.phase}</span> : null}
              </li>
            ))}
          </ul>
        )}
      </section>

      {(res.avertissements.length > 0 || (projet?.avertissements.length ?? 0) > 0) && (
        <section className="bloc">
          <div className="bloc-titre">Avertissements du calcul</div>
          <div style={{ padding: 10 }}>
            {[...res.avertissements, ...(projet?.avertissements ?? [])].map((a, i) => <div key={i} className="alerte orange"><IconeAlerte />{a}</div>)}
          </div>
        </section>
      )}

      <div className="liens-vues">
        <button className="btn" onClick={() => onVue('diagrammes')}>Diagrammes</button>
        <button className="btn" onClick={() => onVue('efforts')}>Efforts d'appui</button>
        <button className="btn" onClick={() => onVue('verifications')}>Vérifications</button>
        <button className="btn" onClick={() => onVue('3d')}>Maquette 3D</button>
        <button className="btn" onClick={() => onVue('hypotheses')}>Hypothèses et référentiel</button>
      </div>
    </div>
  )
}
