/**
 * Gabarits WORD / POWERPOINT téléversés directement — vrai navigateur.
 *
 * CE QUI EST ÉPROUVÉ
 * ------------------
 *   1. FEBA FHA : un diplôme DOCX contenant des marqueurs {{ … }} est
 *      téléversé TEL QUEL depuis l'écran ; FEBA le convertit, l'éditeur
 *      s'ouvre sur le fond converti avec les champs déjà placés aux
 *      marqueurs ; vérification, activation, production, délivrance,
 *      téléchargement du PDF.
 *   2. FEBA : un certificat DOCX portrait SANS marqueur (champs placés dans
 *      l'éditeur) et un diplôme PPTX à marqueurs ; production des deux.
 *   3. Un faux DOCX (PDF renommé) est refusé avec un message explicite.
 *   4. L'administrateur FHA ne voit ni ne télécharge les gabarits de FEBA.
 *
 * Aucun fichier n'est converti à l'avance : les documents Word et
 * PowerPoint sont ceux de backend/tests/fixtures/office_templates/.
 * Le backend doit disposer de LibreOffice (image Docker de FEBA).
 */
import { fileURLToPath } from 'node:url';
import fs from 'node:fs';
import path from 'node:path';
import { chromium } from './playwright.mjs';

const BASE = process.env.E2E_BASE_URL || 'http://127.0.0.1:5173';
const API = process.env.E2E_API_URL || BASE + '/api';
const SHOTS = process.env.E2E_SHOTS || fileURLToPath(new URL('./captures', import.meta.url));
const OFFICE = fileURLToPath(new URL('../backend/tests/fixtures/office_templates', import.meta.url));
const EXTRA = process.env.E2E_TEMPLATE_DIR;
fs.mkdirSync(SHOTS, { recursive: true });

let FAIL = 0;
const OUT = [];
const log = (s) => { OUT.push(s); console.log(s); };
const check = (ok, label, detail = '') => {
  if (!ok) FAIL++;
  log(`${ok ? '  OK  ' : '  ÉCHEC'} ${label}${detail ? ' — ' + detail : ''}`);
  return ok;
};
const errors = [];
const bodyText = (page) => page.evaluate(() => document.body.innerText);
const shot = (page, name) => page.screenshot({ path: `${SHOTS}/multiformats-${name}.png`, fullPage: true });

async function session(email, pwd) {
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || '/opt/pw-browsers/chromium' });
  const page = await (await browser.newContext({ viewport: { width: 1440, height: 950 } })).newPage();
  page.on('pageerror', (e) => errors.push(`${email} : EXCEPTION ${e.message}`));
  page.on('response', (r) => { if (r.status() >= 500) errors.push(`${email} : HTTP ${r.status()} ${r.url()}`); });
  for (let attempt = 1; attempt <= 4; attempt++) {
    await page.goto(BASE + '/login', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('input[type=password]', { timeout: 30000 });
    await page.fill('input[type=email], input[name=email]', email);
    await page.fill('input[type=password]', pwd);
    const reponse = page.waitForResponse((r) => r.url().includes('/auth/login/'), { timeout: 20000 }).catch(() => null);
    await page.locator('button[type=submit]').first().click();
    const r = await reponse;
    if (r && r.status() === 200) {
      for (let i = 0; i < 30; i++) {
        if (/Déconnexion|Logout/.test(await bodyText(page).catch(() => ''))) break;
        await page.waitForTimeout(500);
      }
      return { browser, page };
    }
    await page.waitForTimeout(r && r.status() === 429 ? 20000 : 2500);
  }
  throw new Error(`Connexion impossible pour ${email}`);
}

