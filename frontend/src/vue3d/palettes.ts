// Palettes de couleur des résultats et des taux de travail (fonctions pures).
import * as THREE from 'three'

export type NomPalette = 'divergente' | 'sequentielle' | 'signe'

/** Points de passage des palettes (RVB 0–255). La palette « divergente » est celle de la maquette d'origine. */
export const PALETTES: Record<NomPalette, number[][]> = {
  divergente: [[0x2c, 0x7b, 0xb6], [0xab, 0xd9, 0xe9], [0xff, 0xff, 0xbf], [0xfd, 0xae, 0x61], [0xd7, 0x19, 0x1c]],
  sequentielle: [[0x44, 0x01, 0x54], [0x3b, 0x52, 0x8b], [0x21, 0x91, 0x8c], [0x5e, 0xc9, 0x62], [0xfd, 0xe7, 0x25]],
  signe: [[0x2c, 0x5d, 0xa8], [0x9d, 0xb9, 0xdc], [0xf2, 0xf2, 0xf2], [0xe8, 0x9a, 0x8e], [0xb3, 0x26, 0x1e]],
}

export const NOMS_PALETTES: Record<NomPalette, string> = {
  divergente: 'Bleu → rouge',
  sequentielle: 'Séquentielle (viridis)',
  signe: 'Signée (bleu −, rouge +)',
}

/** Couleur de la palette à la position t ∈ [0, 1] (bornée), écrite dans `out`. */
export function couleurPalette(t: number, nom: NomPalette, out: THREE.Color): THREE.Color {
  const pal = PALETTES[nom]
  const u = Math.min(Math.max(Number.isFinite(t) ? t : 0, 0), 1) * (pal.length - 1)
  const i = Math.min(Math.floor(u), pal.length - 2)
  const f = u - i
  return out.setRGB(
    (pal[i][0] + f * (pal[i + 1][0] - pal[i][0])) / 255,
    (pal[i][1] + f * (pal[i + 1][1] - pal[i][1])) / 255,
    (pal[i][2] + f * (pal[i + 1][2] - pal[i][2])) / 255,
  )
}

/** Dégradé CSS d'une palette (légendes). */
export function degradeCss(nom: NomPalette): string {
  const pal = PALETTES[nom]
  return `linear-gradient(to right, ${pal.map((c, i) => `rgb(${c.join(',')}) ${(100 * i) / (pal.length - 1)}%`).join(', ')})`
}

export interface Seuils { orange: number; rouge: number }
export const SEUILS_DEFAUT: Seuils = { orange: 0.9, rouge: 1.0 }

export type ClasseTaux = 'vert' | 'orange' | 'rouge' | 'gris'

/** Classe d'un taux de travail : vert < 90 % ≤ orange < 100 % ≤ rouge ; gris si non vérifiable. */
export function classeTaux(taux: number | null | undefined, s: Seuils = SEUILS_DEFAUT): ClasseTaux {
  if (taux === null || taux === undefined || Number.isNaN(taux)) return 'gris'
  if (taux >= s.rouge) return 'rouge'
  if (taux >= s.orange) return 'orange'
  return 'vert'
}

export const COULEURS_TAUX: Record<ClasseTaux, number> = { vert: 0x2e9d5b, orange: 0xe39a2b, rouge: 0xc7362c, gris: 0x9aa2ad }

/** Couleur de la valeur v sur l'échelle [min, max]. */
export function couleurValeur(v: number, min: number, max: number, nom: NomPalette, out: THREE.Color): THREE.Color {
  return couleurPalette((v - min) / (max - min || 1), nom, out)
}
