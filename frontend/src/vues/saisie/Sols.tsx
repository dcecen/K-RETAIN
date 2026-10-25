import { useState } from 'react'
import type { Resultats } from '../../lib/api'
import type { Selection } from '../../lib/etat'
import { nb, uniteCote } from '../../lib/format'
import { IconeCorbeille, IconeDescendre, IconeMonter, IconePlus } from '../../lib/icones'
import type { Modele } from '../../lib/scriptDoc'
import { COULEURS_SOL } from '../../lib/theme'
import { confirmer } from '../../lib/dialogue'
import { Champ, ErreursBloc, Th } from './champs'
import { doc, type Ctx } from './outils'
import { COLS_BASE, COLS_AVANCEES } from './cles'

export function Sols({ ctx, selection, res }: { ctx: Ctx; selection: Selection; res: Resultats | null }) {
  const sol: Modele[] = Array.isArray(ctx.modele.sol) ? ctx.modele.sol : []
  const terrain = ctx.modele.terrain ?? {}
  const unite = uniteCote(ctx.modele)
  const methodeK = ctx.modele.calcul?.coefficients === 'kerisel_absi' ? 'Kérisel-Absi' : 'Coulomb (Rankine si δ = 0)'
  const methodeKh = ctx.modele.calcul?.kh === 'impose' ? 'kh imposé' : 'Schmitt (EM, α, EI)'
  const avanceesUtilisees = sol.some((c) => COLS_AVANCEES.some(([k]) => c?.[k] !== undefined && c?.[k] !== null))
  const [avancees, setAvancees] = useState(false)
  const voirAvancees = avancees || avanceesUtilisees
  const cols = voirAvancees ? [...COLS_BASE, ...COLS_AVANCEES] : COLS_BASE
  /** Coefficients du dernier calcul, par nom de couche (— si le script a changé depuis). */
  const calc = (c: Modele) => res?.couches.find((x) => x.nom === c?.nom)
  const val = (v: number | null | undefined, d: number) => (v === null || v === undefined ? '—' : nb(v, d))
  const nouvelle = () => {
    const dernier = sol[sol.length - 1]
    ctx.actions.ajouter(['sol'], { nom: `Couche ${sol.length + 1}`, toit: typeof dernier?.toit === 'number' ? dernier.toit - 3 : 0, gamma: 20, gamma_dejauge: 10, phi: 30, c: 0, EM: 10000, alpha: 0.5 })
  }
  return (
    <div className="saisie">
      <p className="aide">Couches du haut vers le bas, chacune définie par la cote de son toit ({unite}) ; la dernière se prolonge sous le pied de l'écran. Poussée et butée : {methodeK} (avec Coulomb, δp/φ' est limité à 1/3). Coefficient de réaction : {methodeKh}. Les colonnes Ka, Kp, K0 et kh sont les valeurs utilisées par le dernier calcul.</p>
      <div className="bloc"><div className="bloc-titre">Terrain initial</div>
        <div className="grille-form">
          <label>Cote du terrain amont, côté terre ({unite})<Champ ctx={ctx} chemin={['terrain', 'amont']} valeur={terrain.amont} placeholder="toit de la 1re couche" bloc="Terrain" cle="amont" large libelle="Terrain amont" /></label>
          <label>Cote du terrain aval, côté fouille ({unite})<Champ ctx={ctx} chemin={['terrain', 'aval']} valeur={terrain.aval} placeholder="= amont" bloc="Terrain" cle="aval" large libelle="Terrain aval" /></label>
        </div>
      </div>
      <div className="bloc">
        <div className="bloc-titre">Couches de sol
          <span className="espace" />
          <label className="doux" style={{ fontWeight: 400, display: 'inline-flex', gap: 5, alignItems: 'center' }} title="δ, pl, qc, kh imposé, K0, perméabilités, cu">
            <input type="checkbox" checked={voirAvancees} disabled={avanceesUtilisees} onChange={(e) => setAvancees(e.target.checked)} /> colonnes avancées{avanceesUtilisees ? ' (renseignées)' : ''}
          </label>
        </div>
        <table className="tableau">
          <thead>
            <tr><th style={{ width: 28 }} />{cols.map(([k, t, u]) => <Th key={k} t={t} u={u === 'COTE' ? unite : u} titre={doc(ctx.schema, 'Couche', k)} />)}
              <Th t="Ka" u="-" titre={`Coefficient de poussée horizontale utilisé par le calcul (${methodeK})`} /><Th t="Kp" u="-" titre={`Coefficient de butée horizontale utilisé par le calcul (${methodeK})`} />
              <Th t="K0" u="-" titre="Coefficient de pression des terres au repos (saisi, sinon Jaky)" /><Th t="kh" u="kN/m³" titre={`Coefficient de réaction utilisé par le calcul (${methodeKh})`} /><th /></tr>
          </thead>
          <tbody>
            {sol.map((c, i) => (
              <tr key={i} className={selection?.type === 'couche' && selection.index === i ? 'actif' : ''}>
                <td><span className="puce-sol" style={{ background: COULEURS_SOL[i % COULEURS_SOL.length], display: 'inline-block' }} /></td>
                {cols.map(([k, t]) => (
                  <td key={k} style={{ minWidth: k === 'nom' ? 120 : 58 }}>
                    <Champ ctx={ctx} chemin={['sol', i, k]} valeur={c?.[k]} type={k === 'nom' ? 'text' : 'number'} bloc="Couche" cle={k} libelle={`${t} (${c?.nom ?? `couche ${i + 1}`})`} />
                  </td>
                ))}
                <td className="num doux">{val(calc(c)?.kah, 3)}</td><td className="num doux">{val(calc(c)?.kph, 2)}</td>
                <td className="num doux">{val(calc(c)?.k0, 3)}</td><td className="num doux">{val(calc(c)?.kh, 0)}</td>
                <td style={{ whiteSpace: 'nowrap' }}>
                  <button className="btn icone discret" title="Monter" disabled={i === 0} onClick={() => ctx.actions.deplacer(['sol'], i, i - 1)}><IconeMonter taille={14} /></button>
                  <button className="btn icone discret" title="Descendre" disabled={i === sol.length - 1} onClick={() => ctx.actions.deplacer(['sol'], i, i + 1)}><IconeDescendre taille={14} /></button>
                  <button className="btn icone discret" title="Supprimer la couche" onClick={() => void confirmer(`Supprimer la couche « ${c?.nom ?? i + 1} » du script ?`, { ok: 'Supprimer' }).then((ok) => { if (ok) ctx.actions.supprimer(['sol', i]) })}><IconeCorbeille taille={14} /></button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <button className="btn" onClick={nouvelle}><IconePlus /> Ajouter une couche</button>
      <p className="note" style={{ marginTop: 10 }}>Clés du script sans colonne : EM_sur_qc (corrélation qc → EM), coef_decharge, sol_lane (voir le guide, vue Aide).</p>
      <ErreursBloc ctx={ctx} prefixe="sol" />
      <ErreursBloc ctx={ctx} prefixe="terrain" />
    </div>
  )
}
