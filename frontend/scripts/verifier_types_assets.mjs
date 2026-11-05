/**
 * Vérifie que chaque fichier du build sera servi avec le bon type MIME par
 * le nginx de production.
 *
 * Pourquoi : nginx envoie « X-Content-Type-Options: nosniff ». Un script
 * servi en application/octet-stream (extension inconnue de mime.types) est
 * alors refusé par le navigateur. C'est ce qui cassait l'aperçu PDF des
 * bulletins (worker pdf.js en « .mjs »), invisible avec `vite preview`.
 *
 * Usage : node scripts/verifier_types_assets.mjs <mime.types> [dist]
 * La CI extrait mime.types de l'image nginx utilisée en production.
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";

const [fichierMime, dist = "dist"] = process.argv.slice(2);
if (!fichierMime) {
  console.error("usage : verifier_types_assets.mjs <mime.types> [dist]");
  process.exit(2);
}

// Types MIME acceptés par extension (attendus par le navigateur).
const ATTENDU = {
  js: /^(application|text)\/javascript$/,
  css: /^text\/css$/,
  html: /^text\/html$/,
};

const table = new Map();
const texte = readFileSync(fichierMime, "utf8").replace(/#.*$/gm, "");
for (const [, type, exts] of texte.matchAll(/([\w.+-]+\/[\w.+-]+)\s+([^;{}]+);/g)) {
  for (const e of exts.trim().split(/\s+/)) table.set(e.toLowerCase(), type);
}

const fichiers = [];
const parcourir = (dossier) => {
  for (const n of readdirSync(dossier)) {
    const p = path.join(dossier, n);
    if (statSync(p).isDirectory()) parcourir(p); else fichiers.push(p);
  }
};
parcourir(dist);

const erreurs = [];
for (const f of fichiers) {
  const ext = path.extname(f).slice(1).toLowerCase();
  const type = table.get(ext);
  if (!type) erreurs.push(`${f} : extension « .${ext} » absente de mime.types (servi en application/octet-stream)`);
  else if (ATTENDU[ext] && !ATTENDU[ext].test(type)) erreurs.push(`${f} : servi en ${type}`);
}
if (erreurs.length) {
  console.error(erreurs.join("\n"));
  process.exit(1);
}
console.log(`${fichiers.length} fichier(s) du build : types MIME nginx corrects.`);
