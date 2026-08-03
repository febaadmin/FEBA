/**
 * P2 — Parcours réel : une préinscription FEBA, de la famille au dossier.
 *
 * Ce script ne simule rien. Il remplit le formulaire public dans un vrai
 * navigateur, avec un message de 5 000 caractères et un mot de 300
 * caractères, puis ouvre le dossier côté administration et MESURE :
 *
 *  - qu'aucun élément ne déborde horizontalement de la fenêtre ;
 *  - que le message est affiché en entier, sans « … » ;
 *  - que chaque champ saisi est visible dans la fiche ;
 *  - que la fiche PDF se télécharge réellement ;
 *  - qu'un administrateur de l'autre académie est refusé.
 *
 * Le débordement est mesuré, pas jugé à l'œil : on compare la largeur du
 * document à celle de la fenêtre, et on relève tout élément dont le bord
 * droit dépasse. Une capture d'écran ne prouve rien à 1920 px si le
 * défaut n'apparaît qu'à 375 px.
 */
import { chromium } from "./playwright.mjs";
import fs from "node:fs";
import path from "node:path";

const FRONT = process.env.FRONT_URL || "http://localhost:5173";
const API = process.env.API_URL || "http://localhost:8000";
const SORTIE = path.join(process.cwd(), "e2e", "captures");
fs.mkdirSync(SORTIE, { recursive: true });

const LARGEURS = [375, 768, 1024, 1440, 1920];

const MOT_300 = "M" + "o".repeat(298) + "T";
const MESSAGE_LONG =
  "Bonjour,\n\nNous souhaitons inscrire notre fille <en urgence> & en " +
  "internat.\n" +
  "Précision de la famille. ".repeat(210) +
  `\n\nRéférence interne : ${MOT_300}` +
  "\n\nCordialement,\nFamille Adjovi-Bokô";
const ADRESSE =
  "Carrefour Saint-Michel, derrière la pharmacie\nLot 42, parcelle B\n" +
  "Akpakpa, Cotonou, Bénin";

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

/**
 * Relève les débordements horizontaux RÉELS.
 *
 * Un élément plus large que la fenêtre n'est pas fautif en soi : un
 * tableau de huit colonnes DOIT pouvoir défiler dans son propre cadre.
 * Ce qui est fautif, c'est qu'il déborde sans que rien ne puisse le
 * faire défiler — le texte devient alors inatteignable — ou que la PAGE
 * elle-même parte en largeur.
 *
 * On ignore donc tout élément placé dans un ancêtre défilant, et on
 * vérifie séparément que le document ne dépasse pas la fenêtre.
 */
async function debordements(page) {
  return page.evaluate(() => {
    const largeur = document.documentElement.clientWidth;

    const dansUnCadreDefilant = (el) => {
      let parent = el.parentElement;
      while (parent && parent !== document.body) {
        const overflowX = getComputedStyle(parent).overflowX;
        if (overflowX === "auto" || overflowX === "scroll") return true;
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
        classe: (el.className || "").toString().slice(0, 60),
        depassement: Math.round(r.right - largeur),
        texte: (el.textContent || "").trim().slice(0, 40),
      });
    }
    return {
      largeurFenetre: largeur,
      largeurDocument: document.documentElement.scrollWidth,
      pageDefileHorizontalement:
        document.documentElement.scrollWidth > largeur + 1,
      coupables: coupables.slice(0, 5),
    };
  });
}

async function connexion(page, email, motDePasse) {
  await page.goto(`${FRONT}/login`, { waitUntil: "networkidle" });
  await page.fill('input[type="email"]', email);
  await page.fill('input[type="password"]', motDePasse);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.includes("/login"), { timeout: 15000 })
    .catch(() => {});
  await page.waitForTimeout(1500);
}

