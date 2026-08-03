/**
 * P2 — Les documents officiels, dans un vrai navigateur.
 *
 * CE QUI EST ÉPROUVÉ
 * ------------------
 *   1. Le super administrateur produit un certificat ET un diplôme pour
 *      CHACUNE des deux académies, les délivre, et télécharge les PDF.
 *   2. La liste se met à jour au changement d'académie SANS rechargement.
 *   3. L'administrateur de Cotonou ne voit rien de l'académie en ligne,
 *      et réciproquement.
 *   4. La recherche d'élève, la liste vide, l'erreur maîtrisée.
 *   5. L'empreinte affichée est celle du fichier réellement téléchargé.
 *   6. Un identifiant d'une autre académie donne 404, pas 403.
 *
 * POURQUOI « SANS RECHARGEMENT » SE VÉRIFIE AVEC UN TÉMOIN
 * --------------------------------------------------------
 * Une liste qui change après un rechargement complet a l'air correcte à
 * l'œil et ne l'est pas : l'utilisateur perd son contexte, et surtout
 * cela masquerait un cache non invalidé. Un témoin est posé sur `window`
 * avant la bascule ; s'il a disparu après, la page a rechargé.
 *
 * UN NAVIGATEUR PAR PROFIL
 * ------------------------
 * Vider `localStorage` ne suffit pas : encore authentifiée, l'application
 * redirige vers l'espace en cours et le scénario continuerait avec le
 * compte précédent — un contrôle d'isolation passerait alors pour de
 * mauvaises raisons.
 */
import fs from 'node:fs';
import { chromium } from './playwright.mjs';

const BASE = process.env.E2E_BASE_URL || 'http://127.0.0.1:5173';
// L'API est appelée par le PROXY du serveur de développement, donc en
// MÊME ORIGINE que l'application. Viser directement le port du backend
// ferait échouer chaque appel sur la politique d'origine du navigateur —
// ce qui ne prouverait rien sur l'application, seulement sur le scénario.
const API = process.env.E2E_API_URL || BASE + '/api';
const SHOTS = process.env.E2E_SHOTS || new URL('./captures', import.meta.url).pathname;
fs.mkdirSync(SHOTS, { recursive: true });

const OUT = [];
let FAIL = 0;
const log = (s) => { OUT.push(s); console.log(s); };
const check = (ok, label, detail = '') => {
  if (!ok) FAIL++;
  log(`${ok ? '  OK  ' : '  ÉCHEC'} ${label}${detail ? ' — ' + detail : ''}`);
  return ok;
};

const consoleErrors = [];

