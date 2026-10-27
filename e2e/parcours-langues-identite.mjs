/**
 * Programme linguistique et identité des académies — vrai navigateur.
 *
 * CE QUI EST ÉPROUVÉ
 * ------------------
 * Phase « creation » (super administrateur) :
 *   1. Créer une académie sans programme linguistique est impossible
 *      (bouton inactif) ; « testete » est créée « Français uniquement »
 *      depuis l'écran « Académies », avec un nom long et accentué.
 *   2. Sur testete : l'en-tête porte SON nom, l'emploi du temps a un seul
 *      onglet « <testete> — cours présentiels », aucun « Admissions » au
 *      menu, l'URL des admissions saisie à la main affiche « non activée ».
 *   3. Matières : seule la catégorie « Française » est proposée ; classes :
 *      seul le parcours « Francophone ».
 *   4. Rechargement : même académie, même identité.
 *   5. FEBA FHA : « Admissions en ligne » et onglet « FEBA FHA — séances en
 *      ligne » ; « Toutes les Académies » : onglets par type, avec le
 *      nombre d'académies, sans nom en dur.
 *   6. Changement de programme avec conflit : diagnostic affiché,
 *      confirmation exigée, rien de supprimé.
 * Phase « admin » (administrateur de testete, compte créé par le lanceur) :
 *   7. Connexion, déconnexion, reconnexion : toujours testete, jamais FEBA ;
 *      l'API refuse une matière anglaise (400), même forgée à la main.
 *
 * Variables : E2E_BASE_URL, CHROMIUM_PATH, E2E_SHOTS, E2E_PHASE
 * (creation | admin), E2E_TESTETE_EMAIL / E2E_TESTETE_PASSWORD (phase admin,
 * compte de test local fourni par le lanceur — jamais affiché).
 */
import { fileURLToPath } from 'node:url';
import fs from 'node:fs';
import { chromium } from './playwright.mjs';

const BASE = process.env.E2E_BASE_URL || 'http://127.0.0.1:5173';
const SHOTS = process.env.E2E_SHOTS || fileURLToPath(new URL('./captures', import.meta.url));
const PHASE = process.env.E2E_PHASE || 'creation';
fs.mkdirSync(SHOTS, { recursive: true });

const TESTETE = 'Académie Évangélique Saint-Éloi de Natitingou';
const CODE = 'TESTETE';

let FAIL = 0;
const log = (s) => console.log(s);
const check = (ok, label, detail = '') => {
  if (!ok) FAIL++;
  log(`${ok ? '  OK  ' : '  ÉCHEC'} ${label}${detail ? ' — ' + detail : ''}`);
  return ok;
};

const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || '/opt/pw-browsers/chromium' });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 950 } });
const page = await ctx.newPage();
const consoleErrors = [];
page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });
// Réponses en erreur, avec leur adresse : la console ne la donne pas.
const httpErrors = [];
page.on('response', (r) => { if (r.status() >= 400) httpErrors.push(`${r.status()} ${new URL(r.url()).pathname}`); });
// Attendu et documenté : avant la réponse de l'identité publique, le logo est
// demandé à l'URL de CETTE académie ; testete n'en a pas (404), le monogramme
// s'affiche. Jamais le logo d'une autre académie.
const EXPECTED_HTTP = [/^404 \/api\/schools\/public-branding\/TESTETE\/logo\/$/,
  /^400 \/api\/subjects\/$/];   // refus provoqués par le parcours

async function login(email, pwd) {
  await page.goto(BASE + '/login', { waitUntil: 'networkidle' });
  await page.evaluate(() => localStorage.clear());
  await page.goto(BASE + '/login', { waitUntil: 'networkidle' });
  await page.fill('input[type=email], input[name=email]', email);
  await page.fill('input[type=password]', pwd);
  await page.click('button[type=submit]');
  // Redirection de l'application (history.pushState) : condition observée
  // sur l'adresse, pas un événement de navigation.
  await page.waitForFunction(() => !location.pathname.includes('/login'), null, { timeout: 30000 });
  await page.waitForLoadState('networkidle');
}

async function logout() {
  await page.locator('button:has-text("Déconnexion"), a:has-text("Déconnexion")').first().click();
  await page.waitForFunction(() => location.pathname.includes('/login'), null, { timeout: 20000 });
}

