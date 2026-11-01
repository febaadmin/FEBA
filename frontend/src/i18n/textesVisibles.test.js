/**
 * Textes visibles : ni tiret cadratin, y compris seul dans une cellule vide,
 * ni emoji décoratif. Les commentaires ne sont pas analysés.
 */
import { describe, it, expect } from "vitest";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parse } from "@babel/parser";
import traverse from "@babel/traverse";

const RACINE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const EMOJI = /[\u{1F1E6}-\u{1F1FF}\u{1F300}-\u{1FAFF}]/u;
const TIRET = "\u2014";
const CONFORME = (texte) => !texte.includes(TIRET) && !EMOJI.test(texte);

function fichiers(dossier) {
  return fs.readdirSync(dossier, { withFileTypes: true }).flatMap((e) => {
    const chemin = path.join(dossier, e.name);
    if (e.isDirectory()) return fichiers(chemin);
    return /\.jsx?$/.test(e.name) && !/\.test\./.test(e.name) ? [chemin] : [];
  });
}

function textes(chemin) {
  const ast = parse(fs.readFileSync(chemin, "utf8"), { sourceType: "module", plugins: ["jsx"] });
  const trouves = [];
  (traverse.default || traverse)(ast, {
    StringLiteral(p) { trouves.push(p.node.value); },
    JSXText(p) { trouves.push(p.node.value.trim()); },
    TemplateElement(p) { trouves.push(p.node.value.cooked ?? ""); },
  });
  return trouves;
}

describe("textes visibles", () => {
  it("aucun tiret cadratin ni emoji décoratif", () => {
    const ecarts = fichiers(RACINE).flatMap((f) =>
      textes(f).filter((t) => !CONFORME(t)).map((t) => `${path.relative(RACINE, f)} : ${t.slice(0, 70)}`));
    expect(ecarts).toEqual([]);
  }, 60000);

  it("le contrôle repère bien un écart", () => {
    expect(CONFORME(`Paiement ${TIRET} reçu`)).toBe(false);
    expect(CONFORME(TIRET)).toBe(false);
    expect(CONFORME("Paiement - reçu")).toBe(true);
    expect(CONFORME("Bonjour 👋")).toBe(false);
    expect(CONFORME("-")).toBe(true);
    expect(CONFORME("0–20")).toBe(true);
  });
});