async function session(email, pwd) {
  const browser = await chromium.launch({
    executablePath: process.env.CHROMIUM_PATH || '/opt/pw-browsers/chromium',
  });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 950 } });
  const page = await ctx.newPage();
  page.on('console', (m) => {
    if (m.type() === 'error') consoleErrors.push(`${email} : ${m.text()}`);
  });
  // Le message de console d'une ressource refusée ne dit PAS laquelle.
  // Sans l'URL, on ne peut ni l'écarter honnêtement ni la corriger.
  page.on('requestfailed', (r) => {
    consoleErrors.push(`${email} : ${r.failure()?.errorText} ${r.url()}`);
  });

  // LE STATUT DE LA RÉPONSE EST OBSERVÉ, PAS DEVINÉ.
  //
  // Une connexion qui « ne prend pas » a deux causes très différentes :
  // l'application n'a pas soumis, ou le serveur a refusé. La seconde est
  // arrivée ici pour une raison qui n'a rien à voir avec l'application :
  // le limiteur de débit du point d'entrée `/auth/login/` s'appuie sur le
  // cache Redis, et plusieurs rejeux successifs du scénario épuisent son
  // quota. Sans lire le statut, on conclurait à un défaut de connexion.
  for (let attempt = 1; attempt <= 4; attempt++) {
    await page.goto(BASE + '/login', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('input[type=password]', { timeout: 30000 });
    await page.fill('input[type=email], input[name=email]', email);
    await page.fill('input[type=password]', pwd);

    const attendue = page.waitForResponse(
      (r) => r.url().includes('/api/auth/login/'), { timeout: 30000 },
    ).catch(() => null);
    await page.click('button[type=submit]');
    const reponse = await attendue;
    const statut = reponse ? reponse.status() : 0;

    for (let i = 0; i < 30; i++) {
      if (!new URL(page.url()).pathname.includes('/login')) break;
      await page.waitForTimeout(1000);
    }
    if (!new URL(page.url()).pathname.includes('/login')) return { browser, page };

    // LA SESSION EXISTE-T-ELLE MALGRÉ TOUT ?
    //
    // Le serveur a répondu 200 et le magasin porte un jeton, mais la
    // redirection après connexion n'a pas eu lieu. Vu à la troisième
    // session d'un même scénario, jamais isolément : le serveur de
    // développement est mono-processus et encaisse mal trois navigateurs
    // successifs (« ERR_CONNECTION_RESET » dans la console).
    //
    // Ce qu'on éprouve ici est le cloisonnement entre académies, pas la
    // redirection. Si le jeton est là, la session EST ouverte : on va au
    // tableau de bord soi-même plutôt que de déclarer un échec qui ne
    // porte sur rien.
    const jeton = await page.evaluate(() => {
      try {
        const m = JSON.parse(localStorage.getItem('feba-auth') || '{}');
        return (m.state || m).accessToken || null;
      } catch { return null; }
    });
    if (statut === 200 && jeton) {
      log(`  INFO  ${email} : session ouverte, redirection manquée — on poursuit`);
      await page.goto(BASE + '/admin/dashboard', { waitUntil: 'domcontentloaded' });
      // Le magasin d'authentification se réhydrate de façon ASYNCHRONE ;
      // pendant ce temps l'application se croit déconnectée. Naviguer
      // trop tôt vers un écran protégé la fait repartir vers /login, et
      // l'écran suivant reste vide. On attend donc la coquille
      // authentifiée — le bouton de déconnexion — et pas un délai.
      for (let i = 0; i < 30; i++) {
        const texte = await bodyText(page).catch(() => '');
        if (/Déconnexion|Logout/.test(texte)) break;
        await page.waitForTimeout(500);
      }
      if (!new URL(page.url()).pathname.includes('/login')) return { browser, page };
    }

    log(`  INFO  connexion ${email} : essai ${attempt} sans effet (HTTP ${statut})`);
    if (statut === 429) {
      log('        limiteur de débit atteint — pause de 20 s');
      await page.waitForTimeout(20000);
    } else {
      await page.waitForTimeout(2500);
    }
  }
  const body = await page.evaluate(() => document.body.innerText).catch(() => '');
  await browser.close();
  throw new Error(`Connexion impossible pour ${email}. Page : ${body.slice(0, 200)}`);
}

const shot = (page, name) =>
  page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: true });
const bodyText = (page) => page.evaluate(() => document.body.innerText);

/**
 * Préfixe des écrans d'administration, qui dépend du RÔLE.
 * Le super administrateur travaille sous /superadmin, un administrateur
 * d'académie sous /admin. Se tromper de préfixe fait silencieusement
 * atterrir sur le tableau de bord, et le scénario cherche alors un
 * bouton sur une page qui n'est pas la bonne.
 */
const ECRAN = (role, page_) => `/${role}/${page_}`;

