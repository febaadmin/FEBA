// Matrice fonctionnalités ↔ aide, générée depuis le code :
// menu de chaque profil → route → composant → API utilisées → module activable → articles d'aide.
//   node frontend/scripts/generer_matrice.mjs > docs/livraison/cloture/MATRICE_AIDE_FONCTIONNALITES.md
import { readFileSync, existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { ARTICLES, RACINES } from "../src/aide/articles.js";

const SRC = resolve(dirname(fileURLToPath(import.meta.url)), "../src");
const lire = (p) => readFileSync(join(SRC, p), "utf8");
const routeur = lire("router/index.jsx");
const MENUS = { superadmin: "SuperAdminLayout", admin: "AdminLayout", teacher: "TeacherLayout", parent: "ParentLayout", student: "StudentLayout" };

// Composant importé par nom → fichier.
const imports = {};
for (const m of routeur.matchAll(/const (\w+) = lazy\(\(\) => import\("([^"]+)"\)/g)) imports[m[1]] = m[2];
function composantDe(role, chemin) {
  const debut = routeur.indexOf(`<Route path="${RACINES[role]}"`);
  const bloc = routeur.slice(debut, routeur.indexOf('<Route path="/', debut + 10) === -1 ? undefined : routeur.indexOf('<Route path="/', debut + 10));
  const m = bloc.match(new RegExp(`<Route path="${chemin.replace(/[/]/g, "\\/")}"[^>]*element=\\{(?:<FeatureGate[^>]*>)?<(\\w+)`));
  return m ? m[1] : null;
}
function apisDe(composant) {
  const fichier = imports[composant];
  if (!fichier) return [];
  const chemin = [".jsx", ".js", "/index.jsx"].map((e) => join(SRC, "router", fichier + e)).find(existsSync);
  if (!chemin) return [];
  const s = readFileSync(chemin, "utf8");
  return [...new Set([...s.matchAll(/\b(\w+API)\.(\w+)/g)].map((m) => `${m[1]}.${m[2]}`))].sort();
}
const lignes = ["# Matrice des fonctionnalités et de l'aide", "",
  "Générée par `node frontend/scripts/generer_matrice.mjs` à partir des menus, du routeur, des écrans et de `src/aide/articles.js`.",
  "Le test `src/aide/aide.test.js` échoue si un écran de menu n'a pas d'article.", ""];
let manquants = 0;
for (const [role, fichier] of Object.entries(MENUS)) {
  const src = lire(`layouts/${fichier}.jsx`);
  lignes.push(`## ${role}`, "", "| Menu | Route | Écran | Module activable | API utilisées par l'écran | Articles d'aide |", "|---|---|---|---|---|---|");
  for (const m of src.matchAll(/\{ label: "([^"]+)",[^}]*to: "([^"]+)"([^}]*)\}/g)) {
    const [, label, to, reste] = m;
    const chemin = to.replace(RACINES[role] + "/", "");
    const feature = (reste.match(/feature: "(\w+)"/) || [])[1] || "";
    const comp = composantDe(role, chemin);
    const arts = ARTICLES.filter((a) => (a.roles.includes(role) || role === "superadmin") && (a.liens?.[role] === chemin || (a.ecrans?.[role] || []).includes(chemin))).map((a) => a.id);
    if (!arts.length && chemin !== "aide") manquants += 1;
    lignes.push(`| ${label} | \`${to}\` | ${comp || "?"} | ${feature} | ${apisDe(comp).slice(0, 6).join(", ")} | ${arts.join(", ") || (chemin === "aide" ? "(cette page)" : "**MANQUANT**")} |`);
  }
  lignes.push("");
}
lignes.push(`Écrans sans article : ${manquants}.`);
console.log(lignes.join("\n"));
