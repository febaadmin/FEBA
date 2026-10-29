// Parcours complet d'une classe virtuelle DEPUIS FEBA : connexion réelle,
// règles d'accès FEBA, salle d'attente, audio/vidéo, présence (webhooks),
// partage d'écran, coupure réseau, fin de réunion et retour dans FEBA.
//
//   FEBA_URL=http://localhost:15174 ROOM_ID=2 OUT=captures \
//     node e2e/plugnmeet/parcours-feba.mjs
//
// Comptes : ceux de DEMO_ACCOUNTS.md (mots de passe lus dans le fichier,
// jamais affichés). TEACHER / STUDENT doivent avoir accès à la salle ;
// OUTSIDER ne doit pas l'avoir. Code de sortie 1 si un critère échoue.
// Caméra et micro simulés par Chrome : ce test prouve la signalisation, le
// transport et le routage des flux, pas la qualité perçue sur un vrai poste.
import { chromium } from 'playwright-core';
import fs from 'fs';
import { fileURLToPath } from 'url';

const FEBA = (process.env.FEBA_URL || 'http://localhost:15174').replace(/\/$/, '');
const API = (process.env.FEBA_API || FEBA + '/api').replace(/\/$/, '');
const ROOM = process.env.ROOM_ID || '2';
const OUT = process.env.OUT || '.';
const TEACHER = process.env.TEACHER || 'prof@febafha.org';
const STUDENT = process.env.STUDENT || 'eleve1@febafha.org';
const OUTSIDER = process.env.OUTSIDER || 'eleve1@feba.bj';
const COMPTES = process.env.ACCOUNTS_FILE || fileURLToPath(new URL('../../DEMO_ACCOUNTS.md', import.meta.url));
const MDP = Object.fromEntries([...fs.readFileSync(COMPTES, 'utf8').matchAll(/`([^`]+@[^`]+)`\s*\|\s*`([^`]+)`/g)].map(m => [m[1], m[2]]));
const masque = u => String(u).replace(/access_token=[^&]+/, 'access_token=<masqué>');

// Libellés du client plugNmeet en français et en anglais (la langue suit
// celle de l'interface FEBA, transmise par l'en-tête Accept-Language).
const L = {
  preJoin: /Enable Microphone and Camera|Activer le microphone et la caméra/,
  join: /^(Join|Rejoindre)$/,
  micEnable: /^(Enable Microphone|Activer le microphone)$/,
  micUnmute: /^(Unmute Microphone|Réactiver le microphone)$/,
  camOn: /^(Turn Off Camera|Désactiver la caméra)$/,
  camEnable: /^(Enable Camera|Turn On Camera|Activer la caméra)$/,
  share: /^(Share|Partager)$/,
  screen: /^(Share Screen|Partager l'écran)$/,
  approve: /^(Approve|Approuver|Accepter|Admettre)$/,
  end: /^(End meeting|Terminer la réunion)$/,
  waiting: /waiting room|salle d'attente/i,
};

async function apiLogin(email) {
  const r = await fetch(`${API}/auth/login/`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password: MDP[email] }) });
  const d = await r.json();
  return d.access || d.tokens?.access;
}
async function apiGet(token, path) {
  const r = await fetch(`${API}${path}`, { headers: { Authorization: `Bearer ${token}` } });
  return { status: r.status, data: await r.json().catch(() => null) };
}

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
const espion = () => {
  const Orig = window.RTCPeerConnection;
  window.__pcs = [];
  window.RTCPeerConnection = function (...a) { const pc = new Orig(...a); window.__pcs.push(pc); return pc; };
  window.RTCPeerConnection.prototype = Orig.prototype;
  Object.setPrototypeOf(window.RTCPeerConnection, Orig);
};

async function ouvrir(nom, email) {
  const ctx = await browser.newContext({ permissions: ['camera', 'microphone'], viewport: { width: 1280, height: 800 } });
  await ctx.addInitScript(espion);
  const page = await ctx.newPage();
  const p = { nom, email, ctx, page, erreurs: [], navigations: [] };
  page.on('console', m => { if (m.type() === 'error') p.erreurs.push(m.text().slice(0, 200)); });
  page.on('request', r => { if (r.isNavigationRequest() && r.frame() === page.mainFrame()) p.navigations.push(masque(r.url())); });
  await page.goto(FEBA + '/login', { waitUntil: 'networkidle' });
  await page.fill('input[type=email], input[name=email]', email);
  await page.fill('input[type=password]', MDP[email]);
  await page.click('button[type=submit]');
  await page.waitForFunction(() => !location.pathname.includes('/login'), null, { timeout: 45000 });
  return p;
}

async function rejoindre(p) {
  const feba = new URL(FEBA).origin;
  await p.page.goto(`${FEBA}/virtual-room/${ROOM}/join`);
  try {
    await p.page.waitForFunction(o => location.origin !== o, feba, { timeout: 45000 });
  } catch (e) {
    const texte = (await p.page.innerText('body')).replace(/\s+/g, ' ').slice(0, 300);
    throw new Error(`${p.nom} : la page FEBA n'a pas ouvert la salle — « ${texte} »`);
  }
  p.origineVisio = new URL(p.page.url()).origin;
  await p.page.getByText(L.preJoin).click({ timeout: 45000 });
  await p.page.waitForTimeout(2000);
  await p.page.getByRole('button', { name: L.join }).click({ timeout: 20000 });
}

