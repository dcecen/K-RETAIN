// Exports : image PNG de la vue active, note de synthèse imprimable.
import type { Resultats } from './api'
import { cote, nb, pourcent } from './format'

/** Chaque vue qui sait produire une image s'enregistre ici quand elle est affichée. */
let exportateur: (() => void) | null = null
export function enregistrerExport(f: (() => void) | null) {
  exportateur = f
}
export function exportImagePossible(): boolean {
  return exportateur !== null
}
export function exporterImage() {
  exportateur?.()
}

export function telecharger(url: string, nom: string) {
  const a = document.createElement('a')
  a.href = url
  a.download = nom
  a.click()
}

export function telechargerTexte(texte: string, nom: string, type: string) {
  const url = URL.createObjectURL(new Blob([texte], { type }))
  telecharger(url, nom)
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

const echapper = (s: string) => s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]!)

const ETATS: Record<string, string> = { ok: 'Vérifié', attention: 'Limite', non_ok: 'Non vérifié', non_verifiable: 'Non vérifiable' }

/** Note de synthèse (HTML imprimable) : résultats clés, appuis, vérifications, réserves. */
export function noteSynthese(res: Resultats): string {
  const d = res.dimensionnant
  const date = new Date().toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })
  const lignesPhases = res.phases.map((p, i) => `<tr><td>${i + 1}</td><td>${echapper(p.nom)}</td><td class="n">${cote(p.terrain_aval)}</td>
    <td class="n">${cote(p.eau_aval)}</td><td class="n">${nb(p.synthese?.y_max_mm)}</td><td class="n">${nb(p.synthese?.M_max, 0)}</td>
    <td class="n">${nb(p.synthese?.M_min, 0)}</td><td class="n">${pourcent(p.synthese?.butee_mobilisee)}</td>
    <td>${p.ok ? '' : echapper(p.message)}</td></tr>`).join('')
  const lignesAppuis = res.appuis.map((a) => {
    const m = d.appuis?.[a.nom]
    return `<tr><td>${echapper(a.nom)}</td><td>${a.type}</td><td>${echapper(a.element ?? '—')}</td><td class="n">${nb(a.cote, 2)}</td>
      <td class="n">${nb(a.espacement, 2)}</td><td class="n">${nb(m?.effort_kN_m)}</td><td class="n">${nb(m?.effort_axial_kN, 0)}</td>
      <td>${echapper(m?.phase ?? '')}</td></tr>`
  }).join('')
  const lignesVerifs = (res.verifications ?? []).map((v) => `<tr><td>${echapper(v.nom)}</td><td>${echapper(v.element)}</td>
    <td class="n">${v.taux === null ? '—' : pourcent(v.taux)}</td><td>${ETATS[v.etat]}</td><td>${echapper(v.detail)}${
      v.manquants.length ? `<br><i>Valeurs manquantes : ${echapper(v.manquants.join(', '))}</i>` : ''}</td></tr>`).join('')
  return `<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>Note de synthèse — ${echapper(res.projet)}</title>
<style>
  body { font-family: 'IBM Plex Sans', 'Segoe UI', sans-serif; font-size: 10.5pt; color: #1b2330; margin: 18mm 16mm; }
  h1 { font-size: 16pt; margin: 0 0 2mm; } h2 { font-size: 12pt; margin: 7mm 0 2mm; border-bottom: 1px solid #c6cdd8; padding-bottom: 1mm; }
  .reserve { border: 1px solid #a86400; color: #a86400; padding: 2mm 3mm; margin: 4mm 0; font-size: 9.5pt; }
  table { width: 100%; border-collapse: collapse; font-size: 9pt; } th, td { border-bottom: 1px solid #dde2e9; padding: 1.2mm 1.5mm; text-align: left; vertical-align: top; }
  th { background: #f3f5f8; font-weight: 600; } td.n { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
  .cles { display: grid; grid-template-columns: repeat(4, 1fr); gap: 3mm; } .cle { border: 1px solid #dde2e9; padding: 2mm; }
  .cle b { display: block; font-size: 13pt; } .doux { color: #5a6475; font-size: 9pt; }
  @page { size: A4; margin: 0; }
</style></head><body>
<h1>Note de synthèse — ${echapper(res.projet)}</h1>
<div class="doux">RetainWall — calcul d'écran par la méthode aux coefficients de réaction — édité le ${date}</div>
<div class="reserve">Démonstrateur — calculs non validés. Aucun résultat ne doit servir à un projet réel avant comparaison
à K-Réa ou RIDO sur plusieurs cas et visa d'un ingénieur. Valeurs de norme non fournies : les vérifications concernées sont « non vérifiables ».</div>
<h2>Résultats clés</h2>
<div class="cles">
  <div class="cle">Déplacement max<b>${nb(d.deplacement?.valeur_mm)} mm</b><span class="doux">${echapper(d.deplacement?.phase ?? '')}</span></div>
  <div class="cle">Moment positif max<b>${nb(d.moment_positif?.valeur, 0)} kN·m/m</b><span class="doux">${echapper(d.moment_positif?.phase ?? '')}</span></div>
  <div class="cle">Moment négatif min<b>${nb(d.moment_negatif?.valeur, 0)} kN·m/m</b><span class="doux">${echapper(d.moment_negatif?.phase ?? '')}</span></div>
  <div class="cle">Tranchant max<b>${nb(d.tranchant?.valeur, 0)} kN/m</b><span class="doux">${echapper(d.tranchant?.phase ?? '')}</span></div>
</div>
${res.avertissements.length ? `<h2>Avertissements</h2><ul>${res.avertissements.map((a) => `<li>${echapper(a)}</li>`).join('')}</ul>` : ''}
<h2>Phases</h2>
<table><tr><th>#</th><th>Phase</th><th>Fond</th><th>Nappe aval</th><th>y max (mm)</th><th>M max (kN·m/m)</th><th>M min</th><th>Butée mobilisée</th><th></th></tr>${lignesPhases}</table>
<h2>Appuis</h2>
<table><tr><th>Appui</th><th>Type</th><th>Élément</th><th>Cote (m)</th><th>Espacement (m)</th><th>Effort max (kN/m)</th><th>Effort axial (kN)</th><th>Phase</th></tr>${lignesAppuis}</table>
<h2>Vérifications</h2>
<table><tr><th>Vérification</th><th>Élément</th><th>Taux</th><th>État</th><th>Détail</th></tr>${lignesVerifs || '<tr><td colspan="5">Aucune vérification demandée.</td></tr>'}</table>
<p class="doux">Conventions : y positif vers la fouille ; M positif quand la face côté fouille est tendue ; efforts d'appui positifs quand l'appui retient l'écran.</p>
</body></html>`
}

export function imprimerNote(res: Resultats) {
  const w = window.open('', '_blank')
  if (!w) return
  w.document.write(noteSynthese(res))
  w.document.close()
  w.focus()
  setTimeout(() => w.print(), 400)
}
