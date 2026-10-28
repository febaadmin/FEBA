/**
 * Gabarits officiels téléversés — parcours complet dans un vrai navigateur.
 *
 * CE QUI EST ÉPROUVÉ
 * ------------------
 *   1. Le super administrateur, sur FEBA French Heritage Academy, refuse
 *      un faux PNG et un PDF corrompu, téléverse un diplôme PDF, PLACE les
 *      champs à la souris dans l'éditeur, vérifie puis active le gabarit.
 *   2. Il produit et délivre un diplôme pour un élève de cette académie ;
 *      le PDF téléchargé est conservé pour être relu (texte et pixels).
 *   3. Sur FEBA (Cotonou), même parcours pour un certificat PNG portrait.
 *   4. Remplacement : une nouvelle version activée archive l'ancienne ;
 *      le diplôme déjà délivré garde exactement le même fichier.
 *   5. L'administrateur FEBA FHA ne voit que les gabarits de son académie
 *      et reçoit 404 sur ceux de Cotonou.
 *
 * Fichiers d'entrée : `E2E_TEMPLATE_DIR` (diplome_test_vectoriel.pdf,
 * certificat_test_portrait.png, faux_png.png, corrompu.pdf). Les PDF
 * délivrés sont écrits dans `E2E_SHOTS` pour la relecture.
 */
import { fileURLToPath } from 'node:url';
import fs from 'node:fs';
import path from 'node:path';
import { chromium } from './playwright.mjs';

const BASE = process.env.E2E_BASE_URL || 'http://127.0.0.1:5173';
const API = process.env.E2E_API_URL || BASE + '/api';
const SHOTS = process.env.E2E_SHOTS || fileURLToPath(new URL('./captures', import.meta.url));
const FILES = process.env.E2E_TEMPLATE_DIR;
if (!FILES) {
  console.error('E2E_TEMPLATE_DIR doit désigner le dossier des gabarits de test.');
  process.exit(2);
}
fs.mkdirSync(SHOTS, { recursive: true });

let FAIL = 0;
const OUT = [];
const log = (s) => { OUT.push(s); console.log(s); };
const check = (ok, label, detail = '') => {
  if (!ok) FAIL++;
  log(`${ok ? '  OK  ' : '  ÉCHEC'} ${label}${detail ? ' — ' + detail : ''}`);
  return ok;
};
const consoleErrors = [];
const bodyText = (page) => page.evaluate(() => document.body.innerText);
const shot = (page, name) => page.screenshot({ path: `${SHOTS}/gabarits-${name}.png`, fullPage: true });

async function session(email, pwd) {
  const browser = await chromium.launch({
    executablePath: process.env.CHROMIUM_PATH || '/opt/pw-browsers/chromium',
  });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 950 }, acceptDownloads: true });
  const page = await ctx.newPage();
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(`${email} : ${m.text()}`); });
  page.on('pageerror', (e) => consoleErrors.push(`${email} : EXCEPTION ${e.message}`));
  page.on('response', (r) => { if (r.status() >= 500) consoleErrors.push(`${email} : HTTP ${r.status()} ${r.url()}`); });
  for (let attempt = 1; attempt <= 4; attempt++) {
    await page.goto(BASE + '/login', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('input[type=password]', { timeout: 30000 });
    await page.fill('input[type=email], input[name=email]', email);
    await page.fill('input[type=password]', pwd);
    const reponse = page.waitForResponse((r) => r.url().includes('/auth/login/'), { timeout: 20000 })
      .catch(() => null);
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
    const r = await fetch(base + p, {
      method: opts.method || 'GET',
      headers: { Authorization: `Bearer ${jeton}`, 'Content-Type': 'application/json' },
      body: opts.body ? JSON.stringify(opts.body) : undefined,
    });
    const type = r.headers.get('content-type') || '';
    if (type.includes('pdf')) {
      const octets = new Uint8Array(await r.arrayBuffer());
      const empreinte = await crypto.subtle.digest('SHA-256', octets);
      let b64 = '';
      for (let i = 0; i < octets.length; i += 0x8000) b64 += String.fromCharCode(...octets.slice(i, i + 0x8000));
      return { status: r.status, base64: btoa(b64), sha256: Array.from(new Uint8Array(empreinte))
        .map((o) => o.toString(16).padStart(2, '0')).join('') };
    }
    let corps = null;
    try { corps = await r.json(); } catch { corps = null; }
    return { status: r.status, corps };
  }, [API, chemin, options]);
}

