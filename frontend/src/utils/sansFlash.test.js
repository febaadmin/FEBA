import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const racine = resolve(__dirname, "../..");

describe("navigation sans flash", () => {
  it("garde une version de framer-motion qui fige l'opacité finale avant d'annuler l'animation", () => {
    // Avec la version 11, le voile du menu mobile disparaissait une image à la fin de son animation.
    const { version } = JSON.parse(readFileSync(resolve(racine, "node_modules/framer-motion/package.json"), "utf8"));
    expect(Number(version.split(".")[0])).toBeGreaterThanOrEqual(12);
  });

  it("n'efface pas la page en y entrant et ne fait pas clignoter l'attente", () => {
    const texte = readFileSync(resolve(racine, "tailwind.config.js"), "utf8");
    const depart = Number(/apparition: \{ from: \{ opacity: ([\d.]+)/.exec(texte)[1]);
    expect(depart).toBeGreaterThanOrEqual(0.5);
    const creux = Number(/"50%": \{ opacity: ([\d.]+)/.exec(texte)[1]);
    expect(creux).toBeGreaterThanOrEqual(0.6);
  });
});
