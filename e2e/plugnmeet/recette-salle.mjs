// Recette d'une classe : un enseignant et deux élèves dans une salle plugNmeet
// créée par le code FEBA (salle_et_jetons.py, PNM_E2E_ELEVES=2). Caméra et
// micro simulés par Chrome ; chaque critère est mesuré (getStats, DOM).
//
//   PNM_E2E_ELEVES=2 python salle_et_jetons.py > urls.json
//   PNM_URLS=urls.json OUT=captures FIN_CMD="…salle_et_jetons.py --fin" \
//     node e2e/plugnmeet/recette-salle.mjs
//
// Vérifie : réception audio ET vidéo de chacun depuis les deux autres
// (pistes entrantes distinctes), coupure puis reprise du micro et de la
// caméra d'un élève, partage d'écran démarré / arrêté / repris, chat dans
// les deux sens, tableau blanc ouvert par l'enseignant et vu par les élèves,
// commandes de modération absentes chez l'élève, fin de réunion par FEBA.
import { chromium } from 'playwright-core';
import { execSync } from 'child_process';
import fs from 'fs';

const urls = JSON.parse(fs.readFileSync(process.env.PNM_URLS, 'utf8'));
const OUT = process.env.OUT || '.';
const SEUIL = 20000;  // octets

const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  headless: true,
  args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream',
         '--autoplay-policy=no-user-gesture-required',
         '--auto-select-desktop-capture-source=Entire screen', '--auto-accept-this-tab-capture',
         ...(process.env.CHROME_EXTRA_ARGS ? process.env.CHROME_EXTRA_ARGS.split('|') : [])],
});

const espion = () => {
  const Orig = window.RTCPeerConnection;
  window.__pcs = [];
  window.RTCPeerConnection = function (...a) { const pc = new Orig(...a); window.__pcs.push(pc); return pc; };
  window.RTCPeerConnection.prototype = Orig.prototype;
  Object.setPrototypeOf(window.RTCPeerConnection, Orig);
};

async function entrer(nom, url) {
  const ctx = await browser.newContext({ permissions: ['camera', 'microphone'], viewport: { width: 1280, height: 800 } });
  await ctx.addInitScript(espion);
  const page = await ctx.newPage();
  const navigations = [];
  page.on('request', r => { if (r.isNavigationRequest() && r.frame() === page.mainFrame()) navigations.push(r.url()); });
  await page.goto(url, { waitUntil: 'domcontentloaded' });
  await page.getByText('Activer le microphone et la caméra').click({ timeout: 20000 });
  await page.getByRole('button', { name: 'Rejoindre' }).click({ timeout: 20000 });
  await page.getByText(/\((moi|me)\)/).first().waitFor({ timeout: 30000 });
  await page.waitForTimeout(3000);
  for (const libelle of ['Activer le microphone', 'Activer la caméra']) {
    await page.getByRole('button', { name: libelle, exact: true }).click({ timeout: 10000 });
    await page.waitForTimeout(1500);
    if (libelle === 'Activer le microphone') {
      await page.locator('button', { hasText: 'Fake Default Audio Input' }).click({ timeout: 10000 });
    }
    await page.getByRole('button', { name: 'Partager', exact: true }).click({ timeout: 10000 });
    await page.waitForTimeout(2000);
  }
  // mute_on_start : le micro arrive coupé.
  await page.getByRole('button', { name: 'Réactiver le microphone' }).click({ timeout: 10000 }).catch(() => {});
  return { nom, page, navigations };
}

// Pistes entrantes ayant reçu des données, et octets émis par type.
async function mesure(p) {
  return p.page.evaluate(async () => {
    const r = { entrant: { audio: [], video: [] }, sortant: { audio: 0, video: 0 },
                videos: [...document.querySelectorAll('video')].filter(v => v.videoWidth > 0 && !v.paused).length };
    for (const pc of window.__pcs || []) {
      if (pc.connectionState === 'closed') continue;
      (await pc.getStats()).forEach(s => {
        if (s.type === 'inbound-rtp' && s.kind) r.entrant[s.kind].push({ id: s.trackIdentifier || s.id, octets: s.bytesReceived || 0 });
        if (s.type === 'outbound-rtp' && s.kind) r.sortant[s.kind] += s.bytesSent || 0;
      });
    }
    return r;
  });
}
const actives = (m, kind) => m.entrant[kind].filter(t => t.octets > SEUIL).length;
const croissance = (avant, apres, kind) => {
  // Octets reçus depuis la mesure précédente, par piste.
  const a = Object.fromEntries(avant.entrant[kind].map(t => [t.id, t.octets]));
  return apres.entrant[kind].map(t => t.octets - (a[t.id] || 0));
};
const attendre = ms => new Promise(r => setTimeout(r, ms));
const etape = async (journal, nom, fn) => {
  try { journal[nom] = await fn(); } catch (e) { journal[nom] = 'ÉCHEC : ' + e.message.split('\n')[0].slice(0, 160); }
};

