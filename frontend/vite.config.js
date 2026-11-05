import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        // Le worker de pdf.js est livré en « .mjs ». La table MIME de nginx
        // (image officielle 1.28) ne connaît pas cette extension : le fichier
        // partait en application/octet-stream avec « nosniff », le navigateur
        // refusait de l'exécuter et l'aperçu des bulletins échouait en
        // production (alors que `vite preview` sert le bon type). Tout script
        // émis porte donc l'extension « .js » ; scripts/verifier_types_assets.mjs
        // contrôle le build contre la vraie table MIME de nginx en CI.
        assetFileNames: (info) => {
          const nom = info.names?.[0] || info.name || "";
          return nom.endsWith(".mjs") ? "assets/[name]-[hash].js" : "assets/[name]-[hash][extname]";
        },
      },
    },
  },
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  server: {
    port: 5173,
    proxy: {
      // BACKEND_ORIGIN permet de lancer le frontend hors Docker
      // (ex: BACKEND_ORIGIN=http://localhost:8000 npm run dev).
      // Défaut : hostname du service backend dans le réseau docker-compose.
      "/api": { target: process.env.BACKEND_ORIGIN || "http://backend-dev:8000", changeOrigin: true },
      "/media": { target: process.env.BACKEND_ORIGIN || "http://backend-dev:8000", changeOrigin: true },
      "/ws": { target: (process.env.BACKEND_ORIGIN || "http://backend-dev:8000").replace(/^http/, "ws"), ws: true },
    },
  },
  // `vite preview` (test local de la compilation de production) : mêmes
  // proxys que le dev server pour atteindre le backend.
  preview: {
    port: 4173,
    proxy: {
      "/api": { target: process.env.BACKEND_ORIGIN || "http://localhost:8000", changeOrigin: true },
      "/media": { target: process.env.BACKEND_ORIGIN || "http://localhost:8000", changeOrigin: true },
    },
  },
});