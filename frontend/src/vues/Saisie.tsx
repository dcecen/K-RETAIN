import { useEffect, useState, type ReactNode } from 'react'
import type { ErreurScript, Resultats } from '../lib/api'
import { ArbrePhases } from '../composants/ArbrePhases'
import type { Section, Selection } from '../lib/etat'
import { IconeCorbeille, IconeDescendre, IconeMonter, IconePlus } from '../lib/icones'
import { nb, uniteCote } from '../lib/format'
import { cheminErreur, type Chemin, type Modele } from '../lib/scriptDoc'
import { COULEURS_SOL } from '../lib/theme'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Schema = any

export interface Actions {
  fixer: (chemin: Chemin, valeur: unknown) => void
  ajouter: (chemin: Chemin, valeur: unknown) => void
  ajouterCle: (chemin: Chemin, cle: string, valeur: unknown) => void
  supprimer: (chemin: Chemin) => void
  deplacer: (chemin: Chemin, i: number, j: number) => void
  inserer: (chemin: Chemin, index: number, valeur: unknown) => void
  renommerAppui: (ancien: string, nouveau: string) => void
}

interface Ctx {
  modele: Modele
  erreurs: ErreurScript[]
  schema: Schema
  references: Record<string, string[]>
  actions: Actions
}

/** Description d'un champ depuis le schéma JSON (unité et bornes dans la description). */
function doc(schema: Schema, bloc: string, cle: string): string {
  const def = schema?.$defs?.[bloc]?.properties?.[cle]
  return def?.description ?? ''
}

function erreurDe(ctx: Ctx, chemin: Chemin): string | null {
  const c = cheminErreur(chemin)
  return ctx.erreurs.find((e) => e.chemin === c)?.message ?? null
}

/** Champ texte ou numérique, validé à la perte de focus ou à Entrée. */
function Champ({ ctx, chemin, valeur, type = 'number', bloc, cle, placeholder, large }: {
  ctx: Ctx; chemin: Chemin; valeur: unknown; type?: 'number' | 'text'; bloc?: string; cle?: string; placeholder?: string; large?: boolean
}) {
  const [brut, setBrut] = useState(valeur === undefined || valeur === null ? '' : String(valeur))
  useEffect(() => { setBrut(valeur === undefined || valeur === null ? '' : String(valeur)) }, [valeur])
  const err = erreurDe(ctx, chemin)
  const valider = () => {
    const t = brut.trim()
    const actuel = valeur === undefined || valeur === null ? '' : String(valeur)
    if (t === actuel) return
    if (t === '') return ctx.actions.fixer(chemin, '')
    if (type === 'number') {
      const n = Number(t.replace(',', '.'))
      if (!Number.isFinite(n)) return setBrut(actuel)
      ctx.actions.fixer(chemin, n)
    } else ctx.actions.fixer(chemin, t)
  }
  return (
    <input className={`champ ${type === 'number' ? 'num' : ''} ${err ? 'en-erreur' : ''} ${large ? 'champ-bloc' : ''}`}
      value={brut} placeholder={placeholder} inputMode={type === 'number' ? 'decimal' : undefined}
      title={err ?? (bloc && cle ? doc(ctx.schema, bloc, cle) : undefined)}
      onChange={(e) => setBrut(e.target.value)} onBlur={valider}
      onKeyDown={(e) => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur(); if (e.key === 'Escape') setBrut(valeur === undefined ? '' : String(valeur)) }} />
  )
}

function Choix({ ctx, chemin, valeur, options, vide }: { ctx: Ctx; chemin: Chemin; valeur: unknown; options: string[]; vide?: string }) {
  const err = erreurDe(ctx, chemin)
  return (
    <select className={`champ ${err ? 'en-erreur' : ''}`} value={valeur === undefined || valeur === null ? '' : String(valeur)} title={err ?? undefined}
      onChange={(e) => ctx.actions.fixer(chemin, e.target.value)}>
      {vide !== undefined && <option value="">{vide}</option>}
      {options.map((o) => <option key={o} value={o}>{o}</option>)}
    </select>
  )
}

function Case({ ctx, chemin, valeur }: { ctx: Ctx; chemin: Chemin; valeur: unknown }) {
  return <input type="checkbox" checked={!!valeur} onChange={(e) => ctx.actions.fixer(chemin, e.target.checked)} />
}

function enumDe(schema: Schema, bloc: string, cle: string): string[] {
  const def = schema?.$defs?.[bloc]?.properties?.[cle]
  const cand = def?.enum ?? def?.anyOf?.find((x: Schema) => x.enum)?.enum ?? []
  return cand.map(String)
}

const Th = ({ t, u, titre }: { t: ReactNode; u?: string; titre?: string }) => <th title={titre}>{t}{u && <span className="unite">{u}</span>}</th>

// ---------------------------------------------------------------- sections
/** Clés du bloc `projet:` reprises dans le cartouche de la note de calcul. */
const CARTOUCHE: Record<string, string> = {
  affaire: 'Affaire', client: 'Client', lieu: 'Lieu', indice: 'Indice', redacteur: 'Rédacteur', verificateur: 'Vérificateur',
  date: 'Date (vide = date du jour)', systeme_cotes: 'Système de cotes (vide = NGF)',
}

