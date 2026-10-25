// Test de fumée et captures d'écran de l'interface RetainWall par Chrome sans affichage (protocole DevTools).
// Usage : node fumee.mjs <url> <dossier_captures> [prefixe]
//   url      : adresse de l'interface servie (ex. http://127.0.0.1:8011/)
//   dossier  : dossier des PNG (créé au besoin) ; les captures s'appellent <prefixe>_<etape>.png
//   prefixe  : « avant », « apres », « lot1 »… (défaut : « capture »)
// Prérequis : Node 22 ou plus (WebSocket natif), Chrome installé au chemin ci-dessous.
// Code de retour 1 si une exception JavaScript ou une erreur console a été relevée, ou si une vue
// attendue est introuvable.
import { spawn } from 'node:child_process'
import { mkdirSync, writeFileSync } from 'node:fs'
import { join, resolve } from 'node:path'

const [url, dossier, prefixe = 'capture'] = process.argv.slice(2)
if (!url || !dossier) {
  console.error('Usage : node fumee.mjs <url> <dossier_captures> [prefixe]')
  process.exit(2)
}
mkdirSync(dossier, { recursive: true })
const CHROME = process.env.RETAINWALL_CHROME ?? 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const PORT = Number(process.env.RETAINWALL_CDP_PORT ?? 9333)
// le profil doit être un chemin absolu, sinon le port de débogage ne répond pas
const profil = resolve(dossier, 'profil-chrome')
const chrome = spawn(CHROME, [
  '--headless=new', `--remote-debugging-port=${PORT}`, '--remote-debugging-address=127.0.0.1', `--user-data-dir=${profil}`,
  '--no-first-run', '--window-size=1600,1000', '--hide-scrollbars', '--disable-gpu', 'about:blank',
], { stdio: 'ignore' })