async function visit(page, path, settle = 3500) {
  await page.goto(BASE + path, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(settle);
  return bodyText(page);
}

/**
 * Va sur un écran et ATTEND qu'il soit là.
 *
 * Une attente fixe est ce qui rend un scénario de navigateur
 * intermittent : trop courte elle échoue sur une machine chargée, trop
 * longue elle fait perdre une minute à chaque exécution. Ici on attend
 * la chose qu'on va vérifier, puis on la vérifie.
 */
async function visiterEtAttendre(page, path, motif, limiteMs = 20000) {
  for (let essai = 1; essai <= 2; essai++) {
    await page.goto(BASE + path, { waitUntil: 'domcontentloaded' });
    const echeance = Date.now() + limiteMs;
    let texte = '';
    while (Date.now() < echeance) {
      texte = await bodyText(page);
      if (motif.test(texte)) return texte;
      // Renvoyé vers la connexion : la réhydratation du magasin n'était
      // pas finie. Inutile d'attendre davantage sur cette page-ci.
      if (new URL(page.url()).pathname.includes('/login')) break;
      await page.waitForTimeout(500);
    }
    if (essai === 2) return texte;
    await page.waitForTimeout(1500);
  }
  return '';
}

/**
 * Appelle l'API DEPUIS la page, avec les identifiants de la session en
 * cours. Le trafic part du navigateur authentifié : c'est bien le droit
 * de CET utilisateur qui est éprouvé, pas celui d'un jeton fabriqué à
 * côté.
 */
function apiFromPage(page, chemin, options = {}) {
  return page.evaluate(async ([api, path, opts]) => {
    // Le jeton est celui que l'application utilise elle-même : le magasin
    // « feba-auth » persisté par Zustand. En fabriquer un à côté
    // éprouverait les droits d'un utilisateur qui n'est pas connecté.
    let brut = '';
    try {
      const magasin = JSON.parse(localStorage.getItem('feba-auth') || '{}');
      brut = (magasin.state || magasin).accessToken || '';
    } catch { brut = ''; }
    const reponse = await fetch(api + path, {
      method: opts.method || 'GET',
      headers: {
        Authorization: `Bearer ${brut}`,
        'Content-Type': 'application/json',
      },
      body: opts.body ? JSON.stringify(opts.body) : undefined,
    });
    const type = reponse.headers.get('content-type') || '';
    if (type.includes('pdf') || opts.binaire) {
      const tampon = new Uint8Array(await reponse.arrayBuffer());
      const empreinte = await crypto.subtle.digest('SHA-256', tampon);
      return {
        status: reponse.status,
        taille: tampon.length,
        entete: String.fromCharCode(...tampon.slice(0, 4)),
        sha256: Array.from(new Uint8Array(empreinte))
          .map((o) => o.toString(16).padStart(2, '0')).join(''),
      };
    }
    let corps = null;
    try { corps = await reponse.json(); } catch { corps = null; }
    return { status: reponse.status, corps };
  }, [API, chemin, options]);
}

/** Empreinte que l'écran affiche pour un document, lue par l'API. */
async function empreinteAffichee(page, id) {
  const liste = (await apiFromPage(page, '/documents/?page_size=200')).corps;
  const lignes = liste?.results || liste || [];
  return (lignes.find((d) => d.id === id) || {}).file_sha256 || null;
}

/** Ouvre le sélecteur d'académie et choisit l'entrée dont le libellé matche. */
async function basculerAcademie(page, motif) {
  const bouton = page.locator('button[aria-haspopup="listbox"]').first();
  await bouton.click();
  await page.waitForTimeout(400);
  const option = page.locator('[role="option"] button', { hasText: motif }).first();
  await option.click();
  await page.waitForTimeout(2500);
}


/**
 * Choisit un élève dans la liste déroulante cherchable.
 *
 * Le composant n'expose son champ de saisie qu'une fois ouvert : le
 * bouton porte le texte d'invite, le champ qui apparaît en dessous porte
 * « Rechercher... ». Viser directement l'invite cherche un champ qui
 * n'existe pas encore.
 */
async function choisirEleve(page, nomEleve) {
  await page.locator('button', { hasText: 'Rechercher un élève' }).first().click();
  await page.waitForTimeout(400);
  const champ = page.locator('input[placeholder^="Rechercher"]').last();
  await champ.fill('');
  await champ.pressSequentially(nomEleve.slice(0, 7), { delay: 45 });
  await page.waitForTimeout(700);
  await page.locator('button', { hasText: nomEleve }).last().click();
  await page.waitForTimeout(600);
}

/** Produit un document depuis la fenêtre modale. Renvoie le texte final. */
async function produire(page, motifGabarit, nomEleve) {
  await page.locator('button', { hasText: 'Produire un document' }).first().click();
  await page.waitForTimeout(600);
  // Le libellé du gabarit porte le nom de l'académie (« Diplôme FEBA »,
  // « Diplôme FEBA French Heritage Academy ») : on sélectionne par
  // IDENTIFIANT, qui ne bouge pas quand le libellé est retraduit.
  const valeurs = await page.$$eval('#doc-template option',
                                    (o) => o.map((x) => x.value));
  const cible = valeurs.find((v) => v.startsWith(motifGabarit));
  if (!cible) throw new Error(`Aucun gabarit « ${motifGabarit} » parmi ${valeurs}`);
  await page.selectOption('#doc-template', cible);
  await page.waitForTimeout(300);

  await choisirEleve(page, nomEleve);

  const confirmation = page.locator('input[type=checkbox]').first();
  if (await confirmation.count()) await confirmation.check();
  await page.waitForTimeout(200);

  await page.locator('button', { hasText: /^Produire$/ }).first().click();
  await page.waitForTimeout(2500);
  return bodyText(page);
}

/* ══════════════════════════════════════════════════════════════════════ */

log('=== P2 — Documents officiels, parcours navigateur ===');
log(`Application : ${BASE}   API : ${API}`);

const NOMS = {};      // code académie -> nom d'un élève réel
const PRODUITS = {};  // code académie -> [ids]

/* ─── 1. Super administrateur, académie FEBA ─────────────────────────── */
log('\n--- 1. Super administrateur sur FEBA (Cotonou) ---');
{
  const { browser, page } = await session('superadmin@feba.bj', 'SuperAdmin@2024');

  await visit(page, ECRAN('superadmin', 'dashboard'));
  await basculerAcademie(page, 'Faith & Excellence');

  let texte = await visiterEtAttendre(
    page, ECRAN('superadmin', 'official-documents'),
    /Documents officiels|Official documents/);
  check(/Documents officiels|Official documents/.test(texte),
        'l\'écran des documents officiels s\'ouvre');
  check(/Faith & Excellence|FEBA/.test(texte), 'l\'écran annonce l\'académie de Cotonou');
  await shot(page, 'documents-01-superadmin-feba-documents');

  // L'élève est lu depuis l'API : un nom écrit en dur dans le scénario
  // se périme au premier jeu de données différent.
  const eleves = await apiFromPage(page, '/students/?page_size=5');
  const premier = (eleves.corps?.results || eleves.corps || [])[0];
  NOMS.FEBA = premier?.full_name
    || `${premier?.first_name || ''} ${premier?.last_name || ''}`.trim();
  check(!!NOMS.FEBA, 'un élève de Cotonou est disponible', NOMS.FEBA);

  const avant = (await apiFromPage(page, '/documents/?page_size=200')).corps;
  const nAvant = (avant?.results || avant || []).length;

  texte = await produire(page, 'certificate_feba', NOMS.FEBA);
  check(texte.includes(NOMS.FEBA), 'le certificat apparaît dans la liste');
  await shot(page, 'documents-02-feba-certificat-produit');

  texte = await produire(page, 'diploma_feba', NOMS.FEBA);
  const apres = (await apiFromPage(page, '/documents/?page_size=200')).corps;
  const lignes = apres?.results || apres || [];
  check(lignes.length === nAvant + 2,
        'deux documents de plus dans la liste', `${nAvant} → ${lignes.length}`);

  const miens = lignes.filter((d) => d.student === NOMS.FEBA).slice(0, 2);
  PRODUITS.FEBA = miens.map((d) => d.id);
  check(miens.length === 2, 'certificat et diplôme sont bien tous deux là');
  check(miens.every((d) => d.academy_code === 'FEBA'),
        'les deux portent l\'académie de Cotonou',
        miens.map((d) => d.academy_code).join(', '));
  check(new Set(miens.map((d) => d.template_id)).size === 2,
        'les deux types sont distincts',
        miens.map((d) => d.template_id).join(', '));
  check(miens.every((d) => !d.number),
        'un brouillon n\'a pas encore de numéro officiel');

  // Délivrance
  for (const id of PRODUITS.FEBA) {
    const r = await apiFromPage(page, `/documents/${id}/issue/`, { method: 'POST' });
    check(r.status === 200, `délivrance du document ${id}`, `HTTP ${r.status}`);
  }
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2500);
  texte = await bodyText(page);
  check(/FEBA-[A-Z]{3}-\d{4}-\d{4}/.test(texte),
        'le numéro officiel est attribué à la délivrance',
        (texte.match(/FEBA-[A-Z]{3}-\d{4}-\d{4}/) || [])[0] || '');
  await shot(page, 'documents-03-feba-documents-delivres');

  // Téléchargement réel + empreinte
  for (const id of PRODUITS.FEBA) {
    const pdf = await apiFromPage(page, `/documents/${id}/download/`, { binaire: true });
    check(pdf.status === 200 && pdf.entete === '%PDF',
          `le PDF ${id} se télécharge et est un PDF`,
          `HTTP ${pdf.status}, ${pdf.taille} octets`);
    check(pdf.taille > 100000, `le PDF ${id} porte bien son fond`, `${pdf.taille} octets`);
    const affichee = await empreinteAffichee(page, id);
    check(affichee === pdf.sha256,
          `l'empreinte affichée est celle du fichier remis (${id})`,
          `${(affichee || '').slice(0, 12)}… vs ${pdf.sha256.slice(0, 12)}…`);
  }

  /* ─── 2. Bascule d'académie SANS rechargement ────────────────────── */
  log('\n--- 2. Changement d\'académie sans rechargement ---');
  await page.evaluate(() => { window.__temoinP2 = 'pose'; });
  const avantBascule = (await bodyText(page)).includes(NOMS.FEBA);
  check(avantBascule, 'la liste FEBA contient bien l\'élève de Cotonou');

  await basculerAcademie(page, 'French Heritage');
  const temoin = await page.evaluate(() => window.__temoinP2 || null);
  check(temoin === 'pose',
        'la page n\'a PAS rechargé pendant la bascule',
        temoin === null ? 'témoin perdu : rechargement complet' : 'témoin intact');

  const texteFha = await bodyText(page);
  check(!texteFha.includes(NOMS.FEBA),
        'l\'élève de Cotonou disparaît de la liste sans rechargement');
  check(/French Heritage|FHA/.test(texteFha),
        'l\'écran annonce désormais l\'académie en ligne');
  await shot(page, 'documents-04-bascule-sans-rechargement');

  /* ─── 3. Super administrateur, académie FEBA FHA ─────────────────── */
  log('\n--- 3. Super administrateur sur FEBA FHA (en ligne) ---');
  const elevesFha = await apiFromPage(page, '/students/?page_size=5');
  const premierFha = (elevesFha.corps?.results || elevesFha.corps || [])[0];
  NOMS.FEBA_FHA = premierFha?.full_name
    || `${premierFha?.first_name || ''} ${premierFha?.last_name || ''}`.trim();
  check(!!NOMS.FEBA_FHA && NOMS.FEBA_FHA !== NOMS.FEBA,
        'un élève de l\'académie en ligne est disponible', NOMS.FEBA_FHA);

  let t = await produire(page, 'certificate_feba_fha', NOMS.FEBA_FHA);
  check(t.includes(NOMS.FEBA_FHA), 'le certificat FEBA FHA apparaît dans la liste');
  await produire(page, 'diploma_feba_fha', NOMS.FEBA_FHA);

  const listeFha = (await apiFromPage(page, '/documents/?page_size=200')).corps;
  const lignesFha = listeFha?.results || listeFha || [];
  const miensFha = lignesFha.filter((d) => d.student === NOMS.FEBA_FHA).slice(0, 2);
  PRODUITS.FEBA_FHA = miensFha.map((d) => d.id);
  check(miensFha.length === 2, 'certificat et diplôme FEBA FHA sont là');
  check(miensFha.every((d) => d.academy_code === 'FEBA_FHA'),
        'les deux portent l\'académie en ligne',
        miensFha.map((d) => d.academy_code).join(', '));
  check(lignesFha.every((d) => d.academy_code === 'FEBA_FHA'),
        'la liste ne contient AUCUN document de l\'autre académie',
        `${lignesFha.length} ligne(s)`);

  for (const id of PRODUITS.FEBA_FHA) {
    await apiFromPage(page, `/documents/${id}/issue/`, { method: 'POST' });
  }
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2500);
  const texteNum = await bodyText(page);
  check(/\bFHA-[A-Z]{3}-\d{4}-\d{4}/.test(texteNum),
        'le numéro officiel FEBA FHA est attribué',
        (texteNum.match(/\bFHA-[A-Z]{3}-\d{4}-\d{4}/) || [])[0] || '');
  await shot(page, 'documents-05-fha-documents-delivres');

  for (const id of PRODUITS.FEBA_FHA) {
    const pdf = await apiFromPage(page, `/documents/${id}/download/`, { binaire: true });
    check(pdf.status === 200 && pdf.entete === '%PDF',
          `le PDF FEBA FHA ${id} se télécharge`, `HTTP ${pdf.status}, ${pdf.taille} o`);
    const affichee = await empreinteAffichee(page, id);
    check(affichee === pdf.sha256,
          `l'empreinte FEBA FHA ${id} correspond au fichier remis`,
          `${(affichee || '').slice(0, 12)}… vs ${pdf.sha256.slice(0, 12)}…`);
  }

  /* ─── 4. Recherche, liste vide, erreur maîtrisée ─────────────────── */
  log('\n--- 4. Recherche d\'élève, liste vide, erreur maîtrisée ---');
  await page.locator('button', { hasText: 'Produire un document' }).first().click();
  await page.waitForTimeout(600);
  await page.locator('button', { hasText: 'Rechercher un élève' }).first().click();
  await page.waitForTimeout(400);
  const champ = page.locator('input[placeholder^="Rechercher"]').last();
  await champ.pressSequentially(NOMS.FEBA_FHA.slice(0, 5), { delay: 45 });
  await page.waitForTimeout(900);
  let visible = await bodyText(page);
  check(visible.includes(NOMS.FEBA_FHA), 'la recherche trouve l\'élève');
  await shot(page, 'documents-06-recherche-eleve');

  await champ.fill('');
  await champ.pressSequentially('ZZZQWXVB', { delay: 45 });
  await page.waitForTimeout(900);
  const propositions = await page.$$eval(
    'input[placeholder^="Rechercher"] ~ * , .absolute button',
    (n) => n.map((x) => x.innerText.trim()).filter(Boolean));
  check(!propositions.some((p) => p.includes(NOMS.FEBA_FHA)),
        'une recherche sans résultat ne propose plus l\'élève',
        propositions.slice(0, 3).join(' | '));
  visible = await bodyText(page);
  check(/Aucun résultat|No result/i.test(visible),
        'la liste vide est annoncée, pas laissée muette');
  await shot(page, 'documents-07-liste-vide');

  // Erreur maîtrisée : gabarit d'une académie, élève de l'autre.
  const refus = await apiFromPage(page, '/documents/', {
    method: 'POST',
    body: { student: premierFha?.id, template: 'diploma_feba' },
  });
  check(refus.status >= 400 && refus.status < 500,
        'produire un diplôme de Cotonou pour un élève en ligne est refusé',
        `HTTP ${refus.status}`);
  const message = JSON.stringify(refus.corps || '');
  check(message.length > 10, 'le refus porte un message, pas une erreur nue',
        message.slice(0, 140));
  check(!/\/home\/|\/usr\/|\/var\/|backend\/document_templates/.test(message),
        'le message d\'erreur n\'expose aucun chemin du serveur');

  await browser.close();
}

