// Édition du script YAML à partir des formulaires, en conservant commentaires et mise en forme.
// Le script reste la référence. Pour une valeur existante, seuls ses caractères sont
// remplacés dans le texte ; les ajouts, suppressions et déplacements régénèrent le texte.
import { isMap, isScalar, isSeq, parseDocument, Scalar, stringify, type Document } from 'yaml'

export type Chemin = (string | number)[]

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type Modele = any

export function lire(texte: string): { doc: Document | null; modele: Modele; erreur: string | null } {
  const doc = parseDocument(texte)
  if (doc.errors.length) return { doc: null, modele: null, erreur: doc.errors[0].message }
  return { doc, modele: doc.toJS() ?? {}, erreur: null }
}

function ecrire(doc: Document, origine: string): string {
  const s = doc.toString({ lineWidth: 0, flowCollectionPadding: false })
  return origine.includes('\r\n') ? s.replace(/\r?\n/g, '\r\n') : s
}

/** Modification structurelle (ajout, suppression, déplacement) : régénère le texte. */
function modifier(texte: string, action: (doc: Document) => void): string {
  const { doc } = lire(texte)
  if (!doc) return texte
  action(doc)
  return ecrire(doc, texte)
}

/** Écriture d'une valeur simple telle qu'elle apparaîtra dans le script. */
function formaterScalaire(v: string | number | boolean, enLigne: boolean): string {
  if (typeof v !== 'string') return String(v)
  if (enLigne && /[,[\]{}#:]/.test(v)) return JSON.stringify(v)
  return stringify(v).trimEnd()
}

/** Fixe une valeur ; une valeur vide supprime la clé.
 *  Valeur existante : seuls ses caractères sont remplacés dans le texte (commentaires,
 *  alignements et écriture des autres nombres restent intacts). */
export function fixer(texte: string, chemin: Chemin, valeur: unknown): string {
  const vide = valeur === undefined || valeur === null || valeur === ''
  const doc = parseDocument(texte)
  if (doc.errors.length) return texte
  const noeud = doc.getIn(chemin, true)
  if (!vide && isScalar(noeud) && noeud.range && ['string', 'number', 'boolean'].includes(typeof valeur)) {
    const parent = doc.getIn(chemin.slice(0, -1), true)
    const enLigne = (isMap(parent) || isSeq(parent)) && !!parent.flow
    return (texte.slice(0, noeud.range[0]) + formaterScalaire(valeur as string | number | boolean, enLigne)
      + texte.slice(noeud.range[1]))
  }
  return modifier(texte, (d) => {
    if (vide) {
      if (d.hasIn(chemin)) d.deleteIn(chemin)
    } else {
      d.setIn(chemin, valeur)
    }
  })
}

/** Ajoute un élément à une liste (créée si absente), dans le style des éléments voisins. */
export function ajouter(texte: string, chemin: Chemin, valeur: unknown): string {
  return modifier(texte, (doc) => {
    const seq = doc.getIn(chemin, true)
    const noeud = doc.createNode(valeur)
    if (isSeq(seq)) {
      const voisin = seq.items[seq.items.length - 1]
      if (isMap(voisin) && voisin.flow && isMap(noeud)) noeud.flow = true
      seq.items.push(noeud)
    } else {
      doc.setIn(chemin, doc.createNode([valeur]))
    }
  })
}

/** Insère un élément dans une liste à la position donnée. */
export function inserer(texte: string, chemin: Chemin, index: number, valeur: unknown): string {
  return modifier(texte, (doc) => {
    const seq = doc.getIn(chemin, true)
    const noeud = doc.createNode(valeur)
    if (isSeq(seq)) {
      const voisin = seq.items[Math.min(index, seq.items.length) - 1] ?? seq.items[0]
      if (isMap(voisin) && voisin.flow && isMap(noeud)) noeud.flow = true
      seq.items.splice(Math.max(0, Math.min(index, seq.items.length)), 0, noeud)
    } else {
      doc.setIn(chemin, doc.createNode([valeur]))
    }
  })
}

/** Ajoute une entrée nommée à un bloc (appuis, jeux d'eau). */
export function ajouterCle(texte: string, chemin: Chemin, cle: string, valeur: unknown): string {
  return modifier(texte, (doc) => {
    const bloc = doc.getIn(chemin, true)
    const noeud = doc.createNode(valeur)
    if (isMap(bloc)) {
      const voisin = bloc.items[bloc.items.length - 1]?.value
      if (isMap(voisin) && voisin.flow && isMap(noeud)) noeud.flow = true
      bloc.set(cle, noeud)
    } else {
      doc.setIn([...chemin, cle], noeud)
    }
  })
}

export function supprimer(texte: string, chemin: Chemin): string {
  return modifier(texte, (doc) => {
    if (doc.hasIn(chemin)) doc.deleteIn(chemin)
  })
}

/** Échange deux éléments d'une liste. */
export function deplacer(texte: string, chemin: Chemin, i: number, j: number): string {
  return modifier(texte, (doc) => {
    const seq = doc.getIn(chemin, true)
    if (isSeq(seq) && j >= 0 && j < seq.items.length) {
      const t = seq.items[i]
      seq.items[i] = seq.items[j]
      seq.items[j] = t
    }
  })
}

/** Renomme un appui et met à jour les références dans les phases (poser, déposer). */
export function renommerAppui(texte: string, ancien: string, nouveau: string): string {
  return modifier(texte, (doc) => {
    const bloc = doc.getIn(['appuis'], true)
    if (!isMap(bloc) || bloc.has(nouveau)) return
    const paire = bloc.items.find((p) => (p.key as Scalar)?.value === ancien)
    if (paire) paire.key = new Scalar(nouveau)
    const phases = doc.getIn(['phases'], true)
    if (isSeq(phases)) {
      phases.items.forEach((_, k) => {
        for (const cle of ['poser', 'deposer']) {
          const v = doc.getIn(['phases', k, cle])
          if (v === ancien) doc.setIn(['phases', k, cle], nouveau)
          else if (v && typeof v === 'object') {
            const liste = (v as { toJSON: () => string[] }).toJSON()
            if (liste.includes(ancien)) doc.setIn(['phases', k, cle], liste.map((x) => (x === ancien ? nouveau : x)))
          }
        }
      })
    }
  })
}

/** Ligne (1 = première) où commence la valeur désignée, pour y placer le curseur. */
export function ligneDe(texte: string, chemin: Chemin): number | null {
  const doc = parseDocument(texte)
  const noeud = doc.getIn(chemin, true) as { range?: [number, number, number] } | undefined
  if (!noeud?.range) return null
  return texte.slice(0, noeud.range[0]).split('\n').length
}

/** Chemin lisible au format des erreurs du serveur : sol[2].gamma, appuis.B1.cote. */
export function cheminErreur(chemin: Chemin): string {
  let s = ''
  for (const c of chemin) s += typeof c === 'number' ? `[${c + 1}]` : s ? `.${c}` : c
  return s
}
