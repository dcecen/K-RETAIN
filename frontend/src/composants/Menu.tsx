import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

/** Menu déroulant : se ferme au clic extérieur et à Échap.
 *
 * La liste est rendue dans `document.body` (portail) en position fixe, calée sous le bouton :
 * la barre de titre coupe ce qui dépasse (`overflow: hidden`, nécessaire aux écrans étroits),
 * une liste positionnée à l'intérieur y serait masquée. La position suit le redimensionnement
 * et le défilement ; la liste défile si elle est plus haute que la fenêtre. */
export function Menu({ bouton, children, droite = false, titre }: {
  bouton: ReactNode
  children: (fermer: () => void) => ReactNode
  droite?: boolean
  titre?: string
}) {
  const [ouvert, setOuvert] = useState(false)
  const [style, setStyle] = useState<CSSProperties>({ visibility: 'hidden' })
  const ref = useRef<HTMLDivElement>(null)
  const liste = useRef<HTMLDivElement>(null)

  useLayoutEffect(() => {
    if (!ouvert) return
    const placer = () => {
      const r = ref.current?.getBoundingClientRect()
      if (!r) return
      const marge = 8
      const haut = r.bottom + 4
      const s: CSSProperties = { position: 'fixed', top: haut, maxHeight: Math.max(120, window.innerHeight - haut - marge), overflowY: 'auto' }
      if (droite) s.right = Math.max(marge, window.innerWidth - r.right)
      else s.left = Math.max(marge, Math.min(r.left, window.innerWidth - 240 - marge))
      setStyle(s)
    }
    placer()
    window.addEventListener('resize', placer)
    window.addEventListener('scroll', placer, true)
    return () => {
      window.removeEventListener('resize', placer)
      window.removeEventListener('scroll', placer, true)
    }
  }, [ouvert, droite])

  useEffect(() => {
    if (!ouvert) return
    const clic = (e: MouseEvent) => {
      const cible = e.target as Node
      if (!ref.current?.contains(cible) && !liste.current?.contains(cible)) setOuvert(false)
    }
    const touche = (e: KeyboardEvent) => { if (e.key === 'Escape') setOuvert(false) }
    document.addEventListener('mousedown', clic)
    document.addEventListener('keydown', touche)
    return () => {
      document.removeEventListener('mousedown', clic)
      document.removeEventListener('keydown', touche)
    }
  }, [ouvert])

  return (
    <div className="menu" ref={ref}>
      <button className={`btn ${ouvert ? 'actif' : ''}`} onClick={() => setOuvert(!ouvert)} title={titre}
        aria-haspopup="menu" aria-expanded={ouvert}>
        {bouton}
      </button>
      {ouvert && createPortal(
        <div ref={liste} className={`menu-liste flottante ${droite ? 'droite' : ''}`} role="menu" style={style}>
          {children(() => setOuvert(false))}
        </div>,
        document.body,
      )}
    </div>
  )
}