const headerName = async () => (await page.getByTestId('layout-academy-name').innerText()).trim();
const headerTitle = async () => page.getByTestId('layout-academy-name').getAttribute('title');
// Libellé court servi par l'API pour testete (`short_name` : code rendu lisible).
const SHORT = 'TESTETE';
const switcherLabel = async () => (await page.locator('button[aria-haspopup=listbox]').innerText()).trim();
const menuText = async () => (await page.locator('aside nav').innerText());
const tabs = async () => (await page.locator('[role=tab]').allInnerTexts()).map((x) => x.split('\n')[0]);

async function switchAcademy(label) {
  if ((await switcherLabel()).includes(label)) return;
  await page.click('button[aria-haspopup=listbox]');
  await page.waitForSelector('li[role=option]');
  await page.click(`li[role=option]:has-text("${label}")`);
  // Condition observable (le sélecteur affiche l'académie), pas un délai.
  await page.waitForFunction((l) => document.querySelector('button[aria-haspopup=listbox]')?.innerText.includes(l),
    label, { timeout: 30000 });
  await page.waitForLoadState('networkidle');
}

async function api(method, path, body) {
  return page.evaluate(async ({ method, path, body }) => {
    const store = JSON.parse(localStorage.getItem('feba-auth') || '{}');
    const token = store?.state?.accessToken;
    const r = await fetch('/api' + path, {
      method, headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: body ? JSON.stringify(body) : undefined,
    });
    let data = null;
    try { data = await r.json(); } catch { /* vide */ }
    return { status: r.status, data };
  }, { method, path, body });
}