/* ─── 5. Administrateur de Cotonou : cloisonnement ───────────────────── */
log('\n--- 5. Administrateur FEBA (Cotonou) ---');
{
  const { browser, page } = await session('admin@feba.bj', 'Admin@2024');
  const texte = await visiterEtAttendre(
    page, ECRAN('admin', 'official-documents'),
    /Documents officiels|Official documents/);
  check(/Documents officiels|Official documents/.test(texte),
        'l\'écran s\'ouvre pour l\'administrateur FEBA');
  check(!texte.includes(NOMS.FEBA_FHA || ' '),
        'aucun élève de l\'académie en ligne n\'apparaît');
  await shot(page, 'documents-08-admin-feba-cloisonne');

  const liste = (await apiFromPage(page, '/documents/?page_size=200')).corps;
  const lignes = liste?.results || liste || [];
  check(lignes.length > 0, 'l\'administrateur voit ses propres documents',
        `${lignes.length} ligne(s)`);
  check(lignes.every((d) => !d.academy_code || d.academy_code === 'FEBA'),
        'toutes les lignes sont de son académie');

  // Anti-IDOR : un identifiant de l'autre académie.
  for (const id of PRODUITS.FEBA_FHA || []) {
    const fiche = await apiFromPage(page, `/documents/${id}/`);
    check(fiche.status === 404,
          `le document ${id} d'une autre académie est INTROUVABLE (404, pas 403)`,
          `HTTP ${fiche.status}`);
    const pdf = await apiFromPage(page, `/documents/${id}/download/`, { binaire: true });
    check(pdf.status === 404,
          `son PDF ${id} est également introuvable`, `HTTP ${pdf.status}`);
  }
  await browser.close();
}

