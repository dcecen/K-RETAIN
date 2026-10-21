// Auto-complétion du script YAML à partir du schéma JSON servi par le backend.

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Schema = any

export interface Proposition {
  label: string
  insertText: string
  documentation: string
  genre: 'cle' | 'valeur' | 'reference'
}

/** Clés dont la valeur est une référence de la base matériaux. */
const REFERENCES: Record<string, string[]> = {
  profil: ['palplanches', 'profiles'],
  element: ['butons', 'profiles', 'armatures'],
  acier: ['aciers'],
  beton: ['betons'],
  lierne: ['profiles'],
  profil_armature: ['profiles'],
}

function resoudre(racine: Schema, s: Schema): Schema {
  let cur = s
  for (let i = 0; i < 10 && cur; i++) {
    if (cur.$ref) {
      cur = racine.$defs?.[cur.$ref.split('/').pop()]
    } else if (cur.anyOf) {
      cur = cur.anyOf.find((x: Schema) => x.type !== 'null') ?? cur.anyOf[0]
    } else break
  }
  return cur
}

function indentation(l: string): number {
  return l.length - l.trimStart().length
}

/** Chemin YAML de l'objet qui contient la position (ex. ["phases", "[]", "eau"]). */
export function cheminAuCurseur(lignes: string[], iLigne: number, colonne: number): string[] {
  const chemin: string[] = []
  const courante = lignes[iLigne] ?? ''
  const avant = courante.slice(0, colonne - 1)
  const contenu = avant.trimStart()
  let col = contenu.length ? indentation(courante) : colonne - 1

  // Accolade ouverte sur la ligne : on est dans un bloc en ligne « clé: { ... }»
  const ouvertes = (avant.match(/\{/g) ?? []).length - (avant.match(/\}/g) ?? []).length
  if (ouvertes > 0) {
    const m = avant.trimStart().replace(/^- /, '').match(/^([\w]+)\s*:/)
    if (m) chemin.push(m[1])
    if (contenu.startsWith('- ')) chemin.push('[]')
  } else if (contenu.startsWith('- ')) {
    chemin.push('[]')
  }
  if (contenu.startsWith('- ')) col = indentation(courante)

  for (let j = iLigne - 1; j >= 0; j--) {
    const l = lignes[j]
    const t = l.trim()
    if (!t || t.startsWith('#')) continue
    const i = indentation(l)
    if (t.startsWith('- ')) {
      const colCle = i + 2
      if (colCle <= col && i < col) {
        chemin.push('[]')
        col = i
      }
      continue
    }
    if (i < col) {
      const m = t.match(/^([\w]+)\s*:/)
      if (m) chemin.push(m[1])
      col = i
      if (col === 0) break
    }
  }
  return chemin.reverse()
}

/** Schéma de l'objet désigné par le chemin. */
export function schemaDuChemin(racine: Schema, chemin: string[]): Schema {
  let s = racine
  for (const seg of chemin) {
    s = resoudre(racine, s)
    if (!s) return null
    if (seg === '[]') {
      s = s.items ?? null
    } else if (s.properties?.[seg]) {
      s = s.properties[seg]
    } else if (s.additionalProperties && typeof s.additionalProperties === 'object') {
      s = s.additionalProperties // nom libre (appui, jeu d'eau)
    } else {
      return null
    }
  }
  return resoudre(racine, s)
}

function valeursEnum(racine: Schema, s: Schema): string[] {
  const r = resoudre(racine, s)
  if (!r) return []
  if (r.enum) return r.enum.map(String)
  if (r.const !== undefined) return [String(r.const)]
  if (r.items) return valeursEnum(racine, r.items)
  if (r.type === 'boolean') return ['true', 'false']
  return []
}

export function propositions(
  racine: Schema,
  lignes: string[],
  iLigne: number,
  colonne: number,
  references: Record<string, string[]>,
): Proposition[] {
  if (!racine) return []
  const avant = (lignes[iLigne] ?? '').slice(0, colonne - 1)
  const chemin = cheminAuCurseur(lignes, iLigne, colonne)
  const objet = schemaDuChemin(racine, chemin)

  // Après « clé: » -> valeurs possibles
  const mv = avant.match(/([\w]+)\s*:\s*\[[^\]]*$/) ?? avant.match(/([\w]+)\s*:\s*([^,{}[\]]*)$/)
  if (mv && objet?.properties?.[mv[1]]) {
    const cle = mv[1]
    const sorties: Proposition[] = valeursEnum(racine, objet.properties[cle]).map((v) => ({
      label: v,
      insertText: v,
      documentation: objet.properties[cle].description ?? '',
      genre: 'valeur',
    }))
    for (const famille of REFERENCES[cle] ?? []) {
      for (const ref of references[famille] ?? []) {
        sorties.push({ label: ref, insertText: ref, documentation: `base matériaux : ${famille}`, genre: 'reference' })
      }
    }
    return sorties
  }

  // Sinon -> mots-clés de l'objet courant
  const props = objet?.properties ?? {}
  return Object.entries(props).map(([cle, def]) => {
    const d = resoudre(racine, def as Schema) ?? {}
    const descr = (def as Schema).description ?? d.description ?? ''
    const obligatoire = (objet.required ?? []).includes(cle) ? ' (obligatoire)' : ''
    return { label: cle, insertText: `${cle}: `, documentation: descr + obligatoire, genre: 'cle' as const }
  })
}

/** Aide au survol : description du mot-clé. */
export function aideMotCle(racine: Schema, lignes: string[], iLigne: number, mot: string): string | null {
  const l = lignes[iLigne] ?? ''
  const pos = l.indexOf(mot) + 1
  const chemin = cheminAuCurseur(lignes, iLigne, pos)
  const objet = schemaDuChemin(racine, chemin)
  const def = objet?.properties?.[mot]
  if (!def) return null
  const d = resoudre(racine, def)
  return def.description ?? d?.description ?? null
}
