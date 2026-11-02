/** @type {import("tailwindcss").Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        primary: { DEFAULT: "#1D4ED8", 50: "#EFF6FF", 100: "#DBEAFE", 200: "#BFDBFE", 500: "#2563EB", 600: "#1D4ED8", 700: "#1E40AF", 800: "#1E3A8A" },
        secondary: { DEFAULT: "#8B5CF6", 500: "#8B5CF6", 600: "#7C3AED" },
        accent: { DEFAULT: "#F59E0B", 500: "#F59E0B" },
        success: { DEFAULT: "#10B981", 50: "#ECFDF5", 500: "#10B981" },
        danger: { DEFAULT: "#EF4444", 50: "#FEF2F2", 500: "#EF4444" },
        sidebar: { DEFAULT: "#071D49", 2: "#0E2A63" },
        // Charte du site vitrine FEBA (palette officielle — voir
        // Medias/FEBA-SITE-MEDIAS/00-CHARTE/palette-couleurs.txt)
        feba: {
          navy: "#071D49",
          navy2: "#0E2A63",
          gold: "#D89B16",
          gold2: "#B8830F",
          cream: "#F7F2E8",
          sky: "#4AA3DF",
          green: "#1F6B36",
          green2: "#17532A",
          red: "#B42020",
          gray: "#3C4450",
        },
      },
      fontFamily: { sans: ["Inter", "sans-serif"] },
      boxShadow: {
        carte: "0 1px 2px rgba(7,29,73,.04), 0 8px 24px -14px rgba(7,29,73,.14)",
        douce: "inset 0 1px 2px rgba(7,29,73,.05)",
        relief: "0 4px 6px -1px rgba(7,29,73,.08), 0 10px 20px -6px rgba(7,29,73,.10)",
        fenetre: "0 24px 48px -12px rgba(7,29,73,.28)",
      },
      keyframes: {
        // Jamais d'opacité de départ nulle : la page ne s'efface pas, elle glisse. Pas de variation brusque de luminosité.
        apparition: { from: { opacity: 0.55, transform: "translateY(4px)" }, to: { opacity: 1, transform: "none" } },
        attente: { "0%, 100%": { opacity: 1 }, "50%": { opacity: 0.72 } },
      },
      animation: { apparition: "apparition .18s ease-out backwards", attente: "attente 1.8s ease-in-out infinite" },
    },
  },
  plugins: [],
};