// E-mails groupés devenus un outil de composition : À / Cc / Cci (adresses saisies et membres),
// message commun, mise en forme, brouillon avec pièce jointe repris puis envoyé, suivi des envois.
// Le backend E2E capture les messages (locmem) : aucun e-mail ne sort.
import { BASE, api, connecter, jeton, ok, unique } from "../outils.mjs";

const S = "emails";

export default async function () {
  const u = unique();
  const ja = await jeton("admin");
  const options = (await api("GET", "/mass-email/options/", ja)).donnees;
  const membres = (await api("GET", "/mass-email/recipients/", ja)).donnees.results.filter((m) => m.sendable);
  const prof = membres.find((m) => m.role === "teacher") || membres[0];

  // API : confidentialité des champs et refus explicites.
  const apercu = await api("POST", "/mass-email/preview/", ja, {
    adresses: { a: [`a${u}@exemple.org`], cc: [prof.id], cci: [`cache${u}@exemple.org`] }, mode: "commun",
    body_format: "html", body_html: "<p>Bonjour <b>tous</b><script>x()</script></p>",
  });
  ok(S, "API : aperçu par champ (À, Cc, Cci)", apercu.statut === 200 &&
    apercu.donnees.par_champ.a === 1 && apercu.donnees.par_champ.cc === 1 && apercu.donnees.par_champ.cci === 1, JSON.stringify(apercu.donnees.par_champ));
  ok(S, "API : HTML nettoyé côté serveur", apercu.donnees.html_nettoye === "<p>Bonjour <b>tous</b></p>", apercu.donnees.html_nettoye);
  ok(S, "API : adresse invalide refusée (400)",
    (await api("POST", "/mass-email/preview/", ja, { adresses: { a: ["pas-une-adresse"] } })).statut === 400);
  ok(S, "API : compositeur interdit à un enseignant (403)",
    (await api("GET", "/mass-email/brouillons/", await jeton("teacher"))).statut === 403);
  ok(S, "API : statut inconnu refusé (400)", (await api("GET", "/mass-email/campaigns/?statut=livre", ja)).statut === 400);

  const p = await connecter("admin");
  await p.goto(BASE + "/admin/emails");
  await p.getByTestId("compositeur").waitFor({ timeout: 15000 });
  const a = p.getByTestId("champ-a-saisie");
  await a.fill(`externe${u}@exemple.org`);
  await a.press("Enter");
  ok(S, "écran : adresse saisie en pastille", await p.getByTestId("champ-a-pastille").count() === 1);
  await p.getByTestId("voir-copies").click();
  await p.getByTestId("champ-cc-saisie").fill(prof.full_name.slice(0, 4));
  await p.getByTestId(`champ-cc-suggestion-${prof.id}`).click();
  ok(S, "écran : membre suggéré ajouté en Cc", await p.getByTestId("champ-cc-pastille").count() === 1);
  await p.getByTestId("champ-cci-saisie").fill(`cache${u}@exemple.org`);
  await p.getByTestId("champ-cci-saisie").press(",");
  await p.getByTestId("mode-commun").check();
  await p.getByLabel("Objet").fill(`Conseil ${u}`);
  const editeur = p.getByTestId("editeur-html");
  await editeur.click();
  await p.keyboard.type("Bonjour à tous, ");
  await p.getByTestId("outil-bold").click();
  await p.keyboard.type("réunion lundi");
  await p.getByTestId("inserer-signature").click();
  if (await p.getByLabel("Signature (texte)").count()) {
    await p.getByLabel("Signature (texte)").fill(`La direction ${u}`);
    await p.getByRole("button", { name: "Enregistrer", exact: true }).click();
    await p.waitForTimeout(800);
    await p.getByTestId("inserer-signature").click();
  }
  const contenu = await editeur.innerHTML();
  ok(S, "écran : mise en forme et signature dans l'éditeur",
    /<(b|strong)>réunion lundi<\/(b|strong)>/.test(contenu) && /La direction/.test(contenu), contenu);

  // Brouillon avec pièce jointe, puis reprise depuis l'onglet Brouillons.
  await p.getByLabel("Pièces jointes").setInputFiles({ name: "programme.pdf", mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF") });
  await p.getByTestId("enregistrer-brouillon").click();
  await p.locator("[data-testid=compositeur] h2", { hasText: "Brouillon" }).waitFor({ timeout: 10000 }).catch(() => {});
  const titre = await p.locator("[data-testid=compositeur] h2").first().innerText();
  ok(S, "écran : brouillon enregistré avec sa pièce jointe", titre.trim() === "Brouillon", titre);
  await p.getByTestId("onglet-brouillons").click();
  const ligne = p.locator("[data-testid^=brouillon-]", { hasText: `Conseil ${u}` });
  await ligne.waitFor({ timeout: 10000 });
  const texteLigne = (await ligne.innerText()).replace(/\s+/g, " ");
  ok(S, "écran : brouillon listé (1 pièce jointe)", texteLigne.includes("1 pièce(s) jointe(s)"), texteLigne);
  await ligne.getByRole("button", { name: "Reprendre" }).click();
  await p.getByTestId("compositeur").waitFor();
  ok(S, "écran : brouillon repris (destinataires et objet)",
    (await p.getByLabel("Objet").inputValue()) === `Conseil ${u}` && await p.getByTestId("champ-cci-pastille").count() === 1);

  await p.getByTestId("previsualiser").click();
  await p.getByTestId("apercu-email").waitFor({ timeout: 10000 });
  ok(S, "écran : aperçu HTML nettoyé et décompte par champ",
    (await p.getByTestId("apercu-champs").innerText()).includes("Cci : 1") && await p.getByTestId("apercu-html").locator("b, strong").count() === 1);
  await p.getByRole("button", { name: /Envoyer à 3 destinataire/ }).click();
  await p.getByRole("button", { name: /Confirmer l'envoi/ }).click();
  await p.getByText("Rapport d'envoi").waitFor({ timeout: 15000 });
  await p.waitForTimeout(2500);

  const envois = (await api("GET", `/mass-email/campaigns/?q=${encodeURIComponent(`Conseil ${u}`)}`, ja)).donnees.results;
  ok(S, "API : envoi retrouvé par la recherche", envois.length === 1, envois.length);
  const detail = (await api("GET", `/mass-email/campaigns/${envois[0].id}/`, ja)).donnees;
  const champs = Object.fromEntries(detail.recipients.map((r) => [r.email, r.champ]));
  ok(S, "API : destinataires À / Cc / Cci enregistrés", champs[`externe${u}@exemple.org`] === "a" &&
    champs[prof.email] === "cc" && champs[`cache${u}@exemple.org`] === "cci", JSON.stringify(champs));
  ok(S, "API : pièce jointe du brouillon envoyée", detail.attachments.length === 1 && detail.attachments[0].name === "programme.pdf");
  ok(S, "API : message mis en forme archivé", detail.body_format === "html" && /réunion lundi/.test(detail.body));
  ok(S, "API : brouillon supprimé après l'envoi",
    !(await api("GET", "/mass-email/brouillons/", ja)).donnees.results.some((b) => b.objet === `Conseil ${u}`));
  ok(S, "API : statut honnête (jamais « délivré »)", !/délivr/i.test(detail.status_display), detail.status_display);

  await p.getByRole("button", { name: /Fermer/ }).first().click().catch(() => {});
  await p.getByTestId("envois-recherche").fill(`Conseil ${u}`);
  await p.waitForTimeout(1200);
  ok(S, "écran : recherche dans les envois", await p.locator("[data-testid^=envoi-]").count() === 1);
  ok(S, "écran : aucune erreur JS ni 5xx", p.erreurs.length === 0, p.erreurs);
  await p.contexte.close();

  const m = await connecter("admin", { contexte: { viewport: { width: 390, height: 844 } } });
  await m.goto(BASE + "/admin/emails");
  await m.getByTestId("compositeur").waitFor({ timeout: 15000 });
  const deborde = await m.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  ok(S, "390px : compositeur sans débordement, sans erreur", !deborde && m.erreurs.length === 0, `${deborde} ${m.erreurs}`);
  await m.contexte.close();
  void options;
}
