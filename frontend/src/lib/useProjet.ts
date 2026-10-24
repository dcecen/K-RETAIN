// État du projet : script YAML (référence du modèle), validation en direct, calcul (une ou plusieurs coupes),
// résultats, coupe affichée, données de référence du serveur. Aucune logique d'affichage ici.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, ErreurServeur, messageErreur, type ErreurScript, type Exemple, type ProjetCoupes, type ReponseCalcul, type Resultats } from './api'
import type { EtatCalcul } from './etat'
import { nomProjet } from './format'
import { telechargerTexte } from './exporter'
import * as sd from './scriptDoc'

const CLE_BROUILLON = 'retainwall.brouillon'
const COTES_VIDES: Record<string, number> = {}
const lireBrouillon = () => { try { return localStorage.getItem(CLE_BROUILLON) } catch { return null } }
const ecrireBrouillon = (t: string) => { try { localStorage.setItem(CLE_BROUILLON, t) } catch { /* stockage indisponible */ } }

/** Exemple ouvert au premier lancement : la fouille de référence, pas le premier fichier par ordre alphabétique. */
export const EXEMPLE_INITIAL = 'fouille_exemple'

export interface Actions {
  fixer: (chemin: sd.Chemin, valeur: unknown) => void
  ajouter: (chemin: sd.Chemin, valeur: unknown) => void
  ajouterCle: (chemin: sd.Chemin, cle: string, valeur: unknown) => void
  supprimer: (chemin: sd.Chemin) => void
  deplacer: (chemin: sd.Chemin, i: number, j: number) => void
  inserer: (chemin: sd.Chemin, index: number, valeur: unknown) => void
  renommerAppui: (ancien: string, nouveau: string) => void
}

