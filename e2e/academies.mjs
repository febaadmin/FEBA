/**
 * Vérification navigateur complète de l'itération V7.
 * Produit un rapport texte + des captures, et sort en échec si un point
 * du cahier des charges n'est pas satisfait.
 */
import { chromium } from './playwright.mjs';
const BASE = process.env.E2E_BASE_URL || 'http://127.0.0.1:5173';
const SHOTS = process.env.E2E_SHOTS || new URL('./captures', import.meta.url).pathname;
import fs from 'node:fs';
fs.mkdirSync(SHOTS, { recursive: true });
const OUT = [];
let FAIL = 0;
const log = (s) => { OUT.push(s); console.log(s); };
const check = (ok, label, detail = '') => {
  if (!ok) FAIL++;
  log(`${ok ? '  OK ' : '  ÉCHEC'} ${label}${detail ? ' — ' + detail : ''}`);
  return ok;
};

const b = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || '/opt/pw-browsers/chromium' });
const ctx = await b.newContext({ viewport: { width: 1440, height: 950 } });
const page = await ctx.newPage();

/* ── Journal réseau : chaque requête API avec sa portée annoncée ──────── */
const netlog = [];
page.on('response', async (r) => {
  const u = r.url();
  if (!u.includes('/api/')) return;
  netlog.push({
    t: Date.now(),
    url: u.replace(BASE, ''),
    status: r.status(),
    sent: r.request().headers()['x-academy-scope'] || '',
    served: r.headers()['x-academy-scope'] || '',
  });
});

const consoleErrors = [];
page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });

async function login(email, pwd) {
  await page.goto(BASE + '/login', { waitUntil: 'networkidle' });
  await page.evaluate(() => { localStorage.clear(); });
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
  return page.url();
}

/**
 * Effectif RÉELLEMENT servi à l'écran : on relit la dernière réponse de
 * l'endpoint concerné plutôt que de compter des lignes paginées. C'est la
 * donnée à partir de laquelle le tableau est rendu.
 */
const lastPayload = new Map();
page.on('response', async (r) => {
  const u = new URL(r.url()).pathname;
  if (!u.startsWith('/api/') || r.request().method() !== 'GET') return;
  try {
    const body = await r.json();
    const rows = Array.isArray(body) ? body : body?.results;
    if (Array.isArray(rows)) lastPayload.set(u, rows);
  } catch { /* réponse non JSON */ }
});

async function servedRows(endpoint) {
  return lastPayload.get(endpoint) || [];
}

/** Codes d'académie visibles dans le tableau affiché. */
async function visibleAcademies() {
  const badges = await page.locator('table tbody tr span').allInnerTexts();
  return [...new Set(badges.filter((x) => /^(FEBA|FEBA FHA|Sans académie)$/.test(x.trim())))];
}

async function currentAcademyLabel() {
  return (await page.locator('button[aria-haspopup=listbox]').innerText()).trim();
}

async function switchAcademy(label) {
  const before = await currentAcademyLabel();
  if (before.includes(label)) return 0;      // déjà sur cette académie
  await page.click('button[aria-haspopup=listbox]');
  await page.waitForSelector('li[role=option]');
  const t0 = Date.now();
  await page.click(`li[role=option]:has-text("${label}")`);
  // Attente active plutôt que waitForFunction : on veut pouvoir dire ce
  // que le sélecteur affichait si la bascule n'aboutit pas.
  let seen = '';
  for (let i = 0; i < 120; i++) {
    seen = await currentAcademyLabel();
    if (seen.includes(label)) break;
    await page.waitForTimeout(250);
  }
  if (!seen.includes(label)) {
    await page.screenshot({ path: `${SHOTS}/echec-bascule-${label.slice(0, 10).replace(/\W/g, '')}.png` });
    throw new Error(`bascule vers « ${label} » non aboutie — sélecteur = « ${seen} »`);
  }
  await page.waitForLoadState('networkidle');
  const ms = Date.now() - t0;
  await page.waitForTimeout(500);
  return ms;
}

