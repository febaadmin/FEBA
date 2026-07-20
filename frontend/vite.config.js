import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
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