if (PHASE === 'creation') {
  log('\n═══ 1. CRÉATION D\'UNE ACADÉMIE « FRANÇAIS UNIQUEMENT » ═══');
  await login('superadmin@feba.bj', 'SuperAdmin@2024');
  await page.goto(BASE + '/superadmin/academies', { waitUntil: 'networkidle' });
  await page.getByTestId('academy-create').click();
  await page.getByTestId('academy-type-physical_primary').click();
  await page.getByTestId('academy-name').fill(TESTETE);
  await page.getByTestId('academy-code').fill(CODE);
  await page.getByTestId('academy-address').fill('Quartier Yimporima');
  await page.getByTestId('academy-city').fill('Natitingou');
  await page.getByTestId('academy-country').fill('Bénin');
  check(await page.getByTestId('academy-submit').isDisabled(), 'sans programme linguistique : création impossible');
  await page.getByTestId('academy-curriculum-french_only').click();
  check(!(await page.getByTestId('academy-submit').isDisabled()), 'programme choisi : création possible');
  await page.screenshot({ path: `${SHOTS}/lang-01-creation.png` });
  await page.getByTestId('academy-submit').click();
  const created = page.getByTestId('academy-created');
  await created.waitFor({ timeout: 30000 });
  check(/Français uniquement/.test(await created.innerText()), 'académie créée « Français uniquement » (réponse du serveur)');
  await page.keyboard.press('Escape');
  await page.waitForLoadState('networkidle');
  check((await page.getByTestId(`academy-curriculum-${CODE}`).innerText()).trim() === 'Français uniquement',
    'liste des académies : programme affiché');
  const ctxData = (await api('GET', '/auth/entity-context/')).data;
  const testeteEntity = ctxData.entities.find((e) => e.code === CODE);
  check(testeteEntity?.curriculum_language_mode === 'french_only', 'programme enregistré en base (contexte d\'entité)');

  log('\n═══ 2. IDENTITÉ DE TESTETE ═══');
  await page.goto(BASE + '/superadmin/schedule', { waitUntil: 'networkidle' });
  await switchAcademy(TESTETE);
  check(await headerName() === testeteEntity.short_name && await headerTitle() === TESTETE,
    'en-tête : libellé court de testete, nom complet en info-bulle', `${await headerName()} / ${await headerTitle()}`);
  const tt = await tabs();
  check(tt.length === 1 && tt[0] === `${testeteEntity.short_name} — cours présentiels`,
    'emploi du temps : un onglet, au nom de testete', JSON.stringify(tt));
  check(!/FEBA/.test(tt.join(' ')), 'aucun « FEBA » dans les onglets');
  const menu = await menuText();
  check(!/Admissions/.test(menu) && !/Rapports mensuels/.test(menu), 'menu : ni admissions ni rapports mensuels');
  await page.screenshot({ path: `${SHOTS}/lang-02-testete-emploi-du-temps.png` });
  await page.goto(BASE + '/superadmin/fha-admissions', { waitUntil: 'networkidle' });
  check(await page.getByTestId('feature-unavailable').isVisible(), 'URL des admissions saisie : « fonctionnalité non activée »');
  check((await page.getByTestId('feature-unavailable').innerText()).includes(SHORT), 'le message nomme testete');

  log('\n═══ 3. MATIÈRES ET CLASSES SELON LE PROGRAMME ═══');
  await page.goto(BASE + '/superadmin/settings', { waitUntil: 'networkidle' });
  await page.getByTestId('subject-add').click();
  const subjectSelect = page.getByTestId('subject-language');
  if (await subjectSelect.count()) {
    const values = await subjectSelect.locator('option').evaluateAll((os) => os.map((o) => o.value));
    check(JSON.stringify(values) === '["fr"]', 'nouvelle matière : seule la catégorie française est proposée',
      JSON.stringify(values));
    await page.keyboard.press('Escape');
  } else {
    check(false, 'formulaire de matière introuvable');
  }
  await page.goto(BASE + '/superadmin/classes', { waitUntil: 'networkidle' });
  await page.locator('button:has-text("Nouvelle classe")').first().click();
  const tracks = await page.getByTestId('class-track').locator('option').evaluateAll((os) => os.map((o) => o.value));
  check(JSON.stringify(tracks) === '["FRANCOPHONE"]', 'nouvelle classe : seul le parcours francophone', JSON.stringify(tracks));
  await page.keyboard.press('Escape');
  const forged = await api('POST', '/subjects/', { school: testeteEntity.id, name: 'English forgée', code: 'ENGF',
    coefficient: 1, language: 'en' });
  check(forged.status === 400, 'matière anglaise forgée à la main : refusée par le serveur (400)', String(forged.status));

  log('\n═══ 4. RECHARGEMENT ═══');
  await page.reload({ waitUntil: 'networkidle' });
  check(await headerName() === SHORT && (await switcherLabel()).includes(TESTETE), 'après rechargement : toujours testete');

  log('\n═══ 5. AUTRES ACADÉMIES ET « TOUTES » ═══');
  await page.goto(BASE + '/superadmin/schedule', { waitUntil: 'networkidle' });
  await switchAcademy('FEBA French Heritage');
  check((await tabs())[0] === 'FEBA FHA — séances en ligne', 'FEBA FHA : onglet à son nom (donnée de l\'académie)',
    JSON.stringify(await tabs()));
  check(/Admissions en ligne/.test(await menuText()), 'FEBA FHA : « Admissions en ligne » au menu');
  check(!/Admissions FEBA FHA/.test(await menuText()), 'plus de libellé « Admissions FEBA FHA » en dur');
  await switchAcademy('Toutes');
  const all = await tabs();
  check(all.length === 2 && /^Cours présentiels — 2 académie\(s\)$/.test(all[0]) && /^Séances en ligne — 1 académie\(s\)$/.test(all[1]),
    '« Toutes les Académies » : un onglet par type, nombre exact', JSON.stringify(all));
  const campusTitle = await page.getByTestId('schedule-tab-campus').getAttribute('title');
  check(campusTitle.split(', ').sort().join('|') === ['FEBA', SHORT].sort().join('|'),
    'onglet présentiel : les deux académies réelles, d\'après l\'API', campusTitle);
  await page.screenshot({ path: `${SHOTS}/lang-03-toutes-academies.png` });

  log('\n═══ 6. CHANGEMENT DE PROGRAMME AVEC CONFLIT ═══');
  // Passage en bilingue (aucun conflit), une matière anglaise, puis retour au français.
  await page.goto(BASE + '/superadmin/academies', { waitUntil: 'networkidle' });
  await page.getByTestId(`academy-edit-${CODE}`).click();
  await page.getByTestId('academy-edit-curriculum').selectOption('bilingual');
  await page.getByTestId('curriculum-diagnostic-ok').waitFor({ timeout: 15000 });
  await page.getByTestId('academy-edit-submit').click();
  await page.waitForLoadState('networkidle');
  await page.getByTestId(`academy-curriculum-${CODE}`).filter({ hasText: 'Bilingue' }).waitFor({ timeout: 15000 });
  check(true, 'testete passée en bilingue (sans conflit, sans confirmation)');
  const en = await api('POST', '/subjects/', { school: testeteEntity.id, name: 'English Reading', code: 'ENR',
    coefficient: 1, language: 'en' });
  check(en.status === 201, 'bilingue : matière anglaise acceptée', String(en.status));
  await page.getByTestId(`academy-edit-${CODE}`).click();
  await page.getByTestId('academy-edit-curriculum').selectOption('french_only');
  const diag = page.getByTestId('curriculum-diagnostic');
  await diag.waitFor({ timeout: 15000 });
  check(/English Reading/.test(await diag.innerText()) && /rien ne sera supprimé/.test(await diag.innerText()),
    'diagnostic : la matière en conflit est nommée, rien n\'est supprimé');
  check(await page.getByTestId('academy-edit-submit').isDisabled(), 'enregistrement bloqué sans confirmation');
  await page.screenshot({ path: `${SHOTS}/lang-04-diagnostic.png` });
  await page.getByTestId('academy-confirm-curriculum').check();
  await page.getByTestId('academy-edit-submit').click();
  await page.getByTestId(`academy-curriculum-${CODE}`).filter({ hasText: 'Français uniquement' }).waitFor({ timeout: 15000 });
  const subjects = (await api('GET', `/subjects/?school=${testeteEntity.id}`)).data;
  const list = Array.isArray(subjects) ? subjects : subjects?.results || [];
  check(list.some((s) => s.name === 'English Reading'), 'après confirmation : la matière anglaise est conservée');
  // L'académie active du super administrateur est PERSISTÉE côté serveur :
  // la remettre sur FEBA, état attendu par les autres scénarios.
  await switchAcademy('Faith & Excellence');
}

