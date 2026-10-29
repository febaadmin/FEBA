// Classe virtuelle réelle : enseignant + élève dans une salle plugNmeet créée
// par le code FEBA (salle_et_jetons.py). Caméra et micro simulés par Chrome.
//
//   PNM_URLS=urls.json OUT=captures FIN_CMD="…salle_et_jetons.py --fin" \
//     node e2e/plugnmeet/deux-participants.mjs
//
// Vérifie, mesures WebRTC à l'appui (getStats) : entrée des deux rôles,
// audio et vidéo dans les deux sens, transport UDP, partage d'écran de
// l'enseignant, absence du partage chez l'élève, fin de réunion par FEBA et
// retour vers /virtual-room/<id>/ended. Code de sortie 1 si un critère échoue.
import { chromium } from 'playwright-core';
import { execSync } from 'child_process';
import fs from 'fs';

const urls = JSON.parse(fs.readFileSync(process.env.PNM_URLS, 'utf8'));
const OUT = process.env.OUT || '.';
const DUREE_MS = Number(process.env.DUREE_MS || 20000);
const masque = u => u.replace(/access_token=[^&]+/, 'access_token=<masqué>');

const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  headless: true,
  args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream',
         '--autoplay-policy=no-user-gesture-required',
         '--auto-select-desktop-capture-source=Entire screen', '--auto-accept-this-tab-capture',
         // Ex. « --host-resolver-rules=MAP meet.globalfeba.com 127.0.0.1:18443 » :
         // tester un domaine par un tunnel SSH avant sa bascule publique.
         ...(process.env.CHROME_EXTRA_ARGS ? process.env.CHROME_EXTRA_ARGS.split('|') : [])],
});

// Garde une référence à chaque RTCPeerConnection pour lire ses statistiques.
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
  const erreurs = [];
  const navigations = [];
  page.on('console', m => { if (m.type() === 'error') erreurs.push(m.text().slice(0, 200)); });
  page.on('request', r => { if (r.isNavigationRequest() && r.frame() === page.mainFrame()) navigations.push(masque(r.url())); });
  page.on('requestfailed', r => erreurs.push('requête échouée : ' + masque(r.url()).slice(0, 120)));
  await page.goto(url, { waitUntil: 'domcontentloaded' });
  await page.getByText('Activer le microphone et la caméra').click({ timeout: 20000 });
  await page.getByRole('button', { name: 'Rejoindre' }).click({ timeout: 20000 });
  // Sa propre entrée dans la liste : l'en-tête « Participants (n) » peut être
  // masqué par une notification.
  await page.getByText(/\((moi|me)\)/).first().waitFor({ timeout: 30000 });
  await page.waitForTimeout(3000);
  const etapes = [];
  // Micro puis caméra : fenêtre de choix du périphérique, puis « Partager ».
  for (const libelle of ['Activer le microphone', 'Activer la caméra']) {
    try {
      await page.getByRole('button', { name: libelle }).click({ timeout: 10000 });
      await page.waitForTimeout(1500);
      if (libelle === 'Activer le microphone') {
        await page.locator('button', { hasText: 'Fake Default Audio Input' }).click({ timeout: 10000 });
      }  // caméra : présélectionnée, « Partager » actif d'emblée
      await page.getByRole('button', { name: 'Partager', exact: true }).click({ timeout: 10000 });
      await page.waitForTimeout(2000);
      etapes.push(libelle + ' : OK');
    } catch (e) {
      etapes.push(libelle + ' : ÉCHEC');
      await page.screenshot({ path: `${OUT}/echec-${nom}-${libelle.replace(/\W+/g, '_')}.png` });
      await page.keyboard.press('Escape');
    }
  }
  // FEBA impose mute_on_start : le micro arrive coupé, l'utilisateur le réactive.
  try {
    await page.getByRole('button', { name: 'Réactiver le microphone' }).click({ timeout: 10000 });
    etapes.push('micro réactivé');
  } catch (e) { etapes.push('réactivation du micro : ÉCHEC'); }
  return { nom, page, erreurs, navigations, etapes };
}

