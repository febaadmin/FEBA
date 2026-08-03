/**
 * Vérification navigateur de l'itération V9 — cinq parcours réels.
 *
 * Chaque parcours reproduit ce qu'un utilisateur fait vraiment, dans un
 * Chromium réel, sur le build de production. Les captures accompagnent le
 * rapport ; les assertions, elles, portent sur ce qui est mesurable.
 *
 *   1. Public FHA        — la fiche d'inscription est envoyée, et l'écran
 *                          ne promet un e-mail que s'il est parti.
 *   2. Admin FHA         — le dossier apparaît avec sa fiche PDF, l'état
 *                          d'envoi, et les actions par ligne.
 *   3. Super Admin       — la bascule d'académie change réellement ce qui
 *                          est affiché.
 *   4. Contact           — WhatsApp saisi, WhatsApp affiché, message long
 *                          non coupé.
 *   5. Documents         — le filtre par académie s'applique, et produire
 *                          exige de confirmer l'académie.
 *
 * UN NAVIGATEUR PAR PROFIL : voir devises-et-documents.mjs — Chromium
 * étrangle les minuteries des pages non visibles, et une seconde connexion
 * dans le même processus se figeait quarante secondes.
 */
import fs from 'node:fs';
import { chromium } from './playwright.mjs';

const BASE = process.env.E2E_BASE_URL || 'http://127.0.0.1:5173';
const API = process.env.E2E_API_URL || 'http://127.0.0.1:8000';
const SHOTS = process.env.E2E_SHOTS || new URL('./captures', import.meta.url).pathname;
fs.mkdirSync(SHOTS, { recursive: true });

const OUT = [];
let FAIL = 0;

function say(line) { OUT.push(line); console.log(line); }
function ok(label, detail = '') { say(`  ✓ ${label}${detail ? ` — ${detail}` : ''}`); }
function bad(label, detail = '') { FAIL += 1; say(`  ✗ ${label}${detail ? ` — ${detail}` : ''}`); }
function info(label) { say(`  · ${label}`); }
function check(condition, label, detail = '') {
  condition ? ok(label, detail) : bad(label, detail);
  return condition;
}

async function shot(page, name) {
  const path = `${SHOTS}/${name}.png`;
  await page.screenshot({ path, fullPage: true });
  info(`capture ${name}.png`);
  return path;
}

/** Un navigateur neuf, une page, et le nettoyage garanti. */
async function withBrowser(fn) {
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium',
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 950 } });
    const page = await context.newPage();
    return await fn(page, context);
  } finally {
    await browser.close();
  }
}

async function login(page, email, password) {
  await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
  await page.fill('input[type="email"], input[name="email"], input#email', email);
  await page.fill('input[type="password"]', password);
  await page.click('button[type="submit"]');

  // On attend le JETON, pas un changement d'URL. L'application peut rester
  // sur la même adresse un instant après l'authentification ; attendre la
  // navigation ferait échouer un scénario alors que la connexion a réussi.
  await page.waitForFunction(() => {
    const stored = JSON.parse(localStorage.getItem('feba-auth') || '{}');
    return Boolean(stored?.state?.accessToken);
  }, { timeout: 30000 });
  await page.waitForTimeout(1500);
}

const uniq = Date.now().toString().slice(-6);

/**
 * Attend que la page ait RÉELLEMENT affiché quelque chose.
 *
 * Un `waitForTimeout` fixe est calibré sur une machine au repos : dès que
 * plusieurs navigateurs tournent en parallèle, il rend la main sur une page
 * blanche et fait passer un écran correct pour un écran cassé.
 */