/* ─── 6. Administrateur de l'académie en ligne ───────────────────────── */
log('\n--- 6. Administrateur FEBA FHA (en ligne) ---');
{
  const { browser, page } = await session('admin@febafha.org', 'Admin@2024');
  const texte = await visiterEtAttendre(
    page, ECRAN('admin', 'official-documents'),
    /Documents officiels|Official documents/);
  check(/Documents officiels|Official documents/.test(texte),
        'l\'écran s\'ouvre pour l\'administrateur FEBA FHA');
  check(!texte.includes(NOMS.FEBA || ' '),
        'aucun élève de Cotonou n\'apparaît');
  await shot(page, 'documents-09-admin-fha-cloisonne');

  const liste = (await apiFromPage(page, '/documents/?page_size=200')).corps;
  const lignes = liste?.results || liste || [];
  check(lignes.every((d) => !d.academy_code || d.academy_code === 'FEBA_FHA'),
        'toutes les lignes sont de l\'académie en ligne',
        `${lignes.length} ligne(s)`);

  for (const id of PRODUITS.FEBA || []) {
    const fiche = await apiFromPage(page, `/documents/${id}/`);
    check(fiche.status === 404,
          `le document ${id} de Cotonou est INTROUVABLE`, `HTTP ${fiche.status}`);
  }

  // Un administrateur ne peut pas élargir sa portée en le demandant.
  const eleves = (await apiFromPage(page, '/students/?school=1&page_size=200')).corps;
  const rangs = eleves?.results || eleves || [];
  check(!rangs.some((e) => (e.full_name || '') === NOMS.FEBA),
        'demander explicitement l\'autre académie n\'élargit pas la portée');
  await shot(page, 'documents-10-admin-fha-portee-non-elargie');
  await browser.close();
}

