import type { Resultats } from '../../lib/api'
import type { Section, Selection } from '../../lib/etat'
import { Appuis } from './Appuis'
import type { AideChampInfo, Ctx } from './outils'
import { Eau } from './Eau'
import { Ecran } from './Ecran'
import { Geometrie } from './Geometrie'
import { Phases } from './Phases'
import { Projet } from './Projet'
import { Sols } from './Sols'
import { Surcharges } from './Surcharges'
import { Verifs } from './Verifs'

export type { AideChampInfo }

/** Formulaires de saisie : une vue par étape, toutes synchronisées avec le script YAML. */
export function Saisie(p: Ctx & { section: Section; selection: Selection; onSelection: (s: Selection) => void; phaseActive: number; onPhaseActive: (i: number) => void; res: Resultats | null }) {
  const ctx: Ctx = p
  if (!p.modele || typeof p.modele !== 'object') {
    return <div className="vide-centre">Le script contient une erreur de syntaxe : corrigez-la dans la vue « Script YAML » pour utiliser les formulaires.</div>
  }
  switch (p.section) {
    case 'projet': return <Projet ctx={ctx} />
    case 'sol': return <Sols ctx={ctx} selection={p.selection} res={p.res} />
    case 'ecran': return <Ecran ctx={ctx} />
    case 'geometrie': return <Geometrie ctx={ctx} />
    case 'eau': return <Eau ctx={ctx} />
    case 'surcharges': return <Surcharges ctx={ctx} />
    case 'appuis': return <Appuis ctx={ctx} selection={p.selection} onSelection={p.onSelection} />
    case 'phases': return <Phases ctx={ctx} selection={p.selection} onSelection={p.onSelection} phaseActive={p.phaseActive} onPhaseActive={p.onPhaseActive} res={p.res} />
    case 'verifs_demandees': return <Verifs ctx={ctx} />
  }
}