function Projet({ ctx }: { ctx: Ctx }) {
  const m = ctx.modele
  const c = m.calcul ?? {}
  // `projet:` peut être un texte ou un bloc (nom, affaire, client…) : on n'écrase jamais le bloc par un texte
  const projetBloc = m.projet && typeof m.projet === 'object' && !Array.isArray(m.projet) ? (m.projet as Record<string, unknown>) : null
  const infos = projetBloc ? Object.entries(projetBloc).filter(([k, v]) => k !== 'nom' && (typeof v === 'string' || typeof v === 'number')) : []
  return (
    <div className="saisie">
      <h2>Projet et options de calcul</h2>
      <p className="aide">Le script YAML est la référence du modèle : chaque champ modifié met à jour la ligne correspondante du script, et inversement.</p>
      <div className="bloc"><div className="bloc-titre">Projet</div>
        <div className="grille-form">
          <label>Nom du projet<Champ ctx={ctx} chemin={projetBloc ? ['projet', 'nom'] : ['projet']} valeur={projetBloc ? projetBloc.nom : m.projet} type="text" large /></label>
          {infos.map(([k, v]) => <label key={k}>{CARTOUCHE[k] ?? k}<Champ ctx={ctx} chemin={['projet', k]} valeur={v} type={typeof v === 'number' ? 'number' : 'text'} large /></label>)}
          {projetBloc && Object.keys(CARTOUCHE).filter((k) => !(k in projetBloc)).map((k) => (
            <label key={k} className="doux">{CARTOUCHE[k]}<input className="champ champ-bloc" placeholder="—" onBlur={(e) => { if (e.target.value.trim()) ctx.actions.ajouterCle(['projet'], k, e.target.value.trim()) }} /></label>
          ))}
          {!projetBloc && <span className="note" style={{ alignSelf: 'end' }}>Pour renseigner le cartouche de la note (affaire, indice, rédacteur, vérificateur, système de cotes), écrivez le bloc <span className="mono">projet:</span> du script avec une clé <span className="mono">nom</span>.</span>}
        </div>
      </div>
      <div className="bloc"><div className="bloc-titre">Calcul</div>
        <div className="grille-form">
          <label title={doc(ctx.schema, 'Calcul', 'coefficients')}>Coefficients de poussée / butée<Choix ctx={ctx} chemin={['calcul', 'coefficients']} valeur={c.coefficients ?? 'coulomb'} options={enumDe(ctx.schema, 'Calcul', 'coefficients')} /></label>
          <label title={doc(ctx.schema, 'Calcul', 'kh')}>Coefficient de réaction<Choix ctx={ctx} chemin={['calcul', 'kh']} valeur={c.kh ?? 'schmitt'} options={enumDe(ctx.schema, 'Calcul', 'kh')} /></label>
          <label title={doc(ctx.schema, 'Calcul', 'mode')}>Mode<Choix ctx={ctx} chemin={['calcul', 'mode']} valeur={c.mode ?? '2d'} options={enumDe(ctx.schema, 'Calcul', 'mode')} /></label>
          <label>Pas du maillage (m)<Champ ctx={ctx} chemin={['calcul', 'pas']} valeur={c.pas} placeholder="0.1" bloc="Calcul" cle="pas" large /></label>
          <label>γ de l'eau (kN/m³)<Champ ctx={ctx} chemin={['calcul', 'gamma_w']} valeur={c.gamma_w} placeholder="10" bloc="Calcul" cle="gamma_w" large /></label>
          <label>Largeur de fouille, stabilité générale (m)<Champ ctx={ctx} chemin={['calcul', 'largeur_fouille']} valeur={c.largeur_fouille} placeholder="2 × hauteur" bloc="Calcul" cle="largeur_fouille" large /></label>
          <label>Jeu d'eau de référence<Choix ctx={ctx} chemin={['calcul', 'jeu_eau']} valeur={c.jeu_eau} options={Object.keys(m.eau ?? {})} vide="(premier jeu)" /></label>
        </div>
      </div>
      <div className="bloc"><div className="bloc-titre">Critères de déplacement aux ELS</div>
        <div className="grille-form">
          <label>Déplacement maximal admissible (mm)<Champ ctx={ctx} chemin={['criteres', 'deplacement_max_mm']} valeur={m.criteres?.deplacement_max_mm} large /></label>
          <label>Déplacement en tête admissible (mm)<Champ ctx={ctx} chemin={['criteres', 'deplacement_tete_mm']} valeur={m.criteres?.deplacement_tete_mm} large /></label>
        </div>
      </div>
    </div>
  )
}

/** Colonnes saisies : clé du script, en-tête, unité (COTE = unité des cotes du projet). */
const COLS_SOL: [string, string, string][] = [
  ['nom', 'Nom', ''], ['toit', 'Cote du toit', 'COTE'], ['gamma', 'γ', 'kN/m³'], ['gamma_dejauge', "γ'", 'kN/m³'], ['c', "c'", 'kPa'], ['phi', "φ'", '°'],
  ['delta_a_sur_phi', "δa/φ'", '-'], ['delta_p_sur_phi', "δp/φ'", '-'], ['EM', 'EM', 'kPa'], ['alpha', 'α', '-'], ['pl', 'pl', 'kPa'], ['kh', 'kh imposé', 'kN/m³'],
  ['k_h', 'k_h', 'm/s'], ['k_v', 'k_v', 'm/s'], ['cu', 'cu', 'kPa'],
]

