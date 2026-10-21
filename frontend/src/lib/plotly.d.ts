// Déclaration minimale de plotly.js-dist-min (build pré-compilé sans types).
declare module 'plotly.js-dist-min' {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  type Quelconque = any
  const Plotly: {
    react: (el: HTMLElement, data: Quelconque[], layout?: Quelconque, config?: Quelconque) => Promise<Quelconque>
    purge: (el: HTMLElement) => void
    downloadImage: (el: HTMLElement, opts: Quelconque) => Promise<string>
    Plots: { resize: (el: HTMLElement) => void }
  }
  export default Plotly
}
