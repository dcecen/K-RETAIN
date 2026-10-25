// Note de calcul (HTML imprimable, A4) : cartouche, objet, documents de référence, hypothèses,
// caractéristiques géotechniques, phasage, résultats par phase, vérifications ELU/ELS, conclusion.
// Phrases courtes et factuelles ; nombres à la virgule ; unités kN/ml, kN.m/ml, kPa, m.
import type { EntreeNorme, Resultats, Verif } from './api'
import { nb, pourcent, uniteCote } from './format'
import type { Modele } from './scriptDoc'
import { libelleFamille, sourceCourte, valeurs } from './verifs'
import { schemaSvg, valeurFiche } from '../vues/verifs/coupeSvg'

const h = (s: unknown) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]!)
const n = (v: number | null | undefined, d = 1) => nb(v, d)
const ETATS: Record<Verif['etat'], string> = { ok: 'Vérifié', attention: 'Vérifié', non_ok: 'Non vérifié', non_verifiable: 'Non vérifiable' }
const FICHIERS: Record<string, string> = {
  nf_p94_282: 'NF P 94-282 (mars 2009), Calcul géotechnique, ouvrages de soutènement, écrans ; EN 1997-1 (Eurocode 7) et annexe nationale',
  ec2: 'EN 1992-1-1 (Eurocode 2) et annexe nationale',
  ec3: 'EN 1993-1-1 et EN 1993-5 (Eurocode 3) et annexes nationales',
  ec3_assemblages: 'EN 1993-1-8 (Eurocode 3, assemblages)',
  hydraulique: 'Critères hydrauliques (Terzaghi, Lane)',
}

export interface ContexteNote {
  modele: Modele
  normes: Record<string, EntreeNorme[]> | null
  version: string
}

function extremum(z: number[] | undefined, v: number[] | undefined, quoi: 'max' | 'min' | 'abs'): { v: number; z: number } | null {
  if (!z || !v || !v.length) return null
  let k = 0
  for (let i = 1; i < v.length; i++) {
    const a = quoi === 'abs' ? Math.abs(v[i]) : v[i], b = quoi === 'abs' ? Math.abs(v[k]) : v[k]
    if (quoi === 'min' ? a < b : a > b) k = i
  }
  return { v: v[k], z: z[k] }
}

function tableau(entetes: string[], lignes: string[][], classes: string[] = []): string {
  const th = entetes.map((e, i) => `<th class="${classes[i] ?? ''}">${e}</th>`).join('')
  const tr = lignes.map((l) => `<tr>${l.map((c, i) => `<td class="${classes[i] ?? ''}">${c}</td>`).join('')}</tr>`).join('')
  return `<table><thead><tr>${th}</tr></thead><tbody>${tr || `<tr><td colspan="${entetes.length}">Néant.</td></tr>`}</tbody></table>`
}

/** Bloc `projet:` du script sous forme de dictionnaire (vide si le projet est un simple texte). */
function infosProjet(modele: Modele): Record<string, unknown> {
  const p = modele?.projet
  return p && typeof p === 'object' && !Array.isArray(p) ? (p as Record<string, unknown>) : {}
}