if (PHASE === 'admin') {
  log('\n═══ 7. ADMINISTRATEUR DE TESTETE : CONNEXION, RECONNEXION ═══');
  const email = process.env.E2E_TESTETE_EMAIL;
  const password = process.env.E2E_TESTETE_PASSWORD;
  for (const round of ['première connexion', 'reconnexion']) {
    await login(email, password);
    await page.goto(BASE + '/admin/schedule', { waitUntil: 'networkidle' });
    check(await headerName() === SHORT && await headerTitle() === TESTETE, `${round} : en-tête testete`, await headerName());
    const t = await tabs();
    check(t.length === 1 && t[0] === `${SHORT} — cours présentiels`, `${round} : onglet de testete`, JSON.stringify(t));
    const menu = await menuText();
    check(!/Admissions|Rapports mensuels|FEBA/.test(menu), `${round} : menu sans fonctionnalité ni nom d'une autre académie`);
    await page.reload({ waitUntil: 'networkidle' });
    check(await headerName() === SHORT, `${round} : après rechargement, toujours testete`);
    if (round === 'première connexion') {
      await page.goto(BASE + '/admin/fha-admissions', { waitUntil: 'networkidle' });
      check(await page.getByTestId('feature-unavailable').isVisible(), 'admissions saisies à la main : non activées');
      const r = await api('POST', '/subjects/', { name: 'Maths EN', code: 'MEN', coefficient: 1, language: 'en' });
      check(r.status === 400, 'matière anglaise par l\'API : refusée (400)', String(r.status));
      await page.screenshot({ path: `${SHOTS}/lang-05-admin-testete.png` });
      await logout();
    }
  }
}

const unexpectedHttp = httpErrors.filter((e) => !EXPECTED_HTTP.some((re) => re.test(e)));
check(unexpectedHttp.length === 0, 'aucune réponse en erreur hors refus attendus', unexpectedHttp.slice(0, 5).join(' | '));
const relevant = consoleErrors.filter((e) => !/Failed to load resource|DevTools|Download the React/.test(e));
check(relevant.length === 0, 'aucune erreur JavaScript dans la console', relevant.slice(0, 3).join(' | '));
await browser.close();
log(`\n${FAIL ? `ÉCHEC : ${FAIL} point(s)` : 'Tous les points sont vérifiés.'}`);
process.exit(FAIL ? 1 : 0);