async function mesure(p) {
  return p.page.evaluate(async () => {
    const videos = [...document.querySelectorAll('video')].filter(v => v.videoWidth > 0 && !v.paused).length;
    const r = { videos, entrant: { audio: 0, video: 0 }, sortant: { audio: 0, video: 0 }, transports: [] };
    for (const pc of window.__pcs || []) {
      if (pc.connectionState === 'closed') continue;
      const stats = await pc.getStats();
      const parId = {}; stats.forEach(s => { parId[s.id] = s; });
      stats.forEach(s => {
        if (s.type === 'inbound-rtp' && s.kind) r.entrant[s.kind] += s.bytesReceived || 0;
        if (s.type === 'outbound-rtp' && s.kind) r.sortant[s.kind] += s.bytesSent || 0;
        if (s.type === 'candidate-pair' && s.state === 'succeeded' && s.nominated) {
          const l = parId[s.localCandidateId], d = parId[s.remoteCandidateId];
          r.transports.push({ protocole: l?.protocol, port_serveur: d?.port });
        }
      });
    }
    return r;
  });
}

const res = { criteres: {} };
const prof = await entrer('enseignant', urls.enseignant);
await prof.page.waitForTimeout(6000);
const eleve = await entrer('eleve', urls.eleve);
await eleve.page.waitForTimeout(DUREE_MS);

for (const p of [prof, eleve]) {
  res[p.nom] = await mesure(p);
  res[p.nom].etapes = p.etapes;
  await p.page.screenshot({ path: `${OUT}/${p.nom}.png` });
}

// Partage d'écran par l'enseignant.
const avant = res.eleve.videos;
let apres = avant;
try {
  await prof.page.getByRole('button', { name: "Partager l'écran" }).click({ timeout: 5000 });
  await prof.page.waitForTimeout(8000);
  apres = (await mesure(eleve)).videos;
  await eleve.page.screenshot({ path: `${OUT}/eleve-partage-ecran.png` });
} catch (e) { /* critère ci-dessous en échec */ }
res.partage_ecran = { videos_eleve_avant: avant, videos_eleve_apres: apres };
const boutonEleve = await eleve.page.getByRole('button', { name: "Partager l'écran" }).count();

// Fin de réunion décidée par FEBA.
if (process.env.FIN_CMD) {
  res.fin = JSON.parse(execSync(process.env.FIN_CMD).toString().trim().split('\n').pop());
  await prof.page.waitForTimeout(8000);
}
for (const p of [prof, eleve]) {
  res[p.nom].navigation_apres_fin = p.navigations.slice(-1)[0];
  res[p.nom].erreurs = [...new Set(p.erreurs)].slice(0, 6);
}

const SEUIL = 20000;  // octets : bien au-delà de quelques paquets de contrôle
const c = res.criteres;
for (const n of ['enseignant', 'eleve']) {
  const r = res[n];
  c[`${n} : micro et caméra publiés`] = r.etapes.every(e => !e.includes('ÉCHEC'));
  c[`${n} : voit sa vidéo et celle de l'autre`] = r.videos >= 2;
  c[`${n} : audio reçu`] = r.entrant.audio > SEUIL;
  c[`${n} : vidéo reçue`] = r.entrant.video > SEUIL;
  c[`${n} : transport UDP`] = r.transports.length > 0 && r.transports.every(t => t.protocole === 'udp');
}
c["partage d'écran de l'enseignant reçu par l'élève"] = apres > avant;
c["l'élève n'a pas de bouton de partage d'écran"] = boutonEleve === 0;
if (res.fin) {
  c['fin de réunion par FEBA'] = res.fin.actif_avant && res.fin.end_room && !res.fin.actif_apres;
  for (const n of ['enseignant', 'eleve']) {
    c[`${n} : renvoyé vers la page FEBA de fin`] = /\/virtual-room\/\d+\/ended$/.test(res[n].navigation_apres_fin || '');
  }
}
console.log(JSON.stringify(res, null, 1));
const echecs = Object.entries(c).filter(([, ok]) => !ok).map(([k]) => k);
console.log(echecs.length ? `ÉCHEC : ${echecs.join(' ; ')}` : `RÉUSSITE : ${Object.keys(c).length} critères`);
await browser.close();
process.exit(echecs.length ? 1 : 0);