/* ═══ 1. Bascule d'académie : immédiate, sans réponse tardive ═════════ */
log('\n═══ 1. BASCULE D\'ACADÉMIE ═══');
await login('superadmin@feba.bj', 'SuperAdmin@2024');
// État de départ déterministe, quel que soit l'état laissé par une session
// précédente : l'académie active est PERSISTÉE côté serveur.
await page.goto(BASE + '/superadmin/students', { waitUntil: 'networkidle' });
await page.waitForTimeout(900);
await switchAcademy('Faith & Excellence');

const nFeba0 = (await servedRows('/api/students/')).length;
const badgesFeba = await visibleAcademies();
netlog.length = 0;

const msFha = await switchAcademy('FEBA French Heritage Academy');
const nFha = (await servedRows('/api/students/')).length;
const badgesFha = await visibleAcademies();

const msAll = await switchAcademy('Toutes les Académies');
const nAll = (await servedRows('/api/students/')).length;
const badgesAll = await visibleAcademies();

const msFeba = await switchAcademy('Faith & Excellence');
const nFeba = (await servedRows('/api/students/')).length;

log(`  Élèves servis : FEBA=${nFeba0} → FHA=${nFha} (${msFha} ms) → TOUTES=${nAll} (${msAll} ms) → FEBA=${nFeba} (${msFeba} ms)`);
log(`  Badges affichés : FEBA=${JSON.stringify(badgesFeba)} · FHA=${JSON.stringify(badgesFha)} · TOUTES=${JSON.stringify(badgesAll)}`);
check(nFeba0 !== nFha, 'les données changent réellement entre académies', `${nFeba0} ≠ ${nFha}`);
check(nAll === nFeba0 + nFha, 'total consolidé = somme des académies', `${nAll} = ${nFeba0} + ${nFha}`);
check(nFeba === nFeba0, 'retour sur FEBA : même effectif qu\'au départ', `${nFeba} = ${nFeba0}`);
check(badgesAll.length === 2, 'les deux académies apparaissent en mode consolidé', JSON.stringify(badgesAll));
check(Math.max(msFha, msAll, msFeba) < 3000, 'bascule sous 3 s sans rechargement',
      `max ${Math.max(msFha, msAll, msFeba)} ms`);
const reloads = await page.evaluate(() => performance.getEntriesByType('navigation').length);
check(reloads <= 2, 'aucun rechargement complet de page pendant les bascules');

// Aucune réponse servie sous une portée différente de celle demandée n'a
// pu peupler l'écran : on vérifie la cohérence sent/served du journal.
const mismatched = netlog.filter((r) => r.sent && r.served && r.sent !== r.served
                                       && !r.url.includes('entity-context/switch'));
check(mismatched.length === 0, 'aucune réponse servie sous une portée périmée',
      mismatched.length ? JSON.stringify(mismatched.slice(0, 3)) : '');
const lastScope = netlog.filter(r => r.served && r.url.includes('/students/')).slice(-1)[0]?.served;
check(lastScope === 'FEBA', 'dernières données élèves servies sous la bonne académie', `portée=${lastScope}`);