export function useProjet() {
  const [texte, setTexteBrut] = useState<string>(() => lireBrouillon() ?? '')
  const [erreurs, setErreurs] = useState<ErreurScript[]>([])
  const [avertScript, setAvertScript] = useState<ErreurScript[]>([])
  const [res, setRes] = useState<Resultats | null>(null)
  const [resBase, setResBase] = useState<Resultats | null>(null)       // résultats de la première coupe
  const [projet, setProjet] = useState<ProjetCoupes | null>(null)      // coupes de calcul du projet
  const [coupeActive, setCoupeActive] = useState(0)
  const [schema, setSchema] = useState<unknown>(null)
  const [references, setReferences] = useState<Record<string, string[]>>({})
  const [exemples, setExemples] = useState<Exemple[]>([])
  const [enCours, setEnCours] = useState(false)
  const [etat, setEtat] = useState<EtatCalcul>({ genre: 'aucun', texte: 'Aucun calcul' })
  const [serveur, setServeur] = useState('')
  const [rapportRido, setRapportRido] = useState<string[] | null>(null)
  const minuterie = useRef<number | undefined>(undefined)
  const texteCalcule = useRef<string>('')
  const texteCharge = useRef<string | null>(null)   // texte au dernier chargement ou enregistrement (état « modifié »)
  const enCoursRef = useRef(false)                  // Ctrl+Entrée pendant un calcul : ignoré (pas de second calcul concurrent)
  const numeroValidation = useRef(0)                // seule la dernière validation lancée met à jour l'affichage

  const { modele, erreur: erreurYaml } = useMemo(() => sd.lire(texte), [texte])
  const cotesPlan = useMemo<Record<string, number>>(() => (modele?.plan?.cotes && typeof modele.plan.cotes === 'object' ? modele.plan.cotes : COTES_VIDES), [modele])

  useEffect(() => {
    fetch('/api/sante').then((r) => r.json()).then((d) => setServeur(`v${d.version}`)).catch(() => setServeur('serveur injoignable'))
    api.schema().then(setSchema).catch(() => {})
    api.references().then(setReferences)
    api.exemples().then((ex) => {
      setExemples(ex)
      if (!lireBrouillon() && ex.length) {
        const premier = ex.find((e) => e.nom === EXEMPLE_INITIAL) ?? ex[0]
        texteCharge.current = premier.texte
        setTexteBrut(premier.texte)
      }
    }).catch(() => {})
  }, [])

  // Validation en direct, état « modifié »
  useEffect(() => {
    ecrireBrouillon(texte)
    window.clearTimeout(minuterie.current)
    minuterie.current = window.setTimeout(() => {
      if (!texte.trim()) { setErreurs([]); setAvertScript([]); return }
      const numero = ++numeroValidation.current
      api.valider(texte).then((r) => {
        if (numero !== numeroValidation.current) return   // réponse périmée (une frappe plus récente a relancé la validation)
        setErreurs(r.erreurs)
        setAvertScript(r.avertissements ?? [])
        if (r.erreurs.length) {
          const e = r.erreurs[0]
          setEtat({ genre: 'erreur', texte: e.ligne ? `Erreur ligne ${e.ligne}` : 'Script invalide', ligne: e.ligne })
        } else if (texte !== texteCalcule.current) {
          setEtat(res ? { genre: 'modifie', texte: 'Modifié depuis le calcul' } : { genre: 'aucun', texte: 'Aucun calcul' })
        } else if (res) {
          setEtat((e) => (e.genre === 'ok' || e.genre === 'rupture' ? e : { genre: 'ok', texte: `Calcul terminé : ${res.phases.length - 1} phases` }))
        }
      }).catch(() => {})
    }, 500)
  }, [texte, res])

  const setTexte = useCallback((t: string) => setTexteBrut(t), [])

  /** Remplace le script (exemple, fichier, nouveau projet) : résultats effacés, état réinitialisé. */
  const charger = useCallback((t: string, message = 'Script chargé, non calculé') => {
    texteCharge.current = t
    setTexteBrut(t)
    setRes(null)
    setResBase(null)
    setProjet(null)
    setCoupeActive(0)
    setRapportRido(null)
    setEtat({ genre: 'aucun', texte: message })
  }, [])

  /** Script modifié depuis son chargement ou son dernier enregistrement. */
  const modifie = texteCharge.current !== null && texte !== texteCharge.current

  const enregistrer = useCallback(() => {
    const nom = (nomProjet(modele?.projet) || 'projet').trim().replace(/[^\w-]+/g, '_')
    telechargerTexte(texte, `${nom}.yaml`, 'text/yaml')
    texteCharge.current = texte
  }, [texte, modele])

  const importerRido = useCallback(async (f: File): Promise<boolean> => {
    try {
      const d = await api.rido(await f.text(), f.name)
      if (typeof d?.texte !== 'string') throw new Error('réponse du serveur sans script converti')
      charger(d.texte, 'Fichier RIDO converti : rapport de conversion à relire avant calcul')
      setRapportRido(Array.isArray(d.rapport) ? d.rapport : [])
      return true
    } catch (e) {
      setEtat({ genre: 'erreur', texte: `Import RIDO impossible : ${messageErreur(e)}` })
      return false
    }
  }, [charger])

  /** Lance le calcul ; renvoie les résultats, ou null en cas d'erreur ou si un calcul est déjà en cours. */
  const calculer = useCallback(async (): Promise<Resultats | null> => {
    if (!texte.trim() || enCoursRef.current) return null
    enCoursRef.current = true
    setEnCours(true)
    const t0 = performance.now()
    try {
      let r: ReponseCalcul
      const prep = await api.coupesPreparer(texte)
      if (prep.ok && !prep.unique && prep.coupes.length > 1) {
        // une requête par coupe, lancées en parallèle (cache serveur par coupe), puis la synthèse
        const faites = new Set<string>()
        const avancement = () => setEtat({ genre: 'calcul', texte: `Calcul des coupes : ${faites.size}/${prep.coupes.length} terminées (${prep.coupes.map((c) => `${c.nom.split(' — ')[0]}${faites.has(c.nom) ? '' : ' en cours'}`).join(', ')})` })
        avancement()
        const reps = await Promise.all(prep.coupes.map(async (c) => { const rc = await api.calcul(texte, c.nom); faites.add(c.nom); avancement(); return rc }))
        const echec = reps.find((x) => !x.ok || !x.resultats)
        if (echec) r = echec
        else {
          const syn = await api.coupesSynthese(texte)
          if (!syn.ok) r = { ok: false, erreurs: syn.erreurs }
          else {
            const coupes = syn.projet.coupes.map((c, i) => (i === 0 ? c : { ...c, resultats: reps[i].resultats }))
            r = { ok: true, erreurs: [], resultats: reps[0].resultats, projet: { ...syn.projet, coupes } }
          }
        }
      } else r = await api.calcul(texte)
      const ms = Math.round(performance.now() - t0)
      setErreurs(r.erreurs)
      if (r.ok && r.resultats) {
        // chaque coupe porte ses résultats (la première = ceux de la réponse)
        if (r.projet) r.projet = { ...r.projet, coupes: r.projet.coupes.map((c, i) => (i === 0 ? { ...c, resultats: r.resultats } : c)) }
        texteCalcule.current = texte
        setRes(r.resultats)
        setResBase(r.resultats)
        setProjet(r.projet ?? null)
        setCoupeActive(0)
        const nPhases = r.resultats.phases.length
        const derniere = nPhases ? r.resultats.phases[nPhases - 1] : null
        const rompue = r.resultats.phases.find((p) => !p.ok)
        const itMax = Math.max(0, ...r.resultats.phases.map((p) => p.iterations ?? 0))
        setEtat(r.resultats.complet
          ? { genre: 'ok', texte: `Calcul terminé : ${nPhases - 1} phases, convergence atteinte (au plus ${itMax} itérations), ${ms} ms` }
          : { genre: 'rupture', texte: `Calcul interrompu à la phase « ${(rompue ?? derniere)?.nom ?? 'aucune'} » : ${(rompue ?? derniere)?.message ?? 'rupture'}` })
        return r.resultats
      }
      const e = r.erreurs[0]
      setEtat({ genre: 'erreur', texte: e?.ligne ? `Erreur ligne ${e.ligne}` : `Erreur : ${e?.message ?? 'script invalide'}`, ligne: e?.ligne })
      return null
    } catch (e) {
      // ErreurServeur : le serveur a répondu (erreur interne traduite en français) ; sinon il est injoignable
      setEtat({ genre: 'erreur', texte: e instanceof ErreurServeur ? `Erreur du serveur de calcul : ${e.message}` : messageErreur(e) })
      return null
    } finally {
      enCoursRef.current = false
      setEnCours(false)
    }
  }, [texte])

  /** Change de coupe de calcul affichée ; renvoie la phase à afficher (même nom, sinon dernière phase projet
   *  précédente), ou null si rien ne change. */
  const changerCoupe = useCallback((i: number, phase: number): number | null => {
    if (!projet || !resBase || !res || i === coupeActive || i < 0 || i >= projet.coupes.length) return null
    const cible = projet.coupes[i].resultats ?? resBase
    const nom = res.phases[phase]?.nom
    let j = cible.phases.findIndex((p) => p.nom === nom)
    if (j < 0) {
      const ip = projet.coupes[coupeActive].correspondance[phase] ?? phase
      j = 0
      projet.coupes[i].correspondance.forEach((c, k) => { if (c <= ip) j = k })
    }
    setRes(cible)
    setCoupeActive(i)
    return j
  }, [projet, resBase, res, coupeActive])

  // Actions des formulaires : toutes passent par le document YAML (mémorisées : les formulaires ne sont pas recréés à chaque frappe)
  const actions = useMemo<Actions>(() => ({
    fixer: (c, v) => setTexteBrut((t) => sd.fixer(t, c, v)),
    ajouter: (c, v) => setTexteBrut((t) => sd.ajouter(t, c, v)),
    ajouterCle: (c, k, v) => setTexteBrut((t) => sd.ajouterCle(t, c, k, v)),
    supprimer: (c) => setTexteBrut((t) => sd.supprimer(t, c)),
    deplacer: (c, i, j) => setTexteBrut((t) => sd.deplacer(t, c, i, j)),
    inserer: (c, i, v) => setTexteBrut((t) => sd.inserer(t, c, i, v)),
    renommerAppui: (a, n) => setTexteBrut((t) => sd.renommerAppui(t, a, n)),
  }), [])

  const plusieursCoupes = !!projet && !projet.unique && projet.coupes.length > 1

  return {
    texte, setTexte, modele, erreurYaml, cotesPlan, erreurs, avertScript, etat, setEtat,
    res, resBase, projet, coupeActive, changerCoupe, plusieursCoupes, calculer, enCours,
    charger, modifie, enregistrer, importerRido, rapportRido, setRapportRido, actions,
    schema, references, rechargerReferences: () => api.references().then(setReferences),
    exemples, serveur, texteCalcule: () => texteCalcule.current,
  }
}

export type Projet = ReturnType<typeof useProjet>
