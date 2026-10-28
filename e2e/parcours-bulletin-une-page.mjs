/**
 * Bulletin sur UNE page — vrai navigateur, session réelle.
 *
 *   1. L'administrateur ouvre « Bulletins » et clique « Aperçu » sur une
 *      ligne : le PDF reçu par le navigateur est enregistré tel quel.
 *   2. Il régénère des bulletins par l'API de l'application (même session,
 *      même proxy) et télécharge les PDF officiels servis par /media/.
 *   3. Les fichiers sont écrits dans E2E_SHOTS ; le lanceur compte leurs
 *      pages avec pypdf (exactement une attendue) — pas une réponse 200.
 *
 * Variables : E2E_BASE_URL, CHROMIUM_PATH, E2E_SHOTS.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from './playwright.mjs';

const BASE = process.env.E2E_BASE_URL || 'http://127.0.0.1:5173';
const SHOTS = process.env.E2E_SHOTS || fileURLToPath(new URL('./captures', import.meta.url));
const OUT = path.join(SHOTS, 'bulletins');
fs.mkdirSync(OUT, { recursive: true });

let FAIL = 0;
const check = (ok, label, detail = '') => {
  if (!ok) FAIL++;
  console.log(`${ok ? '  OK  ' : '  ÉCHEC'} ${label}${detail ? ' — ' + detail : ''}`);
};

const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || '/opt/pw-browsers/chromium' });
const page = await (await browser.newContext({ viewport: { width: 1440, height: 950 } })).newPage();
const errors = [];
page.on('pageerror', (e) => errors.push(e.message));

await page.goto(BASE + '/login', { waitUntil: 'networkidle' });
await page.evaluate(() => localStorage.clear());
await page.goto(BASE + '/login', { waitUntil: 'networkidle' });
await page.fill('input[type=email]', 'admin@feba.bj');
await page.fill('input[type=password]', 'Admin@2024');
await page.click('button[type=submit]');
await page.waitForFunction(() => !location.pathname.includes('/login'), null, { timeout: 60000 });

console.log('\n═══ 1. APERÇU DEPUIS L\'ÉCRAN « BULLETINS » ═══');
await page.goto(BASE + '/admin/bulletins', { waitUntil: 'networkidle' });
const previewButton = page.locator('button[title="Aperçu du bulletin"]').first();
await previewButton.waitFor({ timeout: 30000 });
const previewResponse = page.waitForResponse((r) => r.url().includes('/api/bulletins/preview/') && r.status() === 200,
  { timeout: 60000 });
await previewButton.click();
const response = await previewResponse;
const previewPdf = await response.body();
fs.writeFileSync(path.join(OUT, 'apercu.pdf'), previewPdf);
check(response.headers()['content-type'] === 'application/pdf', 'aperçu : PDF reçu par le navigateur',
  `${previewPdf.length} octets`);
await page.screenshot({ path: path.join(SHOTS, 'bulletin-apercu.png') });

console.log('\n═══ 2. GÉNÉRATION ET TÉLÉCHARGEMENT DES PDF OFFICIELS ═══');
const results = await page.evaluate(async () => {
  const token = JSON.parse(localStorage.getItem('feba-auth') || '{}')?.state?.accessToken;
  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };
  const list = await (await fetch('/api/bulletins/?page_size=200', { headers })).json();
  const rows = (Array.isArray(list) ? list : list.results || []).filter((b) => b.period !== 'annual').slice(0, 6);
  const out = [];
  for (const b of rows) {
    const r = await fetch('/api/bulletins/generate/', {
      method: 'POST', headers,
      body: JSON.stringify({ student_id: b.student, school_year_id: b.school_year, period: b.period }),
    });
    const data = await r.json();
    let bytes = null;
    if (data.pdf_url) {
      const file = await fetch(data.pdf_url, { headers });
      const buf = new Uint8Array(await file.arrayBuffer());
      let bin = '';
      for (let i = 0; i < buf.length; i += 1) bin += String.fromCharCode(buf[i]);
      bytes = btoa(bin);
    }
    out.push({ status: r.status, student: b.student_name || b.student, period: b.period, bytes });
  }
  return out;
});
check(results.length > 0, 'bulletins disponibles dans la base de démonstration', `${results.length}`);
results.forEach((r, i) => {
  check(r.status === 201 && r.bytes, `génération ${i + 1} (${r.period})`, `HTTP ${r.status}`);
  if (r.bytes) fs.writeFileSync(path.join(OUT, `officiel-${i + 1}.pdf`), Buffer.from(r.bytes, 'base64'));
});

check(errors.length === 0, 'aucune erreur JavaScript', errors.slice(0, 2).join(' | '));
await browser.close();
console.log(`\n${FAIL ? `ÉCHEC : ${FAIL} point(s)` : 'Tous les points sont vérifiés (pages comptées par le lanceur).'}`);
process.exit(FAIL ? 1 : 0);