function api(page, chemin, options = {}) {
  return page.evaluate(async ([base, p, opts]) => {
    const magasin = JSON.parse(localStorage.getItem('feba-auth') || '{}');
    const jeton = (magasin.state || magasin).accessToken || '';
    const r = await fetch(base + p, { method: opts.method || 'GET',
      headers: { Authorization: `Bearer ${jeton}`, 'Content-Type': 'application/json' } });
    const type = r.headers.get('content-type') || '';
    if (!type.includes('json')) {
      const octets = new Uint8Array(await r.arrayBuffer());
      let b64 = '';
      for (let i = 0; i < octets.length; i += 0x8000) b64 += String.fromCharCode(...octets.slice(i, i + 0x8000));
      return { status: r.status, base64: btoa(b64), type };
    }
    return { status: r.status, corps: await r.json() };
  }, [API, chemin, options]);
}

async function attendreTexte(page, motif, limite = 30000) {
  const fin = Date.now() + limite;
  let texte = '';
  while (Date.now() < fin) {
    texte = await bodyText(page);
    if (motif.test(texte)) return texte;
    await page.waitForTimeout(400);
  }
  return texte;
}

async function basculerAcademie(page, motif) {
  await page.locator('button[aria-haspopup="listbox"]').first().click();
  await page.waitForTimeout(400);
  await page.locator('[role="option"] button', { hasText: motif }).first().click();
  await page.waitForTimeout(2500);
}

async function televerser(page, kind, fichier) {
  await page.goto(`${BASE}/superadmin/document-templates`, { waitUntil: 'domcontentloaded' });
  await attendreTexte(page, /Gabarit du diplôme/);
  await page.locator(`[data-testid="kind-${kind}"] button`, { hasText: /Téléverser|Remplacer/ }).first().click();
  await page.locator('[data-testid="template-file"]').setInputFiles(fichier);
  const dialogue = page.locator('div.relative', { hasText: /Téléverser le gabarit/ }).last();
  const debut = Date.now();
  await dialogue.locator('button', { hasText: /^Téléverser$/ }).click();
  const texte = await attendreTexte(page, /Fichier accepté|refusé|corrompu|ne correspond pas|échoué/, 120000);
  return { texte, secondes: ((Date.now() - debut) / 1000).toFixed(1) };
}

async function placer(page, nom, geo) {
  await page.selectOption('#add-field', nom);
  await page.locator('button[title="Placer ce champ"]').click();
  for (const [libelle, valeur] of [['Largeur (mm)', geo.w], ['Hauteur (mm)', geo.h], ['X (mm)', geo.x], ['Y (mm)', geo.y]]) {
    await page.locator('label', { hasText: libelle }).locator('input').fill(String(valeur));
  }
}

async function verifierActiver(page, kind) {
  await page.locator('button', { hasText: 'Enregistrer et vérifier' }).click();
  const texte = await attendreTexte(page, /Valide, prêt à être activé|Invalide/, 60000);
  const ok = /Valide, prêt à être activé/.test(texte);
  if (ok) {
    await page.locator(`[data-testid="kind-${kind}"] button`, { hasText: /^Activer$/ }).click();
    await attendreTexte(page, /Actif — utilisé pour les documents/);
  }
  return ok;
}

async function produire(page, kind, nomEleve, fichier) {
  await page.goto(`${BASE}/superadmin/official-documents`, { waitUntil: 'domcontentloaded' });
  await attendreTexte(page, /Documents officiels/);
  await page.locator('button', { hasText: 'Produire un document' }).first().click();
  await page.selectOption('#doc-kind', kind);
  await page.locator('button', { hasText: 'Rechercher un élève' }).first().click();
  await page.locator('input[placeholder^="Rechercher"]').last().pressSequentially(nomEleve.slice(0, 7), { delay: 40 });
  await page.waitForTimeout(700);
  await page.locator('button', { hasText: nomEleve }).last().click();
  await page.waitForSelector('[data-testid="document-check"]', { timeout: 20000 });
  const verification = await page.locator('[data-testid="document-check"]').innerText();
  await page.locator('input[type=checkbox]').first().check();
  const avant = (await api(page, '/documents/')).corps.map((d) => d.id);
  await page.locator('button', { hasText: /^Produire$/ }).first().click();
  await page.waitForTimeout(3000);
  const doc = (await api(page, '/documents/')).corps.find((d) => !avant.includes(d.id));
  if (!doc) return { verification, doc: null };
  await page.locator('tr', { hasText: nomEleve }).filter({ hasText: /non délivré/ }).first()
    .locator('button', { hasText: 'Délivrer' }).click();
  await page.waitForTimeout(3000);
  const delivre = (await api(page, '/documents/')).corps.find((d) => d.id === doc.id);
  const pdf = await api(page, `/documents/${doc.id}/download/`);
  fs.writeFileSync(path.join(SHOTS, fichier), Buffer.from(pdf.base64, 'base64'));
  return { verification, doc: delivre };
}