const res = { criteres: {}, journal: {} };
const c = res.criteres, j = res.journal;
const prof = await entrer('enseignant', urls.enseignant);
await attendre(4000);
const e1 = await entrer('eleve1', urls.eleve);
const e2 = await entrer('eleve2', urls.eleve2);
const tous = [prof, e1, e2];
await attendre(20000);

// 1. Audio et vidéo : chacun reçoit des deux autres.
const m0 = {};
for (const p of tous) { m0[p.nom] = await mesure(p); await p.page.screenshot({ path: `${OUT}/recette-${p.nom}.png` }); }
res.depart = Object.fromEntries(tous.map(p => [p.nom, { audio: actives(m0[p.nom], 'audio'), video: actives(m0[p.nom], 'video'), videos_affichees: m0[p.nom].videos }]));
for (const p of tous) {
  c[`${p.nom} : reçoit l'audio des deux autres`] = actives(m0[p.nom], 'audio') >= 2;
  c[`${p.nom} : reçoit la vidéo des deux autres`] = actives(m0[p.nom], 'video') >= 2;
}

// 2. Micro de l'élève 1 coupé puis rétabli : ses octets audio émis s'arrêtent puis reprennent.
await etape(j, 'micro élève 1', async () => {
  const a = await mesure(e1);
  await e1.page.getByRole('button', { name: /^(Couper|Désactiver) le (micro|microphone)$/ }).first().click({ timeout: 8000 });
  await attendre(8000);
  const b = await mesure(e1);
  await e1.page.getByRole('button', { name: /^(Réactiver|Activer) le (micro|microphone)$/ }).first().click({ timeout: 8000 });
  await attendre(8000);
  const d = await mesure(e1);
  return { coupe: b.sortant.audio - a.sortant.audio, repris: d.sortant.audio - b.sortant.audio };
});
if (typeof j['micro élève 1'] === 'object') {
  c["micro coupé : l'élève 1 n'émet presque plus"] = j['micro élève 1'].coupe < SEUIL / 2;
  c["micro réactivé : l'élève 1 émet de nouveau"] = j['micro élève 1'].repris > SEUIL;
} else c["micro coupé puis réactivé (élève 1)"] = false;

// 3. Caméra de l'élève 1 coupée puis rétablie : vue par l'enseignant.
await etape(j, 'caméra élève 1', async () => {
  const avant = (await mesure(prof)).videos;
  await e1.page.getByRole('button', { name: /^(Désactiver|Couper|Arrêter) la caméra$/ }).first().click({ timeout: 8000 });
  await attendre(6000);
  const pendant = (await mesure(prof)).videos;
  await e1.page.getByRole('button', { name: 'Activer la caméra', exact: true }).click({ timeout: 8000 });
  await attendre(1500);
  await e1.page.getByRole('button', { name: 'Partager', exact: true }).click({ timeout: 8000 }).catch(() => {});
  await attendre(8000);
  return { avant, pendant, apres: (await mesure(prof)).videos };
});
if (typeof j['caméra élève 1'] === 'object') {
  const k = j['caméra élève 1'];
  c["caméra coupée : l'enseignant voit une vidéo de moins"] = k.pendant < k.avant;
  c["caméra réactivée : l'enseignant la revoit"] = k.apres >= k.avant;
} else c["caméra coupée puis réactivée (élève 1)"] = false;

// 4. Partage d'écran : démarré, arrêté, repris — vu par les deux élèves.
await etape(j, "partage d'écran", async () => {
  const base = [(await mesure(e1)).videos, (await mesure(e2)).videos];
  await prof.page.getByRole('button', { name: "Partager l'écran" }).click({ timeout: 8000 });
  await attendre(8000);
  const on = [(await mesure(e1)).videos, (await mesure(e2)).videos];
  await prof.page.getByRole('button', { name: /^(Arrêter|Stopper) (le partage|de partager)/ }).first().click({ timeout: 8000 });
  await attendre(6000);
  const off = [(await mesure(e1)).videos, (await mesure(e2)).videos];
  await prof.page.getByRole('button', { name: "Partager l'écran" }).click({ timeout: 8000 });
  await attendre(8000);
  const encore = [(await mesure(e1)).videos, (await mesure(e2)).videos];
  // Arrêt final : le partage occupe l'affichage principal (tableau blanc, chat).
  await prof.page.getByRole('button', { name: /^(Arrêter|Stopper) (le partage|de partager)/ }).first().click({ timeout: 8000 });
  await attendre(4000);
  return { base, on, off, encore };
});
if (typeof j["partage d'écran"] === 'object') {
  const k = j["partage d'écran"];
  c["partage d'écran reçu par les deux élèves"] = k.on.every((v, i) => v > k.base[i]);
  c["partage d'écran arrêté chez les deux élèves"] = k.off.every((v, i) => v < k.on[i]);
  c["partage d'écran repris"] = k.encore.every((v, i) => v > k.off[i]);
} else c["partage d'écran démarré / arrêté / repris"] = false;

