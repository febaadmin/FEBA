import { chromium } from './playwright.mjs';
const BASE = process.env.E2E_BASE_URL || 'http://127.0.0.1:5173';
const SHOTS = process.env.E2E_SHOTS || new URL('./captures', import.meta.url).pathname;
import fs from 'node:fs';
fs.mkdirSync(SHOTS, { recursive: true });

const PAGES = [
  ['/', 'Accueil'], ['/a-propos', 'À propos'], ['/academique', 'Académique'],
  ['/admissions', 'Admissions'], ['/vie-scolaire', 'Vie scolaire'], ['/campus', 'Campus'],
  ['/galerie', 'Galerie'], ['/actualites', 'Actualités'], ['/contact', 'Contact'],
  ['/mentions-legales', 'Mentions légales'], ['/confidentialite', 'Confidentialité'],
  ['/feba-fha', 'FEBA FHA'], ['/page-inexistante', '404'],
];

// Mots français sans ambiguïté : leur présence en mode EN prouve qu'un
// texte n'a pas été traduit.
const FR = /\b(les|des|une|nos|notre|votre|vous|pour|avec|dans|chaque|toutes|élèves|école|enfants|scolaire|inscription|découvrir|bienvenue)\b/i;

const b = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || '/opt/pw-browsers/chromium' });
const page = await b.newPage({ viewport: { width: 1400, height: 950 } });

// Passe le site en anglais EN CLIQUANT sur le sélecteur, comme le ferait
// un visiteur — c'est le parcours réel, pas un raccourci par localStorage.
await page.goto(BASE + '/', { waitUntil: 'networkidle' });
await page.click('[role=group] button[aria-label="English"]');
await page.waitForTimeout(500);
console.log('langue après clic EN :', await page.evaluate(() => document.documentElement.lang));

let failures = 0;
for (const [url, label] of PAGES) {
  await page.goto(BASE + url, { waitUntil: 'networkidle' });
  await page.waitForTimeout(700);
  const lang = await page.evaluate(() => document.documentElement.lang);
  // On ignore le pied de page « Français » du sélecteur lui-même.
  const text = await page.evaluate(() => {
    const clone = document.body.cloneNode(true);
    clone.querySelectorAll('[data-lang-switcher], footer').forEach(n => n.remove());
    return clone.innerText;
  });
  const words = [...new Set((text.match(FR) ? text.split(/\s+/).filter(w => FR.test(w)) : []))].slice(0, 8);
  const ok = words.length === 0;
  if (!ok) failures++;
  console.log(`${ok ? 'OK ' : 'FR!'} ${label.padEnd(18)} lang=${lang} ${ok ? '' : '→ ' + JSON.stringify(words)}`);
}

// Bascule EN → FR en direct, sans rechargement : le contenu doit changer.
await page.goto(BASE + '/', { waitUntil: 'networkidle' });
// Le titre du carrousel : contenu ADMINISTRÉ, donc la preuve que la
// bascule atteint aussi la base et pas seulement les libellés du code.
// (Un `h2` comme « Faith & Excellence Bilingual Academy » est un nom
// propre, identique dans les deux langues : il ne prouve rien.)
const before = await page.locator('h1').first().innerText();
await page.click('[role=group] button[aria-label="Français"]');
await page.waitForTimeout(900);
const after = await page.locator('h1').first().innerText();
const switched = before !== after;
if (!switched) failures++;
console.log(`\nBascule EN → FR sans rechargement : "${before}" → "${after}" · ${switched ? 'CONTENU CHANGÉ' : 'INCHANGÉ (ÉCHEC)'}`);
await page.screenshot({ path: `${SHOTS}/shot-site-fr.png`, fullPage: false });

await page.click('[role=group] button[aria-label="English"]');
await page.waitForTimeout(600);
await page.screenshot({ path: `${SHOTS}/shot-site-en.png`, fullPage: false });

console.log(`\nPages avec du français résiduel : ${failures} / ${PAGES.length}`);
await b.close();
process.exit(failures ? 1 : 0);