export function noteCalcul(res: Resultats, ctx: ContexteNote): string {
  const { modele, normes, version } = ctx
  const unite = uniteCote(modele)
  const infos = infosProjet(modele)
  const texte = (k: string) => (infos[k] === undefined || infos[k] === null ? '' : String(infos[k]))
  const date = texte('date') || new Date().toLocaleDateString('fr-FR')
  const nomProjet = res.projet || texte('nom')
  const phasesOk = res.phases.filter((p) => p.ok)
  const sol: Modele[] = Array.isArray(modele?.sol) ? modele.sol : []
  const couche = (nom: string) => sol.find((c) => c?.nom === nom) ?? {}
  const nf = normes?.nf_p94_282 ?? []
  const norme = (cle: string) => nf.find((e) => e.cle === cle)
  const appuisDef = res.appuis
  const verifs = res.verifications ?? []
  const nonOk = verifs.filter((v) => v.etat === 'non_ok')
  const nonVerifiables = verifs.filter((v) => v.etat === 'non_verifiable')
  const d = res.dimensionnant
  const calcul = (modele?.calcul ?? {}) as Record<string, unknown>

  // ---- 1. objet
  const objet = `<p>Calcul de l'écran de soutènement du projet « ${h(nomProjet)} » par la méthode aux coefficients de réaction.</p>
<p>Écran : ${h(res.paroi.type ?? 'type non renseigné')}, tête à ${n(res.paroi.tete, 2)} ${unite}, pied à ${n(res.paroi.pied, 2)} ${unite}, fiche de ${n(res.paroi.tete - res.paroi.pied, 2)} m.
Phasage : ${res.phases.length - 1} phases après l'état initial (phase 0). Appuis : ${appuisDef.length ? appuisDef.map((a) => `${h(a.nom)} (${h(a.type)}, cote ${n(a.cote, 2)})`).join(', ') : 'aucun'}.</p>
<p>Résultats fournis : déplacements, moments fléchissants, efforts tranchants, pressions des terres et de l'eau, efforts d'appui par phase ; vérifications géotechniques et structurelles demandées dans le script.</p>`

  // ---- 2. documents de référence
  const docs = [
    ...Object.keys(normes ?? {}).map((f) => `${h(FICHIERS[f] ?? f)} (valeurs lues dans docs/normes/${h(f)}.yaml)`),
    'Script de calcul YAML du projet (données d\'entrée, reproduit en annexe du dossier)',
    'Base matériaux RetainWall (profilés, palplanches, butons, armatures, aciers, bétons)',
  ]
  const documents = `<ol>${docs.map((x) => `<li>${x}</li>`).join('')}</ol>`

  // ---- 3. hypothèses
  const approche = norme('approche_de_calcul')
  const coeffs = nf.filter((e) => /^(combinaisons|butee)\./.test(e.cle))
  const eau: Record<string, Modele> = modele?.eau && typeof modele.eau === 'object' ? modele.eau : {}
  const surcharges: Modele[] = Array.isArray(modele?.surcharges) ? modele.surcharges : []
  const reserves = [
    'Version du logiciel non validée : résultats à comparer à K-Réa ou RIDO sur plusieurs cas et à viser par un ingénieur avant tout usage en projet.',
    'Valeurs normatives de docs/normes renseignées « à confirmer » : relecture sur le texte des normes requise (statut indiqué dans la colonne Source).',
    ...res.avertissements,
  ]
  const hypotheses = `
<h3>3.1 Méthode</h3>
<p>Écran modélisé en poutre d'Euler-Bernoulli sur ressorts élasto-plastiques (méthode aux coefficients de réaction). Calcul phasé : chaque phase repart de l'état de la précédente, avec mémoire des ressorts. Coefficients de poussée et de butée : ${h(res.couches[0]?.methode_k ?? String(calcul.coefficients ?? 'Coulomb'))}. Coefficient de réaction : ${h(calcul.kh === 'impose' ? 'kh imposé par couche' : 'formule de Schmitt (EM, α, EI)')}.</p>
<p>Approche de calcul : ${approche ? `${h(approche.valeur ?? 'non renseignée')} <span class="src">(${h(approche.source)})</span>` : 'non renseignée dans docs/normes'}.</p>
<h3>3.2 Coefficients partiels</h3>
${tableau(['Coefficient', 'Valeur', 'Source'], coeffs.map((e) => [h(e.cle), e.valeur === null ? 'non renseigné' : h(typeof e.valeur === 'number' ? n(e.valeur, 2) : e.valeur), `<span class="src">${h(e.source)}</span>`]), ['', 'n', ''])}
<h3>3.3 Conventions</h3>
<ul>
<li>Cotes en ${h(unite)}, axe vertical vers le haut.</li>
${Object.values(res.conventions ?? {}).map((v) => `<li>${h(v)}</li>`).join('')}
<li>Unités de la note : kN/ml et kN.m/ml par mètre linéaire d'écran ; kN par appui ; kPa ; m.</li>
</ul>
<h3>3.4 Écran</h3>
${tableau(['Paramètre', 'Valeur'], [
    ['Type', h(res.paroi.type ?? '')], ['Cote de tête', `${n(res.paroi.tete, 2)} ${unite}`], ['Cote du pied', `${n(res.paroi.pied, 2)} ${unite}`],
    ...(typeof res.paroi.EI === 'number' ? [['Rigidité EI', `${n(res.paroi.EI, 0)} kN.m²/ml (${h(res.paroi.EI_source ?? '')})`]] : []),
    ...(typeof res.paroi.rapport_largeur_fiche === 'number' ? [['Largeur de réaction sous le fond', `${pourcent(res.paroi.rapport_largeur_fiche)} de l'entraxe`]] : []),
    ...Object.entries(res.paroi).filter(([k, v]) => ['profil', 'acier', 'beton', 'epaisseur', 'diametre', 'entraxe'].includes(k) && (typeof v === 'string' || typeof v === 'number')).map(([k, v]) => [h(k), h(typeof v === 'number' ? n(v, 2) : v)]),
  ], ['', 'n'])}
