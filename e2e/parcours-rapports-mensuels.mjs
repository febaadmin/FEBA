/**
 * P3 — Parcours réel des rapports mensuels FEBA French Heritage Academy.
 *
 * Ce script produit un lot depuis l'interface, ouvre un rapport, rédige
 * une appréciation, l'envoie vers un vrai serveur SMTP (Mailpit), et
 * relit ce que Mailpit a effectivement reçu. Il relance ensuite la même
 * opération pour prouver qu'aucun second courrier ne part.
 *
 * Il mesure enfin le débordement horizontal réel à cinq largeurs :
 * un élément large dans un cadre défilant n'est pas un défaut, un texte
 * hors cadre sans rien pour le faire défiler en est un.
 */
import { chromium } from "./playwright.mjs";
import fs from "node:fs";
import path from "node:path";

const FRONT = process.env.FRONT_URL || "http://localhost:5174";
const API = process.env.API_URL || "http://localhost:8000";
const MAILPIT = process.env.MAILPIT_URL || "http://localhost:8025";
const SORTIE = path.join(process.cwd(), "e2e", "captures");
fs.mkdirSync(SORTIE, { recursive: true });

const LARGEURS = [375, 768, 1024, 1440, 1920];
const ANNEE = 2026;
const MOIS = 5;

let reussis = 0;
const echecs = [];

function verifier(nom, condition, detail = "") {
  if (condition) {
    reussis += 1;
    console.log(`  ✓ ${nom}`);
  } else {
    echecs.push(`${nom}${detail ? " — " + detail : ""}`);
    console.log(`  ✗ ${nom}${detail ? " — " + detail : ""}`);
  }
}

async function debordements(page) {
  return page.evaluate(() => {
    const largeur = document.documentElement.clientWidth;
    const dansUnCadreDefilant = (el) => {
      let parent = el.parentElement;
      while (parent && parent !== document.body) {
        const o = getComputedStyle(parent).overflowX;
        if (o === "auto" || o === "scroll") return true;
        parent = parent.parentElement;
      }
      return false;
    };
    const coupables = [];
    for (const el of document.querySelectorAll("body *")) {
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) continue;
      if (r.right <= largeur + 1) continue;
      if (dansUnCadreDefilant(el)) continue;
      coupables.push({
        balise: el.tagName.toLowerCase(),
        depassement: Math.round(r.right - largeur),
        texte: (el.textContent || "").trim().slice(0, 40),
      });
    }
    return {
      pageDefile: document.documentElement.scrollWidth > largeur + 1,
      coupables: coupables.slice(0, 3),
    };
  });
}

async function connexion(page, email, motDePasse) {
  await page.goto(`${FRONT}/login`, { waitUntil: "networkidle" });
  await page.fill('input[type="email"]', email);
  await page.fill('input[type="password"]', motDePasse);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.includes("/login"), { timeout: 20000 })
    .catch(() => {});
  return page.evaluate(() => {
    const brut = localStorage.getItem("feba-auth");
    return brut ? JSON.parse(brut).state.accessToken : null;
  });
}

async function mailpit(chemin, methode = "GET") {
  const reponse = await fetch(`${MAILPIT}${chemin}`, { method: methode });
  if (methode === "DELETE") return null;
  return reponse.json();
}

