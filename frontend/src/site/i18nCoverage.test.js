/**
 * Couverture i18n du SITE PUBLIC (P1).
 *
 * Le sélecteur EN/FR était visible partout, mais seule la page FEBA FHA
 * changeait réellement de langue : le carrousel, « Bienvenue à FEBA »,
 * « Découvrir l'école » et toutes les sections de la page d'accueil
 * restaient en français. Une traduction partielle est plus déroutante
 * qu'une absence de traduction : dans la même page, l'utilisateur voit
 * un menu anglais au-dessus d'un contenu français.
 *
 * Ce test ne se contente plus de tenir une liste de pages « à faire » :
 * il VÉRIFIE, page par page, qu'aucun texte français visible ne subsiste
 * hors du mécanisme de traduction. C'est ce qui empêche une nouvelle page
 * d'arriver en français uniquement.
 */
import { describe, it, expect } from "vitest";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SITE = path.dirname(fileURLToPath(import.meta.url));
const PAGES = path.join(SITE, "pages");

/** Toutes les pages du site public, sans exception. */
const ALL_PAGES = fs.readdirSync(PAGES).filter((f) => f.endsWith(".jsx"));

/**
 * Mots français fréquents et sans ambiguïté. Ils servent à repérer un
 * texte codé en dur ; on les cherche uniquement là où un texte serait
 * VISIBLE (nœud JSX ou valeur de prop textuelle), jamais dans les
 * commentaires ni dans les noms de fichiers.
 */
const FRENCH_MARKERS =
  /\b(le|la|les|des|une|nos|notre|votre|vous|pour|avec|dans|sur|est|sont|chaque|toutes|tous)\b/i;

/** Props dont la valeur est affichée ou lue par une aide technique. */
const TEXT_PROPS = ["title", "intro", "description", "label", "alt", "placeholder", "aria-label"];

function stripComments(code) {
  return code
    .replace(/\/\*[\s\S]*?\*\//g, " ")   // blocs /* … */ et {/* … */}
    .replace(/^\s*\/\/.*$/gm, " ");      // lignes //
}

/**
 * Textes français codés en dur d'un fichier.
 *
 * On accepte tout ce qui passe par `t("fr", "en")`, `tr(entry, lang)` ou
 * une expression `{…}` : ces formes sont, par construction, bilingues.
 */
function hardcodedFrench(code) {
  const src = stripComments(code);
  const found = [];

  // 1. Texte brut entre balises : <h1>Bienvenue à FEBA</h1>
  for (const match of src.matchAll(/>([^<>{}\n][^<>{}]{6,})</g)) {
    const text = match[1].trim();
    if (!text || !FRENCH_MARKERS.test(text)) continue;
    found.push(text.slice(0, 60));
  }

  // 2. Props textuelles à valeur littérale : title="Notre campus"
  const propNames = TEXT_PROPS.join("|");
  const propRe = new RegExp(`\\b(${propNames})=\\{?"([^"]{6,})"`, "g");
  for (const match of src.matchAll(propRe)) {
    const value = match[2].trim();
    if (!FRENCH_MARKERS.test(value)) continue;
    found.push(`${match[1]}="${value.slice(0, 50)}"`);
  }

  return found;
}

describe("Couverture i18n du site public", () => {
  it("le layout — donc toutes les pages — est traduit", () => {
    const layout = fs.readFileSync(path.join(SITE, "SiteLayout.jsx"), "utf8");
    expect(layout).toContain("useSiteLang");
    expect(layout).toMatch(/buildNavLinks\(lang\)/);
    // Plus aucun libellé de menu codé en dur.
    expect(layout).not.toMatch(/label:\s*"Accueil"/);
    expect(layout).not.toMatch(/label:\s*"Vie scolaire"/);
  });

  it("le sélecteur de langue est unique et partagé", () => {
    const switcher = fs.readFileSync(
      path.join(SITE, "components", "SiteLangSwitcher.jsx"), "utf8",
    );
    expect(switcher).toContain("useSiteLang");
    // Aucune page ne doit redéfinir son propre état de langue : c'est ce
    // qui faisait que le choix ne survivait pas à la navigation.
    for (const file of ALL_PAGES) {
      const code = fs.readFileSync(path.join(PAGES, file), "utf8");
      expect(code, `${file} ne doit pas gérer sa propre langue`)
        .not.toMatch(/localStorage\.(get|set)Item\(\s*["']feba-fha-lang/);
    }
  });

  it("chaque page du site public consomme la langue active", () => {
    const notWired = ALL_PAGES.filter((file) => {
      const code = fs.readFileSync(path.join(PAGES, file), "utf8");
      return !code.includes("useSiteLang");
    });
    expect(notWired, "page(s) ignorant le sélecteur de langue").toEqual([]);
  });

  it("aucune page ne contient de texte français codé en dur", () => {
    const offenders = [];
    for (const file of ALL_PAGES) {
      const code = fs.readFileSync(path.join(PAGES, file), "utf8");
      for (const text of hardcodedFrench(code)) {
        offenders.push(`${file} : ${text}`);
      }
    }
    expect(offenders, `${offenders.length} texte(s) non traduisible(s)`).toEqual([]);
  });

  it("les formulaires publics sont eux aussi bilingues", () => {
    // Les messages de validation sont ce que l'utilisateur lit au pire
    // moment : les laisser en français annulerait tout le reste.
    const forms = fs.readFileSync(path.join(SITE, "components", "PublicForms.jsx"), "utf8");
    expect(forms).toContain("useSiteLang");
    expect(forms).not.toMatch(/required:\s*"[^"]*obligatoire/);
  });

  it("le contenu structurel est fourni dans les deux langues", () => {
    const content = fs.readFileSync(path.join(SITE, "content.js"), "utf8");
    for (const key of ["LEVELS", "WHY_FEBA", "VALUES", "ACTIVITIES", "ONLINE_FEATURES"]) {
      expect(content).toContain(`export const ${key}`);
    }
    // Chaque libellé structurel est un couple { fr, en }.
    const frEntries = content.match(/\bfr:\s*"/g) || [];
    const enEntries = content.match(/\ben:\s*"/g) || [];
    expect(frEntries.length).toBeGreaterThan(40);
    expect(enEntries.length).toBe(frEntries.length);
  });

  it("les traductions du site couvrent navigation, interface et accueil", () => {
    const table = fs.readFileSync(path.join(SITE, "siteTranslations.js"), "utf8");
    for (const key of ["NAV", "UI", "HOME", "CONTENT_EN"]) {
      expect(table).toContain(`export const ${key}`);
    }
    const pairs = table.match(/\{\s*fr:/g) || [];
    expect(pairs.length).toBeGreaterThan(30);
  });
});
