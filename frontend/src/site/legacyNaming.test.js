/**
 * Test de non-régression du renommage « FEBA Online » → FEBA FHA.
 *
 * L'ancien nom du programme ne doit plus apparaître dans AUCUN texte
 * visible par un utilisateur : libellés de menu, titres, contenus
 * éditoriaux, métadonnées SEO, textes alternatifs d'images, options de
 * formulaire.
 *
 * Les COMMENTAIRES de code sont tolérés (ils documentent précisément le
 * renommage et sa redirection), de même que la clé technique
 * `feba_online` conservée en base pour ne pas invalider les demandes de
 * préinscription déjà enregistrées.
 */
import { describe, it, expect } from "vitest";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SRC = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

/** Fichiers source à inspecter (hors tests et dépendances). */
function collectSourceFiles(dir, acc = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === "node_modules") continue;
      collectSourceFiles(full, acc);
      continue;
    }
    if (!/\.(jsx?|tsx?)$/.test(entry.name)) continue;
    if (/\.test\.(jsx?|tsx?)$/.test(entry.name)) continue;
    acc.push(full);
  }
  return acc;
}

/**
 * Retire les commentaires (// et bloc) pour ne conserver que le code et
 * les chaînes réellement rendues.
 */
function stripComments(source) {
  return source
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/^\s*\/\/.*$/gm, "");
}

describe("Renommage FEBA Online → FEBA French Heritage Academy", () => {
  const files = collectSourceFiles(SRC);

  it("inspecte réellement des fichiers source", () => {
    expect(files.length).toBeGreaterThan(20);
  });

  it("n'affiche plus « FEBA Online » dans aucun texte visible", () => {
    const offenders = [];
    for (const file of files) {
      const code = stripComments(fs.readFileSync(file, "utf8"));
      if (/FEBA\s+Online/i.test(code)) {
        offenders.push(path.relative(SRC, file));
      }
    }
    expect(offenders).toEqual([]);
  });

  it("ne référence plus l'ancienne route /feba-online, sauf pour la rediriger", () => {
    const offenders = [];
    for (const file of files) {
      const code = stripComments(fs.readFileSync(file, "utf8"));
      if (!code.includes("/feba-online")) continue;
      // Seul le routeur peut encore mentionner l'ancienne route, et
      // uniquement pour la rediriger vers la nouvelle.
      const isRouter = file.endsWith(path.join("router", "index.jsx"));
      const redirects = /path="\/feba-online[^"]*"\s+element=\{<Navigate to="\/feba-fha"/.test(code);
      if (!isRouter || !redirects) {
        offenders.push(path.relative(SRC, file));
      }
    }
    expect(offenders).toEqual([]);
  });

  it("expose la nouvelle route /feba-fha et ses formulaires dédiés", () => {
    const router = fs.readFileSync(path.join(SRC, "router", "index.jsx"), "utf8");
    expect(router).toContain('path="/feba-fha"');
    expect(router).toContain('path="/feba-fha/enroll"');
    expect(router).toContain('path="/feba-fha/contact"');
  });

  it("affiche l'abréviation « FEBA FHA » dans le menu principal", () => {
    const layout = fs.readFileSync(path.join(SRC, "site", "SiteLayout.jsx"), "utf8");
    // Le menu est désormais TRADUIT (P1) : le libellé vient de la table
    // NAV plutôt que d'une chaîne codée en dur. On vérifie donc la route
    // et la valeur de la table, qui reste « FEBA FHA » dans les deux
    // langues (le nom complet est trop long pour la barre).
    expect(layout).toMatch(/to:\s*"\/feba-fha",\s*label:\s*L\(NAV\.fha\)/);
    const table = fs.readFileSync(path.join(SRC, "site", "siteTranslations.js"), "utf8");
    expect(table).toMatch(/fha:\s*\{\s*fr:\s*"FEBA FHA",\s*en:\s*"FEBA FHA"\s*\}/);
  });
});
