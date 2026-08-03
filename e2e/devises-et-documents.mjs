/**
 * Vérification navigateur de l'itération V8.
 *
 * Quatre points sont éprouvés dans un vrai navigateur, avec inspection du
 * trafic réseau :
 *
 *   P0  FEBA French Heritage Academy affiche des dollars, FEBA des francs
 *       CFA, et aucun écran ne mélange les deux dans un total.
 *   P1  Le panneau de paiement par carte propose des LIGNES tarifaires,
 *       jamais un champ de montant.
 *   P2  L'écran des documents officiels annonce l'état réel des gabarits.
 *   P3  Le certificat suit la même règle que le diplôme.
 *
 * UN NAVIGATEUR PAR PROFIL
 * ------------------------
 * Chaque connexion lance un navigateur NEUF, fermé ensuite.
 *
 * Vider `localStorage` puis retourner sur /login ne suffit pas : encore
 * authentifiée, l'application redirige immédiatement vers l'espace en
 * cours, et le scénario se poursuivrait avec le compte précédent — une
 * vérification d'isolation entre académies passerait alors pour de
 * mauvaises raisons.
 *
 * Un simple contexte neuf ne suffit pas non plus. Chromium étrangle les
 * minuteries des pages non visibles ; après la fermeture d'un premier
 * contexte, la connexion suivante se figeait quarante secondes — le jeton
 * était obtenu, mais la requête de contexte d'académie restait suspendue.
 * Un processus par profil supprime ce couplage. C'est plus lent, et c'est
 * le prix d'un scénario qui échoue seulement quand quelque chose ne va
 * réellement pas.
 */
import fs from 'node:fs';
import { chromium } from './playwright.mjs';

const BASE = process.env.E2E_BASE_URL || 'http://127.0.0.1:5173';
const SHOTS = process.env.E2E_SHOTS || new URL('./captures', import.meta.url).pathname;
fs.mkdirSync(SHOTS, { recursive: true });

const OUT = [];
let FAIL = 0;
const log = (s) => { OUT.push(s); console.log(s); };
const check = (ok, label, detail = '') => {
  if (!ok) FAIL++;
  log(`${ok ? '  OK ' : '  ÉCHEC'} ${label}${detail ? ' — ' + detail : ''}`);
  return ok;
};

const netlog = [];
const consoleErrors = [];

/** Lance un navigateur neuf et connecte le profil demandé. */
async function session(email, pwd) {
  const browser = await chromium.launch({
    executablePath: process.env.CHROMIUM_PATH || '/opt/pw-browsers/chromium',
  });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 950 } });
  const page = await ctx.newPage();

  page.on('response', (r) => {
    const u = r.url();
    if (u.includes('/api/')) netlog.push({ url: u.replace(BASE, ''), status: r.status() });
  });
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });

  // Deux essais : le premier échoue parfois sans erreur visible — le jeton
  // est bien obtenu (le serveur journalise une connexion réussie) mais
  // l'application reste sur le formulaire. Recharger et resoumettre suffit.
  // Une seule tentative rendrait le scénario intermittent, ce qui est pire
  // qu'un scénario lent : on finirait par ignorer ses échecs.
  for (let attempt = 1; attempt <= 2; attempt++) {
    await page.goto(BASE + '/login', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('input[type=password]', { timeout: 30000 });
    await page.fill('input[type=email], input[name=email]', email);
    await page.fill('input[type=password]', pwd);
    await page.click('button[type=submit]');

    // Sondage plutôt que `waitForURL` : la navigation peut se produire
    // pendant que l'attente s'arme.
    for (let i = 0; i < 30; i++) {
      if (!new URL(page.url()).pathname.includes('/login')) break;
      await page.waitForTimeout(1000);
    }
    if (!new URL(page.url()).pathname.includes('/login')) return { browser, page };
    log(`  INFO  connexion ${email} : essai ${attempt} sans effet, nouvelle tentative`);
  }

  const body = await page.evaluate(() => document.body.innerText).catch(() => '');
  await browser.close();
  throw new Error(`Connexion impossible pour ${email}. Page : ${body.slice(0, 200)}`);
}

const shot = (page, name) =>
  page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: true });
const bodyText = (page) => page.evaluate(() => document.body.innerText);

