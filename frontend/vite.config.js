// vite.config.js — Configuration de Vite
// Ajoute le plugin Tailwind pour que les classes CSS soient reconnues

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'  // ← nouvel import

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),  // ← nouveau plugin ajouté
  ],
})