<h3>3.5 Appuis</h3>
${tableau(['Appui', 'Type', 'Élément', `Cote (${unite})`, 'Espacement (m)', 'Angle (°)', 'Précharge (kN)', 'Raideur (kN/m/ml)'],
    appuisDef.map((a) => [h(a.nom), h(a.type), h(a.element ?? '—'), n(a.cote, 2), n(a.espacement, 2), n(a.angle, 1), n(a.precharge, 0), n(a.raideur, 0)]), ['', '', '', 'n', 'n', 'n', 'n', 'n'])}
<h3>3.6 Eau</h3>
${tableau(['Jeu de niveaux', `Nappe amont (${unite})`, `Nappe aval (${unite})`], Object.entries(eau).map(([k, v]) => [h(k), v?.amont === null || v?.amont === undefined ? 'aucune' : n(v.amont, 2), v?.aval === null || v?.aval === undefined ? 'aucune' : n(v.aval, 2)]), ['', 'n', 'n'])}
<p>Régime : ${h(String((modele?.hydraulique?.regime as string | undefined) ?? 'hydrostatique'))}. Les niveaux modifiés dans les phases figurent au tableau du phasage.</p>
<h3>3.7 Surcharges</h3>
${tableau(['Nom', 'Type', 'q', 'Distance (m)', 'Largeur (m)', 'Face'], surcharges.map((s, i) => [h(s?.nom ?? `S${i + 1}`), h(s?.type ?? ''), h(s?.q ?? ''), s?.distance === undefined ? '0' : h(s.distance), s?.largeur === undefined ? '—' : h(s.largeur), h(s?.cote_ecran ?? 'amont')]), ['', '', 'n', 'n', 'n', ''])}
<p>q en kPa (répartie, uniforme, bande, rectangulaire), kN (ponctuelle) ou kN/ml (linéique). Diffusion élastique (Boussinesq, Flamant).</p>
<h3>3.8 Réserves</h3>
<ul>${reserves.map((r) => `<li>${h(r)}</li>`).join('')}</ul>`

  // ---- 4. caractéristiques géotechniques
  const geotech = tableau(
    ['Couche', `Toit (${unite})`, 'γ (kN/m³)', "γ' (kN/m³)", "c' (kPa)", "φ' (°)", "δa/φ'", "δp/φ'", 'EM (kPa)', 'α', 'Ka', 'Kp', 'K0', 'kh (kN/m³)'],
    res.couches.map((c) => {
      const s = couche(c.nom) as Record<string, unknown>
      const v = (k: string, d: number) => (typeof s[k] === 'number' ? n(s[k] as number, d) : '—')
      return [h(c.nom), n(c.toit, 2), v('gamma', 1), v('gamma_dejauge', 1), n(c.c ?? (s.c as number | undefined) ?? 0, 1), n(c.phi ?? (s.phi as number | undefined), 1),
        n(c.delta_a_sur_phi ?? (s.delta_a_sur_phi as number | undefined) ?? 0, 2), n(c.delta_p_sur_phi ?? (s.delta_p_sur_phi as number | undefined) ?? 0, 2),
        v('EM', 0), v('alpha', 2), n(c.kah, 3), n(c.kph, 2), n(c.k0, 3), n(c.kh, 0)]
    }), ['', 'n', 'n', 'n', 'n', 'n', 'n', 'n', 'n', 'n', 'n', 'n', 'n', 'n'])
  const methodes = `<p>Ka, Kp : ${h(res.couches[0]?.methode_k ?? '')}. K0 : ${h([...new Set(res.couches.map((c) => c.k0_source ?? ''))].filter(Boolean).join(' ; ') || 'Jaky')}. kh : ${h([...new Set(res.couches.map((c) => c.methode_kh ?? ''))].filter(Boolean).join(' ; '))}. Cohésion par les états correspondants.</p>`

  // ---- 5. phasage
  const phasage = tableau(['N°', 'Phase', 'Actions', `Fond de fouille (${unite})`, `Nappe amont (${unite})`, `Nappe aval (${unite})`],
    res.phases.map((p, i) => [String(i), h(p.nom) + (p.depuis ? ` <span class="src">(variante depuis « ${h(p.depuis)} »)</span>` : ''), h(p.actions.map((a) => a.texte).join(' ; ')), n(p.terrain_aval, 2), p.eau_amont === null ? 'aucune' : n(p.eau_amont, 2), p.eau_aval === null ? 'aucune' : n(p.eau_aval, 2)]),
    ['n', '', '', 'n', 'n', 'n'])

  // ---- 6. résultats par phase
  const lignesRes = res.phases.map((p, i) => {
    if (!p.ok) return [String(i), h(p.nom), `<span class="ko">${h(p.message)}</span>`, '', '', '', '', '', '', '']
    const y = extremum(p.z, p.y_mm, 'abs'), mx = extremum(p.z_diag, p.M, 'max'), mn = extremum(p.z_diag, p.M, 'min'), v = extremum(p.z_diag, p.V, 'abs')
    return [String(i), h(p.nom), `${n(y?.v)} (${n(y?.z, 2)})`, `${n(mx?.v)} (${n(mx?.z, 2)})`, `${n(mn?.v)} (${n(mn?.z, 2)})`, `${n(v?.v)} (${n(v?.z, 2)})`,
      n(p.synthese?.Bm_kN_m), n(p.synthese?.Bt_kN_m), pourcent(p.synthese?.butee_mobilisee), String(p.iterations ?? '')]
  })
  const resultats = tableau(['N°', 'Phase', 'y max (mm) à la cote', 'M max (kN.m/ml) à la cote', 'M min (kN.m/ml) à la cote', 'V max (kN/ml) à la cote', 'Bm (kN/ml)', 'Bt (kN/ml)', 'Bm/Bt', 'Itérations'],
    lignesRes, ['n', '', 'n', 'n', 'n', 'n', 'n', 'n', 'n', 'n'])
  const effortsAppuis = appuisDef.length ? tableau(['N°', 'Phase', ...appuisDef.flatMap((a) => [`${h(a.nom)} (kN/ml)`, `${h(a.nom)} (kN)`])],
    res.phases.map((p, i) => [String(i), h(p.nom), ...appuisDef.flatMap((a) => { const e = p.appuis?.find((x) => x.nom === a.nom); return e ? [n(e.effort_kN_m) + (e.actif ? '' : ' (décollé)'), n(e.effort_axial_kN, 0)] : ['', ''] })]),
    ['n', '', ...appuisDef.flatMap(() => ['n', 'n'])]) : '<p>Aucun appui.</p>'
  const dimensionnant = tableau(['Grandeur', 'Valeur', 'Phase'], [
    ['Déplacement maximal', `${n(d.deplacement?.valeur_mm)} mm`, h(d.deplacement?.phase ?? '')],
    ['Moment maximal (face côté fouille tendue)', `${n(d.moment_positif?.valeur)} kN.m/ml`, h(d.moment_positif?.phase ?? '')],
    ['Moment minimal (face côté terre tendue)', `${n(d.moment_negatif?.valeur)} kN.m/ml`, h(d.moment_negatif?.phase ?? '')],
    ['Effort tranchant maximal', `${n(d.tranchant?.valeur)} kN/ml`, h(d.tranchant?.phase ?? '')],
    ...Object.entries(d.appuis ?? {}).map(([nom, a]) => [`Effort maximal dans ${h(nom)}`, `${n(a.effort_kN_m)} kN/ml, soit ${n(a.effort_axial_kN, 0)} kN par appui`, h(a.phase)]),
  ], ['', 'n', ''])

  // ---- 7. vérifications
  const famille = (v: Verif) => (/ELS|déplacement/i.test(v.nom) ? 'ELS' : v.categorie === 'geotechnique' ? 'ELU géotechnique (GEO, UPL, HYD)' : 'ELU structure (STR)')
  const groupes = new Map<string, Verif[]>()
  for (const v of verifs) groupes.set(famille(v), [...(groupes.get(famille(v)) ?? []), v])
  const verifications = verifs.length ? [...groupes.entries()].map(([nom, liste]) => `<h3>${h(nom)}</h3>${tableau(
    ['Vérification', 'Élément', 'Phase', 'Valeur de calcul', 'Valeur limite', 'Taux de travail', 'Statut', 'Référence'],
    liste.map((v) => {
      const [calc, lim] = valeurs(v)
      return [h(v.nom), h(v.element), h(v.phase ?? '—'), h(calc), h(lim) || (v.manquants.length ? `<span class="src">valeur de norme manquante : ${h(v.manquants.join(', '))}</span>` : ''),
        v.taux === null ? '—' : pourcent(v.taux), `<span class="${v.etat === 'non_ok' ? 'ko' : ''}">${ETATS[v.etat]}</span>`, `<span class="src" title="${h(v.source)}">${h(sourceCourte(v.source))}</span>`]
    }), ['', '', '', '', '', 'n', '', ''])}`).join('') : '<p>Aucune vérification demandée dans le script.</p>'
  // fiches détaillées (principe, données, étapes, schéma) des vérifications qui en portent une
  const fiches = verifs.filter((v) => v.principe).map((v) => {
    const donnees = v.donnees.filter((d) => !d.origine.startsWith('norme:'))
    const normes = v.donnees.filter((d) => d.origine.startsWith('norme:'))
    const svg = schemaSvg(v.schema)
    return `<div class="fiche"><h4>${h(v.nom)} — ${h(v.element)}${v.phase ? ` (${h(v.phase)})` : ''} : ${ETATS[v.etat]}${v.taux === null ? '' : `, taux ${pourcent(v.taux)}`}</h4>