async function publier(p) {
  const page = p.page;
  const etapes = [];
  await page.waitForTimeout(3000);
  if (await page.getByRole('button', { name: L.micEnable }).count()) {
    await page.getByRole('button', { name: L.micEnable }).click();
    await page.locator('button', { hasText: 'Fake Default Audio Input' }).click({ timeout: 10000 });
    await page.getByRole('button', { name: L.share }).click({ timeout: 10000 });
    await page.waitForTimeout(2000);
    etapes.push('micro publié');
  }
  if (!(await page.getByRole('button', { name: L.camOn }).count()) && await page.getByRole('button', { name: L.camEnable }).count()) {
    await page.getByRole('button', { name: L.camEnable }).click();
    await page.getByRole('button', { name: L.share }).click({ timeout: 10000 });
    await page.waitForTimeout(2000);
    etapes.push('caméra publiée');
  }
  // FEBA impose mute_on_start : le micro arrive coupé.
  if (await page.getByRole('button', { name: L.micUnmute }).count()) {
    await page.getByRole('button', { name: L.micUnmute }).click();
    etapes.push('micro réactivé');
  }
  p.etapes = etapes;
  await page.waitForTimeout(2000);  // l'interface met à jour les boutons après la publication
  return {
    micro_actif: !(await page.getByRole('button', { name: L.micUnmute }).count()) && !(await page.getByRole('button', { name: L.micEnable }).count()),
    camera_active: (await page.getByRole('button', { name: L.camOn }).count()) > 0,
  };
}

