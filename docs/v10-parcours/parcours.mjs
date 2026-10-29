/**
 * Parcours navigateur reels (§30) - application FEBA servie en local.
 *
 * L'academie FEBA FHA est volontairement laissee dans l'etat qui a
 * produit les captures d'ecran du rapport : une annee scolaire existe et
 * n'a jamais ete activee. C'est le cas ou les menus tombaient a zero.
 */
import { chromium } from "/opt/node22/lib/node_modules/playwright/index.mjs";

const BASE = "http://127.0.0.1:5173";
const SORTIE = process.argv[2];
const resultats = [];
function verifier(nom, ok, detail = "") {
  resultats.push({ nom, ok, detail });
  console.log(`${ok ? "PASS " : "ECHEC"} - ${nom}${detail ? " :: " + detail : ""}`);
}

const nav = await chromium.launch({
  executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
  args: ["--no-sandbox", "--use-fake-ui-for-media-stream",
         "--use-fake-device-for-media-stream"],
});
const ctx = await nav.newContext({ viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
const erreursJs = [];
page.on("pageerror", (e) => erreursJs.push(String(e)));

async function connexion(email, mdp) {
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle", timeout: 60000 });
  await page.fill('input[name="email"]', email);
  await page.fill('input[name="password"]', mdp);
  await page.click('button[type="submit"]');
  // L'attente porte sur l'URL reelle plutot que sur un evenement de
  // navigation : l'application est une SPA, elle ne recharge pas la page.
  for (let i = 0; i < 60 && page.url().includes("/login"); i++) {
    await page.waitForTimeout(500);
  }
  // Le compte FHA a « en » comme langue preferee. Les parcours verifient
  // des libelles : on fixe la langue pour que le test porte sur le
  // comportement, pas sur la langue du compte de demonstration.
  await page.evaluate(() => localStorage.setItem("feba-lang", "fr"));
  await page.reload({ waitUntil: "networkidle" });
  await page.waitForTimeout(2500);
}

async function allerA(chemin) {
  await page.goto(`${BASE}${chemin}`, { waitUntil: "networkidle", timeout: 60000 });
  await page.waitForTimeout(2500);
}

// ---- A. Connexion administrateur FEBA FHA -----------------------------
await connexion("admin@febafha.org", "Admin@2024");
verifier("A. Connexion administrateur FEBA FHA", !page.url().includes("/login"), page.url());
await page.screenshot({ path: `${SORTIE}/A-tableau-de-bord.png` });

// ---- B. Menu « Classe » d'une nouvelle salle virtuelle (bug n1) -------
await allerA("/admin/virtual");
await page.getByRole("button", { name: /Nouvelle salle/i }).first().click();
await page.waitForTimeout(2000);
// On rassemble les options de TOUS les menus du formulaire : le test
// porte sur la presence des classes, pas sur l'ordre des champs.
const toutesOptions = await page.locator("form select option").allTextContents();
const ATTENDUES = ["Junior Roots", "French Explorers", "French Ambassadors"];
const manquantes = ATTENDUES.filter((n) => !toutesOptions.some((o) => o.includes(n)));
verifier("B. Le menu « Classe » propose les classes FHA (bug n1)",
  manquantes.length === 0,
  manquantes.length ? `manquantes = ${manquantes.join(", ")}`
                    : `options = ${JSON.stringify(toutesOptions)}`);
await page.screenshot({ path: `${SORTIE}/B-menu-classe.png` });

// ---- B2. Ciblage par profil (§1) --------------------------------------
const cases = page.locator('input[type="checkbox"]');
verifier("B2. Cases « Reservee a » presentes", (await cases.count()) >= 4,
  `cases = ${await cases.count()}`);
await page.keyboard.press("Escape");
await page.waitForTimeout(1000);

// ---- C. « Classes assignees » d'un enseignant (bug n4) ----------------
await allerA("/admin/teachers");
await page.getByRole("button", { name: /Nouvel enseignant|Ajouter/i }).first().click();
await page.waitForTimeout(2000);
const zoneClasses = page.locator("text=Classes assignees").locator("..");
await zoneClasses.locator("input, [role='combobox'], button").first().click().catch(() => {});
await page.waitForTimeout(1500);
const texteModale = await page.locator("form").first().innerText().catch(() => "");
const aucunResultat = /Aucun resultat/i.test(texteModale);
verifier("C. « Classes assignees » ne dit plus « Aucun resultat » (bug n4)",
  !aucunResultat, aucunResultat ? "« Aucun resultat » toujours affiche" : "menu peuple");
await page.screenshot({ path: `${SORTIE}/C-classes-assignees.png` });
await page.keyboard.press("Escape");
await page.waitForTimeout(1000);

// ---- D. Salles physiques dans Parametres (bug n5) ---------------------
await allerA("/admin/settings");
const texteParams = await page.locator("body").innerText();
const m = texteParams.match(/Salles physiques[^\n]*\((\d+)\)/i);
verifier("D. « Salles physiques de l'ecole » n'est plus a 0 (bug n5)",
  !!m && Number(m[1]) > 0, m ? `compteur = ${m[1]}` : "compteur introuvable a l'ecran");
await page.screenshot({ path: `${SORTIE}/D-salles-physiques.png` });

// ---- E. Parcours linguistique d'une classe (§2) ------------------------
await allerA("/admin/classes");
const texteClasses = await page.locator("body").innerText();
verifier("E. Les classes FHA sont listees",
  /Junior Roots/i.test(texteClasses) && /French Ambassadors/i.test(texteClasses));
await page.getByRole("button", { name: /Nouvelle classe|Ajouter/i }).first().click();
await page.waitForTimeout(2000);
const texteFormClasse = await page.locator("form").first().innerText().catch(() => "");
verifier("E2. Le formulaire propose le parcours linguistique (§2)",
  /Parcours linguistique/i.test(texteFormClasse), texteFormClasse.slice(0, 120));
await page.screenshot({ path: `${SORTIE}/E-parcours-linguistique.png` });
await page.keyboard.press("Escape");
await page.waitForTimeout(1000);

// ---- F. « Rejoindre » ouvre un NOUVEL ONGLET plein ecran (§11) --------
await allerA("/admin/virtual");
const boutonRejoindre = page.getByRole("button", { name: /^Rejoindre$/i }).first();
const presence = await boutonRejoindre.count();
if (presence === 0) {
  verifier("F. Bouton « Rejoindre » present", false, "aucune salle rejoignable dans la liste");
} else {
  const [onglet] = await Promise.all([
    ctx.waitForEvent("page", { timeout: 30000 }),
    boutonRejoindre.click(),
  ]);
  await onglet.waitForLoadState("domcontentloaded");
  verifier("F. « Rejoindre » ouvre un NOUVEL onglet (§11)", true, onglet.url());
  verifier("F2. L'onglet pointe la route plein ecran /virtual-room/:id/join",
    /\/virtual-room\/\d+\/join/.test(onglet.url()), onglet.url());
  verifier("F3. Aucun jeton dans l'URL de l'onglet (§12)",
    !/jwt|token|jeton/i.test(onglet.url()), onglet.url());

  await onglet.waitForTimeout(6000);
  const structure = await onglet.evaluate(() => ({
    nav: document.querySelectorAll("nav").length,
    aside: document.querySelectorAll("aside").length,
    header: document.querySelectorAll("header").length,
    session: !!document.querySelector('[data-testid="virtual-room-session"]'),
    texte: (document.body.innerText || "").slice(0, 400),
  }));
  verifier("F4. Aucune barre laterale / en-tete FEBA autour de la conference (§11)",
    structure.nav === 0 && structure.aside === 0 && structure.header === 0,
    JSON.stringify({ nav: structure.nav, aside: structure.aside, header: structure.header }));
  verifier("F5. Jamais de repli vers un service public (meet.jit.si)",
    !/meet\.jit\.si/i.test(structure.texte) &&
    !(await onglet.content()).includes("meet.jit.si"));
  console.log("    Contenu de l'onglet :", JSON.stringify(structure.texte.slice(0, 220)));
  await onglet.screenshot({ path: `${SORTIE}/F-onglet-conference.png` });
  await onglet.close();
}

// ---- G. Non-regression FEBA (§37) -------------------------------------
await page.goto(`${BASE}/logout`, { waitUntil: "networkidle" }).catch(() => {});
await ctx.clearCookies();
await page.evaluate(() => { localStorage.clear(); sessionStorage.clear(); }).catch(() => {});
await connexion("admin@feba.bj", "Admin@2024");
verifier("G. Connexion administrateur FEBA", !page.url().includes("/login"), page.url());
await allerA("/admin/classes");
const texteFeba = await page.locator("body").innerText();
verifier("G2. FEBA affiche toujours ses classes (§37)",
  /CP1|CE1|CM1|CM2|6eme|6e/i.test(texteFeba), texteFeba.slice(0, 160).replace(/\n/g, " | "));
await page.screenshot({ path: `${SORTIE}/G-feba-classes.png` });

verifier("H. Aucune erreur JavaScript pendant les parcours",
  erreursJs.length === 0, erreursJs.slice(0, 3).join(" || "));

console.log("\n===== RESUME =====");
const echecs = resultats.filter((r) => !r.ok);
console.log(`${resultats.length - echecs.length}/${resultats.length} verifications PASS`);
echecs.forEach((e) => console.log(`  ECHEC: ${e.nom} :: ${e.detail}`));
await nav.close();
process.exit(echecs.length ? 1 : 0);