<p>${h(v.principe)}</p>
${donnees.length ? tableau(['Symbole', 'Donnée', 'Valeur', 'Unité', 'Origine'], donnees.map((d) => [h(d.symbole), h(d.libelle), h(valeurFiche(d.valeur)), h(d.unite), h(d.origine)]), ['', '', 'n', '', '']) : ''}
${normes.length ? `<p class="src">Valeurs normatives : ${normes.map((d) => `${h(d.symbole)} = ${h(valeurFiche(d.valeur))} (${h(d.origine.replace('norme:', 'docs/normes/').replace(':', '.yaml : '))})`).join(' ; ')}</p>` : ''}
${v.etapes.length ? `<ol>${v.etapes.map((e) => `<li>${h(e)}</li>`).join('')}</ol>` : ''}
${svg ?? ''}
<p class="src">Référence : ${h(v.source)}</p></div>`
  }).join('')
  const fichesParFamille = fiches ? `<h3>7.4 Fiches détaillées</h3><p>Pour chaque vérification : principe de la méthode, données utilisées et leur origine, étapes du calcul et schéma. Les vérifications sont regroupées par famille (${[...new Set(verifs.filter((v) => v.principe).map((v) => libelleFamille(v.famille)))].map(h).join(', ')}).</p>${fiches}` : ''

  // ---- 8. conclusion
  const conclusion = `<ul>
