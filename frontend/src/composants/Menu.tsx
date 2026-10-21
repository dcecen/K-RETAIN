import { useEffect, useRef, useState, type ReactNode } from 'react'

/** Menu déroulant : se ferme au clic extérieur et à Échap. */
export function Menu({ bouton, children, droite = false, titre }: {
  bouton: ReactNode
  children: (fermer: () => void) => ReactNode
  droite?: boolean
  titre?: string
}) {
  const [ouvert, setOuvert] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!ouvert) return
    const clic = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOuvert(false) }
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
      {ouvert && <div className={`menu-liste ${droite ? 'droite' : ''}`} role="menu">{children(() => setOuvert(false))}</div>}
    </div>
  )
}