async function basculerAcademie(page, motif) {
  await page.locator('button[aria-haspopup="listbox"]').first().click();
  await page.waitForTimeout(400);
  await page.locator('[role="option"] button', { hasText: motif }).first().click();
  await page.waitForTimeout(2500);
}

async function attendreTexte(page, motif, limite = 20000) {
  const fin = Date.now() + limite;
  let texte = '';
  while (Date.now() < fin) {
    texte = await bodyText(page);
    if (motif.test(texte)) return texte;
    await page.waitForTimeout(400);
  }
  return texte;
}

async function ouvrirGabarits(page, role) {
  await page.goto(`${BASE}/${role}/document-templates`, { waitUntil: 'domcontentloaded' });
  return attendreTexte(page, /Gabarit du diplôme/);
}

/** Téléverse un fichier depuis l'espace d'un type ; renvoie le texte de la page. */
async function televerser(page, kind, fichier) {
  const espace = page.locator(`[data-testid="kind-${kind}"]`);
  await espace.locator('button', { hasText: /Téléverser|Remplacer/ }).first().click();
  await page.locator('[data-testid="template-file"]').setInputFiles(path.join(FILES, fichier));
  await page.waitForTimeout(300);
  const dialogue = page.locator('div.relative', { hasText: /Téléverser le gabarit/ }).last();
  await dialogue.locator('button', { hasText: /^Téléverser$/ }).click();
  await page.waitForTimeout(2500);
  return bodyText(page);
}

/** Ajoute un champ dans l'éditeur et règle sa géométrie (mm). */
async function placer(page, nom, geo) {
  await page.selectOption('#add-field', nom);
  await page.locator('button[title="Placer ce champ"]').click();
  await page.waitForTimeout(200);
  // Dimensions d'abord : une position est ramenée dans la page selon la
  // largeur EN COURS, comme pour un utilisateur.
  const champs = [['Largeur (mm)', geo.w], ['Hauteur (mm)', geo.h], ['X (mm)', geo.x], ['Y (mm)', geo.y]];
  for (const [libelle, valeur] of champs) {
    if (valeur === undefined) continue;
    const input = page.locator('label', { hasText: libelle }).locator('input');
    await input.fill(String(valeur));
  }
}

/** Glisse la zone d'un champ de (dx, dy) millimètres, à la souris. */
async function glisser(page, nom, dxMm, dyMm, pageMm) {
  const surface = await page.locator('[data-testid="template-surface"]').boundingBox();
  const zone = await page.locator(`[data-testid="zone-${nom}"]`).boundingBox();
  const x = zone.x + zone.width / 2;
  const y = zone.y + zone.height / 2;
  await page.mouse.move(x, y);
  await page.mouse.down();
  const tx = x + (dxMm / pageMm.w) * surface.width;
  const ty = y + (dyMm / pageMm.h) * surface.height;
  await page.mouse.move(tx, ty, { steps: 12 });
  await page.mouse.up();
  await page.waitForTimeout(200);
}

const valeurDe = async (page, libelle) =>
  Number(await page.locator('label', { hasText: libelle }).locator('input').inputValue());

async function choisirEleve(page, nomEleve) {
  await page.locator('button', { hasText: 'Rechercher un élève' }).first().click();
  await page.waitForTimeout(400);
  const champ = page.locator('input[placeholder^="Rechercher"]').last();
  await champ.pressSequentially(nomEleve.slice(0, 7), { delay: 45 });
  await page.waitForTimeout(700);
  await page.locator('button', { hasText: nomEleve }).last().click();
  await page.waitForTimeout(600);
}