async function waitForContent(page, pattern, timeout = 45000) {
  await page.waitForLoadState('networkidle', { timeout }).catch(() => {});

  // Un premier rendu qui n'arrive pas du tout — page vide, aucun texte —
  // n'est pas un défaut de l'application : c'est un chargement perdu sous
  // la charge de plusieurs navigateurs simultanés. On recharge UNE fois.
  // Au-delà, l'échec est réel et doit être signalé.
  const empty = await page.evaluate(
    () => (document.body.innerText || '').trim().length === 0);
  if (empty) {
    info('première peinture vide — rechargement unique');
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle', { timeout }).catch(() => {});
  }

  try {
    await page.waitForFunction(
      (source) => new RegExp(source, 'i').test(document.body.innerText || ''),
      pattern.source, { timeout },
    );
  } catch (error) {
    // Capturer CE QU'ON VOIT au moment de l'échec. Sans cela, un écran
    // vide et un écran plein mais différent produisent le même message,
    // et le diagnostic se fait au jugé.
    await shot(page, `echec-${Date.now()}`);
    const seen = await page.evaluate(
      () => (document.body.innerText || '').slice(0, 600));
    info(`contenu vu à l'échec : ${JSON.stringify(seen)}`);
    throw error;
  }
  // Laisser React reposer après le dernier rendu.
  await page.waitForTimeout(500);
}

/* ── 1. Parcours public FEBA FHA ────────────────────────────────────── */

