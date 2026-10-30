// Charge contrôlée : N participants (enseignant + élèves, salle_et_jetons.py
// avec PNM_E2E_ELEVES=N-1) publient micro et caméra simulés pendant DUREE_MS.
// Mesure par participant : temps d'entrée, pistes audio / vidéo reçues
// (attendu N-1 chacune), paquets perdus, gigue, aller-retour ICE.
//
//   PNM_URLS=urls.json DUREE_MS=60000 node e2e/plugnmeet/charge.mjs
import { chromium } from 'playwright-core';
import fs from 'fs';

const urls = JSON.parse(fs.readFileSync(process.env.PNM_URLS, 'utf8'));
const DUREE_MS = Number(process.env.DUREE_MS || 60000);
const SEUIL = 20000;
const cles = Object.keys(urls).filter(k => k !== 'room_id');

const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  headless: true,
  args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream',
         '--autoplay-policy=no-user-gesture-required'],
});
const espion = () => {
  const Orig = window.RTCPeerConnection;
  window.__pcs = [];
  window.RTCPeerConnection = function (...a) { const pc = new Orig(...a); window.__pcs.push(pc); return pc; };
  window.RTCPeerConnection.prototype = Orig.prototype;
  Object.setPrototypeOf(window.RTCPeerConnection, Orig);
};

async function entrer(nom) {
  const t0 = Date.now();
  const ctx = await browser.newContext({ permissions: ['camera', 'microphone'], viewport: { width: 1280, height: 800 } });
  await ctx.addInitScript(espion);
  const page = await ctx.newPage();
  await page.goto(urls[nom], { waitUntil: 'domcontentloaded' });
  await page.getByText('Activer le microphone et la caméra').click({ timeout: 30000 });
  await page.getByRole('button', { name: 'Rejoindre' }).click({ timeout: 30000 });
  await page.getByText(/\((moi|me)\)/).first().waitFor({ timeout: 45000 });
  const entree_ms = Date.now() - t0;
  for (const libelle of ['Activer le microphone', 'Activer la caméra']) {
    try {
      await page.getByRole('button', { name: libelle, exact: true }).click({ timeout: 15000 });
    } catch (e) {
      // Diagnostic : état réel de la page au moment de l'échec.
      await page.screenshot({ path: `${process.env.OUT || '.'}/charge-echec-${nom}.png` });
      const boutons = await page.locator('button').evaluateAll(els => els.map(x => (x.getAttribute('aria-label') || x.innerText || '').trim()).filter(Boolean));
      throw new Error(`${nom} : « ${libelle} » introuvable ; boutons : ${boutons.slice(0, 25).join(' | ')}`);
    }
    await page.waitForTimeout(1500);
    // Avec beaucoup de vignettes, le menu des périphériques peut être recouvert :
    // clic forcé, sinon le périphérique par défaut reste sélectionné.
    if (libelle === 'Activer le microphone')
      await page.locator('button', { hasText: 'Fake Default Audio Input' }).click({ timeout: 15000, force: true }).catch(() => {});
    await page.getByRole('button', { name: 'Partager', exact: true }).click({ timeout: 15000, force: true });
    await page.waitForTimeout(1500);
  }
  await page.getByRole('button', { name: 'Réactiver le microphone' }).click({ timeout: 10000 }).catch(() => {});
  return { nom, page, entree_ms };
}

async function mesure(p) {
  return p.page.evaluate(async seuil => {
    const r = { audio: 0, video: 0, perdus: 0, recus: 0, gigue_ms: [], rtt_ms: [] };
    for (const pc of window.__pcs || []) {
      if (pc.connectionState === 'closed') continue;
      (await pc.getStats()).forEach(s => {
        if (s.type === 'inbound-rtp' && s.kind) {
          if ((s.bytesReceived || 0) > seuil) r[s.kind] += 1;
          r.perdus += s.packetsLost || 0; r.recus += s.packetsReceived || 0;
          if (s.kind === 'audio' && s.jitter != null) r.gigue_ms.push(s.jitter * 1000);
        }
        if (s.type === 'candidate-pair' && s.nominated && s.currentRoundTripTime != null) r.rtt_ms.push(s.currentRoundTripTime * 1000);
      });
    }
    return r;
  }, SEUIL);
}

const participants = [];
// Entrées successives, comme une classe. Un échec d'automatisation sur un
// participant est consigné (capture) sans interrompre la mesure des autres.
const echecs_entree = [];
for (const nom of cles) {
  try { participants.push(await entrer(nom)); }
  catch (e) { echecs_entree.push({ nom, erreur: e.message.split('\n')[0].slice(0, 300) }); }
}
await new Promise(r => setTimeout(r, DUREE_MS));
const n = participants.length;
const lignes = [];
for (const p of participants) {
  const m = await mesure(p);
  const moy = a => a.length ? +(a.reduce((x, y) => x + y, 0) / a.length).toFixed(1) : null;
  lignes.push({ nom: p.nom, entree_ms: p.entree_ms, audio_recus: m.audio, video_recues: m.video,
                perte_pct: m.recus ? +(100 * m.perdus / (m.perdus + m.recus)).toFixed(2) : null,
                gigue_audio_ms: moy(m.gigue_ms), rtt_ms: moy(m.rtt_ms) });
}
const complets = lignes.filter(l => l.audio_recus >= n - 1 && l.video_recues >= n - 1).length;
console.log(JSON.stringify({ participants: n, complets, echecs_entree, lignes }, null, 1));
console.log(complets === n ? `RÉUSSITE : ${n}/${n} participants reçoivent les ${n - 1} autres (audio et vidéo)`
                          : `ÉCHEC : ${complets}/${n} participants complets`);
await browser.close();
process.exit(complets === n ? 0 : 1);
