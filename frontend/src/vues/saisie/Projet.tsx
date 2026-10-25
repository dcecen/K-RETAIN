import { Avance, Champ, Choix, ErreursBloc } from './champs'
import { enumDe, renseignes, type Ctx } from './outils'
import { CARTOUCHE, CLES_CALCUL } from './cles'

const LIBELLES_COEF: Record<string, string> = { coulomb: 'Coulomb (Rankine si δ = 0)', kerisel_absi: 'Kérisel-Absi (tables)' }
const LIBELLES_KH: Record<string, string> = { schmitt: 'Schmitt (EM, α, EI)', impose: 'kh imposé par couche' }
const LIBELLES_MODE: Record<string, string> = { '2d': '2D (poutre sur ressorts)', pseudo3d: 'Pseudo-3D (plaque sur ressorts)' }

export function Projet({ ctx }: { ctx: Ctx }) {
  const m = ctx.modele
  const c = m.calcul ?? {}
  // `projet:` peut être un texte ou un bloc (nom, affaire, client…) : un champ de cartouche convertit le texte en bloc
  const projetBloc = m.projet && typeof m.projet === 'object' && !Array.isArray(m.projet) ? (m.projet as Record<string, unknown>) : null
  const nom = projetBloc ? projetBloc.nom : m.projet
  const fixerCartouche = (k: string, v: string) => {
    if (projetBloc) ctx.actions.fixer(['projet', k], v)
    else ctx.actions.fixer(['projet'], { nom: typeof nom === 'string' || typeof nom === 'number' ? nom : '', [k]: v })
  }
  return (
    <div className="saisie">
      <p className="aide">Nom affiché dans la barre de titre et cartouche de la note de calcul. Les options de calcul (méthodes, maillage) sont regroupées sous « Options avancées » : les valeurs par défaut conviennent à la plupart des projets.</p>
      <div className="bloc"><div className="bloc-titre">Projet</div>
        <div className="grille-form">
          <label>Nom du projet<Champ ctx={ctx} chemin={projetBloc ? ['projet', 'nom'] : ['projet']} valeur={nom} type="text" large libelle="Nom du projet" bloc="Script" cle="projet" /></label>
          {CARTOUCHE.map(([k, lib]) => (
            projetBloc ? (
              <label key={k}>{lib}<Champ ctx={ctx} chemin={['projet', k]} valeur={projetBloc[k]} type="text" large libelle={lib} /></label>
            ) : (
              <label key={k} className="doux">{lib}
                <input className="champ champ-bloc" placeholder="—" onBlur={(e) => { if (e.target.value.trim()) fixerCartouche(k, e.target.value.trim()) }}
                  onKeyDown={(e) => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur() }} />
              </label>
            )
          ))}
        </div>
      </div>
      <Avance titre="Options avancées : méthodes et réglages du calcul" nb={renseignes(c, CLES_CALCUL)}>
        <div className="grille-form">
          <label>Coefficients de poussée et de butée<Choix ctx={ctx} chemin={['calcul', 'coefficients']} valeur={c.coefficients ?? 'coulomb'} options={enumDe(ctx.schema, 'Calcul', 'coefficients')} libelles={LIBELLES_COEF} bloc="Calcul" cle="coefficients" libelle="Coefficients de poussée et de butée" /></label>
          <label>Coefficient de réaction kh<Choix ctx={ctx} chemin={['calcul', 'kh']} valeur={c.kh ?? 'schmitt'} options={enumDe(ctx.schema, 'Calcul', 'kh')} libelles={LIBELLES_KH} bloc="Calcul" cle="kh" libelle="Coefficient de réaction" /></label>
          <label>Mode de calcul<Choix ctx={ctx} chemin={['calcul', 'mode']} valeur={c.mode ?? '2d'} options={enumDe(ctx.schema, 'Calcul', 'mode')} libelles={LIBELLES_MODE} bloc="Calcul" cle="mode" libelle="Mode de calcul" /></label>
          <label>Pas du maillage (m)<Champ ctx={ctx} chemin={['calcul', 'pas']} valeur={c.pas} placeholder="0.1" bloc="Calcul" cle="pas" large libelle="Pas du maillage" /></label>
          <label>Poids volumique de l'eau γw (kN/m³)<Champ ctx={ctx} chemin={['calcul', 'gamma_w']} valeur={c.gamma_w} placeholder="10" bloc="Calcul" cle="gamma_w" large libelle="Poids volumique de l'eau" /></label>
          <label>Largeur de fouille pour la stabilité générale (m)<Champ ctx={ctx} chemin={['calcul', 'largeur_fouille']} valeur={c.largeur_fouille} placeholder="2 × hauteur" bloc="Calcul" cle="largeur_fouille" large libelle="Largeur de fouille" /></label>
          <label>Jeu d'eau de référence<Choix ctx={ctx} chemin={['calcul', 'jeu_eau']} valeur={c.jeu_eau} options={Object.keys(m.eau ?? {})} vide="(premier jeu)" bloc="Calcul" cle="jeu_eau" libelle="Jeu d'eau de référence" /></label>
        </div>
      </Avance>
      <ErreursBloc ctx={ctx} prefixe="projet" />
      <ErreursBloc ctx={ctx} prefixe="calcul" />
    </div>
  )
}
