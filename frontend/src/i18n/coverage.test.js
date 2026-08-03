/**
 * Couverture de traduction de l'APPLICATION PRIVÉE.
 *
 * PROBLÈME RÉSOLU (P1)
 * --------------------
 * Le sélecteur EN/FR était actif partout, mais une partie des écrans
 * restait en français quand l'anglais était choisi. Le résultat n'était
 * ni français ni anglais : dans le même tableau, « Groupe » côtoyait
 * « Subject ». Une traduction incomplète est plus déroutante qu'une
 * absence de traduction.
 *
 * Ce test parcourt le code source, extrait chaque chaîne passée à `t()`
 * et vérifie qu'elle possède une entrée anglaise. Il échoue donc dès
 * qu'un nouvel écran introduit un libellé non traduit — c'est la seule
 * façon d'empêcher le problème de réapparaître écran par écran.
 *
 * Les chaînes dynamiques (`t(variable)`) ne sont pas détectables et ne
 * sont pas comptées : le test porte sur les littéraux, qui représentent
 * la quasi-totalité des libellés.
 */
import { describe, expect, it } from "vitest";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { EN } from "./translations";

const SRC = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

/** Le site vitrine a son propre mécanisme ({fr, en}), hors périmètre ici. */
const EXCLUDED = [path.join(SRC, "site")];

function sourceFiles(dir, acc = []) {
  for (const entry of fs.readdirSync(dir)) {
    const full = path.join(dir, entry);
    if (EXCLUDED.some((skip) => full.startsWith(skip))) continue;
    const stat = fs.statSync(full);
    if (stat.isDirectory()) sourceFiles(full, acc);
    else if (/\.jsx?$/.test(entry) && !/\.test\./.test(entry)) acc.push(full);
  }
  return acc;
}

/** Littéraux passés à `t("…")` — guillemets simples ou doubles. */
const CALL = /\bt\(\s*("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/g;

function extractLabels() {
  const found = new Map(); // libellé -> fichier où il apparaît d'abord
  for (const file of sourceFiles(SRC)) {
    const code = fs.readFileSync(file, "utf8");
    let match;
    while ((match = CALL.exec(code)) !== null) {
      const raw = match[1];
      const label = raw
        .slice(1, -1)
        .replace(/\\'/g, "'")
        .replace(/\\"/g, '"')
        .replace(/\\n/g, "\n");
      if (!found.has(label)) found.set(label, path.relative(SRC, file));
    }
  }
  return found;
}

describe("couverture de traduction FR → EN", () => {
  const labels = extractLabels();

  it("trouve bien les libellés dans le code source", () => {
    // Garde-fou : si l'extraction cassait, le test suivant passerait pour
    // de mauvaises raisons — un dictionnaire complet pour zéro libellé.
    expect(labels.size).toBeGreaterThan(500);
  });

  it("traduit chaque libellé de l'application privée", () => {
    const untranslated = [...labels.entries()]
      .filter(([label]) => !(label in EN))
      .map(([label, file]) => `${file} : ${JSON.stringify(label)}`);

    expect(untranslated, `${untranslated.length} libellé(s) sans traduction anglaise`)
      .toEqual([]);
  });

  it("ne laisse aucune traduction identique au français par inadvertance", () => {
    /* Certaines égalités sont légitimes — noms propres, sigles, unités.
       On les liste explicitement pour que toute NOUVELLE égalité soit
       signalée : une valeur recopiée du français est le symptôme d'une
       entrée ajoutée sans être traduite. */
    const legitimate = new Set([
      // Noms propres, marques et sigles
      "WhatsApp", "SEO", "Instagram", "Facebook", "Mobile Money", "PDF",
      "FEBA", "FEBA Academy", "Branding & Logo", "Logo & Branding", "Internet",
      "SUPER ADMIN", "Super Admin", "Admin", "Administration", "Endpoint",
      // Périodes scolaires et codes de langue
      "T1", "T2", "T3", "FR + EN", "FR+EN",
      // Mots identiques en français et en anglais
      "Contact", "Question", "Sport", "Excellence", "Discipline", "Message",
      "Messages", "Notification", "Notifications", "Options", "Description",
      "Date", "Format", "Version", "Actions", "Documents", "Configuration",
      "Solution", "Type", "Support", "Types", "Import", "Total", "Transport",
      "Incident", "Extra", "Contacts", "Introduction", "Sections", "Signature",
      "Photo", "Photos", "Documentation", "Communication", "Communications",
      "Simple", "Double", "Standard", "Public", "Application", "Applications",
      "Test", "Tests", "Portable", "Important", "Long", "Position",
      "Orientation", "Direction", "Distance", "Certification", "Certifications",
      "Composition", "Suggestions", "Section", "Original", "Signal",
      "Instruction", "Instructions", "Email", "Parent", "Parents", "Classes",
      "Absence", "Absences", "Active", "Inactive", "Absent", "Justification",
      "Action", "Bio", "Code", "Mode", "Permanent", "Page", "Occur.",
      // Libellés de formulaire : seule l'astérisque distingue ces variantes
      "Code *", "Date *", "Date*", "Description*", "Email *", "Email*",
      "Message *", "Mode *", "Type *",
      // Formes plurielles portées par l'interpolation
      "occurrence(s)", "{n} parent(s)",
      // Appréciations : valeurs métier normalisées, non traduites
      "EXCELLENT", "ACCEPTABLE",
      // Chaînes déjà en anglais dans les deux langues
      "Images, PDF, Word, Excel, CSV, ZIP — max 5 MB",
    ]);
    const suspicious = Object.entries(EN)
      .filter(([fr, en]) => fr === en && !legitimate.has(fr))
      .map(([fr]) => fr);

    expect(suspicious, "traductions identiques au français").toEqual([]);
  });
});
