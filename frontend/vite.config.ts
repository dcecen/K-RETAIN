import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Le serveur de calcul (FastAPI) tourne sur le port 8000 ; Vite lui relaie /api.
export default defineConfig({
  plugins: [react()],
  // Plotly, three et Monaco sont volumineux mais servis localement (usage interne, hors réseau) : chacun
  // dans son propre fichier (Monaco n'est chargé qu'à l'ouverture de l'onglet Script, three à celle de la 3D).
  build: {
    chunkSizeWarningLimit: 4000,   // le paquet Plotly seul dépasse 3 Mo : seuil au-dessus, pour garder l'alerte utile
    rollupOptions: { output: { manualChunks: { plotly: ['plotly.js-dist-min'], three: ['three'] } } },
  },
  server: {
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
})