async function mesure(p) {
  return p.page.evaluate(async () => {
    const r = { videos: [...document.querySelectorAll('video')].filter(v => v.videoWidth > 0 && !v.paused).length,
      entrant: { audio: 0, video: 0 }, sortant: { audio: 0, video: 0 }, transports: [] };
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

const c = {};       // critères
const res = {};     // mesures
const SEUIL = 20000;

// ── 1. Règles d'accès FEBA (API)
const tProf = await apiLogin(TEACHER), tEleve = await apiLogin(STUDENT), tAutre = await apiLogin(OUTSIDER);
c['API : connexion des trois comptes'] = Boolean(tProf && tEleve && tAutre);
const salleProf = await apiGet(tProf, `/virtual-rooms/${ROOM}/`);
const salleAutre = await apiGet(tAutre, `/virtual-rooms/${ROOM}/`);
c["API : l'enseignant voit la salle et peut la gérer"] = salleProf.status === 200 && salleProf.data?.can_manage === true;
c["API : un compte hors de la classe ne voit pas la salle (404)"] = salleAutre.status === 404;

// ── 2. Enseignant : FEBA → plugNmeet
const prof = await ouvrir('enseignant', TEACHER);
await rejoindre(prof);
// Sa propre entrée : l'en-tête « Participants (n) » peut être masqué par une notification.
await prof.page.getByText(/\((moi|me)\)/).first().waitFor({ timeout: 45000 });
c["navigateur : l'enseignant passe de FEBA à la salle plugNmeet"] = prof.origineVisio !== new URL(FEBA).origin;

// ── 3. Élève : salle d'attente puis admission par l'enseignant
const eleve = await ouvrir('eleve', STUDENT);
await rejoindre(eleve);
let enAttente = false;
try { await eleve.page.getByText(L.waiting).waitFor({ timeout: 20000 }); enAttente = true; } catch { /* salle sans attente */ }
res.salle_attente = enAttente;
if (enAttente) {
  const admettre = prof.page.getByRole('button', { name: L.approve }).first();
  await admettre.waitFor({ timeout: 20000 });
  await admettre.click();
  c["salle d'attente : l'élève attend puis est admis par l'enseignant"] = true;
}
await eleve.page.getByText(/Participants \(2\)/).waitFor({ timeout: 45000 });
c["navigateur : l'élève est dans la salle (2 participants)"] = true;

// ── 4. Médias
res.enseignant_etat = await publier(prof);
res.eleve_etat = await publier(eleve);
await eleve.page.waitForTimeout(15000);
for (const p of [prof, eleve]) res[p.nom] = await mesure(p);
for (const p of [prof, eleve]) {
  const r = res[p.nom];
  c[`WebRTC ${p.nom} : micro et caméra actifs`] = res[`${p.nom}_etat`].micro_actif && res[`${p.nom}_etat`].camera_active;
  c[`WebRTC ${p.nom} : voit sa vidéo et celle de l'autre`] = r.videos >= 2;
  c[`WebRTC ${p.nom} : audio reçu`] = r.entrant.audio > SEUIL;
  c[`WebRTC ${p.nom} : vidéo reçue`] = r.entrant.video > SEUIL;
  c[`WebRTC ${p.nom} : transport UDP`] = r.transports.length > 0 && r.transports.every(t => t.protocole === 'udp');
}

// ── 5. Présence enregistrée par FEBA (webhooks plugNmeet → FEBA)
const presence = await apiGet(tProf, `/virtual-rooms/${ROOM}/participants/`);
const lignes = Array.isArray(presence.data) ? presence.data : presence.data?.results || [];
const ouvertes = lignes.filter(l => !l.left_at);
res.presence_pendant = ouvertes.map(l => ({ role: l.user_role, source: l.source }));
c['FEBA : présence ouverte pour l\'enseignant et l\'élève'] =
  ['teacher', 'student'].every(role => ouvertes.some(l => l.user_role === role));

// ── 6. Partage d'écran ; aucun partage proposé à l'élève
const avant = res.eleve.videos;
let apres = avant;
try {
  await prof.page.getByRole('button', { name: L.screen }).click({ timeout: 5000 });
  await prof.page.waitForTimeout(8000);
  apres = (await mesure(eleve)).videos;
} catch { /* critère en échec */ }
res.partage_ecran = { videos_eleve_avant: avant, videos_eleve_apres: apres };
c["partage d'écran de l'enseignant reçu par l'élève"] = apres > avant;
c["l'élève n'a pas de bouton de partage d'écran"] = (await eleve.page.getByRole('button', { name: L.screen }).count()) === 0;

// ── 7. Accès refusé dans le navigateur à un compte hors de la classe
const autre = await ouvrir('hors-classe', OUTSIDER);
await autre.page.goto(`${FEBA}/virtual-room/${ROOM}/join`);
await autre.page.waitForTimeout(8000);
res.hors_classe = { url: masque(autre.page.url()), texte: (await autre.page.innerText('body')).replace(/\s+/g, ' ').slice(0, 160) };
c['navigateur : un compte hors de la classe reste dans FEBA, sans salle'] =
  new URL(autre.page.url()).origin === new URL(FEBA).origin && !autre.navigations.some(u => u.includes('access_token'));
await autre.ctx.close();

// ── 8. Coupure réseau de l'élève (12 s), puis reprise du flux
const avantCoupure = (await mesure(eleve)).entrant.video;
await eleve.ctx.setOffline(true);
await eleve.page.waitForTimeout(12000);
await eleve.ctx.setOffline(false);
await eleve.page.waitForTimeout(25000);
const apresCoupure = (await mesure(eleve)).entrant.video;
res.coupure = { video_recue_avant: avantCoupure, video_recue_apres: apresCoupure };
c["coupure réseau de 12 s : l'élève reçoit de nouveau la vidéo"] = apresCoupure > avantCoupure + SEUIL;
c["coupure réseau : l'élève est toujours dans la salle"] = (await eleve.page.getByText(/Participants \(2\)/).count()) > 0;

// ── 9. Fin de réunion par l'enseignant dans plugNmeet, retour dans FEBA
await prof.page.getByRole('button', { name: L.end }).click({ timeout: 10000 });
await prof.page.waitForTimeout(1500);
const confirmer = prof.page.locator('[role=dialog] button, .modal button').filter({ hasText: /End|Terminer|Yes|Oui|Confirm/ });
if (await confirmer.count()) await confirmer.last().click();
await prof.page.waitForTimeout(10000);
for (const p of [prof, eleve]) {
  res[`${p.nom}_retour`] = p.navigations.filter(u => u.startsWith(new URL(FEBA).origin)).slice(-1)[0];
  c[`fin : ${p.nom} renvoyé vers /virtual-room/${ROOM}/ended`] = new RegExp(`/virtual-room/${ROOM}/ended$`).test(res[`${p.nom}_retour`] || '');
}
const etat = await apiGet(tProf, `/virtual-rooms/${ROOM}/meeting-status/`);
res.etat_apres_fin = etat.data;
c['FEBA : réunion inactive après la fin'] = etat.status === 200 && etat.data?.active === false;
const apresFin = await apiGet(tProf, `/virtual-rooms/${ROOM}/participants/`);
const lignesFin = Array.isArray(apresFin.data) ? apresFin.data : apresFin.data?.results || [];
res.presence_apres_fin = lignesFin.slice(0, 6).map(l => ({ role: l.user_role, fermee: Boolean(l.left_at), duree_s: l.duration_seconds, source: l.source }));
c['FEBA : présences fermées après la fin'] = lignesFin.length > 0 && lignesFin.every(l => l.left_at);

for (const p of [prof, eleve]) res[`${p.nom}_erreurs`] = [...new Set(p.erreurs)].slice(0, 5);
console.log(JSON.stringify({ mesures: res, criteres: c }, null, 1));
const echecs = Object.entries(c).filter(([, ok]) => !ok).map(([k]) => k);
console.log(echecs.length ? `ÉCHEC : ${echecs.join(' ; ')}` : `RÉUSSITE : ${Object.keys(c).length} critères`);
await browser.close();
process.exit(echecs.length ? 1 : 0);
