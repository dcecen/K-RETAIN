import { defineConfig } from 'vitest/config'

// Tests de logique de la vue 3D : three.js sans WebGL (géométries, matériaux, arbre de scène).
export default defineConfig({
  test: {
    include: ['src/**/__tests__/**/*.test.ts'],
    environment: 'node',
  },
})