function Sol({ ctx, selection, res }: { ctx: Ctx; selection: Selection; res: Resultats | null }) {
  const sol: Modele[] = Array.isArray(ctx.modele.sol) ? ctx.modele.sol : []
  const unite = uniteCote(ctx.modele)
  const methodeK = ctx.modele.calcul?.coefficients === 'kerisel_absi' ? 'Kérisel-Absi' : 'Coulomb (Rankine si δ = 0)'
  const methodeKh = ctx.modele.calcul?.kh === 'impose' ? 'kh imposé' : 'Schmitt (EM, α, EI)'
  /** Coefficients du dernier calcul, par nom de couche (— si le script a changé depuis). */
  const calc = (c: Modele) => res?.couches.find((x) => x.nom === c?.nom)
  const val = (v: number | null | undefined, d: number) => (v === null || v === undefined ? '—' : nb(v, d))
  const nouvelle = () => {
    const dernier = sol[sol.length - 1]
    ctx.actions.ajouter(['sol'], { nom: `Couche ${sol.length + 1}`, toit: typeof dernier?.toit === 'number' ? dernier.toit - 3 : 0, gamma: 20, gamma_dejauge: 10, phi: 30, c: 0, EM: 10000, alpha: 0.5 })
  }
  return (
    <div className="saisie">
      <h2>Couches de sol</h2>
      <p className="aide">Couches du haut vers le bas, chacune définie par la cote de son toit ({unite}) ; la dernière se prolonge sous le pied de l'écran. Poussée et butée : {methodeK}. Coefficient de réaction : {methodeKh}. Avec Coulomb, δp/φ' est limité à 1/3. Les colonnes Ka, Kp, K0 et kh sont les valeurs utilisées par le dernier calcul.</p>
      <div className="bloc">
        <table className="tableau">
          <thead>
            <tr><th style={{ width: 28 }} />{COLS_SOL.map(([k, t, u]) => <Th key={k} t={t} u={u === 'COTE' ? unite : u} titre={doc(ctx.schema, 'Couche', k)} />)}
              <Th t="Ka" u="-" titre={`Coefficient de poussée horizontale utilisé par le calcul (${methodeK})`} /><Th t="Kp" u="-" titre={`Coefficient de butée horizontale utilisé par le calcul (${methodeK})`} />
              <Th t="K0" u="-" titre="Coefficient de pression des terres au repos (saisi, sinon Jaky)" /><Th t="kh" u="kN/m³" titre={`Coefficient de réaction utilisé par le calcul (${methodeKh})`} /><th /></tr>
          </thead>
          <tbody>
            {sol.map((c, i) => (
              <tr key={i} className={selection?.type === 'couche' && selection.index === i ? 'actif' : ''}>
                <td><span className="puce-sol" style={{ background: COULEURS_SOL[i % COULEURS_SOL.length], display: 'inline-block' }} /></td>
                {COLS_SOL.map(([k]) => (
                  <td key={k} style={{ minWidth: k === 'nom' ? 120 : 58 }}>
                    <Champ ctx={ctx} chemin={['sol', i, k]} valeur={c?.[k]} type={k === 'nom' ? 'text' : 'number'} bloc="Couche" cle={k} />
                  </td>
                ))}
                <td className="num doux">{val(calc(c)?.kah, 3)}</td><td className="num doux">{val(calc(c)?.kph, 2)}</td>
                <td className="num doux">{val(calc(c)?.k0, 3)}</td><td className="num doux">{val(calc(c)?.kh, 0)}</td>
                <td style={{ whiteSpace: 'nowrap' }}>
                  <button className="btn icone discret" title="Monter" disabled={i === 0} onClick={() => ctx.actions.deplacer(['sol'], i, i - 1)}><IconeMonter taille={14} /></button>
                  <button className="btn icone discret" title="Descendre" disabled={i === sol.length - 1} onClick={() => ctx.actions.deplacer(['sol'], i, i + 1)}><IconeDescendre taille={14} /></button>
                  <button className="btn icone discret" title="Supprimer la couche" onClick={() => { if (window.confirm('Supprimer cette couche de sol du script ?')) ctx.actions.supprimer(['sol', i]) }}><IconeCorbeille taille={14} /></button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <button className="btn" onClick={nouvelle}><IconePlus /> Ajouter une couche</button>
      {ctx.erreurs.filter((e) => e.chemin.startsWith('sol')).map((e, i) => <div key={i} className="message-erreur" style={{ marginTop: 8 }}>{e.chemin} : {e.message}</div>)}
    </div>
  )
}

function Paroi({ ctx }: { ctx: Ctx }) {
  const p = ctx.modele.paroi ?? {}
  const t = p.type
  const ch = (k: string) => ['paroi', k]
  const R = ctx.references
  const champ = (k: string, lib: string, type: 'number' | 'text' = 'number') => (
    <label key={k} title={doc(ctx.schema, 'Paroi', k)}>{lib}<Champ ctx={ctx} chemin={ch(k)} valeur={p[k]} type={type} bloc="Paroi" cle={k} large /></label>
  )
  const ref = (k: string, lib: string, famille: string[]) => (
    <label key={k} title={doc(ctx.schema, 'Paroi', k)}>{lib}
      <select className="champ champ-bloc" value={p[k] ?? ''} onChange={(e) => ctx.actions.fixer(ch(k), e.target.value)}>
        <option value="">—</option>
        {famille.flatMap((f) => R[f] ?? []).map((r) => <option key={r} value={r}>{r}</option>)}
      </select>
    </label>
  )
  return (
    <div className="saisie">
      <h2>Paroi</h2>
      <p className="aide">La rigidité EI par mètre est calculée depuis la base matériaux, ou imposée directement. Les fiches discontinues (pieux disjoints, berlinoise) exigent une largeur de réaction sous le fond.</p>
      <div className="bloc"><div className="bloc-titre">Type et géométrie</div>
        <div className="grille-form">
          <label>Type de paroi<Choix ctx={ctx} chemin={ch('type')} valeur={t} options={enumDe(ctx.schema, 'Paroi', 'type')} /></label>
          {champ('tete', `Cote de tête (${uniteCote(ctx.modele)})`)}{champ('pied', `Cote du pied (${uniteCote(ctx.modele)})`)}{champ('EI', 'EI imposé (kN·m²/m)')}
        </div>
      </div>
      <div className="bloc"><div className="bloc-titre">Matériaux et section</div>
        <div className="grille-form">
          {(t === 'palplanche' || t === 'berlinoise') && ref('profil', t === 'palplanche' ? 'Profil de palplanche' : 'Profilé', t === 'palplanche' ? ['palplanches'] : ['profiles'])}
          {(t === 'palplanche' || t === 'berlinoise' || p.profil_armature) && ref('acier', "Nuance d'acier", ['aciers'])}
          {t === 'palplanche' && champ('classe_section', 'Classe de section (1 à 4)')}
          {t === 'palplanche' && champ('beta_D', 'β_D (profils en U)')}
          {t === 'palplanche' && champ('perte_epaisseur', "Perte d'épaisseur, corrosion (mm)")}
          {(t === 'paroi_moulee' || t?.startsWith('pieux')) && ref('beton', 'Classe de béton', ['betons'])}
          {t === 'paroi_moulee' && champ('epaisseur', 'Épaisseur (m)')}
          {t?.startsWith('pieux') && champ('diametre', 'Diamètre des pieux (m)')}
          {(t?.startsWith('pieux') || t === 'berlinoise') && champ('entraxe', 'Entraxe (m)')}
          {t?.startsWith('pieux') && ref('profil_armature', "Profilé d'armature", ['profiles'])}
          {t === 'pieux_secants' && <label>Pieux primaires armés<div><Case ctx={ctx} chemin={ch('primaires_armes')} valeur={p.primaires_armes} /></div></label>}
          {(t === 'paroi_moulee' || t?.startsWith('pieux')) && champ('rapport_EI_fissure', 'Rapport EI fissuré / non fissuré')}
          {(t === 'paroi_moulee' || t?.startsWith('pieux')) && champ('enrobage', "Distance parement → axe des armatures (m)")}
          {t === 'paroi_moulee' && champ('armatures_fouille', 'Armatures côté fouille (cm²/m)')}
          {t === 'paroi_moulee' && champ('armatures_terre', 'Armatures côté terre (cm²/m)')}
          {t?.startsWith('pieux') && champ('armatures_pieu', 'Armatures par pieu (cm²)')}
          {(t === 'pieux_disjoints' || t === 'berlinoise') && champ('largeur_reaction_fiche', 'Largeur de réaction sous le fond (m)')}
        </div>
      </div>
      {t === 'berlinoise' && (
        <div className="bloc"><div className="bloc-titre">Blindage entre profilés</div>
          <div className="grille-form">
            <label>Épaisseur (m)<Champ ctx={ctx} chemin={['paroi', 'blindage', 'epaisseur']} valeur={p.blindage?.epaisseur} large /></label>
            <label>Matériau<Choix ctx={ctx} chemin={['paroi', 'blindage', 'materiau']} valeur={p.blindage?.materiau} options={enumDe(ctx.schema, 'Blindage', 'materiau')} vide="—" /></label>
            <label>Résistance de calcul en flexion (MPa)<Champ ctx={ctx} chemin={['paroi', 'blindage', 'resistance']} valeur={p.blindage?.resistance} large /></label>
          </div>
        </div>
      )}
      {ctx.erreurs.filter((e) => e.chemin.startsWith('paroi')).map((e, i) => <div key={i} className="message-erreur">{e.chemin} : {e.message}</div>)}
    </div>
  )
}

function Eau({ ctx }: { ctx: Ctx }) {
  const eau: Record<string, Modele> = ctx.modele.eau ?? {}
  const terrain = ctx.modele.terrain ?? {}
  const hy: Modele = ctx.modele.hydraulique ?? {}
  const [nouveau, setNouveau] = useState('')
  return (
    <div className="saisie">
      <h2>Eau et terrain initial</h2>
      <p className="aide">Chaque jeu de niveaux (service, exceptionnel…) est calculé ; les vérifications retiennent le cas le plus défavorable. Un jeu dont le nom contient « except » ou « accid » est vérifié en combinaison accidentelle. Seul le régime hydrostatique est modélisé.</p>
      <div className="bloc"><div className="bloc-titre">Jeux de niveaux d'eau</div>
        <table className="tableau">
          <thead><tr><Th t="Jeu" /><Th t="Nappe amont" u={uniteCote(ctx.modele)} /><Th t="Nappe aval" u={uniteCote(ctx.modele)} /><th /></tr></thead>
          <tbody>
            {Object.entries(eau).map(([nom, n]) => (
              <tr key={nom}>
                <td style={{ fontWeight: 500 }}>{nom}</td>
                <td><Champ ctx={ctx} chemin={['eau', nom, 'amont']} valeur={n?.amont} placeholder="aucune" /></td>
                <td><Champ ctx={ctx} chemin={['eau', nom, 'aval']} valeur={n?.aval} placeholder="aucune" /></td>
                <td><button className="btn icone discret" title="Supprimer" onClick={() => { if (window.confirm(`Supprimer le jeu d'eau « ${nom} » du script ?`)) ctx.actions.supprimer(['eau', nom]) }}><IconeCorbeille taille={14} /></button></td>
              </tr>
            ))}
            <tr>
              <td><input className="champ" placeholder="nom du jeu (ex. exceptionnel)" value={nouveau} onChange={(e) => setNouveau(e.target.value)} /></td>
              <td colSpan={3}><button className="btn" disabled={!nouveau.trim() || nouveau in eau}
                onClick={() => { ctx.actions.ajouterCle(['eau'], nouveau.trim(), { amont: null, aval: null }); setNouveau('') }}><IconePlus /> Ajouter le jeu</button></td>
            </tr>
          </tbody>
        </table>
      </div>
      <div className="bloc"><div className="bloc-titre">Écoulement autour de l'écran</div>
        <div className="grille-form">
          <label title={doc(ctx.schema, 'Hydraulique', 'regime')}>Régime de l'eau
            <Choix ctx={ctx} chemin={['hydraulique', 'regime']} valeur={hy.regime ?? 'hydrostatique'} options={enumDe(ctx.schema, 'Hydraulique', 'regime')} /></label>
          <label>Toit du substratum imperméable (m)<Champ ctx={ctx} chemin={['hydraulique', 'substratum']} valeur={hy.substratum} placeholder="pied − 2H" large /></label>
          <label>Étendue du domaine amont (m)<Champ ctx={ctx} chemin={['hydraulique', 'largeur_amont']} valeur={hy.largeur_amont} placeholder="4 × H" large /></label>
          <label>Largeur de la fouille (m)<Champ ctx={ctx} chemin={['hydraulique', 'largeur_fouille']} valeur={hy.largeur_fouille} placeholder="2 × H" large /></label>
          <label>Maillage d'écoulement (m)<Champ ctx={ctx} chemin={['hydraulique', 'pas']} valeur={hy.pas} placeholder="0.5" large /></label>
          <label>Sol pour Lane (clé de la table)<Champ ctx={ctx} chemin={['hydraulique', 'sol_lane']} valeur={hy.sol_lane} type="text" placeholder="sable_moyen" large /></label>
        </div>
        <p className="note" style={{ padding: '0 12px 10px' }}>Régimes : hydrostatique (nappes indépendantes), simplifié (perte de charge uniforme le long du cheminement), différences finies (écoulement 2D sur la coupe, k_h et k_v par couche). L'écoulement corrige les pressions d'eau sur l'écran et les contraintes effectives.</p>
      </div>
      <div className="bloc"><div className="bloc-titre">Bouchon de fond de fouille</div>
        <div className="grille-form">
          <label title={doc(ctx.schema, 'BouchonScript', 'type')}>Type<Choix ctx={ctx} chemin={['hydraulique', 'bouchon', 'type']} valeur={hy.bouchon?.type} options={enumDe(ctx.schema, 'BouchonScript', 'type')} vide="aucun" /></label>
          <label>Toit (m)<Champ ctx={ctx} chemin={['hydraulique', 'bouchon', 'toit']} valeur={hy.bouchon?.toit} large /></label>
          <label>Base (m)<Champ ctx={ctx} chemin={['hydraulique', 'bouchon', 'base']} valeur={hy.bouchon?.base} large /></label>
          <label>Perméabilité (m/s, vide = imperméable)<Champ ctx={ctx} chemin={['hydraulique', 'bouchon', 'k']} valeur={hy.bouchon?.k} large /></label>
          <label>Poids volumique (kN/m³)<Champ ctx={ctx} chemin={['hydraulique', 'bouchon', 'gamma']} valeur={hy.bouchon?.gamma} placeholder="20" large /></label>
          <label>Actif à partir de la phase (n° ou nom)<Champ ctx={ctx} chemin={['hydraulique', 'bouchon', 'phase']} valeur={hy.bouchon?.phase} type="text" placeholder="dès le début" large /></label>
          <label>Lest sus-jacent (kPa)<Champ ctx={ctx} chemin={['hydraulique', 'bouchon', 'lest']} valeur={hy.bouchon?.lest} placeholder="0" large /></label>
        </div>
      </div>
      <div className="bloc"><div className="bloc-titre">Terrain initial</div>
        <div className="grille-form">
          <label>Cote du terrain amont ({uniteCote(ctx.modele)})<Champ ctx={ctx} chemin={['terrain', 'amont']} valeur={terrain.amont} placeholder="toit de la 1re couche" large /></label>
          <label>Cote du terrain aval ({uniteCote(ctx.modele)})<Champ ctx={ctx} chemin={['terrain', 'aval']} valeur={terrain.aval} placeholder="= amont" large /></label>
        </div>
      </div>
    </div>
  )
}

function Surcharges({ ctx }: { ctx: Ctx }) {
  const liste: Modele[] = Array.isArray(ctx.modele.surcharges) ? ctx.modele.surcharges : []
  return (
    <div className="saisie">
      <h2>Surcharges</h2>
      <p className="aide">Uniforme, en bande (Boussinesq), linéique (Flamant), et en plan : rectangulaire, ponctuelle, linéaire (position, emprise, trace, profondeur, phase d'application : dans le script ou depuis la maquette 3D, outil « Ajouter une surcharge »). Les surcharges ajoutées ou retirées en cours de chantier se déclarent par <code>phase</code> / <code>phases</code> ou dans les phases.</p>
      <div className="bloc">
        <table className="tableau">
          <thead><tr><Th t="Nom" /><Th t="Type" /><Th t="q" u="kPa ou kN/m" /><Th t="Distance" u="m" /><Th t="Largeur" u="m" /><Th t="Côté" /><th /></tr></thead>
          <tbody>
            {liste.map((s, i) => (
              <tr key={i}>
                <td><Champ ctx={ctx} chemin={['surcharges', i, 'nom']} valeur={s?.nom} type="text" placeholder={`S${i + 1}`} /></td>
                <td><Choix ctx={ctx} chemin={['surcharges', i, 'type']} valeur={s?.type} options={enumDe(ctx.schema, 'Surcharge', 'type')} /></td>
                <td><Champ ctx={ctx} chemin={['surcharges', i, 'q']} valeur={s?.q} /></td>
                <td><Champ ctx={ctx} chemin={['surcharges', i, 'distance']} valeur={s?.distance} placeholder="0" /></td>
                <td><Champ ctx={ctx} chemin={['surcharges', i, 'largeur']} valeur={s?.largeur} /></td>
                <td><Choix ctx={ctx} chemin={['surcharges', i, 'cote_ecran']} valeur={s?.cote_ecran ?? 'amont'} options={['amont', 'aval']} /></td>
                <td><button className="btn icone discret" title="Supprimer" onClick={() => { if (window.confirm('Supprimer cette surcharge du script ?')) ctx.actions.supprimer(['surcharges', i]) }}><IconeCorbeille taille={14} /></button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <button className="btn" onClick={() => ctx.actions.ajouter(['surcharges'], { type: 'repartie', q: 10 })}><IconePlus /> Ajouter une surcharge</button>
    </div>
  )
}

const CHAMPS_APPUI: Record<string, [string, string][]> = {
  buton: [['longueur', 'Longueur (m)'], ['espacement', 'Espacement (m)'], ['angle', 'Angle (°)'], ['precharge', 'Précharge (kN)']],
  bracon: [['longueur', 'Longueur (m)'], ['espacement', 'Espacement (m)'], ['angle', 'Angle (°)'], ['pied_bracon', 'Cote de l’appui en pied (m)'], ['precharge', 'Précharge (kN)']],
  tirant: [['longueur_libre', 'Longueur libre (m)'], ['longueur_scellee', 'Longueur scellée (m)'], ['angle', 'Inclinaison (°)'], ['espacement', 'Espacement (m)'],
    ['precharge', 'Précontrainte (kN)'], ['diametre_forage', 'Diamètre de forage (m)'], ['qs', 'qs du scellement (kPa)'], ['nombre', 'Nombre de torons / barres']],
  dalle: [['epaisseur', 'Épaisseur (m)'], ['longueur', 'Portée (m)']],
}

function Appuis({ ctx, selection, onSelection }: { ctx: Ctx; selection: Selection; onSelection: (s: Selection) => void }) {
  const appuis: Record<string, Modele> = ctx.modele.appuis ?? {}
  const noms = Object.keys(appuis)
  const actif = selection?.type === 'appui' && selection.nom in appuis ? selection.nom : noms[0]
  const a = actif ? appuis[actif] : null
  const R = ctx.references
  const [nom, setNom] = useState(actif ?? '')
  useEffect(() => setNom(actif ?? ''), [actif])
  const nouveau = () => {
    let k = noms.length + 1
    while (`B${k}` in appuis) k++
    ctx.actions.ajouterCle(['appuis'], `B${k}`, { type: 'buton', cote: -1.5, espacement: 5, longueur: 15 })
    onSelection({ type: 'appui', nom: `B${k}` })
  }
  const ch = (k: string) => ['appuis', actif!, k]
  const famille = a?.type === 'tirant' ? ['armatures', 'butons', 'profiles'] : ['butons', 'profiles']
  return (
    <div className="saisie">
      <h2>Appuis</h2>
      <p className="aide">Butons, tirants, bracons et dalles. La raideur est calculée depuis l'élément de la base matériaux (ou E et A), sauf raideur imposée. La précharge est l'effort axial par appui, appliqué à la pose.</p>
      <div className="puces-choix" style={{ marginBottom: 12 }}>
        {noms.map((n) => <button key={n} className={`puce-choix ${n === actif ? 'actif' : ''}`} onClick={() => onSelection({ type: 'appui', nom: n })}>{n} <span style={{ opacity: 0.7 }}>· {appuis[n]?.type}</span></button>)}
        <button className="puce-choix" onClick={nouveau}><IconePlus taille={12} /> nouvel appui</button>
      </div>
      {a && actif && (
        <div className="bloc"><div className="bloc-titre">{actif}
          <span className="espace" />
          <button className="btn icone discret" title="Supprimer l'appui" onClick={() => { if (window.confirm(`Supprimer l'appui « ${actif} » du script (et ses références dans les phases) ?`)) { ctx.actions.supprimer(['appuis', actif]); onSelection(null) } }}><IconeCorbeille taille={14} /></button>
        </div>
          <div className="grille-form">
            <label>Nom<input className="champ champ-bloc" value={nom} onChange={(e) => setNom(e.target.value)}
              onBlur={() => { const n = nom.trim(); if (n && n !== actif && !(n in appuis)) { ctx.actions.renommerAppui(actif, n); onSelection({ type: 'appui', nom: n }) } else setNom(actif) }} /></label>
            <label>Type<Choix ctx={ctx} chemin={ch('type')} valeur={a.type} options={enumDe(ctx.schema, 'Appui', 'type')} /></label>
            <label>Cote sur la paroi ({uniteCote(ctx.modele)})<Champ ctx={ctx} chemin={ch('cote')} valeur={a.cote} bloc="Appui" cle="cote" large /></label>
            <label>Élément (base matériaux)
              <select className="champ champ-bloc" value={a.element ?? ''} onChange={(e) => ctx.actions.fixer(ch('element'), e.target.value)}>
                <option value="">— (donner E et A)</option>
                {famille.flatMap((f) => R[f] ?? []).map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
            </label>
            {a.type !== 'dalle' && <label>Nuance d'acier<select className="champ champ-bloc" value={a.acier ?? ''} onChange={(e) => ctx.actions.fixer(ch('acier'), e.target.value)}>
              <option value="">—</option>{(R.aciers ?? []).map((r) => <option key={r} value={r}>{r}</option>)}</select></label>}
            {a.type === 'dalle' && <label>Classe de béton<select className="champ champ-bloc" value={a.beton ?? ''} onChange={(e) => ctx.actions.fixer(ch('beton'), e.target.value)}>
              <option value="">—</option>{(R.betons ?? []).map((r) => <option key={r} value={r}>{r}</option>)}</select></label>}
            <label>E (MPa), si pas d'élément<Champ ctx={ctx} chemin={ch('E')} valeur={a.E} large /></label>
            <label>A (cm²), si pas d'élément<Champ ctx={ctx} chemin={ch('A')} valeur={a.A} large /></label>
            {(CHAMPS_APPUI[a.type] ?? CHAMPS_APPUI.buton).map(([k, lib]) => (
              <label key={k} title={doc(ctx.schema, 'Appui', k)}>{lib}<Champ ctx={ctx} chemin={ch(k)} valeur={a[k]} bloc="Appui" cle={k} large /></label>
            ))}
            <label>Raideur imposée (kN/m par m)<Champ ctx={ctx} chemin={ch('raideur')} valeur={a.raideur} large /></label>
            {a.type !== 'tirant' && <label>Symétrique (deux parois)<div><Case ctx={ctx} chemin={ch('symetrique')} valeur={a.symetrique ?? true} /></div></label>}
            <label>Lierne (profilé)<select className="champ champ-bloc" value={a.lierne ?? ''} onChange={(e) => ctx.actions.fixer(ch('lierne'), e.target.value)}>
              <option value="">aucune</option>{(R.profiles ?? []).map((r) => <option key={r} value={r}>{r}</option>)}</select></label>
          </div>
        </div>
      )}
      {ctx.erreurs.filter((e) => e.chemin.startsWith('appuis')).map((e, i) => <div key={i} className="message-erreur">{e.chemin} : {e.message}</div>)}
    </div>
  )
}

function Phases({ ctx, selection, onSelection, phaseActive, onPhaseActive, res }: {
  ctx: Ctx; selection: Selection; onSelection: (s: Selection) => void; phaseActive: number; onPhaseActive: (i: number) => void; res: Resultats | null
}) {
  const phases: Modele[] = Array.isArray(ctx.modele.phases) ? ctx.modele.phases : []
  const appuis = Object.keys(ctx.modele.appuis ?? {})
  const surcharges: string[] = (ctx.modele.surcharges ?? []).map((s: Modele, i: number) => s?.nom ?? `S${i + 1}`)
  const sel = selection?.type === 'phase' ? selection.index : null
  const ph = sel !== null ? phases[sel] : null
  const listeStr = (v: unknown): string => (Array.isArray(v) ? v.join(', ') : v ? String(v) : '')
  const fixerListe = (chemin: Chemin, texte: string) => {
    const l = texte.split(',').map((s) => s.trim()).filter(Boolean)
    ctx.actions.fixer(chemin, l.length === 0 ? '' : l.length === 1 ? l[0] : l)
  }
  const nomLibre = (base: string) => {
    const noms = new Set(phases.map((p) => String(p?.nom ?? '')))
    let n = base, k = 2
    while (noms.has(n)) n = `${base} ${k++}`
    return n
  }
  const inserer = (apres: number) => {
    // nouvelle phase enchaînée après `apres` (−1 = après l'état initial, en tête de liste) ;
    // la phase qui suivait garde son enchaînement sur la nouvelle (parent implicite = précédente de la liste)
    const nom = nomLibre('Nouvelle phase')
    const suivante = phases[apres + 1]
    const valeur: Record<string, unknown> = { nom }
    if (apres >= 0 && phases[apres]?.depuis && suivante && !suivante.depuis) {
      // on insère dans une branche : la nouvelle phase enchaîne sur `apres` et la suivante restait sur `apres`
      valeur.depuis = phases[apres].nom
    }
    ctx.actions.inserer(['phases'], apres + 1, valeur)
    if (suivante && !suivante.depuis && apres >= 0 && phases[apres]?.depuis) ctx.actions.fixer(['phases', apres + 2, 'depuis'], nom)
    onSelection({ type: 'phase', index: apres + 1 })
  }
  const brancher = (depuis: number) => {
    const nom = nomLibre('Variante')
    ctx.actions.ajouter(['phases'], depuis >= 0 ? { nom, depuis: phases[depuis]?.nom } : { nom, depuis: 'État initial' })
    onSelection({ type: 'phase', index: phases.length })
  }
  const supprimer = (i: number) => {
    const nom = String(phases[i]?.nom ?? '')
    const refs = phases.map((p, k) => (p?.depuis === nom ? k + 1 : 0)).filter(Boolean)
    if (refs.length && !window.confirm(`La phase « ${nom} » est le point de départ des phases ${refs.join(', ')}. Supprimer quand même ?`)) return
    if (!refs.length && !window.confirm(`Supprimer la phase « ${nom} » du script ?`)) return
    ctx.actions.supprimer(['phases', i])
    onSelection(null)
  }
  return (
    <div className="saisie">
      <h2>Phases</h2>
      <p className="aide">Explorateur de phases : chaque phase repart de l'état de la précédente, ou de la phase indiquée par <span className="mono">depuis</span> (variante, comme une branche dans Plaxis). Insérez une phase après une autre, ou créez une variante à partir d'une phase ; cliquez une phase pour l'éditer et l'afficher dans les résultats.</p>
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(360px, 1fr) minmax(300px, 1fr)', gap: 16, alignItems: 'start' }}>
        <ArbrePhases phases={phases} res={res} actif={phaseActive} selection={sel}
          onChoisir={(i) => { onSelection(i >= 0 ? { type: 'phase', index: i } : null); if (res && i + 1 < res.phases.length) onPhaseActive(i + 1) }}
          onInserer={inserer} onBrancher={brancher} onSupprimer={supprimer} />
        <div className="bloc" style={{ margin: 0 }}>
          <div className="bloc-titre">{ph ? `Phase ${sel! + 1} — ${ph.nom ?? ''}` : 'Sélectionnez une phase'}</div>
          {ph && sel !== null && (
            <div className="grille-form" style={{ gridTemplateColumns: '1fr 1fr' }}>
              <label style={{ gridColumn: '1 / -1' }}>Nom<Champ ctx={ctx} chemin={['phases', sel, 'nom']} valeur={ph.nom} type="text" large /></label>
              <label>Phase de départ (vide = précédente)
                <select className="champ champ-bloc" value={ph.depuis ?? ''} onChange={(e) => ctx.actions.fixer(['phases', sel, 'depuis'], e.target.value)}>
                  <option value="">— précédente —</option>
                  {phases.slice(0, sel).map((p, k) => <option key={k} value={String(p?.nom ?? '')}>{k + 1}. {p?.nom}</option>)}
                </select></label>
              <label>Excaver à ({uniteCote(ctx.modele)})<Champ ctx={ctx} chemin={['phases', sel, 'excaver']} valeur={ph.excaver} placeholder="—" bloc="Phase" cle="excaver" large /></label>
              <label>Poser (appuis, virgules)<input className="champ champ-bloc" key={`p${sel}${listeStr(ph.poser)}`} defaultValue={listeStr(ph.poser)} list="liste-appuis" placeholder="—"
                onBlur={(e) => { if (e.target.value.trim() !== listeStr(ph.poser)) fixerListe(['phases', sel, 'poser'], e.target.value) }} /></label>
              <label>Déposer<input className="champ champ-bloc" key={`d${sel}${listeStr(ph.deposer)}`} defaultValue={listeStr(ph.deposer)} list="liste-appuis" placeholder="—"
                onBlur={(e) => { if (e.target.value.trim() !== listeStr(ph.deposer)) fixerListe(['phases', sel, 'deposer'], e.target.value) }} /></label>
              <label>Nappe aval ({uniteCote(ctx.modele)})<Champ ctx={ctx} chemin={['phases', sel, 'eau', 'aval']} valeur={ph.eau?.aval} placeholder="inchangée" large /></label>
              <label>Nappe amont ({uniteCote(ctx.modele)})<Champ ctx={ctx} chemin={['phases', sel, 'eau', 'amont']} valeur={ph.eau?.amont} placeholder="inchangée" large /></label>
              <label>Remblai aval à (m)<Champ ctx={ctx} chemin={['phases', sel, 'remblayer', 'aval']} valeur={ph.remblayer?.aval} placeholder="—" large /></label>
              <label>Remblai amont à (m)<Champ ctx={ctx} chemin={['phases', sel, 'remblayer', 'amont']} valeur={ph.remblayer?.amont} placeholder="—" large /></label>
              <label style={{ gridColumn: '1 / -1' }}>Retirer des surcharges (noms, virgules){surcharges.length ? ` — définies : ${surcharges.join(', ')}` : ''}
                <input className="champ champ-bloc" key={`r${sel}${listeStr(ph.retirer_surcharges)}`} defaultValue={listeStr(ph.retirer_surcharges)} placeholder="—"
                  onBlur={(e) => { const l = e.target.value.split(',').map((s) => s.trim()).filter(Boolean); if (listeStr(l) !== listeStr(ph.retirer_surcharges)) ctx.actions.fixer(['phases', sel, 'retirer_surcharges'], l.length ? l : '') }} /></label>
              {res?.phases[sel + 1] && !res.phases[sel + 1].ok && <div className="alerte rouge" style={{ gridColumn: '1 / -1' }}>{res.phases[sel + 1].message}</div>}
            </div>
          )}
        </div>
      </div>
      <datalist id="liste-appuis">{appuis.map((a) => <option key={a} value={a} />)}</datalist>
      {ctx.erreurs.filter((e) => e.chemin.startsWith('phases')).map((e, i) => <div key={i} className="message-erreur" style={{ marginTop: 8 }}>{e.chemin} : {e.message}</div>)}
    </div>
  )
}

const VERIFS: [string, string][] = [
  ['butee', 'Mobilisation de la butée'], ['equilibre_vertical', 'Équilibre vertical'], ['kranz', 'Massif d’ancrage (Kranz)'],
  ['fond_de_fouille', 'Fond de fouille (soulèvement, boulance, renard)'], ['stabilite_generale', 'Stabilité générale (Bishop)'],
  ['deplacements', 'Déplacements aux ELS'], ['structure', 'Structure (EC3, EC2)'],
]

function Verifs({ ctx }: { ctx: Ctx }) {
  const actives: string[] = Array.isArray(ctx.modele.verifications) ? ctx.modele.verifications : []
  const basculer = (k: string) => {
    const l = actives.includes(k) ? actives.filter((x) => x !== k) : [...actives, k]
    ctx.actions.fixer(['verifications'], l.length ? l : '')
  }
  return (
    <div className="saisie">
      <h2>Vérifications à mener</h2>
      <p className="aide">Les coefficients partiels sont lus dans docs/normes/*.yaml. Tant qu'une valeur y manque, la vérification est « non vérifiable » et affiche la valeur caractéristique.</p>
      <div className="bloc">
        <table className="tableau">
          <tbody>
            {VERIFS.map(([k, lib]) => (
              <tr key={k} className="cliquable" onClick={() => basculer(k)}>
                <td style={{ width: 30 }}><input type="checkbox" checked={actives.includes(k)} readOnly /></td>
                <td>{lib}</td><td className="doux mono">{k}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export function Saisie(p: Ctx & { section: Section; selection: Selection; onSelection: (s: Selection) => void; phaseActive: number; onPhaseActive: (i: number) => void; res: Resultats | null }) {
  const ctx: Ctx = p
  if (!p.modele || typeof p.modele !== 'object') {
    return <div className="vide-centre">Le script contient une erreur de syntaxe : corrigez-la dans l'onglet Script pour utiliser les formulaires.</div>
  }
  switch (p.section) {
    case 'projet': return <Projet ctx={ctx} />
    case 'sol': return <Sol ctx={ctx} selection={p.selection} res={p.res} />
    case 'paroi': return <Paroi ctx={ctx} />
    case 'eau': return <Eau ctx={ctx} />
    case 'surcharges': return <Surcharges ctx={ctx} />
    case 'appuis': return <Appuis ctx={ctx} selection={p.selection} onSelection={p.onSelection} />
    case 'phases': return <Phases ctx={ctx} selection={p.selection} onSelection={p.onSelection} phaseActive={p.phaseActive} onPhaseActive={p.onPhaseActive} res={p.res} />
    case 'verifications': return <Verifs ctx={ctx} />
  }
}