// 5. Chat dans les deux sens.
await etape(j, 'chat', async () => {
  const ecrire = async (p, texte) => {
    if (await p.page.getByRole('button', { name: 'Afficher le chat' }).count())
      await p.page.getByRole('button', { name: 'Afficher le chat' }).click();
    const zone = p.page.locator('textarea:visible').filter({ hasNot: p.page.locator('[aria-hidden=true]') }).last();
    // fill() donne le focus : un clic serait intercepté par l'infobulle du bouton de chat.
    await zone.fill(texte, { timeout: 8000 });
    await zone.press('Enter');
  };
  const voit = async (p, texte) => {
    if (await p.page.getByRole('button', { name: 'Afficher le chat' }).count())
      await p.page.getByRole('button', { name: 'Afficher le chat' }).click();
    return p.page.getByText(texte).first().waitFor({ timeout: 10000 }).then(() => true, () => false);
  };
  await ecrire(prof, 'Bonjour la classe 314');
  const eleves = [await voit(e1, 'Bonjour la classe 314'), await voit(e2, 'Bonjour la classe 314')];
  await ecrire(e2, 'Bonjour madame 271');
  return { eleves_lisent_prof: eleves, prof_lit_eleve: await voit(prof, 'Bonjour madame 271') };
});
c['chat : les deux élèves lisent le message de l\'enseignant'] = j.chat?.eleves_lisent_prof?.every(Boolean) === true;
c['chat : l\'enseignant lit le message d\'un élève'] = j.chat?.prof_lit_eleve === true;

// 6. Tableau blanc ouvert par l'enseignant, affiché chez les élèves.
await etape(j, 'tableau blanc', async () => {
  await prof.page.getByRole('button', { name: 'Afficher le tableau blanc' }).click({ timeout: 8000 });
  await attendre(8000);
  const vu = async p => (await p.page.locator('.excalidraw').count()) > 0;
  const r = { prof: await vu(prof), eleve1: await vu(e1), eleve2: await vu(e2) };
  await e1.page.screenshot({ path: `${OUT}/recette-eleve1-tableau.png` });
  return r;
});
c['tableau blanc affiché chez les deux élèves'] = j['tableau blanc']?.eleve1 === true && j['tableau blanc']?.eleve2 === true;

// 7. Rôles : modération chez l'enseignant seulement.
const MODERATION = ['Terminer la réunion', 'Couper le micro de tous les participants',
                    'Gérer les salles de sous-commission', 'Activer les sondages', 'Paramètres de verrouillage de la réunion'];
// Présence dans la page, menus fermés compris : un élève n'a pas ces commandes du tout.
// Le menu « Plus d'options » est ouvert d'abord : certaines commandes n'existent
// dans la page qu'une fois le menu déployé.
const present = async (p, n) => {
  for (const role of ['button', 'menuitem'])
    if (await p.page.getByRole(role, { name: n, exact: true, includeHidden: true }).count()) return true;
  return (await p.page.getByText(n, { exact: true }).count()) > 0;
};
for (const p of [prof, e1]) {
  const m = p.page.getByRole('button', { name: 'Plus d’options' });
  if (await m.count()) { await m.first().click(); await attendre(1500); }
}
res.moderation = {
  enseignant: Object.fromEntries(await Promise.all(MODERATION.map(async n => [n, await present(prof, n)]))),
  eleve1: Object.fromEntries(await Promise.all(MODERATION.map(async n => [n, await present(e1, n)]))),
};
c['enseignant : commandes de modération présentes'] = Object.values(res.moderation.enseignant).every(Boolean);
c['élève : aucune commande de modération'] = Object.values(res.moderation.eleve1).every(v => !v);
c["élève : pas de bouton de partage d'écran"] = (await e1.page.getByRole('button', { name: "Partager l'écran" }).count()) === 0;

// 8. Fin de réunion décidée par FEBA, retour des trois vers FEBA.
if (process.env.FIN_CMD) {
  res.fin = JSON.parse(execSync(process.env.FIN_CMD).toString().trim().split('\n').pop());
  await attendre(8000);
  c['fin de réunion par FEBA'] = res.fin.actif_avant && res.fin.end_room && !res.fin.actif_apres;
  for (const p of tous) c[`${p.nom} : renvoyé vers la page FEBA de fin`] = /\/virtual-room\/\d+\/ended$/.test(p.navigations.slice(-1)[0] || '');
}

console.log(JSON.stringify(res, null, 1));
const echecs = Object.entries(c).filter(([, ok]) => !ok).map(([k]) => k);
console.log(echecs.length ? `ÉCHEC : ${echecs.join(' ; ')}` : `RÉUSSITE : ${Object.keys(c).length} critères`);
await browser.close();
process.exit(echecs.length ? 1 : 0);