const dormir = (ms) => new Promise((r) => setTimeout(r, ms))
async function cible() {
  for (let i = 0; i < 150; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${PORT}/json/list`)
      const l = await r.json()
      const p = l.find((t) => t.type === 'page')
      if (p) return p.webSocketDebuggerUrl
    } catch { /* pas encore prêt */ }
    await dormir(200)
  }
  throw new Error('Chrome injoignable sur le port de débogage')
}

const ws = new WebSocket(await cible())
await new Promise((r) => (ws.onopen = r))
let id = 0
const attentes = new Map()
const journal = []      // exceptions et erreurs console
const manquantes = []   // vues attendues introuvables
ws.onmessage = (ev) => {
  const m = JSON.parse(ev.data)
  if (m.id && attentes.has(m.id)) { attentes.get(m.id)(m); attentes.delete(m.id) }
  if (m.method === 'Runtime.exceptionThrown') journal.push('EXCEPTION ' + (m.params.exceptionDetails.exception?.description ?? JSON.stringify(m.params.exceptionDetails)))
  if (m.method === 'Runtime.consoleAPICalled' && m.params.type === 'error')
    journal.push('console.error ' + m.params.args.map((a) => a.value ?? a.description).join(' '))
}
const envoyer = (method, params = {}) => new Promise((r) => { const i = ++id; attentes.set(i, r); ws.send(JSON.stringify({ id: i, method, params })) })
const evaluer = async (expression) => {
  const r = await envoyer('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })
  if (r.result?.exceptionDetails) throw new Error(JSON.stringify(r.result.exceptionDetails))
  return r.result?.result?.value
}
const capture = async (nom) => {
  const r = await envoyer('Page.captureScreenshot', { format: 'png' })
  writeFileSync(join(dossier, `${prefixe}_${nom}.png`), Buffer.from(r.result.data, 'base64'))
  console.log('capture', nom)
}
/** Clic sur l'élément (onglet, nœud de navigation ou bouton) dont le texte est exactement `texte`, sinon sur le
 *  premier dont le texte commence par `texte` (« Vérifications » désigne la vue de résultats, pas l'étape de
 *  saisie « Vérifications demandées »). */
const aller = async (texte, { attente = 1200, obligatoire = true } = {}) => {
  const ok = await evaluer(`(() => {
    const lib = (x) => (x.querySelector('.libelle') ?? x).textContent.trim()
    const cands = [...document.querySelectorAll('.noeud'), ...document.querySelectorAll('.onglet'), ...document.querySelectorAll('button')]
    const b = cands.find((x) => lib(x) === ${JSON.stringify(texte)}) ?? cands.find((x) => lib(x).startsWith(${JSON.stringify(texte)}))
    if (b) { b.click(); return true } return false })()`)
  if (!ok) { console.log('vue introuvable :', texte); if (obligatoire) manquantes.push(texte) }
  await dormir(attente)
  return ok
}
const touche = async (key, code, keyCode, modifiers = 0) => {
  await envoyer('Input.dispatchKeyEvent', { type: 'keyDown', key, code, windowsVirtualKeyCode: keyCode, modifiers })
  await envoyer('Input.dispatchKeyEvent', { type: 'keyUp', key, code, windowsVirtualKeyCode: keyCode, modifiers })
}
const etatCalcul = () => evaluer(`document.querySelector('.etat-calcul')?.textContent ?? ''`)

await envoyer('Runtime.enable')
await envoyer('Page.enable')
await envoyer('Emulation.setDeviceMetricsOverride', { width: 1600, height: 1000, deviceScaleFactor: 1, mobile: false })
await envoyer('Page.navigate', { url })
await dormir(3000)
await evaluer('localStorage.clear()')           // état de premier lancement
await envoyer('Page.navigate', { url })
await dormir(4000)
await capture('00_accueil')

// Calcul par Ctrl+Entrée, attente de la fin
await touche('Enter', 'Enter', 13, 2)
for (let i = 0; i < 80; i++) {
  if (/Calcul terminé|interrompu|Erreur/.test(await etatCalcul())) break
  await dormir(500)
}
console.log('état :', await etatCalcul())
await dormir(1500)
await capture('01_apres_calcul')

// Vues de résultats (anciens et nouveaux libellés : les absents ne sont pas obligatoires)
for (const [nom, texte, oblig] of [
  ['02_synthese', 'Synthèse', false], ['03_diagrammes', 'Diagrammes', false], ['03_coupe', 'Coupe', false],
  ['04_efforts', 'Efforts', true], ['05_verifications', 'Vérifications', true], ['06_hypotheses', 'Hypothèses', true],
]) {
  if (await aller(texte, { obligatoire: oblig })) await capture(nom)
}
// Vérifications : sous-onglets par famille et fiches détaillées avec schéma (clic sur le premier onglet : butée)
if (await aller('Vérifications', { obligatoire: false })) {
  const n = await evaluer(`document.querySelectorAll('.onglets-verifs .onglet-verif').length`)
  if (!n) journal.push('vérifications : aucun sous-onglet de famille')
  await evaluer(`(() => { const b = document.querySelector('.onglets-verifs .onglet-verif'); if (b) b.click() })()`)
  await dormir(600)
  if (!(await evaluer(`!!document.querySelector('.fiche-verif')`))) journal.push('vérifications : aucune fiche détaillée affichée')
  if (!(await evaluer(`!!document.querySelector('.fiche-verif svg')`))) journal.push('vérifications : aucun schéma SVG dans la fiche de butée')
  // clic sur une ligne de la synthèse : la fiche correspondante défile en vue
  await evaluer(`(() => { const l = document.querySelector('.synthese-verifs tr.cliquable'); if (l) l.click() })()`)
  await dormir(600)
  await capture('05b_verifications_fiche')
}
// Maquette 3D : panneau Résultats (R), puis Échap
if (await aller('Maquette 3D', { attente: 4000 })) {
  await capture('07_maquette3d')
  await touche('r', 'KeyR', 82)
  await dormir(1500)
  await capture('08_maquette3d_resultats')
  // un seul panneau à la fois : L ouvre les calques et ferme les résultats ; C ouvre les courbes en un point
  await touche('l', 'KeyL', 76)
  await dormir(800)
  const panneaux = await evaluer(`[!!document.querySelector('.panneau-calques'), !!document.querySelector('.panneau-resultats')]`)
  if (!(panneaux[0] && !panneaux[1])) journal.push(`maquette : après L, calques=${panneaux[0]} résultats=${panneaux[1]} (attendu : calques seuls)`)
  await capture('08b_maquette3d_calques')
  await touche('c', 'KeyC', 67)
  await dormir(1500)
  if (!(await evaluer(`!!document.querySelector('.panneau-coupe-locale') && !document.querySelector('.panneau-calques')`))) journal.push('maquette : après C, les courbes en un point ne remplacent pas les calques')
  await capture('08c_maquette3d_courbes')
  await touche('Escape', 'Escape', 27)
  await dormir(500)
  if (await evaluer(`!!document.querySelector('.panneau-coupe-locale')`)) journal.push('maquette : Échap ne ferme pas les courbes en un point')
  // les menus de la barre s'ouvrent
  if (await aller('Outils', { attente: 500, obligatoire: false })) { await capture('08d_maquette3d_menu_outils'); await touche('Escape', 'Escape', 27); await dormir(300) }
}
// Saisie : première couche, puis chaque étape
await evaluer(`(() => { const b = [...document.querySelectorAll('.noeud.enfant')][0]; b?.click() })()`)
await dormir(1200)
await capture('09_saisie_couche')
// Saisie de phi' sur la première couche : l'aide du champ s'affiche, une seule ligne du script change
{
  const avant = await evaluer(`localStorage.getItem('retainwall.brouillon') ?? ''`)
  const ok = await evaluer(`(() => {
    const i = [...document.querySelectorAll('.saisie table tbody tr:first-child input.champ.num')][4]
    if (!i) return false
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set
    i.focus(); setter.call(i, String(Number(i.value) + 1)); i.dispatchEvent(new Event('input', { bubbles: true })); i.blur(); return true })()`)
  await dormir(900)
  if (ok) {
    await capture('09b_aide_champ')
    const apres = await evaluer(`localStorage.getItem('retainwall.brouillon') ?? ''`)
    const a = avant.split(/\r?\n/), b = apres.split(/\r?\n/)
    const diff = a.length !== b.length ? -1 : a.filter((l, k) => l !== b[k]).length
    if (diff !== 1) journal.push(`saisie de phi : ${diff} ligne(s) du script modifiée(s) au lieu de 1`)
    else console.log('saisie de phi : une seule ligne du script modifiée')
  } else journal.push('champ phi introuvable dans la vue Sols')
}
for (const [nom, texte] of [['10_projet', 'Projet'], ['11_ecran', 'Écran'], ['12_eau', 'Eau'], ['13_surcharges', 'Surcharges'], ['14_appuis', 'Appuis'], ['15_phases', 'Phases']]) {
  if (await aller(texte)) await capture(nom)
}
// Formulaire de la deuxième phase (clic sur sa ligne)
if (await evaluer(`(() => { const l = [...document.querySelectorAll('.ligne-phase')][2]; if (l) { l.click(); return true } return false })()`)) {
  await dormir(800)
  await capture('15b_phase_formulaire')
} else journal.push('ligne de phase introuvable')
// Outils
for (const [nom, texte, oblig] of [['16_script', 'Script', true], ['17_assemblages', 'Assemblages', true], ['18_materiaux', 'Base matériaux', true], ['19_aide', 'Aide', false]]) {
  if (await aller(texte, { attente: 2000, obligatoire: oblig })) await capture(nom)
  if (nom === '17_assemblages') {
    // ouverture d'un assemblage déjà présent dans le script (A1 de l'exemple)
    const ok = await evaluer(`(() => { const b = [...document.querySelectorAll('.noeud')].find((x) => x.querySelector('.libelle')?.textContent.trim() === 'A1'); if (b) { b.click(); return true } return false })()`)
    await dormir(1500)
    if (ok) await capture('17b_assemblage_existant'); else console.log('assemblage A1 introuvable (exemple sans assemblages ?)')
  }
}

// Menu Fichier ouvert, puis boîte de dialogue de confirmation (suppression d'une surcharge, annulée par Échap)
if (await aller('Fichier', { attente: 600, obligatoire: false })) { await capture('20_menu_fichier'); await touche('Escape', 'Escape', 27); await dormir(300) }
if (await aller('Surcharges')) {
  const ok = await evaluer(`(() => { const b = document.querySelector('.saisie button[title="Supprimer"]'); if (b) { b.click(); return true } return false })()`)
  await dormir(600)
  if (ok) { await capture('21_dialogue'); await touche('Escape', 'Escape', 27); await dormir(300) }
  const reste = await evaluer(`!!document.querySelector('.dialogue')`)
  if (reste) journal.push('dialogue encore ouvert après Échap')
}

console.log(`--- journal : ${journal.length} entrée(s) ; vues manquantes : ${manquantes.length}`)
for (const l of journal.slice(0, 30)) console.log(l)
ws.close()
chrome.kill()
process.exit(journal.length || manquantes.length ? 1 : 0)