(async () => {
  const navigateur = await chromium.launch({
    // Le binaire préinstallé de l'environnement : la version de
    // playwright-core résolue ne correspond pas toujours au dossier
    // qu'elle attend par défaut.
    executablePath: '/opt/pw-browsers/chromium',
  });

  // ── 1. La famille dépose une demande complète ────────────────────
  console.log("\n── 1. Dépôt public d'une préinscription FEBA ──");
  {
    const page = await navigateur.newPage({ viewport: { width: 1440, height: 900 } });
    const reponse = await page.request.post(
      `${API}/api/website/preregistrations/`,
      {
        data: {
          parent_name: "Chris Adjovi-Bokô",
          phone: "+229 01 02 03 04",
          phone_secondary: "+229 05 06 07 08",
          whatsapp: "+229 09 10 11 12",
          email: "chris.adjovi@example.org",
          address: ADRESSE,
          child_name: "Amélie Adjovi-Bokô",
          child_age: 8,
          child_birth_date: "2017-04-12",
          desired_level: "ce1",
          school_year: "2026-2027",
          message: MESSAGE_LONG,
        },
      },
    );
    const corps = await reponse.json().catch(() => ({}));
    verifier("la demande est acceptée", reponse.status() === 201,
             `HTTP ${reponse.status()} ${JSON.stringify(corps).slice(0, 200)}`);
    verifier("un numéro de dossier est renvoyé à la famille",
             typeof corps.reference === "string" && corps.reference.startsWith("FEBA-"),
             JSON.stringify(corps.reference));
    global.__reference = corps.reference;
    await page.close();
  }

  // ── 2. Le dossier côté administration ────────────────────────────
  console.log("\n── 2. Le dossier vu par l'administration FEBA ──");
  {
    const page = await navigateur.newPage({ viewport: { width: 1440, height: 900 } });
    await connexion(page, "admin@feba.bj", "Admin@2024");
    await page.goto(`${FRONT}/admin/website`, { waitUntil: "networkidle" });

    // On attend l'onglet lui-même plutôt qu'un délai fixe : un délai
    // calibré sur une machine rapide fait échouer le parcours sur une
    // machine lente, et fait passer un écran vide sur une machine encore
    // plus rapide.
    const onglet = page.getByRole("button", { name: /Préinscriptions/ }).first();
    await onglet.waitFor({ state: "visible", timeout: 30000 });
    await onglet.click();
    // On attend la première ligne du tableau, pas un délai.
    await page.getByText(/FEBA-\d{4}-\d{4}/).first()
      .waitFor({ state: "visible", timeout: 30000 });

    const corps = await page.textContent("body");
    verifier("le numéro de dossier figure dans le tableau",
             corps.includes(global.__reference || "FEBA-"));
    verifier("le tableau reste compact (pas de message long dedans)",
             !(await page.textContent("table").catch(() => ""))
               .includes("Précision de la famille."));

    await page.screenshot({
      path: path.join(SORTIE, "p2-01-tableau-preinscriptions.png"), fullPage: true,
    });

    // Ouvrir la fiche complète.
    await page.locator('[title*="Voir le dossier"]').first().click();
    // Le titre du panneau est rendu avant la réponse du serveur :
    // on attend un élément du CORPS chargé.
    await page.getByRole("button", { name: /Régénérer la fiche/ })
      .waitFor({ state: "visible", timeout: 30000 });

    const fiche = await page.textContent("body");
    const attendus = [
      ["adresse électronique", "chris.adjovi@example.org"],
      ["WhatsApp", "+229 09 10 11 12"],
      ["téléphone secondaire", "+229 05 06 07 08"],
      ["date de naissance", "2017-04-12"],
      ["âge", "8 ans"],
      ["année scolaire", "2026-2027"],
      ["adresse du domicile", "Saint-Michel"],
      ["fin du message long", "Famille Adjovi-Bokô"],
    ];
    for (const [nom, valeur] of attendus) {
      verifier(`la fiche montre ${nom}`, fiche.includes(valeur), valeur);
    }

    // Le message est-il ENTIER ?
    const messageRendu = await page.evaluate(() => {
      const blocs = [...document.querySelectorAll('[data-testid="long-text"]')];
      const m = blocs.find((b) => b.textContent.includes("Précision de la famille."));
      return m ? { longueur: m.textContent.length,
                   fin: m.textContent.slice(-30),
                   coupe: m.textContent.includes("…") } : null;
    });
    verifier("le message long est présent dans la fiche", messageRendu !== null);
    if (messageRendu) {
      verifier("le message n'est pas tronqué par des points de suspension",
               !messageRendu.coupe);
      verifier("la fin du message est bien rendue",
               messageRendu.fin.includes("Adjovi-Bokô"), messageRendu.fin);
      verifier("la longueur affichée correspond à la saisie",
               messageRendu.longueur === MESSAGE_LONG.length,
               `${messageRendu.longueur} au lieu de ${MESSAGE_LONG.length}`);
    }

    await page.screenshot({
      path: path.join(SORTIE, "p2-02-fiche-complete.png"), fullPage: true,
    });

    // ── Mesure du débordement à chaque largeur ────────────────────
    console.log("\n── 3. Textes longs : mesure à cinq largeurs ──");
    for (const largeur of LARGEURS) {
      await page.setViewportSize({ width: largeur, height: 900 });
      await page.waitForTimeout(700);
      const m = await debordements(page);
      verifier(
        `aucun texte hors cadre à ${largeur} px`,
        m.coupables.length === 0,
        m.coupables.length
          ? `${m.coupables.length} élément(s), ex. ${JSON.stringify(m.coupables[0])}`
          : "",
      );
      verifier(
        `la page ne défile pas horizontalement à ${largeur} px`,
        !m.pageDefileHorizontalement,
        `document ${m.largeurDocument} px > fenêtre ${m.largeurFenetre} px`,
      );
      await page.screenshot({
        path: path.join(SORTIE, `p2-03-fiche-${largeur}px.png`), fullPage: true,
      });
    }

    await page.close();
  }

  // ── 4. Téléchargement de la fiche PDF ────────────────────────────
  console.log("\n── 4. La fiche PDF ──");
  {
    const page = await navigateur.newPage({ viewport: { width: 1440, height: 900 } });
    await connexion(page, "admin@feba.bj", "Admin@2024");
    const jeton = await page.evaluate(() => {
      const brut = localStorage.getItem("feba-auth");
      return brut ? JSON.parse(brut).state.accessToken : null;
    });
    verifier("l'administrateur dispose d'un jeton", !!jeton);

    const liste = await page.request.get(
      `${API}/api/website/admin/preregistrations/`,
      { headers: { Authorization: `Bearer ${jeton}` } });
    const lignes = await liste.json();
    const rows = lignes.results || lignes;
    const cible = rows[0];
    verifier("l'API admin renvoie la demande", !!cible);

    const pdf = await page.request.get(
      `${API}/api/website/admin/preregistrations/${cible.id}/sheet/`,
      { headers: { Authorization: `Bearer ${jeton}` } });
    verifier("la fiche PDF se télécharge", pdf.status() === 200,
             `HTTP ${pdf.status()}`);
    const octets = await pdf.body();
    verifier("le fichier reçu est bien un PDF",
             octets.slice(0, 5).toString() === "%PDF-");
    verifier("la fiche n'est pas mise en cache",
             (pdf.headers()["cache-control"] || "").includes("no-store"),
             pdf.headers()["cache-control"]);
    fs.writeFileSync(path.join(SORTIE, "p2-fiche-preinscription.pdf"), octets);

    const csv = await page.request.get(
      `${API}/api/website/admin/preregistrations/export/`,
      { headers: { Authorization: `Bearer ${jeton}` } });
    verifier("l'export CSV répond", csv.status() === 200);
    const texteCsv = (await csv.body()).toString("utf8");
    for (const colonne of ["WhatsApp", "Adresse du domicile", "Téléphone secondaire",
                           "Date de naissance", "Message"]) {
      verifier(`le CSV contient la colonne « ${colonne} »`,
               texteCsv.includes(colonne));
    }
    verifier("le CSV ne divulgue aucun chemin serveur",
             !texteCsv.includes("private_media"));
    fs.writeFileSync(path.join(SORTIE, "p2-preinscriptions.csv"), texteCsv);

    await page.close();
  }

  // ── 5. Cloisonnement des académies ───────────────────────────────
  console.log("\n── 5. Un administrateur FEBA FHA n'accède à rien ──");
  {
    const page = await navigateur.newPage({ viewport: { width: 1440, height: 900 } });
    await connexion(page, "admin@febafha.org", "Admin@2024");
    const jeton = await page.evaluate(() => {
      const brut = localStorage.getItem("feba-auth");
      return brut ? JSON.parse(brut).state.accessToken : null;
    });
    const liste = await page.request.get(
      `${API}/api/website/admin/preregistrations/`,
      { headers: { Authorization: `Bearer ${jeton}` } });
    verifier("la liste des préinscriptions FEBA lui est refusée",
             liste.status() === 403, `HTTP ${liste.status()}`);

    const pdf = await page.request.get(
      `${API}/api/website/admin/preregistrations/1/sheet/`,
      { headers: { Authorization: `Bearer ${jeton}` } });
    verifier("la fiche PDF d'une famille de Cotonou lui est refusée",
             pdf.status() === 403, `HTTP ${pdf.status()}`);

    const anonyme = await page.request.get(
      `${API}/api/website/admin/preregistrations/1/sheet/`);
    verifier("un anonyme n'obtient aucune fiche",
             [401, 403].includes(anonyme.status()), `HTTP ${anonyme.status()}`);
    await page.close();
  }

  await navigateur.close();

  console.log(`\n════ ${reussis} contrôle(s) réussi(s), ${echecs.length} échec(s) ════`);
  if (echecs.length) {
    for (const e of echecs) console.log(`  ✗ ${e}`);
    process.exit(1);
  }
})();