async function premierEleve(page) {
  const liste = (await api(page, '/students/?page_size=5')).corps;
  const e = (liste.results || liste)[0];
  return e.full_name || `${e.first_name} ${e.last_name}`;
}

/* ══════════════════════════════════════════════════════════════════════ */
log('=== Gabarits Word / PowerPoint téléversés directement — navigateur ===');
const R = {};
{
  const { browser, page } = await session('superadmin@feba.bj', 'SuperAdmin@2024');
  await page.goto(BASE + '/superadmin/dashboard', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2500);

  log('\n--- 1. FEBA French Heritage Academy : diplôme DOCX à marqueurs ---');
  await basculerAcademie(page, 'French Heritage');
  await page.goto(`${BASE}/superadmin/document-templates`, { waitUntil: 'domcontentloaded' });
  let texte = await attendreTexte(page, /Word \(DOCX\)/);
  check(/Word \(DOCX\).*Word 97-2003 \(DOC\).*OpenDocument texte \(ODT\).*Texte enrichi \(RTF\)/s.test(texte),
        "l'écran annonce Word, DOC, ODT, RTF parmi les formats acceptés");
  if (EXTRA) {
    const refus = await televerser(page, 'diploma', path.join(EXTRA, 'faux_word.docx'));
    check(/ne correspond pas au contenu réel du fichier \(PDF\)/.test(refus.texte), 'faux DOCX (PDF renommé) refusé, message explicite');
    await page.keyboard.press('Escape');
  }
  const up = await televerser(page, 'diploma', path.join(OFFICE, 'diplome_paysage_marqueurs.docx'));
  check(/Fichier accepté \(version 1\)/.test(up.texte), 'DOCX téléversé directement et converti', `${up.secondes} s`);
  await page.waitForSelector('[data-testid="template-surface"] img', { timeout: 20000 });
  for (const champ of ['student_name', 'academy_name', 'school_year', 'issue_date', 'document_number']) {
    check(await page.locator(`[data-testid="zone-${champ}"]`).count() === 1, `champ « ${champ} » placé au marqueur`);
  }
  await shot(page, '01-editeur-docx-champs-places');
  check(await verifierActiver(page, 'diploma'), 'gabarit DOCX vérifié puis activé');
  texte = await bodyText(page);
  check(/Word \(DOCX\) → fond normalisé PDF/.test(texte), "l'écran indique l'original Word et le fond PDF");
  check(/5 champ\(s\) placé\(s\) automatiquement/.test(texte), 'cinq champs placés automatiquement');
  await shot(page, '02-docx-actif');
  const nomFha = await premierEleve(page);
  let r = await produire(page, 'diploma', nomFha, 'fha-diplome-docx.pdf');
  check(/version 1/.test(r.verification), 'la production annonce le gabarit téléversé');
  check(r.doc?.status === 'issued', 'diplôme FHA délivré sur le fond Word', r.doc?.number);
  R.fha = { doc: r.doc, nom: nomFha };

  log('\n--- 2. FEBA : certificat DOCX portrait (champs placés à la main) et diplôme PPTX ---');
  await basculerAcademie(page, 'Faith & Excellence');
  const cert = await televerser(page, 'certificate', path.join(OFFICE, 'certificat_portrait.docx'));
  check(/Fichier accepté/.test(cert.texte), 'certificat DOCX portrait converti', `${cert.secondes} s`);
  await page.waitForSelector('[data-testid="template-surface"] img', { timeout: 20000 });
  check(/210(\.0\d)? × 297(\.0\d)? mm/.test(await bodyText(page)), 'page portrait 210 × 297 mm (±0,05)');
  // Zones libres du fond : sous « … certifie que l'élève : », après « … en classe de : ».
  await placer(page, 'student_name', { x: 30, y: 78, w: 150, h: 12 });
  await placer(page, 'class_name', { x: 100, y: 94, w: 90, h: 8 });
  await placer(page, 'document_number', { x: 110, y: 270, w: 80, h: 8 });
  await shot(page, '03-editeur-certificat-docx');
  check(await verifierActiver(page, 'certificate'), 'certificat DOCX vérifié puis activé');
  const pptx = await televerser(page, 'diploma', path.join(OFFICE, 'diplome_diapo_marqueurs.pptx'));
  check(/Fichier accepté/.test(pptx.texte), 'diplôme PPTX converti', `${pptx.secondes} s`);
  await page.waitForSelector('[data-testid="template-surface"] img', { timeout: 20000 });
  check(await page.locator('[data-testid="zone-student_name"]').count() === 1, 'PPTX : nom placé au marqueur');
  check(await verifierActiver(page, 'diploma'), 'diplôme PPTX vérifié puis activé');
  const nomFeba = await premierEleve(page);
  r = await produire(page, 'certificate', nomFeba, 'feba-certificat-docx.pdf');
  check(r.doc?.status === 'issued', 'certificat FEBA délivré sur le fond Word', r.doc?.number);
  R.febaCert = r.doc;
  r = await produire(page, 'diploma', nomFeba, 'feba-diplome-pptx.pdf');
  check(r.doc?.status === 'issued', 'diplôme FEBA délivré sur le fond PowerPoint', r.doc?.number);
  R.febaTemplates = (await api(page, '/documents/academy-templates/')).corps.kinds;
  await browser.close();
}