/** Va sur une page de l'application et laisse ses requêtes se poser. */
async function visit(page, path, settle = 1800) {
  await page.goto(BASE + path, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(settle);
  return bodyText(page);
}

/* ═══ P0 — La devise vient de l'académie ═══════════════════════════════ */
log('\n=== P0 — Devise imposée par l\'académie ===');

{
  const { browser, page } = await session('admin@febafha.org', 'Admin@2024');
  let text = await visit(page, '/admin/payments');
  check(/\$\s?\d/.test(text), 'FEBA FHA affiche des dollars');
  check(!/\bFCFA\b/.test(text), 'aucun « FCFA » sur l\'écran FEBA FHA');
  await shot(page, 'v8-01-paiements-fha-dollars');

  text = await visit(page, '/admin/dashboard');
  check(!/\bFCFA\b/.test(text), 'tableau de bord FEBA FHA sans « FCFA »');
  await shot(page, 'v8-02-tableau-de-bord-fha');
  await browser.close();
}

// La session FEBA sert à DEUX vérifications — la devise ici, les
// documents officiels plus bas. Elle est donc ouverte une seule fois et
// fermée à la fin : rouvrir la même session ne prouverait rien de plus.
const feba = await session('admin@feba.bj', 'Admin@2024');
{
  const text = await visit(feba.page, '/admin/payments');
  check(/FCFA/.test(text), 'FEBA affiche des francs CFA');
  check(!/\$\s?\d/.test(text), 'aucun montant en dollars sur l\'écran FEBA');
  await shot(feba.page, 'v8-03-paiements-feba-francs');
}

/* ═══ P1 — Paiement par carte ══════════════════════════════════════════ */
log('\n=== P1 — Paiement par carte ===');

{
  const { browser, page } = await session('parent@febafha.org', 'Parent@2024');

  const payloads = [];
  page.on('request', (r) => {
    if (r.url().includes('/payments/card/checkout/') && r.method() === 'POST') {
      payloads.push(r.postData() || '');
    }
  });

  const text = await visit(page, '/parent/payments', 2500);
  check(/Payer par carte|Pay by card|indisponible|unavailable/.test(text),
        'le panneau de paiement par carte est présent');

  // Le point central : le payeur choisit une ligne, jamais un montant.
  const amountInputs = await page.evaluate(() =>
    [...document.querySelectorAll('input')].filter((i) => {
      const hint = `${i.name} ${i.id} ${i.placeholder}`.toLowerCase();
      return /montant|amount|prix|price/.test(hint);
    }).length);
  check(amountInputs === 0,
        'aucun champ de saisie de montant n\'est proposé au parent',
        amountInputs ? `${amountInputs} champ(s)` : '');

  check(/125[.,]50|75[.,]00/.test(text),
        'les tarifs publiés par l\'académie sont affichés');
  check(!/\bFCFA\b/.test(text), 'les tarifs FHA ne sont pas libellés en FCFA');
  await shot(page, 'v8-04-paiement-carte-parent-fha');

  const feeButton = page.locator('button', { hasText: /125[.,]50|75[.,]00/ }).first();
  if (await feeButton.count()) {
    await feeButton.click({ timeout: 10000 }).catch(() => {});
    await page.waitForTimeout(4000);
    const sent = payloads.join(' ');
    check(payloads.length > 0, 'le clic déclenche bien une demande de paiement');
    check(payloads.length > 0 && !/amount/i.test(sent),
          'la requête ne transporte AUCUN montant', sent.slice(0, 120));
    await shot(page, 'v8-05-tentative-de-paiement');
  } else {
    log('  INFO  aucun tarif cliquable (paiement carte désactivé sur cette instance)');
  }
  await browser.close();
}

/* ═══ P2 / P3 — Documents officiels ════════════════════════════════════ */
log('\n=== P2 / P3 — Diplômes et certificats ===');

{
  const text = await visit(feba.page, '/admin/official-documents', 2500);

  check(/Diplôme|Diploma|diploma_feba/.test(text), 'le gabarit du diplôme est listé');
  check(/Certificat|Certificate|certificate_feba/.test(text),
        'le gabarit du certificat est listé');
  check(/pas installé|not installed|calibr/i.test(text),
        'l\'état réel des gabarits est annoncé, sans le masquer');
  await shot(feba.page, 'v8-06-documents-officiels-etat');
  await feba.browser.close();
}

/* ═══ Réseau et console ════════════════════════════════════════════════ */
log('\n=== Réseau et console ===');
// Le 502 de /payments/card/checkout/ est ATTENDU tant qu'aucun compte
// marchand valide n'est branché : c'est le prestataire qui refuse la clé,
// et le signaler comme un défaut du serveur masquerait de vrais 500. Le
// distinguer ici est la seule façon de garder cette vérification utile.
const providerGateway = (r) =>
  r.status === 502 && r.url.includes('/payments/card/checkout/');
const serverErrors = netlog.filter((r) => r.status >= 500 && !providerGateway(r));
check(serverErrors.length === 0, 'aucune erreur serveur',
      serverErrors.map((e) => `${e.status} ${e.url}`).join(', '));

const gatewayCount = netlog.filter(providerGateway).length;
if (gatewayCount) {
  log(`  INFO  ${gatewayCount} réponse(s) 502 sur le paiement carte : le `
      + `prestataire refuse la clé de démonstration. C'est le comportement `
      + `attendu sans compte marchand — et la preuve qu'aucune interface `
      + `factice ne simule un encaissement.`);
}

// Un 401 avant connexion et un 403 attendu sur une fonctionnalité réservée
// ne sont pas des anomalies ; le 502 du prestataire non configuré non plus.
const realConsoleErrors = consoleErrors.filter(
  (e) => !/401|403|502|Failed to load resource|ERR_CONNECTION/.test(e),
);
check(realConsoleErrors.length === 0, 'aucune erreur de console inattendue',
      realConsoleErrors.slice(0, 3).join(' | '));

log(`\nRequêtes API observées : ${netlog.length}`);
log(`Captures : ${SHOTS}`);

fs.writeFileSync(`${SHOTS}/../rapport-v8.txt`, OUT.join('\n'), 'utf-8');
if (FAIL) {
  console.error(`\n${FAIL} vérification(s) en échec.`);
  process.exit(1);
}
console.log('\nToutes les vérifications V8 sont passées.');