<li>Calcul ${res.complet ? 'mené à terme sur toutes les phases' : `interrompu : ${h(res.phases.find((p) => !p.ok)?.message ?? 'rupture')}`} (${phasesOk.length} états calculés sur ${res.phases.length}, état initial compris).</li>
<li>Déplacement maximal : ${n(d.deplacement?.valeur_mm)} mm (${h(d.deplacement?.phase ?? '')}). Moment maximal : ${n(d.moment_positif?.valeur)} kN.m/ml ; minimal : ${n(d.moment_negatif?.valeur)} kN.m/ml. Effort tranchant maximal : ${n(d.tranchant?.valeur)} kN/ml.</li>
<li>Butée mobilisée Bm/Bt maximale : ${pourcent(Math.max(0, ...phasesOk.map((p) => p.synthese?.butee_mobilisee ?? 0)))} (valeurs caractéristiques).</li>
<li>Vérifications : ${verifs.length} demandées ; vérifiées : ${verifs.length - nonOk.length - nonVerifiables.length} ; non vérifiées : ${nonOk.length}${nonOk.length ? ` (${nonOk.map((v) => `${h(v.nom)}, ${h(v.element)}, taux ${v.taux === null ? '—' : pourcent(v.taux)}`).join(' ; ')})` : ''} ; non vérifiables : ${nonVerifiables.length}${nonVerifiables.length ? ` (${nonVerifiables.map((v) => `${h(v.nom)}, ${h(v.element)}`).join(' ; ')})` : ''}.</li>
<li>Réserves : voir § 3.8.</li>
</ul>`

  const cartouche = tableau(['Affaire', 'Projet', 'Indice', 'Date', 'Rédacteur', 'Vérificateur', 'Logiciel'],
    [[h(texte('affaire') || '—'), h(nomProjet || '—'), h(texte('indice') || '—'), h(date), h(texte('redacteur') || '—'), h(texte('verificateur') || '—'), `RetainWall ${h(version)}`]])
  const complement = ['client', 'lieu'].filter((k) => texte(k)).map((k) => `${k === 'client' ? 'Client' : 'Lieu'} : ${h(texte(k))}`).join(' ; ')

  return `<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>Note de calcul ${h(nomProjet)}</title>