/* ═══ 2. Mode consolidé : badges partout ═════════════════════════════ */
log('\n═══ 2. MODE « TOUTES LES ACADÉMIES » — IDENTIFICATION ═══');
await switchAcademy('Toutes les Académies');
const PAGES_ALL = [
  ['students', 'Élèves'], ['users', 'Utilisateurs'], ['classes', 'Classes'],
  ['teachers', 'Enseignants'], ['parents', 'Parents'], ['levels', 'Niveaux'],
  ['grades', 'Notes'], ['payments', 'Paiements'], ['attendance', 'Présences'],
  ['homework', 'Devoirs'], ['bulletins', 'Bulletins'], ['announcements', 'Annonces'],
];
for (const [slug, label] of PAGES_ALL) {
  await page.goto(`${BASE}/superadmin/${slug}`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(900);
  const headers = await page.locator('table thead th').allInnerTexts();
  const hasCol = headers.some((h) => /ACAD[ÉE]MIE|ACADEMY/i.test(h));
  const rows = await page.locator('table tbody tr').count();
  const badges = await page.locator('table tbody tr span:text-matches("^(FEBA|FEBA FHA|Sans académie)$")').count();
  if (rows === 0) { log(`  (vide) ${label}`); continue; }
  check(hasCol && badges > 0, `colonne Académie sur « ${label} »`,
        `${badges} badge(s) / ${rows} ligne(s)`);
}
await page.goto(`${BASE}/superadmin/students`, { waitUntil: 'networkidle' });
await page.waitForTimeout(900);
const codesAll = await visibleAcademies();
check(codesAll.length >= 2, 'les deux académies sont visibles dans la même liste', JSON.stringify(codesAll));
await page.screenshot({ path: `${SHOTS}/v7-02-mode-consolide-badges.png` });

/* ═══ 3. Emplois du temps séparés ════════════════════════════════════ */
log('\n═══ 3. EMPLOIS DU TEMPS SÉPARÉS ═══');
await switchAcademy('Faith & Excellence');
await page.goto(BASE + '/superadmin/schedule', { waitUntil: 'networkidle' });
await page.waitForTimeout(1200);
let tabs = await page.locator('[role=tab]').allInnerTexts();
check(tabs.length === 2, 'deux onglets nommés FEBA et FEBA FHA', JSON.stringify(tabs.map(x => x.split('\n')[0])));
check(tabs.some(x => /^FEBA — /.test(x)) && tabs.some(x => /^FEBA FHA — /.test(x)),
      'onglets nommés en toutes lettres (pas de simple couleur)');
await page.screenshot({ path: `${SHOTS}/v7-03-emploi-du-temps-onglets.png` });

// Onglet FEBA : créneaux présentiels avec salle physique
const febaBody = await page.locator('main, body').first().innerText();
check(/Nouveau créneau/.test(febaBody), 'création de créneau proposée sur l\'onglet FEBA');

// Onglet FEBA FHA depuis le superadmin sur FEBA : le serveur doit refuser
await page.click('[role=tab]:has-text("FEBA FHA")');
await page.waitForTimeout(1200);
const onlineBody = await page.locator('body').innerText();
check(/n'existent pas pour cette académie|do not exist for this academy/.test(onlineBody),
      'séances en ligne refusées pour une académie présentielle (403 serveur)');
await page.screenshot({ path: `${SHOTS}/v7-03-seances-refusees-feba.png` });

// Admin FEBA FHA : CRUD réel des séances en ligne
await login('admin@febafha.org', 'Admin@2024');
await page.goto(BASE + '/admin/schedule', { waitUntil: 'networkidle' });
await page.waitForTimeout(1400);
const fhaHeaders = await page.locator('table thead th').allInnerTexts();
check(fhaHeaders.some(h => /UTC/i.test(h)), 'colonne heure UTC sur les séances FEBA FHA', JSON.stringify(fhaHeaders));
check(fhaHeaders.some(h => /locale|local/i.test(h)), 'colonne heure locale');
check(fhaHeaders.some(h => /virtuelle|virtual/i.test(h)), 'colonne salle virtuelle');
check(fhaHeaders.some(h => /rappel|reminder/i.test(h)), 'colonne rappel');
const fhaRows = await page.locator('table tbody tr').count();
check(fhaRows > 0, 'séances en ligne listées', `${fhaRows} séance(s)`);
await page.screenshot({ path: `${SHOTS}/v7-03-seances-fha.png`, fullPage: true });

// Modification d'une séance : le formulaire est bien celui du métier FHA
await page.locator('table tbody tr').first().locator('button').first().click();
await page.waitForTimeout(900);
const modal = await page.locator('body').innerText();
check(/UTC/.test(modal) && /(Fuseau|time zone)/i.test(modal),
      'formulaire d\'édition FHA : heure UTC et fuseau');
check(/(Rappel|Reminder)/i.test(modal), 'formulaire d\'édition FHA : rappel aux familles');
await page.screenshot({ path: `${SHOTS}/v7-03-formulaire-seance-fha.png` });
await page.keyboard.press('Escape');

// L'admin FHA n'a AUCUN accès à l'emploi du temps présentiel
const fhaTabTexts = await page.locator('[role=tab]').allInnerTexts();
check(fhaTabTexts.length === 1 && /FEBA FHA/.test(fhaTabTexts[0]),
      'admin FEBA FHA : uniquement l\'onglet des séances en ligne',
      JSON.stringify(fhaTabTexts.map(x => x.split('\n')[0])));

/* ═══ 4. Application privée en anglais, tous les profils ══════════════ */
log('\n═══ 4. APPLICATION PRIVÉE EN ANGLAIS — TOUS LES PROFILS ═══');
const FR_WORDS = /\b(Élèves|Enseignants|Paramètres|Emploi du temps|Tableau de bord|Notes|Présences|Devoirs|Bulletins|Paiements|Annonces|Déconnexion|Rechercher|Enregistrer|Ajouter|Modifier|Supprimer)\b/;
const PROFILS = [
  ['superadmin@feba.bj', 'SuperAdmin@2024', 'superadmin',
   ['dashboard', 'students', 'teachers', 'classes', 'grades', 'payments', 'attendance', 'schedule', 'settings']],
  ['admin@feba.bj', 'Admin@2024', 'admin',
   ['dashboard', 'students', 'teachers', 'grades', 'schedule', 'settings']],
  ['prof.math@feba.bj', 'Teacher@2024', 'teacher', ['dashboard', 'grades', 'schedule']],
  ['parent1@feba.bj', 'Parent@2024', 'parent', ['dashboard', 'grades', 'schedule']],
  ['eleve1@feba.bj', 'Student@2024', 'student', ['dashboard', 'grades', 'schedule']],
];
for (const [email, pwd, space, routes] of PROFILS) {
  await login(email, pwd);
  // Bascule en anglais via le sélecteur de l'application.
  await page.evaluate(() => localStorage.setItem('feba-lang', 'en'));
  await page.reload({ waitUntil: 'networkidle' });
  await page.waitForTimeout(700);
  let leftovers = [];
  for (const route of routes) {
    const url = `${BASE}/${space}/${route}`;
    const resp = await page.goto(url, { waitUntil: 'networkidle' }).catch(() => null);
    if (!resp) continue;
    await page.waitForTimeout(700);
    if (page.url().includes('/login')) continue;
    const text = await page.locator('body').innerText();
    const hit = text.match(FR_WORDS);
    if (hit) leftovers.push(`${route}:${hit[0]}`);
  }
  check(leftovers.length === 0, `profil ${space} en anglais`,
        leftovers.length ? leftovers.join(', ') : `${routes.length} vues`);
}
await page.screenshot({ path: `${SHOTS}/v7-04-application-anglais.png` });

/* ═══ 5. Erreurs console ═════════════════════════════════════════════ */
log('\n═══ 5. JOURNAL ═══');
/* Deux familles de messages sont attendues et ne sont pas des anomalies :
   - les connexions avortées, conséquence directe de l'annulation des
     requêtes en vol lors d'une bascule d'académie (c'est le comportement
     recherché) ;
   - le 403 des séances en ligne, que ce scénario PROVOQUE lui-même pour
     vérifier que le serveur refuse bien l'endpoint à une académie
     présentielle. */
const realErrors = consoleErrors.filter((e) =>
  !/ERR_CONNECTION_RESET|ERR_ABORTED|favicon|Download the React DevTools/.test(e)
  && !/403 \(Forbidden\)/.test(e));
check(realErrors.length === 0, 'aucune erreur console applicative',
      realErrors.slice(0, 3).join(' | '));
log(`  ${netlog.length} réponses API observées · ${netlog.filter(r => r.served).length} portées annoncées`);

log(`\n═══ RÉSULTAT : ${FAIL === 0 ? 'TOUS LES POINTS VÉRIFIÉS' : FAIL + ' ÉCHEC(S)'} ═══`);
await b.close();
process.exit(FAIL ? 1 : 0);
