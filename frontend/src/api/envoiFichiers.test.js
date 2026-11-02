import { describe, it, expect } from "vitest";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

// Reproduit le défaut de production : un FormData envoyé avec l'en-tête JSON par défaut.
const source = fs.readFileSync(path.join(path.dirname(fileURLToPath(import.meta.url)), "index.js"), "utf8");

describe("envois de fichiers des modules pédagogiques", () => {
  it.each([
    "/suivi/competences/importer/", "/evaluations/questions/importer/",
    "/evaluations/questions/${id}/`, d", "/evaluations/passage/${id}/repondre/",
  ])("%s précise le format", (route) => {
    const ligne = source.split("\n").find((l) => l.includes(route) && /api\.(post|patch)/.test(l));
    expect(ligne).toContain("envoi(d)");
  });
});
