/**
 * GARDE-FOU STATIQUE — cause racine de la page blanche /parent/home.
 *
 * Le crash « Uncaught TypeError: t2 is not a function » venait d'un
 * destructuring `.map(([t, v]) => …)` qui masquait la fonction de
 * traduction `t` importée : l'appel `t("Moy.")` tombait alors sur la
 * chaîne "T1" (élément du tableau), pas sur la fonction.
 *
 * Ce test échoue si un fichier qui importe { t } depuis src/i18n déclare
 * une liaison locale nommée `t` (paramètre de callback, destructuring,
 * const/let/var, catch, boucle for). Il empêche définitivement la
 * réintroduction de ce type de régression.
 */
import { describe, it, expect } from "vitest";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SRC = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

const BINDING_PATTERNS = [
  [/\.(?:map|filter|forEach|find|findIndex|reduce|some|every|flatMap|sort)\(\s*\(?\s*t\s*[,)]/, "paramètre de callback nommé t"],
  [/\.(?:map|filter|forEach|find|findIndex|reduce|some|every|flatMap|sort)\(\s*\(\s*\[\s*t\s*[,\]]/, "destructuring de tableau [t, …]"],
  [/\.(?:map|filter|forEach|find|findIndex|reduce|some|every|flatMap|sort)\(\s*\(\s*\{\s*t\s*[,}]/, "destructuring d'objet {t, …}"],
  [/\(\s*\[\s*t\s*[,\]][^)]*\)\s*=>/, "arrow destructuring ([t, …]) =>"],
  [/\(\s*t\s*\)\s*=>/, "arrow (t) =>"],
  [/\(\s*t\s*,[^)]*\)\s*=>/, "arrow (t, …) =>"],
  [/,\s*t\s*\)\s*=>/, "arrow (…, t) =>"],
  [/\b(?:const|let|var)\s+t\s*=/, "déclaration const/let/var t ="],
  [/\b(?:const|let|var)\s+\[\s*t\s*[,\]]/, "déclaration const [t, …]"],
  [/\b(?:const|let|var)\s+\{\s*t\s*[,}:]/, "déclaration const {t, …}"],
  [/\bfunction\s+t\s*\(/, "function t("],
  [/\bfunction\s*\(\s*t\s*[,)]/, "function(t, …)"],
  [/\bcatch\s*\(\s*t\s*\)/, "catch (t)"],
  [/\bfor\s*\(\s*(?:const|let|var)\s+t\b/, "for (const t …)"],
];

function* walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) yield* walk(full);
    else if (/\.(jsx?|tsx?)$/.test(entry.name) && !/\.test\./.test(entry.name)) yield full;
  }
}

describe("aucun fichier important { t } ne doit masquer t par une liaison locale", () => {
  const offenders = [];
  for (const file of walk(SRC)) {
    const src = fs.readFileSync(file, "utf8");
    if (!/import\s*\{[^}]*\bt\b[^}]*\}\s*from\s*["'][^"']*i18n["']/.test(src)) continue;
    for (const [pattern, label] of BINDING_PATTERNS) {
      const m = src.match(pattern);
      if (m) {
        const line = src.slice(0, m.index).split("\n").length;
        offenders.push(`${path.relative(SRC, file)}:${line} — ${label}`);
      }
    }
  }

  it("aucun shadowing détecté", () => {
    expect(offenders, `Shadowing de la fonction t détecté :\n${offenders.join("\n")}`).toEqual([]);
  });
});
