/** @type {import("tailwindcss").Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        primary: { DEFAULT: "#6366F1", 50: "#EEF2FF", 100: "#E0E7FF", 500: "#6366F1", 600: "#4F46E5", 700: "#4338CA" },
        secondary: { DEFAULT: "#8B5CF6", 500: "#8B5CF6", 600: "#7C3AED" },
        accent: { DEFAULT: "#F59E0B", 500: "#F59E0B" },
        success: { DEFAULT: "#10B981", 50: "#ECFDF5", 500: "#10B981" },
        danger: { DEFAULT: "#EF4444", 50: "#FEF2F2", 500: "#EF4444" },
        sidebar: { DEFAULT: "#0F172A" },
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
    },
  },
  plugins: [],
};