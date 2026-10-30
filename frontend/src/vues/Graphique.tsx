import { useEffect, useRef } from 'react'
import Plotly from 'plotly.js-dist-min'
import { couleurs } from '../lib/theme'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Trace = any
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Mise = any

const POLICE = { family: 'system-ui, sans-serif', size: 12 }

/** Graphique Plotly interactif, export PNG et SVG depuis la barre d'outils. */
export function Graphique({ data, layout, hauteur = 520, nom = 'k-retain', theme }: { theme?: string;
  data: Trace[]
  layout: Mise
  hauteur?: number
  nom?: string
}) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const c = couleurs()
    void Plotly.react(
      el,
      data,
      { font: { ...POLICE, color: c.texte }, margin: { l: 60, r: 20, t: 40, b: 50 }, paper_bgcolor: c.fond, plot_bgcolor: c.fond, separators: ', ', ...layout },
      {
        responsive: true,
        displaylogo: false,
        locale: 'fr',
        toImageButtonOptions: { format: 'png', filename: nom, scale: 2 },
        modeBarButtonsToAdd: [
          {
            name: 'Exporter en SVG',
            icon: {
              width: 24,
              height: 24,
              path: 'M5 20h14v-2H5v2zm7-18L5.33 9h3.84v6h5.66V9h3.84L12 2z',
            },
            click: (gd: HTMLElement) => Plotly.downloadImage(gd, { format: 'svg', filename: nom }),
          },
        ],
      },
    )
  }, [data, layout, nom, theme])

  useEffect(() => {
    const el = ref.current
    return () => {
      if (el) Plotly.purge(el)
    }
  }, [])

  return <div ref={ref} style={{ width: '100%', height: hauteur }} />
}