/* ─── Bilan ──────────────────────────────────────────────────────────── */
log('\n=== Bilan ===');
// Une seule famille d'erreurs est écartée, et elle est nommée : la
// feuille de style de Google Fonts, que la politique réseau du bac à
// sable coupe (« ERR_CONNECTION_RESET »). Elle ne vient pas de
// l'application mais d'un CDN tiers, et son échec est sans effet sur le
// rendu — la pile de polices de secours prend le relais. C'est écrit
// ici plutôt que filtré par un motif large : « masquer les erreurs de
// console » et « écarter UNE erreur pour une raison connue » ne se
// distinguent que par la phrase qui l'accompagne.
const IGNOREES = [
  // Feuille de style d'un CDN tiers, coupée par la politique réseau du
  // bac à sable. La pile de polices de secours prend le relais.
  /fonts\.googleapis\.com/i,
  // Le message de console d'une ressource refusée ne porte PAS son URL.
  // Celui-ci accompagne la ligne précédente, une pour une.
  /Failed to load resource: net::ERR_CONNECTION_RESET/i,
  // ANNULATION VOULUE, PAS ERREUR. Au changement d'académie, tout ce qui
  // est en vol est avorté : une réponse arrivée en retard réafficherait
  // les données de l'académie qu'on vient de quitter. Voir
  // `src/api/academyScope.js`. La voir ici prouve que le mécanisme
  // fonctionne — l'absence serait plus inquiétante que la présence.
  /net::ERR_ABORTED .*\/api\//i,
  /favicon|ResizeObserver|React DevTools/i,
];