async function produireEtDelivrer(page, role, kind, nomEleve, nomFichier) {
  await page.goto(`${BASE}/${role}/official-documents`, { waitUntil: 'domcontentloaded' });
  await attendreTexte(page, /Documents officiels/);
  await page.locator('button', { hasText: 'Produire un document' }).first().click();
  await page.waitForTimeout(500);
  await page.selectOption('#doc-kind', kind);
  await choisirEleve(page, nomEleve);
  await page.waitForSelector('[data-testid="document-check"]', { timeout: 15000 });
  const verification = await page.locator('[data-testid="document-check"]').innerText();
  await page.locator('input[type=checkbox]').first().check();
  await shot(page, `${nomFichier}-verification`);
  const avant = (await api(page, '/documents/')).corps.map((d) => d.id);
  await page.locator('button', { hasText: /^Produire$/ }).first().click();
  await page.waitForTimeout(2500);
  const apres = (await api(page, '/documents/')).corps;
  const doc = apres.find((d) => !avant.includes(d.id));
  if (!doc) return { verification, doc: null };
  await page.locator('tr', { hasText: nomEleve }).filter({ hasText: /non délivré/ }).first()
    .locator('button', { hasText: 'Délivrer' }).click();
  await page.waitForTimeout(2500);
  const delivre = (await api(page, '/documents/')).corps.find((d) => d.id === doc.id);
  const fichier = await api(page, `/documents/${doc.id}/download/`);
  fs.writeFileSync(path.join(SHOTS, `${nomFichier}.pdf`), Buffer.from(fichier.base64, 'base64'));
  return { verification, doc: delivre, fichier };
}

/* ══════════════════════════════════════════════════════════════════════ */
log('=== Gabarits officiels téléversés — parcours navigateur ===');
const RESULTATS = {};

