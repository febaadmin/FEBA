/** Application privée en anglais : profils enseignant, parent et élève. */
import { chromium } from './playwright.mjs';
const BASE = process.env.E2E_BASE_URL || 'http://127.0.0.1:5173';
const SHOTS = process.env.E2E_SHOTS || new URL('./captures', import.meta.url).pathname;
import fs from 'node:fs';
fs.mkdirSync(SHOTS, { recursive: true });
let FAIL = 0;
const check = (ok, label, detail = '') => {
  if (!ok) FAIL++;
  console.log(`  ${ok ? 'OK ' : 'ÉCHEC'} ${label}${detail ? ' — ' + detail : ''}`);
};
const b = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || '/opt/pw-browsers/chromium' });
const page = await b.newPage({ viewport: { width: 1440, height: 950 } });
const consoleErrors = [];
page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });

const FR_WORDS = /\b(Élèves|Enseignants|Paramètres|Emploi du temps|Tableau de bord|Présences|Devoirs|Bulletins|Paiements|Annonces|Déconnexion|Rechercher|Enregistrer|Ajouter|Modifier|Supprimer|Chargement)\b/;

async function login(email, pwd) {
  await page.goto(BASE + '/login', { waitUntil: 'domcontentloaded' });
  await page.evaluate(() => localStorage.clear());
  await page.goto(BASE + '/login', { waitUntil: 'networkidle' });
  await page.fill('input[type=email], input[name=email]', email);
  await page.fill('input[type=password]', pwd);
  await page.click('button[type=submit]');
  // Une seule nouvelle tentative : sur une machine chargée, la première
  // navigation après le POST de connexion peut dépasser le délai sans que
  // rien ne soit cassé.
  try {
    await page.waitForURL((u) => !u.pathname.includes('/login'), { timeout: 20000 });
  } catch {
    await page.click('button[type=submit]');
    await page.waitForURL((u) => !u.pathname.includes('/login'), { timeout: 30000 });
  }
  await page.waitForLoadState('networkidle');
}

const PROFILS = [
  ['prof.math@feba.bj', 'Teacher@2024', 'teacher',
   ['dashboard', 'grades', 'attendance', 'homework', 'schedule', 'messages', 'profile']],
  ['parent1@feba.bj', 'Parent@2024', 'parent',
   ['dashboard', 'grades', 'attendance', 'payments', 'schedule', 'messages', 'profile']],
  ['eleve1@feba.bj', 'Student@2024', 'student',
   ['dashboard', 'grades', 'attendance', 'homework', 'schedule', 'profile']],
];
console.log('═══ APPLICATION PRIVÉE EN ANGLAIS ═══');
for (const [email, pwd, space, routes] of PROFILS) {
  await login(email, pwd);
  await page.evaluate(() => localStorage.setItem('feba-lang', 'en'));
  await page.reload({ waitUntil: 'networkidle' });
  await page.waitForTimeout(600);
  const leftovers = [];
  let visited = 0;
  for (const route of routes) {
    const r = await page.goto(`${BASE}/${space}/${route}`, { waitUntil: 'networkidle' }).catch(() => null);
    if (!r || page.url().includes('/login')) continue;
    await page.waitForTimeout(600);
    visited++;
    const hit = (await page.locator('body').innerText()).match(FR_WORDS);
    if (hit) leftovers.push(`${route}:${hit[0]}`);
  }
  check(leftovers.length === 0, `profil ${space} en anglais`,
        leftovers.length ? leftovers.join(', ') : `${visited} vues`);
  await page.screenshot({ path: `${SHOTS}/v7-04-${space}-anglais.png` });
}
const real = consoleErrors.filter((e) => !/ERR_CONNECTION_RESET|ERR_ABORTED|favicon|DevTools/.test(e));
check(real.length === 0, 'aucune erreur console applicative', real.slice(0, 3).join(' | '));
console.log(`\n═══ ${FAIL === 0 ? 'TOUS LES PROFILS VÉRIFIÉS' : FAIL + ' ÉCHEC(S)'} ═══`);
await b.close();
process.exit(FAIL ? 1 : 0);
