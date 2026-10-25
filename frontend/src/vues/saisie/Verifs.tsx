import { Champ, ErreursBloc } from './champs'
import { type Ctx } from './outils'
import { VERIFS } from './cles'

export function Verifs({ ctx }: { ctx: Ctx }) {
  const actives: string[] = Array.isArray(ctx.modele.verifications) ? ctx.modele.verifications : []
  const m = ctx.modele
  const basculer = (k: string) => {
    const l = actives.includes(k) ? actives.filter((x) => x !== k) : [...actives, k]
    ctx.actions.fixer(['verifications'], l.length ? l : '')
  }
  return (
    <div className="saisie">
      <p className="aide">Vérifications menées à chaque calcul, sur le jeu d'eau le plus défavorable. Les coefficients partiels sont lus dans docs/normes ; tant qu'une valeur y manque, la vérification est « non vérifiable » et affiche la valeur caractéristique (vue Hypothèses et référentiel).</p>
      <div className="bloc"><div className="bloc-titre">Vérifications à mener</div>
        <table className="tableau">
          <tbody>
            {VERIFS.map(([k, lib, detail]) => (
              <tr key={k} className="cliquable" onClick={() => basculer(k)}>
                <td style={{ width: 30 }}><input type="checkbox" checked={actives.includes(k)} readOnly /></td>
                <td>{lib}</td><td className="doux">{detail}</td><td className="doux mono">{k}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="bloc"><div className="bloc-titre">Critères de déplacement aux ELS</div>
        <div className="grille-form">
          <label>Déplacement maximal admissible (mm)<Champ ctx={ctx} chemin={['criteres', 'deplacement_max_mm']} valeur={m.criteres?.deplacement_max_mm} large bloc="Criteres" cle="deplacement_max_mm" libelle="Déplacement maximal admissible" /></label>
          <label>Déplacement en tête admissible (mm)<Champ ctx={ctx} chemin={['criteres', 'deplacement_tete_mm']} valeur={m.criteres?.deplacement_tete_mm} large bloc="Criteres" cle="deplacement_tete_mm" libelle="Déplacement en tête admissible" /></label>
        </div>
        <p className="note" style={{ padding: '0 12px 10px' }}>Valeurs de projet (non normatives) : sans critère, la vérification « déplacements » est non vérifiable.</p>
      </div>
      <ErreursBloc ctx={ctx} prefixe="verifications" />
      <ErreursBloc ctx={ctx} prefixe="criteres" />
    </div>
  )
}
