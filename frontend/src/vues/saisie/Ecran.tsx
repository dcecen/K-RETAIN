import { uniteCote } from '../../lib/format'
import { Avance, Case, Champ, Choix, ErreursBloc, Reference } from './champs'
import { enumDe, erreurParmi, renseignes, type Ctx } from './outils'
import { CLES_AVANCEES_ECRAN } from './cles'

const LIBELLES_TYPE: Record<string, string> = {
  palplanche: 'Palplanches', paroi_moulee: 'Paroi moulée', pieux_secants: 'Pieux sécants', pieux_disjoints: 'Pieux disjoints', berlinoise: 'Berlinoise',
}

export function Ecran({ ctx }: { ctx: Ctx }) {
  const p = ctx.modele.paroi ?? {}
  const t = p.type
  const ch = (k: string) => ['paroi', k]
  const unite = uniteCote(ctx.modele)
  const champ = (k: string, lib: string, type: 'number' | 'text' = 'number', placeholder?: string) => (
    <label key={k}>{lib}<Champ ctx={ctx} chemin={ch(k)} valeur={p[k]} type={type} bloc="Paroi" cle={k} large libelle={lib} placeholder={placeholder} /></label>
  )
  const ref = (k: string, lib: string, familles: string[]) => (
    <label key={k}>{lib}<Reference ctx={ctx} chemin={ch(k)} valeur={p[k]} familles={familles} bloc="Paroi" cle={k} libelle={lib} /></label>
  )
  const beton = t === 'paroi_moulee' || t?.startsWith('pieux')
  const pieux = !!t?.startsWith('pieux')
  const avancees = CLES_AVANCEES_ECRAN.filter((k) => (t === 'palplanche' ? ['EI', 'classe_section', 'beta_D', 'perte_epaisseur'] : t === 'berlinoise' ? ['EI'] : t === 'paroi_moulee' ? ['EI', 'rapport_EI_fissure', 'enrobage', 'armatures_fouille', 'armatures_terre', 'armatures_horizontales', 'enrobage_horizontal', 'longueur_panneau', 'origine_panneaux'] : ['EI', 'rapport_EI_fissure', 'enrobage', 'armatures_pieu']).includes(k))
  return (
    <div className="saisie">
      <p className="aide">Type d'écran (clé <span className="mono">paroi</span> du script), cotes de tête et de pied ({unite}), matériaux et section. La rigidité EI par mètre est calculée depuis la base matériaux ; une valeur imposée se donne sous « Options avancées ». Les fiches discontinues (pieux disjoints, berlinoise) exigent une largeur de réaction sous le fond.</p>
      <div className="bloc"><div className="bloc-titre">Type et géométrie</div>
        <div className="grille-form">
          <label>Type d'écran<Choix ctx={ctx} chemin={ch('type')} valeur={t} options={enumDe(ctx.schema, 'Paroi', 'type')} libelles={LIBELLES_TYPE} bloc="Paroi" cle="type" libelle="Type d'écran" /></label>
          {champ('tete', `Cote de tête (${unite})`)}{champ('pied', `Cote du pied (${unite})`)}
          {(pieux || t === 'berlinoise') && champ('entraxe', 'Entraxe (m)')}
          {(t === 'pieux_disjoints' || t === 'berlinoise') && champ('largeur_reaction_fiche', 'Largeur de réaction sous le fond (m par élément)')}
        </div>
      </div>
      <div className="bloc"><div className="bloc-titre">Matériaux et section</div>
        <div className="grille-form">
          {(t === 'palplanche' || t === 'berlinoise') && ref('profil', t === 'palplanche' ? 'Profil de palplanche' : 'Profilé', t === 'palplanche' ? ['palplanches'] : ['profiles'])}
          {(t === 'palplanche' || t === 'berlinoise' || p.profil_armature) && ref('acier', "Nuance d'acier", ['aciers'])}
          {beton && ref('beton', 'Classe de béton', ['betons'])}
          {t === 'paroi_moulee' && champ('epaisseur', 'Épaisseur (m)')}
          {pieux && champ('diametre', 'Diamètre des pieux (m)')}
          {pieux && ref('profil_armature', "Profilé d'armature", ['profiles'])}
          {t === 'pieux_secants' && <label>Pieux primaires armés<div><Case ctx={ctx} chemin={ch('primaires_armes')} valeur={p.primaires_armes} bloc="Paroi" cle="primaires_armes" libelle="Pieux primaires armés" /></div></label>}
          {!t && <span className="note">Choisissez d'abord le type d'écran.</span>}
        </div>
      </div>
      {t === 'berlinoise' && (
        <div className="bloc"><div className="bloc-titre">Blindage entre profilés</div>
          <div className="grille-form">
            <label>Épaisseur (m)<Champ ctx={ctx} chemin={['paroi', 'blindage', 'epaisseur']} valeur={p.blindage?.epaisseur} large bloc="Blindage" cle="epaisseur" libelle="Épaisseur du blindage" /></label>
            <label>Matériau<Choix ctx={ctx} chemin={['paroi', 'blindage', 'materiau']} valeur={p.blindage?.materiau} options={enumDe(ctx.schema, 'Blindage', 'materiau')} vide="—" bloc="Blindage" cle="materiau" libelle="Matériau du blindage" /></label>
            <label>Résistance de calcul en flexion (MPa)<Champ ctx={ctx} chemin={['paroi', 'blindage', 'resistance']} valeur={p.blindage?.resistance} large bloc="Blindage" cle="resistance" libelle="Résistance du blindage" /></label>
          </div>
        </div>
      )}
      {t && (
        <Avance nb={renseignes(p, avancees)} forcer={erreurParmi(ctx, ['paroi'], avancees)}>
          <div className="grille-form">
            {champ('EI', 'EI imposé (kN·m²/m), à la place de la base matériaux')}
            {t === 'palplanche' && champ('classe_section', 'Classe de section (1 à 4)')}
            {t === 'palplanche' && champ('beta_D', 'β_D (profils en U)')}
            {t === 'palplanche' && champ('perte_epaisseur', "Perte d'épaisseur, corrosion (mm)")}
            {beton && champ('rapport_EI_fissure', 'Rapport EI fissuré / non fissuré')}
            {beton && champ('enrobage', "Distance du parement à l'axe des armatures (m)")}
            {t === 'paroi_moulee' && champ('armatures_fouille', 'Armatures côté fouille (cm²/m)')}
            {t === 'paroi_moulee' && champ('armatures_terre', 'Armatures côté terre (cm²/m)')}
            {pieux && champ('armatures_pieu', 'Armatures par pieu (cm²)')}
          </div>
          {t === 'paroi_moulee' && (
            <>
              <div className="bloc-titre" style={{ borderTop: '1px solid var(--filet)' }}>Pseudo-3D (plaque) : flexion horizontale et panneaux</div>
              <div className="grille-form">
                {champ('armatures_horizontales', 'Armatures horizontales par face (cm²/m)')}
                {champ('enrobage_horizontal', "Distance du parement à l'axe des armatures horizontales (m)", 'number', '= enrobage')}
                {champ('longueur_panneau', 'Longueur des panneaux (m)')}
                {champ('origine_panneaux', 'Abscisse du premier joint (m)', 'number', '0')}
              </div>
            </>
          )}
        </Avance>
      )}
      <ErreursBloc ctx={ctx} prefixe="paroi" />
    </div>
  )
}