<style>
  body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 10pt; color: #1b2330; margin: 16mm 14mm; line-height: 1.35; }
  h1 { font-size: 15pt; margin: 0 0 3mm; } h2 { font-size: 12pt; margin: 7mm 0 2mm; border-bottom: 1px solid #1f4e79; padding-bottom: 1mm; page-break-after: avoid; }
  h3 { font-size: 10.5pt; margin: 4mm 0 1.5mm; page-break-after: avoid; }
  p { margin: 0 0 2mm; } ul, ol { margin: 0 0 2mm; padding-left: 5mm; } li { margin-bottom: 0.8mm; }
  table { width: 100%; border-collapse: collapse; font-size: 8.5pt; margin: 1mm 0 3mm; page-break-inside: auto; }
  th, td { border: 1px solid #b8c0cc; padding: 1mm 1.5mm; text-align: left; vertical-align: top; }
  th { background: #eef1f5; font-weight: 600; } td.n, th.n { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
  tr { page-break-inside: avoid; } .src { color: #5a6475; font-size: 8pt; } .ko { color: #a32018; font-weight: 600; }
  .cartouche table { font-size: 9pt; } .cartouche th { background: #e8eef5; }
  .fiche { page-break-inside: avoid; margin: 3mm 0 5mm; padding: 2mm 3mm; border: 1px solid #dde2e9; }
  .fiche h4 { font-size: 10pt; margin: 0 0 1.5mm; } .fiche ol { padding-left: 6mm; } .fiche svg { display: block; max-width: 125mm; height: auto; margin: 2mm 0; }
  .pied { margin-top: 8mm; font-size: 8pt; color: #5a6475; border-top: 1px solid #b8c0cc; padding-top: 1mm; }
  @page { size: A4; margin: 12mm; } @media print { body { margin: 0; } }
</style></head><body>
<div class="cartouche">
<h1>Note de calcul : écran de soutènement</h1>
${cartouche}
${complement ? `<p>${complement}</p>` : ''}
</div>
<h2>1. Objet</h2>${objet}
<h2>2. Documents de référence</h2>${documents}
<h2>3. Hypothèses</h2>${hypotheses}
<h2>4. Caractéristiques géotechniques</h2>${geotech}${methodes}
<h2>5. Phasage</h2>${phasage}
<h2>6. Résultats par phase</h2>
<h3>6.1 Déplacements, moments, efforts tranchants, butée</h3>${resultats}
<p>Valeurs caractéristiques par mètre linéaire d'écran. Cotes des extrêmes entre parenthèses (${h(unite)}). Bm : résultante des pressions mobilisées côté fouille ; Bt : résultante des pressions limites de butée.</p>
<h3>6.2 Efforts d'appui</h3>${effortsAppuis}
<p>Effort positif : l'appui retient l'écran (buton comprimé, tirant tendu). kN par appui = kN/ml × espacement / cos(angle).</p>
<h3>6.3 Valeurs dimensionnantes</h3>${dimensionnant}
<h2>7. Vérifications aux ELU et aux ELS</h2>
<p>Taux de travail = valeur de calcul / valeur limite. Vérifié si taux ≤ 100 %. Non vérifiable : valeur de norme manquante dans docs/normes (la valeur caractéristique est donnée).</p>
${verifications}
${fichesParFamille}
<h2>8. Conclusion</h2>${conclusion}
<div class="pied">RetainWall ${h(version)}, note éditée le ${h(new Date().toLocaleDateString('fr-FR'))}. Conventions : y positif vers la fouille ; M positif quand la face côté fouille est tendue ; efforts d'appui positifs quand l'appui retient l'écran.</div>
</body></html>`
}
