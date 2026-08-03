/**
 * Chargement de Playwright, quel que soit l'endroit où il est installé.
 *
 * `playwright-core` n'est pas une dépendance du projet : il est ajouté à la
 * demande, le plus souvent dans `frontend/node_modules`. Le résoudre
 * explicitement évite d'imposer une installation dédiée au dossier e2e —
 * et donne un message clair quand il manque, plutôt qu'une trace
 * MODULE_NOT_FOUND illisible.
 */
import { createRequire } from 'node:module';

const CANDIDATES = [
  'playwright-core',
  new URL('../frontend/node_modules/playwright-core/index.js', import.meta.url).pathname,
  new URL('../node_modules/playwright-core/index.js', import.meta.url).pathname,
];

const require = createRequire(import.meta.url);

let loaded = null;
for (const candidate of CANDIDATES) {
  try {
    loaded = require(candidate);
    break;
  } catch {
    /* candidat suivant */
  }
}

if (!loaded) {
  console.error(
    "playwright-core est introuvable.\n" +
    "Installez-le une fois :\n" +
    "  npm --prefix frontend install --no-save playwright-core",
  );
  process.exit(2);
}

export const { chromium } = loaded;
