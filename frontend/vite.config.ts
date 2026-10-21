import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Le serveur de calcul (FastAPI) tourne sur le port 8000 ; Vite lui relaie /api.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
})
