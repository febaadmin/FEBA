// Modules non couverts ailleurs : site public et préinscription, export protégé, relances, transactions,
// rapports mensuels, admissions FHA, emploi du temps. Écritures sur la base jetable seulement.
import { API, BASE, api, connecter, jeton, liste, ok, page, unique } from "../outils.mjs";

const S = "modules";
export default async function () {
  const u = unique();
  const [sa, ad, pr, el] = await Promise.all(["superadmin", "admin", "teacher", "student"].map(jeton));

  // Site public : pages en français puis en anglais, sans erreur.
  const p = await page();
  const pages = ["/", "/a-propos", "/academique", "/admissions", "/actualites", "/galerie", "/contact", "/campus", "/feba-fha"];
  const vides = [];
  for (const chemin of pages) {
    await p.goto(BASE + chemin);
    await p.waitForTimeout(900);
    if ((await p.locator("body").innerText()).length < 200) vides.push(chemin);
  }
  ok(S, `site public : ${pages.length} pages remplies, sans erreur`, vides.length === 0 && p.erreurs.length === 0, `${vides} ${p.erreurs}`);
  await p.goto(BASE + "/");
  await p.waitForTimeout(800);
  const fr = await p.locator("body").innerText();
  await p.getByRole("button", { name: "English", exact: true }).filter({ visible: true }).first().click();
  await p.waitForTimeout(1200);
  ok(S, "site public : bascule en anglais", (await p.locator("body").innerText()) !== fr);
  await p.contexte.close();

  // Préinscription publique, puis lecture par l'administration et export protégé contre les formules.
  const formule = `=HYPERLINK("http://exemple.test","E2E${u}")`;
  const pre = await fetch(API + "/website/preregistrations/", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ parent_name: formule, phone: "+22997000000", child_name: `Enfant${u}`, desired_level: "maternelle1", website: "" }) });
  ok(S, "préinscription publique acceptée", pre.status === 201, pre.status);
  const piege = await fetch(API + "/website/preregistrations/", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ parent_name: "Robot", phone: "+22997000001", child_name: `Robot${u}`, desired_level: "maternelle1", website: "http://spam.test" }) });
  const demandes = liste((await api("GET", "/website/admin/preregistrations/?page_size=500", sa)).donnees);
  ok(S, "préinscription visible par l'administration", demandes.some((d) => d.child_name === `Enfant${u}`));
  ok(S, "champ piège : le robot n'est pas enregistré", !demandes.some((d) => d.child_name === `Robot${u}`), piege.status);
  const csv = await api("GET", "/website/admin/preregistrations/export/", sa);
  ok(S, "export : la formule est neutralisée", csv.statut === 200 && csv.brut.includes(`'=HYPERLINK`) && !/(^|;|")=HYPERLINK/.test(csv.brut.replace(/'=HYPERLINK/g, "")), csv.statut);
  ok(S, "préinscriptions refusées à un enseignant", [403, 404].includes((await api("GET", "/website/admin/preregistrations/", pr)).statut));

  // Relances de paiement : lecture des règles et de l'aperçu, refus hors administration.
  for (const chemin of ["/payments/reminders/status/", "/payments/reminders/policy/", "/payments/reminders/preview/"]) {
    ok(S, `relances ${chemin.split("/")[3]} : administration`, (await api("GET", chemin, ad)).statut === 200);
  }
  ok(S, "relances refusées à un enseignant", (await api("GET", "/payments/reminders/policy/", pr)).statut === 403);
  ok(S, "lancement des relances refusé à un élève", [403, 405].includes((await api("POST", "/payments/reminders/run/", el, {})).statut));

  // Transactions par carte : liste lisible, paiement par carte désactivé, pas de remboursement par un élève.
  ok(S, "transactions carte : liste administration", (await api("GET", "/payments/card/transactions/", ad)).statut === 200);
  const config = await api("GET", "/payments/card/config/", el);
  ok(S, "paiement par carte : configuration lisible", config.statut === 200, config.statut);
  ok(S, "remboursement refusé à un élève", [403, 404].includes((await api("POST", "/payments/card/1/refund/", el, {})).statut));

  // Rapports mensuels et admissions FHA : lecture par l'administration de l'académie en ligne.
  const contexte = (await api("GET", "/auth/entity-context/", sa)).donnees;
  const fha = (contexte.entities || contexte.allowed_entities || []).find((e) => /FHA/.test(e.code || ""));
  ok(S, "académie en ligne trouvée", Boolean(fha), JSON.stringify(Object.keys(contexte)));
  if (fha) {
    ok(S, "rapports mensuels : liste superadmin", (await api("GET", `/monthly-reports/reports/?school_id=${fha.id}`, sa)).statut === 200);
    ok(S, "admissions FHA : liste superadmin", (await api("GET", `/website/admin/fha-applications/?school_id=${fha.id}`, sa)).statut === 200);
  }
  ok(S, "rapports mensuels refusés à un élève", [403, 404].includes((await api("GET", "/monthly-reports/reports/", el)).statut));

  // Interfaces de ces modules : ouverture et état cohérent pour l'administration.
  const a = await connecter("admin");
  for (const chemin of ["/admin/payment-reminders", "/admin/card-transactions", "/admin/enrollments", "/admin/official-documents", "/admin/document-templates", "/admin/schedule"]) {
    a.erreurs.length = 0;
    await a.goto(BASE + chemin);
    await a.waitForTimeout(1300);
    ok(S, `écran ${chemin}`, a.erreurs.length === 0 && (await a.locator("main").innerText()).length > 50, a.erreurs.join(" | "));
  }
  await a.contexte.close();
}
