import { nb } from '../lib/format'
import type { Legende } from './legendes'

/** Légendes empilées dans un coin de la vue 3D (lisibles en clair et en sombre). */
export function Legendes({ liste }: { liste: Legende[] }) {
  if (!liste.length) return null
  return (
    <div className="vue3d-legendes" aria-label="Légendes">
      {liste.map((l) => (
        <div key={l.id} className="legende-3d">
          <div className="titre">{l.titre}</div>
          {l.type === 'continue' ? (
            <>
              <div className="degrade" style={{ background: l.degrade }} />
              <div className="bornes"><span>{nb(l.min, l.unite === 'mm' ? 1 : 0)}</span><span className="unite">{l.unite}</span><span>{nb(l.max, l.unite === 'mm' ? 1 : 0)}</span></div>
            </>
          ) : l.classes.length > 0 && (
            <div className="classes">{l.classes.map((c) => <span key={c.texte}><i style={{ background: c.couleur }} />{c.texte}</span>)}</div>
          )}
          <div className="phase">{l.phase}{l.note ? ` · ${l.note}` : ''}</div>
        </div>
      ))}
    </div>
  )
}
