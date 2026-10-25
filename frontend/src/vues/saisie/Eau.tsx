import { useState } from 'react'
import { confirmer } from '../../lib/dialogue'
import { uniteCote } from '../../lib/format'
import { IconeCorbeille, IconePlus } from '../../lib/icones'
import type { Modele } from '../../lib/scriptDoc'
import { Avance, Champ, Choix, ErreursBloc, Th } from './champs'
import { enumDe, erreurParmi, renseignes, type Ctx } from './outils'
import { CLES_HYDRAULIQUE, CLES_BOUCHON } from './cles'

const LIBELLES_REGIME: Record<string, string> = { hydrostatique: 'Hydrostatique (nappes indépendantes)', simplifie: 'Simplifié (perte de charge le long du cheminement)', differences_finies: 'Écoulement 2D (différences finies)' }

export function Eau({ ctx }: { ctx: Ctx }) {
  const eau: Record<string, Modele> = ctx.modele.eau ?? {}
  const hy: Modele = ctx.modele.hydraulique ?? {}
  const unite = uniteCote(ctx.modele)
  const [nouveau, setNouveau] = useState('')
  const nbAvance = renseignes(hy, CLES_HYDRAULIQUE) + renseignes(hy.bouchon, CLES_BOUCHON)
  return (
    <div className="saisie">
      <p className="aide">Un jeu de niveaux = une nappe amont (côté terre) et une nappe aval (côté fouille), en {unite} ; vide = aucune nappe. Chaque jeu (service, exceptionnel…) est calculé et les vérifications retiennent le cas le plus défavorable ; un jeu dont le nom contient « except » ou « accid » est vérifié en combinaison accidentelle. Les niveaux changent au fil des phases dans la vue Phases. Par défaut le régime est hydrostatique ; l'écoulement autour de l'écran et un bouchon de fond se déclarent sous « Options avancées ».</p>
      <div className="bloc"><div className="bloc-titre">Jeux de niveaux de nappe</div>
        <table className="tableau">
          <thead><tr><Th t="Jeu" /><Th t="Nappe amont (côté terre)" u={unite} /><Th t="Nappe aval (côté fouille)" u={unite} /><th /></tr></thead>
          <tbody>
            {Object.entries(eau).map(([nom, n]) => (
              <tr key={nom}>
                <td style={{ fontWeight: 500 }}>{nom}</td>
                <td><Champ ctx={ctx} chemin={['eau', nom, 'amont']} valeur={n?.amont} placeholder="aucune" libelle={`Nappe amont (${nom})`} /></td>
                <td><Champ ctx={ctx} chemin={['eau', nom, 'aval']} valeur={n?.aval} placeholder="aucune" libelle={`Nappe aval (${nom})`} /></td>
                <td><button className="btn icone discret" title="Supprimer" onClick={() => void confirmer(`Supprimer le jeu d'eau « ${nom} » du script ?`, { ok: 'Supprimer' }).then((ok) => { if (ok) ctx.actions.supprimer(['eau', nom]) })}><IconeCorbeille taille={14} /></button></td>
              </tr>
            ))}
            <tr>
              <td><input className="champ" placeholder="nom du jeu (ex. exceptionnel)" value={nouveau} onChange={(e) => setNouveau(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && nouveau.trim() && !(nouveau.trim() in eau)) { ctx.actions.ajouterCle(['eau'], nouveau.trim(), { amont: null, aval: null }); setNouveau('') } }} /></td>
              <td colSpan={3}><button className="btn" disabled={!nouveau.trim() || nouveau.trim() in eau}
                onClick={() => { ctx.actions.ajouterCle(['eau'], nouveau.trim(), { amont: null, aval: null }); setNouveau('') }}><IconePlus /> Ajouter le jeu</button></td>
            </tr>
          </tbody>
        </table>
      </div>
      <Avance titre="Options avancées : écoulement autour de l'écran et bouchon de fond" nb={nbAvance} forcer={erreurParmi(ctx, ['hydraulique'], CLES_HYDRAULIQUE) || erreurParmi(ctx, ['hydraulique', 'bouchon'], CLES_BOUCHON)}>
        <div className="grille-form">
          <label>Régime de l'eau<Choix ctx={ctx} chemin={['hydraulique', 'regime']} valeur={hy.regime ?? 'hydrostatique'} options={enumDe(ctx.schema, 'Hydraulique', 'regime')} libelles={LIBELLES_REGIME} bloc="Hydraulique" cle="regime" libelle="Régime de l'eau" /></label>
          <label>Toit du substratum imperméable ({unite})<Champ ctx={ctx} chemin={['hydraulique', 'substratum']} valeur={hy.substratum} placeholder="pied − 2H" bloc="Hydraulique" cle="substratum" large libelle="Substratum" /></label>
          <label>Étendue du domaine amont (m)<Champ ctx={ctx} chemin={['hydraulique', 'largeur_amont']} valeur={hy.largeur_amont} placeholder="4 × H" bloc="Hydraulique" cle="largeur_amont" large libelle="Domaine amont" /></label>
          <label>Largeur de la fouille (m)<Champ ctx={ctx} chemin={['hydraulique', 'largeur_fouille']} valeur={hy.largeur_fouille} placeholder="vis-à-vis de la géométrie, sinon 2 × H" bloc="Hydraulique" cle="largeur_fouille" large libelle="Largeur de la fouille" /></label>
          <label>Maillage d'écoulement (m)<Champ ctx={ctx} chemin={['hydraulique', 'pas']} valeur={hy.pas} placeholder="0.5" bloc="Hydraulique" cle="pas" large libelle="Maillage d'écoulement" /></label>
          <label>Sol pour Lane (clé de la table)<Champ ctx={ctx} chemin={['hydraulique', 'sol_lane']} valeur={hy.sol_lane} type="text" placeholder="sable_moyen" bloc="Hydraulique" cle="sol_lane" large libelle="Sol pour Lane" /></label>
        </div>
        <p className="note" style={{ padding: '0 12px 6px' }}>L'écoulement corrige les pressions d'eau sur l'écran et les contraintes effectives ; le régime 2D exige k_h (et k_v) par couche (colonnes avancées de la vue Sols).</p>
        <div className="bloc-titre" style={{ borderTop: '1px solid var(--filet)' }}>Bouchon de fond de fouille</div>
        <div className="grille-form">
          <label>Type<Choix ctx={ctx} chemin={['hydraulique', 'bouchon', 'type']} valeur={hy.bouchon?.type} options={enumDe(ctx.schema, 'BouchonScript', 'type')} vide="aucun" bloc="BouchonScript" cle="type" libelle="Type de bouchon" /></label>
          <label>Toit ({unite})<Champ ctx={ctx} chemin={['hydraulique', 'bouchon', 'toit']} valeur={hy.bouchon?.toit} large bloc="BouchonScript" cle="toit" libelle="Toit du bouchon" /></label>
          <label>Base ({unite})<Champ ctx={ctx} chemin={['hydraulique', 'bouchon', 'base']} valeur={hy.bouchon?.base} large bloc="BouchonScript" cle="base" libelle="Base du bouchon" /></label>
          <label>Perméabilité (m/s, vide = imperméable)<Champ ctx={ctx} chemin={['hydraulique', 'bouchon', 'k']} valeur={hy.bouchon?.k} large bloc="BouchonScript" cle="k" libelle="Perméabilité du bouchon" /></label>
          <label>Poids volumique (kN/m³)<Champ ctx={ctx} chemin={['hydraulique', 'bouchon', 'gamma']} valeur={hy.bouchon?.gamma} placeholder="20" large bloc="BouchonScript" cle="gamma" libelle="Poids volumique du bouchon" /></label>
          <label>Actif à partir de la phase (n° ou nom)<Champ ctx={ctx} chemin={['hydraulique', 'bouchon', 'phase']} valeur={hy.bouchon?.phase} type="text" placeholder="dès le début" large bloc="BouchonScript" cle="phase" libelle="Phase du bouchon" /></label>
          <label>Lest sus-jacent (kPa)<Champ ctx={ctx} chemin={['hydraulique', 'bouchon', 'lest']} valeur={hy.bouchon?.lest} placeholder="0" large bloc="BouchonScript" cle="lest" libelle="Lest" /></label>
        </div>
      </Avance>
      <ErreursBloc ctx={ctx} prefixe="eau" />
      <ErreursBloc ctx={ctx} prefixe="hydraulique" />
    </div>
  )
}