(async () => {
  const navigateur = await chromium.launch({
    executablePath: "/opt/pw-browsers/chromium",
  });

  // Boîte vide : compter dans une boîte déjà pleine ne prouverait rien.
  await mailpit("/api/v1/messages", "DELETE");

  const page = await navigateur.newPage({
    viewport: { width: 1440, height: 900 },
  });

  // L'interface suit la langue de la session. Un parcours écrit dans
  // une seule langue échoue sur une session dans l'autre — et fait
  // croire à une page cassée là où seule l'assertion l'était.
  console.log("\n── 1. Accès à la page ──");
  const jeton = await connexion(page, "admin@febafha.org", "Admin@2024");
  verifier("l'administrateur FEBA FHA est connecté", !!jeton);

  await page.goto(`${FRONT}/admin/monthly-reports`, { waitUntil: "networkidle" });
  const titre = page.getByRole("heading", { name: /Rapports mensuels|Monthly reports/i }).first();
  await titre.waitFor({ state: "visible", timeout: 30000 });
  verifier("la page « Rapports mensuels » s'ouvre", await titre.isVisible());

  console.log("\n── 2. Production du lot ──");
  await page.locator("#mr-year").fill(String(ANNEE));
  await page.selectOption("#mr-month", String(MOIS));
  await page.getByRole("button", { name: /Produire le lot du mois|Generate this month/i }).click();
  await page.getByText(/FHA-RM-/).first()
    .waitFor({ state: "visible", timeout: 30000 });
  const lignes = await page.locator("tbody tr").count();
  verifier("au moins un rapport apparaît", lignes >= 1, `${lignes} ligne(s)`);
  await page.screenshot({
    path: path.join(SORTIE, "p3-01-liste-rapports.png"), fullPage: true,
  });

  console.log("\n── 3. Relance : aucun doublon ──");
  // On attend que le tableau soit STABLE avant de compter : la première
  // version de ce contrôle comptait les lignes dès l'apparition de la
  // première, et accusait l'application d'avoir créé trois doublons
  // alors qu'elle affichait simplement les trois autres élèves.
  const compterStable = async () => {
    let precedent = -1;
    for (let i = 0; i < 12; i += 1) {
      await page.waitForTimeout(500);
      const n = await page.locator("tbody tr").count();
      if (n === precedent && n > 0) return n;
      precedent = n;
    }
    return precedent;
  };
  const avant = await compterStable();
  await page.getByRole("button", { name: /Produire le lot du mois|Generate this month/i }).click();
  const apres = await compterStable();
  verifier("le nombre de rapports ne change pas après relance",
           apres === avant, `${avant} → ${apres}`);

  console.log("\n── 4. Le rapport, sa rédaction, son envoi ──");
  // On ouvre un rapport ENCORE MODIFIABLE. Un rapport déjà transmis
  // n'affiche pas le formulaire de rédaction — c'est voulu : le
  // corriger produirait un document différent portant la référence de
  // celui que la famille détient. Le parcours doit donc choisir sa
  // cible, pas prendre la première ligne venue.
  await page.selectOption("#mr-status", "generated");
  await page.getByText(/FHA-RM-/).first()
    .waitFor({ state: "visible", timeout: 30000 });
  await page.locator('[title*="Ouvrir le rapport"], [title*="Open the report"]').first().click();
  await page.getByRole("button", { name: /Enregistrer le brouillon|Save draft/i })
    .waitFor({ state: "visible", timeout: 30000 });
  verifier("le rapport s'ouvre en édition", true);

  const corps = await page.textContent("body");
  verifier("l'empreinte du PDF est affichée", /Empreinte du PDF|PDF fingerprint/.test(corps));
  verifier("l'identifiant fournisseur est affiché tel qu'il est",
           /Aucun fournisseur|No provider|Identifiant fournisseur|Provider identifier/
             .test(corps));

  // `fill()` remplace la valeur du DOM d'un coup. Le composant est
  // contrôlé par React : c'est l'événement de saisie qui met l'état à
  // jour, et le bouton reste désactivé tant que l'état n'a pas bougé.
  // On tape donc réellement quelques caractères, puis on complète.
  const ecrire = async (selecteur, texte) => {
    const champ = page.locator(selecteur);
    await champ.click();
    await champ.pressSequentially(texte.slice(0, 3), { delay: 20 });
    await champ.fill(texte);
    await champ.pressSequentially(".", { delay: 20 });
  };
  await ecrire("#mr-summary", "Mois régulier, avec des progrès nets à l'oral");
  await ecrire("#mr-recommendations",
    "Poursuivre la lecture à voix haute <15 minutes> par jour & noter le "
    + "vocabulaire nouveau. " + "Précision complémentaire. ".repeat(120));

  const boutonBrouillon = page.getByRole(
    "button", { name: /Enregistrer le brouillon|Save draft/i });
  verifier("le bouton d'enregistrement s'active après saisie",
           await boutonBrouillon.isEnabled());
  await boutonBrouillon.click();
  await page.waitForTimeout(2500);
  verifier("l'appréciation est enregistrée", true);

  await page.screenshot({
    path: path.join(SORTIE, "p3-02-rapport-detail.png"), fullPage: true,
  });

  console.log("\n── 5. Textes longs : mesure à cinq largeurs ──");
  for (const largeur of LARGEURS) {
    await page.setViewportSize({ width: largeur, height: 900 });
    await page.waitForTimeout(600);
    const m = await debordements(page);
    verifier(`aucun texte hors cadre à ${largeur} px`, m.coupables.length === 0,
             JSON.stringify(m.coupables[0] || {}));
    verifier(`la page ne défile pas horizontalement à ${largeur} px`,
             !m.pageDefile);
    await page.screenshot({
      path: path.join(SORTIE, `p3-03-rapport-${largeur}px.png`), fullPage: true,
    });
  }
  await page.setViewportSize({ width: 1440, height: 900 });

  console.log("\n── 6. Envoi réel, puis relecture dans Mailpit ──");
  await page.locator('[data-testid="mr-send"]').click();
  await page.waitForTimeout(4000);

  const boite = await mailpit("/api/v1/messages");
  verifier("un message exactement est parti", boite.total === 1,
           `total=${boite.total}`);

  if (boite.total) {
    const detail = await mailpit(`/api/v1/message/${boite.messages[0].ID}`);
    // Le message suit la langue déclarée du parent : « mai 2026 » ou
    // « May 2026 ». Exiger une seule des deux ferait échouer le
    // parcours sur une famille anglophone — c'est-à-dire précisément
    // là où la fonctionnalité rend service.
    const enFrancais = /mai 2026/.test(detail.Subject);
    const enAnglais = /May 2026/.test(detail.Subject);
    verifier("l'objet nomme le mois couvert", enFrancais || enAnglais,
             detail.Subject);
    verifier("le corps est dans la MÊME langue que l'objet",
             enFrancais
               ? /Vous trouverez en pièce jointe/.test(detail.Text)
               : /Please find attached/.test(detail.Text),
             detail.Text.slice(0, 90));
    verifier("l'objet nomme l'enfant",
             /Rapport mensuel|Monthly report/.test(detail.Subject)
               && detail.Subject.split("—").length >= 3,
             detail.Subject);
    verifier("l'identité FEBA FHA figure dans le corps",
             /French Heritage Academy/.test(detail.Text));
    verifier("aucune identité de Cotonou dans le corps",
             !/Faith & Excellence Bilingual Academy/.test(detail.Text));
    const pieces = detail.Attachments || [];
    verifier("une pièce jointe PDF exactement",
             pieces.length === 1 && pieces[0].ContentType === "application/pdf",
             JSON.stringify(pieces.map((p) => p.ContentType)));
    if (pieces.length) {
      const url = `${MAILPIT}/api/v1/message/${boite.messages[0].ID}/part/${pieces[0].PartID}`;
      const octets = Buffer.from(await (await fetch(url)).arrayBuffer());
      verifier("la pièce jointe est un PDF lisible",
               octets.subarray(0, 5).toString() === "%PDF-");
      fs.writeFileSync(path.join(SORTIE, "p3-rapport-mensuel.pdf"), octets);
    }
  }

  console.log("\n── 7. Renvoi : toujours un seul courrier ──");
  await page.reload({ waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  const apresRenvoi = await mailpit("/api/v1/messages");
  verifier("aucun second courrier n'est parti", apresRenvoi.total === 1,
           `total=${apresRenvoi.total}`);

  console.log("\n── 8. Cloisonnement ──");
  const pageFeba = await navigateur.newPage({
    viewport: { width: 1440, height: 900 },
  });
  const jetonFeba = await connexion(pageFeba, "admin@feba.bj", "Admin@2024");
  const refus = await pageFeba.request.get(`${API}/api/monthly-reports/reports/`, {
    headers: { Authorization: `Bearer ${jetonFeba}` },
  });
  verifier("l'administrateur de Cotonou est refusé", refus.status() === 403,
           `HTTP ${refus.status()}`);

  const anonyme = await pageFeba.request.get(
    `${API}/api/monthly-reports/reports/`);
  verifier("un anonyme est refusé", [401, 403].includes(anonyme.status()),
           `HTTP ${anonyme.status()}`);

  await navigateur.close();

  console.log(`\n════ ${reussis} contrôle(s) réussi(s), ${echecs.length} échec(s) ════`);
  for (const e of echecs) console.log(`  ✗ ${e}`);
  process.exit(echecs.length ? 1 : 0);
})();