// LES ERREURS QUE LE SCÉNARIO PROVOQUE LUI-MÊME.
//
// Chromium journalise toute réponse non-2xx comme une erreur de console.
// Or ce scénario en demande exprès : un refus de gabarit (400) et six
// sondes anti-IDOR (404). Les compter est plus utile que les filtrer —
// si le nombre change, c'est qu'une requête a échoué là où on ne
// l'attendait pas, ou qu'une sonde a cessé d'être refusée.
const VOULUES = /the server responded with a status of (400|404)/i;
const provoquees = consoleErrors.filter((m) => VOULUES.test(m));
check(provoquees.length === 7,
      'les seules réponses en erreur sont les 7 que le scénario demande',
      `${provoquees.length} observée(s) : 1 refus de gabarit + 6 sondes anti-IDOR`);
IGNOREES.push(VOULUES);
const propres = consoleErrors.filter((m) => !IGNOREES.some((r) => r.test(m)));
check(propres.length === 0, 'aucune erreur de console imputable à l\'application',
      propres.slice(0, 3).join(' | '));
const annulees = consoleErrors.filter((m) => /ERR_ABORTED .*\/api\//i.test(m));
log(`  INFO  ${consoleErrors.length - propres.length} message(s) écarté(s), `
    + `dont ${annulees.length} annulation(s) volontaire(s) de requête au `
    + 'changement d\'académie et le reste imputable au CDN de polices.');
// PAS D'ASSERTION ICI, ET C'EST DÉLIBÉRÉ.
//
// Le nombre d'annulations dépend de ce qui se trouve EN VOL à l'instant
// précis de la bascule : selon la charge de la machine, il vaut zéro,
// une ou trois. Un contrôle sur une course est un contrôle qui échouera
// un jour sans qu'il se soit rien passé, et qu'on finira par ignorer.
// Le mécanisme lui-même est éprouvé par les tests d'`academyScope`, où
// la course est maîtrisée. Ici, on se contente de l'observer.
log(`  INFO  ${annulees.length} requête(s) annulée(s) à la bascule `
    + '(nombre variable : dépend de ce qui est en vol à cet instant).');

const total = OUT.filter((l) => /^\s+(OK|ÉCHEC)/.test(l)).length;
log(`\n${total - FAIL}/${total} contrôles passés.`);
log(`Captures : ${SHOTS}`);

fs.writeFileSync(new URL('./rapport-documents-officiels.txt', import.meta.url).pathname,
                 OUT.join('\n') + '\n');
process.exit(FAIL === 0 ? 0 : 1);
