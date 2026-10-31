// Tableau blanc : téléversement, conversion, ajout, navigation jusqu'à la
// dernière page et synchronisation chez l'élève, pour chaque document de
// DOCS_DIR. PNM_URLS : JSON {enseignant, eleve}. Mesure le temps de conversion
// et les images de pages reçues par l'élève.
import { chromium } from 'playwright-core';
import fs from 'fs';
import path from 'path';

const urls = JSON.parse(fs.readFileSync(process.env.PNM_URLS, 'utf8'));
const OUT = process.env.OUT || '.';
const DOCS = process.env.DOCS_DIR;
const b = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  headless: true, args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'],
});
async function go(url) {
  const c = await b.newContext({ permissions: ['camera', 'microphone'], viewport: { width: 1400, height: 900 } });
  const p = await c.newPage();
  p.images = new Set(); p.echecs = [];
  p.on('response', r => {
    const u = r.url().split('?')[0];
    if (/page_\d+\.(png|jpg)/.test(u)) (r.ok() ? p.images : { add: x => p.echecs.push(x) }).add(u.split('/').slice(-2).join('/'));
  });
  await p.goto(url);
  // Selon la langue et le navigateur, l'apostrophe du libellé varie.
  await p.getByText(/Rejoindre en tant qu.auditeur/).click({ timeout: 30000 });
  await p.getByText(/\((moi|me)\)/).first().waitFor({ timeout: 30000 });
  await p.waitForTimeout(2000);
  return p;
}
const prof = await go(urls.enseignant), eleve = await go(urls.eleve);
await prof.getByRole('button', { name: 'Afficher le tableau blanc' }).click();
await prof.waitForTimeout(5000);
const pageCourante = p => p.locator('.wb-page-navigation select').inputValue().catch(() => null);
const nbPages = p => p.locator('.wb-page-navigation select option').count().catch(() => null);
const res = [];
for (const nom of fs.readdirSync(DOCS).sort()) {
  const r = { document: nom, attendu: Number((nom.match(/(\d+)p\./) || [])[1]) || 17 };
  try {
    await prof.locator('button', { hasText: 'Fichiers' }).first().click({ timeout: 8000, force: true });
    await prof.waitForTimeout(800);
    const t0 = Date.now();
    await prof.locator('input[type=file]').last().setInputFiles(path.join(DOCS, nom));
    await prof.getByText(nom, { exact: true }).first().waitFor({ timeout: 180000 });
    await prof.getByRole('button', { name: 'Ajouter au tableau blanc' }).waitFor({ timeout: 5000 });
    r.conversion_s = Math.round((Date.now() - t0) / 1000);
    await prof.getByText(nom, { exact: true }).first().click();
    await prof.getByRole('button', { name: 'Ajouter au tableau blanc' }).click({ timeout: 8000 });
    await prof.waitForTimeout(5000);
    // Le contenu présent déclenche un avertissement de changement : le confirmer.
    const ok = prof.getByRole('button', { name: /^(Oui|Continuer|Confirmer|OK)$/ });
    if (await ok.count()) { r.avertissement = true; await ok.first().click(); await prof.waitForTimeout(4000); }
    r.pages_prof = await nbPages(prof);
    let garde = 0;
    while (garde++ < 60 && !(await prof.getByRole('button', { name: 'Page suivante' }).isDisabled().catch(() => true))) {
      await prof.getByRole('button', { name: 'Page suivante' }).click({ force: true });
      await prof.waitForTimeout(700);
    }
    r.derniere_page_prof = await pageCourante(prof);
    await prof.waitForTimeout(4000);
    r.page_eleve = await eleve.locator('text=/Page \\d+/').first().innerText().catch(() => null);
    r.images_eleve = eleve.images.size;
    await eleve.screenshot({ path: `${OUT}/wb-eleve-${r.attendu}p.png` });
    r.ok = r.pages_prof === r.attendu && Number(r.derniere_page_prof) === r.attendu;
  } catch (e) {
    r.erreur = e.message.split('\n')[0].slice(0, 200);
    await prof.screenshot({ path: `${OUT}/wb-echec-${r.attendu}p.png` });
    await prof.keyboard.press('Escape');
    await prof.getByRole('button', { name: 'Fermer' }).last().click({ timeout: 2000, force: true }).catch(() => {});
    r.ok = false;
  }
  console.log(JSON.stringify(r));
}
console.log('ÉCHECS IMAGES ÉLÈVE', eleve.echecs.length);
await b.close();