/* ─── 1-2. Super administrateur, FEBA FHA : diplôme PDF ─────────────── */
log('\n--- 1. FEBA French Heritage Academy : diplôme PDF ---');
{
  const { browser, page } = await session('superadmin@feba.bj', 'SuperAdmin@2024');
  await page.goto(BASE + '/superadmin/dashboard', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2500);
  await basculerAcademie(page, 'French Heritage');
  let texte = await ouvrirGabarits(page, 'superadmin');
  check(/Gabarit du diplôme/.test(texte) && /Gabarit du certificat/.test(texte), 'deux espaces distincts');
  check(/FEBA French Heritage Academy/.test(texte), "l'écran annonce l'académie FHA");

  texte = await televerser(page, 'diploma', 'faux_png.png');
  check(/ne correspond pas au contenu réel/.test(texte), 'faux PNG (PDF renommé) refusé', 'message affiché');
  await page.keyboard.press('Escape');
  texte = await televerser(page, 'diploma', 'corrompu.pdf');
  check(/PDF lisible|corrompu/.test(texte), 'PDF corrompu refusé');
  await page.keyboard.press('Escape');
  await page.waitForTimeout(500);

  texte = await televerser(page, 'diploma', 'diplome_test_vectoriel.pdf');
  check(/Fichier accepté \(version 1\)/.test(texte), 'diplôme PDF accepté (version 1)');
  await page.waitForSelector('[data-testid="template-surface"] img', { timeout: 15000 });
  check(true, "l'éditeur s'ouvre sur le fond réel du PDF");

  const pageMm = { w: 297, h: 210 };
  await placer(page, 'student_name', {});
  const y0 = await valeurDe(page, 'Y (mm)');
  await glisser(page, 'student_name', 0, 36, pageMm);
  const y1 = await valeurDe(page, 'Y (mm)');
  check(Math.abs(y1 - y0 - 36) < 1.5, 'zone du nom déplacée à la souris, en millimètres', `${y0} → ${y1} mm`);
  // La zone glissée reste sélectionnée : ses champs numériques s'affinent.
  for (const [label, val] of [['X (mm)', 53.5], ['Y (mm)', 68], ['Largeur (mm)', 190], ['Hauteur (mm)', 18]]) {
    await page.locator('label', { hasText: label }).locator('input').fill(String(val));
  }
  await placer(page, 'academy_name', { x: 60, y: 92, w: 177, h: 10 });
  await placer(page, 'issue_date', { x: 212, y: 160, w: 63, h: 9 });
  await placer(page, 'document_number', { x: 200, y: 180, w: 80, h: 8 });
  await shot(page, '01-editeur-diplome');
  await page.locator('button', { hasText: /^Aperçu$/ }).click();
  await page.waitForSelector('img[alt="Aperçu du document"]', { timeout: 20000 });
  await shot(page, '02-apercu-serveur');
  check(true, "aperçu rendu par le serveur affiché dans l'éditeur");
  await page.locator('button', { hasText: 'Enregistrer et vérifier' }).click();
  texte = await attendreTexte(page, /Valide, prêt à être activé/);
  check(/Valide, prêt à être activé/.test(texte), 'vérification réussie : « Valide, prêt à être activé »');
  await page.locator('[data-testid="kind-diploma"] button', { hasText: /^Activer$/ }).click();
  texte = await attendreTexte(page, /Actif — utilisé pour les documents/);
  check(/Actif — utilisé pour les documents/.test(texte), 'gabarit activé');
  await shot(page, '03-diplome-actif');

  const eleves = (await api(page, '/students/?page_size=5')).corps;
  const eleve = (eleves.results || eleves)[0];
  const nom = eleve.full_name || `${eleve.first_name} ${eleve.last_name}`;
  const r = await produireEtDelivrer(page, 'superadmin', 'diploma', nom, 'fha-diplome-v1');
  check(/Gabarit téléversé de l'académie — version 1/.test(r.verification), 'la production annonce le gabarit v1 de FHA');
  check(r.doc && r.doc.status === 'issued', 'diplôme délivré', r.doc?.number);
  check(r.fichier && r.fichier.sha256 === r.doc.file_sha256, 'empreinte du PDF téléchargé = empreinte affichée');
  RESULTATS.fha = { nom, doc: r.doc, sha: r.fichier?.sha256 };

  /* ─── 4. Remplacement ─── */
  log('\n--- 4. Remplacement du gabarit du diplôme FHA ---');
  texte = await ouvrirGabarits(page, 'superadmin');
  await page.locator('[data-testid="kind-diploma"] button', { hasText: 'Remplacer' }).click();
  await page.locator('[data-testid="template-file"]').setInputFiles(path.join(FILES, 'diplome_test_vectoriel.pdf'));
  const reprise = page.locator('label', { hasText: 'Reprendre la configuration de la version 1' }).locator('input');
  check(await reprise.isChecked(), 'reprise de la configuration proposée et cochée');
  await page.locator('div.relative', { hasText: /Téléverser le gabarit/ }).last()
    .locator('button', { hasText: /^Téléverser$/ }).click();
  await page.waitForSelector('[data-testid="template-surface"]', { timeout: 15000 });
  texte = await bodyText(page);
  check(/version n° 2/.test(texte), "l'éditeur s'ouvre sur la version 2");
  await page.locator('button', { hasText: 'Enregistrer et vérifier' }).click();
  texte = await attendreTexte(page, /remplacement en préparation/);
  check(/remplacement en préparation/.test(texte), 'état « Actif — remplacement en préparation »');
  await page.locator('[data-testid="kind-diploma"] button', { hasText: /^Activer$/ }).click();
  await page.waitForTimeout(2000);
  const etat = (await api(page, '/documents/academy-templates/')).corps.kinds.diploma;
  check(etat.active?.version === 2, 'la version 2 est active');
  check(etat.versions.find((v) => v.version === 1)?.status === 'archived', 'la version 1 est archivée');
  const relu = await api(page, `/documents/${RESULTATS.fha.doc.id}/download/`);
  check(relu.sha256 === RESULTATS.fha.sha, 'le diplôme déjà délivré est inchangé (même empreinte)');
  await shot(page, '04-remplacement');
  await browser.close();
}

/* ─── 3. FEBA (Cotonou) : certificat PNG portrait ───────────────────── */
log('\n--- 3. FEBA (Cotonou) : certificat PNG portrait ---');
{
  const { browser, page } = await session('superadmin@feba.bj', 'SuperAdmin@2024');
  await page.goto(BASE + '/superadmin/dashboard', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2500);
  await basculerAcademie(page, 'Faith & Excellence');
  let texte = await ouvrirGabarits(page, 'superadmin');
  check(/Faith & Excellence/.test(texte), "l'écran annonce l'académie de Cotonou");
  check(!/diplome_test_vectoriel/.test(texte), "aucun gabarit de FHA n'apparaît sur FEBA");
  texte = await televerser(page, 'certificate', 'certificat_test_portrait.png');
  check(/Fichier accepté/.test(texte), 'certificat PNG accepté');
  await page.waitForSelector('[data-testid="template-surface"] img', { timeout: 15000 });
  check(/210 × 297 mm/.test(await bodyText(page)), 'page A4 portrait déduite de l\'image');
  await placer(page, 'student_name', { x: 25, y: 108, w: 160, h: 18 });
  await placer(page, 'class_name', { x: 25, y: 140, w: 75, h: 10 });
  await placer(page, 'school_year', { x: 110, y: 140, w: 75, h: 10 });
  await placer(page, 'certificate_purpose', { x: 25, y: 170, w: 160, h: 12 });
  await placer(page, 'document_number', { x: 110, y: 270, w: 80, h: 8 });
  await page.locator('label', { hasText: 'Objet du certificat' }).first().locator('input')
    .fill('Certificat délivré pour servir et valoir ce que de droit');
  await page.locator('button', { hasText: 'Enregistrer et vérifier' }).click();
  texte = await attendreTexte(page, /Valide, prêt à être activé/);
  check(/Valide, prêt à être activé/.test(texte), 'certificat vérifié');
  await page.locator('[data-testid="kind-certificate"] button', { hasText: /^Activer$/ }).click();
  await attendreTexte(page, /Actif — utilisé pour les documents/);
  await shot(page, '05-feba-certificat-actif');

  const eleves = (await api(page, '/students/?page_size=5')).corps;
  const eleve = (eleves.results || eleves)[0];
  const nom = eleve.full_name || `${eleve.first_name} ${eleve.last_name}`;
  const r = await produireEtDelivrer(page, 'superadmin', 'certificate', nom, 'feba-certificat-v1');
  check(r.doc && r.doc.status === 'issued', 'certificat FEBA délivré', r.doc?.number);
  check(/-CER-/.test(r.doc?.number || ''), 'numéro de certificat', r.doc?.number);
  RESULTATS.feba = { nom, doc: r.doc, template: (await api(page, '/documents/academy-templates/')).corps.kinds.certificate.active.id };
  await browser.close();
}

/* ─── 5. Isolation : administrateur FHA ─────────────────────────────── */
log('\n--- 5. Administrateur FEBA FHA ---');
{
  const { browser, page } = await session('admin@febafha.org', 'Admin@2024');
  const texte = await ouvrirGabarits(page, 'admin');
  check(/FEBA French Heritage Academy/.test(texte), 'son académie, et elle seule');
  const liste = (await api(page, '/documents/academy-templates/')).corps;
  check(liste.kinds.certificate.state === 'absent', "le certificat de Cotonou n'apparaît pas chez FHA");
  for (const suffixe of ['', 'background/', 'original/']) {
    const r = await api(page, `/documents/academy-templates/${RESULTATS.feba.template}/${suffixe}`);
    check(r.status === 404, `gabarit de Cotonou, ${suffixe || 'détail'} : 404`, `HTTP ${r.status}`);
  }
  const r = await api(page, `/documents/academy-templates/${RESULTATS.feba.template}/disable/`, { method: 'POST' });
  check(r.status === 404, 'désactiver le gabarit de Cotonou : 404', `HTTP ${r.status}`);
  const doc = await api(page, `/documents/${RESULTATS.feba.doc.id}/download/`);
  check(doc.status === 404, 'télécharger le certificat de Cotonou : 404', `HTTP ${doc.status}`);
  await shot(page, '06-admin-fha');
  await browser.close();
}

// Les 400 (fichiers refusés exprès) et 404 (accès croisés exprès) sont
// les réponses ATTENDUES de ce scénario ; tout le reste compte : exception
// JavaScript, réponse 5xx, autre message d'erreur.
const pertinentes = consoleErrors.filter((e) =>
  !/favicon|ResizeObserver/.test(e)
  && !/Failed to load resource: the server responded with a status of (400|404)/.test(e));
check(pertinentes.length === 0, 'aucune erreur de console', pertinentes.slice(0, 3).join(' | '));
log(`\n${FAIL === 0 ? 'SUCCÈS' : `ÉCHECS : ${FAIL}`}`);
fs.writeFileSync(path.join(SHOTS, 'gabarits-rapport.txt'), OUT.join('\n') + '\n');
fs.writeFileSync(path.join(SHOTS, 'gabarits-resultats.json'), JSON.stringify(RESULTATS, null, 2));
process.exit(FAIL === 0 ? 0 : 1);