log('\n--- 3. Administrateur FEBA FHA : isolation ---');
{
  const { browser, page } = await session('admin@febafha.org', 'Admin@2024');
  const liste = (await api(page, '/documents/academy-templates/')).corps;
  check(liste.kinds.diploma.active?.source_format === 'docx', 'son diplôme Word, et lui seul');
  check(liste.kinds.certificate.state === 'absent', "le certificat Word de FEBA n'apparaît pas");
  const id = R.febaTemplates.certificate.active.id;
  for (const suffixe of ['', 'background/', 'original/']) {
    const res = await api(page, `/documents/academy-templates/${id}/${suffixe}`);
    check(res.status === 404, `gabarit Word de FEBA, ${suffixe || 'détail'} : 404`, `HTTP ${res.status}`);
  }
  const doc = await api(page, `/documents/${R.febaCert.id}/download/`);
  check(doc.status === 404, 'certificat délivré par FEBA : 404', `HTTP ${doc.status}`);
  await browser.close();
}

check(errors.length === 0, 'aucune exception JavaScript ni réponse 5xx', errors.slice(0, 3).join(' | '));
log(`\n${FAIL === 0 ? 'SUCCÈS' : `ÉCHECS : ${FAIL}`}`);
fs.writeFileSync(path.join(SHOTS, 'multiformats-rapport.txt'), OUT.join('\n') + '\n');
fs.writeFileSync(path.join(SHOTS, 'multiformats-resultats.json'), JSON.stringify(R, null, 2));
process.exit(FAIL === 0 ? 0 : 1);