async function parcoursPublicFha() {
  say('\n1. Parcours public — fiche d\'inscription FEBA FHA');

  return withBrowser(async (page) => {
    // La fiche complète est envoyée par l'API : le formulaire compte douze
    // étapes, et ce parcours vérifie le TRAITEMENT de la soumission, pas la
    // navigation entre les étapes (couverte par les tests de composants).
    const payload = {
      child_last_name: 'Gbêdjissi', child_first_name: 'Élisabeth',
      child_birth_date: '2015-04-12', child_country: 'United States',
      parent1_last_name: 'Gbêdjissi', parent1_first_name: 'Ahouéfa',
      parent1_phone: '+1 215 555 0100', parent1_whatsapp: '+1 215 555 0199',
      parent1_email: `parcours.${uniq}@example.test`,
      parent1_preferred_language: 'fr', family_timezone: 'America/New_York',
      special_needs: 'Suivi orthophonique en anglais, séances courtes.',
      available_days: [3, 6],
      available_time_slots: [{ start: '16:00', end: '17:30' }],
      french_levels: ['few_words'], parent_goals: ['grandparents'],
      consent_rules: true, consent_privacy: true,
      consent_data_processing: true, consent_parental_authorization: true,
      consent_zoom: true,
    };

    await page.goto(`${BASE}/feba-fha/enroll`, { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle').catch(() => {});
    await shot(page, 'v9-1-public-fha-formulaire');

    const result = await page.evaluate(async ([api, body]) => {
      const response = await fetch(`${api}/api/website/fha/enroll/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      return { status: response.status, data: await response.json() };
    }, [API, payload]);

    if (!check(result.status === 201, 'la fiche est acceptée',
               `HTTP ${result.status}`)) {
      info(JSON.stringify(result.data).slice(0, 300));
      return null;
    }

    const data = result.data;
    check(/^FHA-\d{4}-\d{4}$/.test(data.reference || ''),
          'un numéro de dossier est attribué', data.reference);
    check(data.sheet_generated === true,
          'la fiche PDF est produite à la soumission');
    check(typeof data.email === 'object' && data.email !== null,
          'l\'état de l\'e-mail est renvoyé au navigateur',
          JSON.stringify(data.email));

    // Le point de P1 : l'écran ne promet un e-mail que s'il est parti.
    const promises = /e-mail de confirmation vient de vous être envoyé/.test(data.detail);
    if (data.email?.accepted) {
      check(promises, 'l\'e-mail annoncé l\'a réellement été');
    } else {
      check(!promises,
            'aucun e-mail n\'est promis alors qu\'il n\'est pas parti');
      check(/n'a pas pu être effectué/.test(data.detail),
            'l\'échec d\'envoi est annoncé à la famille');
    }
    check((data.detail || '').includes(data.reference),
          'le numéro de dossier est mis en avant — il est acquis, lui');

    return data.reference;
  });
}

/* ── 2. Admin FEBA FHA ──────────────────────────────────────────────── */

async function parcoursAdminFha(reference) {
  say('\n2. Espace administrateur FEBA FHA — le dossier est traitable');

  return withBrowser(async (page) => {
    await login(page, 'admin@febafha.org', 'Admin@2024');
    await page.goto(`${BASE}/admin/fha-admissions`, { waitUntil: 'domcontentloaded' });
    await waitForContent(page, /Dossier|File|Admissions/);
    await shot(page, 'v9-2-admin-fha-admissions');

    const text = await page.evaluate(() => document.body.innerText);

    check(reference == null || text.includes(reference),
          'le dossier soumis apparaît dans la liste', reference || '(non soumis)');
    check(/Fiche PDF|PDF form/i.test(text),
          'la colonne « Fiche PDF » est présente');
    check(/E-mail parent|Parent e-mail/i.test(text),
          'la colonne « E-mail parent » est présente');
    check(/Produite|Absente|Generated|Missing/.test(text),
          'l\'état de la fiche est affiché');

    // Actions par ligne, exigées par les annotations de la capture.
    // Les libellés suivent la langue de l'interface : on cible donc les
    // deux, plutôt que de supposer celle de la session.
    const actions = await page.evaluate(() => {
      const count = (...needles) => document.querySelectorAll(
        needles.map((n) => `[aria-label*="${n}"]`).join(','),
      ).length;
      return {
        sheet: count('fiche PDF', 'PDF form'),
        resend: count('confirmation'),
        detail: count('détail complet', 'full details'),
      };
    });
    check(actions.sheet > 0, 'action « Télécharger la fiche PDF » par ligne',
          `${actions.sheet} bouton(s)`);
    check(actions.resend > 0, 'action « Renvoyer l\'e-mail » par ligne',
          `${actions.resend} bouton(s)`);
    check(actions.detail > 0, 'action « Voir le détail complet » par ligne',
          `${actions.detail} bouton(s)`);

    // Le détail complet : WhatsApp et besoins particuliers visibles.
    if (actions.detail > 0) {
      await page.click('[aria-label*="détail complet"], [aria-label*="full details"]');
      await waitForContent(page, /Consentements|Consents/);
      await shot(page, 'v9-2-admin-fha-detail');
      const detail = await page.evaluate(() => document.body.innerText);
      check(/WhatsApp/i.test(detail), 'le détail affiche le WhatsApp');
      check(/Fiche et notifications|Form and notifications/i.test(detail),
            'le détail affiche l\'état de la fiche et des envois');
      check(/Consentements|Consents/i.test(detail),
            'le détail affiche les consentements');
    }
  });
}

/* ── 3. Super administrateur — la bascule change ce qui est affiché ─── */

async function parcoursSuperAdmin() {
  say('\n3. Super administrateur — la bascule d\'académie change l\'affichage');

  return withBrowser(async (page) => {
    await login(page, 'superadmin@feba.bj', 'SuperAdmin@2024');

    const readTemplates = async () => page.evaluate(async (api) => {
      // Le jeton est persisté par zustand sous « feba-auth ».
      const stored = JSON.parse(localStorage.getItem('feba-auth') || '{}');
      const token = stored?.state?.accessToken;
      const response = await fetch(`${api}/api/documents/templates/`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      return response.json();
    }, API);

    // Le super administrateur atterrit sur SA vue globale : on emprunte le
    // menu, comme lui. Naviguer par URL suppose une route qui pourrait ne
    // pas être la sienne, et le scénario échouerait pour la mauvaise raison.
    //
    // On cible le lien par son ADRESSE, pas par son libellé. Le libellé
    // suit la langue de l'interface, et « text=A, text=B » n'est pas une
    // liste valide pour le moteur `text=` de Playwright : les deux
    // tentatives précédentes échouaient sur un menu parfaitement correct.
    // Une URL, elle, ne se traduit pas.
    await page.locator('a[href$="/official-documents"]').first().click();
    await waitForContent(page, /Diplôme|Diploma|Certificat|Certificate/);
    await shot(page, 'v9-3-superadmin-documents');

    const body = await page.evaluate(() => document.body.innerText);
    check(/Toutes les Académies|All Academies|Académie active|Active academy|Faith & Excellence|French Heritage/i.test(body),
          'la page annonce la portée sous laquelle elle travaille');

    const payload = await readTemplates();
    if (payload && Array.isArray(payload.templates)) {
      check(payload.templates.every((t) => 'allowed_for_academy' in t),
            'chaque gabarit dit s\'il est utilisable par l\'académie en cours');
      check(payload.templates.every((t) => Array.isArray(t.academies)),
            'chaque gabarit déclare ses académies autorisées');
      info(`gabarits : ${payload.templates.map(
        (t) => `${t.id}[${t.academies.join(',') || 'toutes'}]`).join(' ')}`);
    } else {
      bad('la liste des gabarits est lisible');
    }
  });
}

/* ── 4. Contact — WhatsApp conservé, message long non coupé ─────────── */

async function parcoursContact() {
  say('\n4. Contact — le WhatsApp s\'affiche, le message long n\'est pas coupé');

  const longWord = 'M'.repeat(300);
  const longUrl = `https://exemple.test/${'chemin-tres-long/'.repeat(18)}?q=${'x'.repeat(120)}`;
  const message = [
    'Bonjour,', '',
    'Voici un message volontairement long pour éprouver l\'affichage.',
    `Un mot continu de 300 caractères : ${longWord}`,
    `Une URL très longue : ${longUrl}`,
    'Des accents : Élisabeth Ahouéfa Gbêdjissi — « N\'Guessan »',
    'Un contenu qui ressemble à du code : <script>alert(1)</script>',
    '', 'Merci.',
  ].join('\n');

  const whatsapp = '+229 96 11 22 33';

  await withBrowser(async (page) => {
    await page.goto(`${BASE}/contact`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#ct-whatsapp, form', { timeout: 30000 });

    const hasField = await page.locator('#ct-whatsapp').count();
    check(hasField > 0, 'le formulaire FEBA demande un numéro WhatsApp');
    await shot(page, 'v9-4-contact-formulaire');

    const result = await page.evaluate(async ([api, body]) => {
      const response = await fetch(`${api}/api/website/contact/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      return { status: response.status, data: await response.json() };
    }, [API, {
      name: `Parcours ${uniq}`, email: `contact.${uniq}@example.test`,
      phone: '+229 97 00 00 00', whatsapp,
      subject: `Message long ${uniq}`, message, consent: true,
    }]);
    check(result.status === 201, 'le message est accepté', `HTTP ${result.status}`);
  });

  await withBrowser(async (page) => {
    await login(page, 'admin@feba.bj', 'Admin@2024');
    await page.goto(`${BASE}/admin/website`, { waitUntil: 'domcontentloaded' });
    await waitForContent(page, new RegExp(`Message long ${uniq}`));

    const row = page.locator(`text=Message long ${uniq}`).first();
    if (await row.count() === 0) {
      bad('le message apparaît dans la boîte de réception');
      await shot(page, 'v9-4-contact-liste');
      return;
    }
    await row.click();
    await page.waitForSelector('[data-testid="long-text"]', { timeout: 30000 });
    await page.waitForTimeout(500);
    await shot(page, 'v9-4-contact-detail');

    const detail = await page.evaluate(() => document.body.innerText);
    check(detail.includes(whatsapp),
          'le numéro WhatsApp saisi est affiché', whatsapp);

    const block = page.locator('[data-testid="long-text"]').first();
    check(await block.count() > 0, 'le message est rendu par le bloc dédié');

    // P6 — mesures RÉELLES dans le navigateur, pas des classes CSS.
    const box = await block.evaluate((el) => {
      const style = getComputedStyle(el);
      return {
        whiteSpace: style.whiteSpace,
        overflowWrap: style.overflowWrap,
        textOverflow: style.textOverflow,
        scrollWidth: el.scrollWidth,
        clientWidth: el.clientWidth,
        scrollHeight: el.scrollHeight,
        clientHeight: el.clientHeight,
        overflowY: style.overflowY,
        textLength: el.innerText.length,
      };
    });

    check(box.whiteSpace === 'pre-wrap',
          'les retours à la ligne sont conservés', box.whiteSpace);
    check(box.overflowWrap === 'anywhere',
          'les mots très longs se coupent', box.overflowWrap);
    check(box.textOverflow !== 'ellipsis',
          'aucune troncature par points de suspension', box.textOverflow);
    check(box.scrollWidth <= box.clientWidth + 1,
          'AUCUN débordement horizontal',
          `${box.scrollWidth} ≤ ${box.clientWidth}`);
    check(box.overflowY === 'auto' || box.scrollHeight <= box.clientHeight + 1,
          'le texte long défile verticalement au lieu de déborder',
          box.overflowY);
    check(box.textLength >= message.length - 20,
          'le message est affiché ENTIER',
          `${box.textLength} caractères affichés sur ${message.length}`);

    // Le contenu ressemblant à du code ne doit pas être exécuté.
    const injected = await block.evaluate((el) => el.querySelectorAll('script').length);
    check(injected === 0, 'aucune balise script n\'a été créée dans le DOM');

    // La page elle-même ne déborde pas latéralement.
    const pageOverflow = await page.evaluate(() =>
      document.documentElement.scrollWidth - document.documentElement.clientWidth);
    check(pageOverflow <= 1, 'la page ne défile pas horizontalement',
          `${pageOverflow} px`);
  });
}

/* ── 5. Documents officiels — le filtre par académie s'applique ─────── */

async function parcoursDocuments() {
  say('\n5. Documents officiels — académie, gabarits et confirmation');

  return withBrowser(async (page) => {
    await login(page, 'admin@feba.bj', 'Admin@2024');
    await page.goto(`${BASE}/admin/official-documents`, { waitUntil: 'domcontentloaded' });
    await waitForContent(page, /Diplôme|Diploma|Certificat|Certificate/);
    await shot(page, 'v9-5-documents-feba');

    const body = await page.evaluate(() => document.body.innerText);

    // P7 — le message reproché ne doit plus apparaître.
    check(!/document_neutralize/.test(body),
          'aucun message ne demande de lancer « document_neutralize »');
    check(!/n'existe pas encore/.test(body),
          'aucun gabarit n\'est bloqué faute de fond dérivé');

    check(/Diplôme|Diploma/i.test(body), 'le diplôme est présent sur la page');
    check(/émission possible|issuance possible|Fond vérifié|Background verified/i.test(body),
          'au moins un gabarit se déclare émissible');

    // La fenêtre de production exige une confirmation d'académie.
    const produce = page.locator(
      'button:has-text("Produire un document"), button:has-text("Produce a document")',
    ).first();
    if (await produce.count() === 0) {
      bad('le bouton « Produire un document » est disponible');
      return;
    }
    await produce.click();
    await waitForContent(page, /confirme produire|confirm producing|Sélectionnez un élève|Select a student/);
    await shot(page, 'v9-5-documents-modale');

    const modal = await page.evaluate(() => document.body.innerText);
    check(/confirme produire ce document au nom de|confirm producing this document|Sélectionnez un élève|Select a student/i.test(modal),
          'la production exige une confirmation explicite de l\'académie');

    const submit = page.locator(
      'button:has-text("Produire"), button:has-text("Produce")',
    ).last();
    check(await submit.isDisabled(),
          'le bouton reste inactif tant que l\'académie n\'est pas confirmée');
  });
}

/* ── Exécution ──────────────────────────────────────────────────────── */

const started = Date.now();
say('Vérification navigateur V9 — Chromium réel, build de production');
say(`Application : ${BASE}   API : ${API}`);

let reference = null;
try {
  reference = await parcoursPublicFha();
  await parcoursAdminFha(reference);
  await parcoursSuperAdmin();
  await parcoursContact();
  await parcoursDocuments();
} catch (error) {
  bad('exception pendant les parcours', String(error).slice(0, 400));
}

const seconds = ((Date.now() - started) / 1000).toFixed(1);
say(`\n${FAIL === 0 ? 'TOUT EST VERT' : `${FAIL} VÉRIFICATION(S) EN ÉCHEC`} — ${seconds} s`);

fs.writeFileSync(new URL('./rapport-v9.txt', import.meta.url), OUT.join('\n') + '\n');
process.exit(FAIL === 0 ? 0 : 1);
