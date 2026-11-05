// Messagerie interne : enseignant → parent (pièce jointe), réponse, non-lus, dossiers personnels
// (important, archives, corbeille, restauration), recherche, brouillon, confidentialité
// (identifiant deviné refusé), affichage mobile.
import { BASE, api, connecter, jeton, ok, unique } from "../outils.mjs";

const S = "messagerie";
const PDF = Buffer.from("%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF");

export default async function () {
  const u = unique();
  const jp = await jeton("parent");
  const jt = await jeton("teacher");
  const parentId = (await api("GET", "/auth/me/", jp)).donnees.id;

  const t = await connecter("teacher");
  await t.goto(BASE + "/teacher/messages");
  await t.getByTestId("messagerie").waitFor({ timeout: 15000 });
  await t.getByTestId("nouveau-message").click();
  await t.getByTestId(`destinataire-${parentId}`).waitFor({ timeout: 10000 });
  await t.getByTestId(`destinataire-${parentId}`).click();
  await t.getByLabel("Objet").fill("Sujet" + u);
  await t.getByLabel("Message", { exact: true }).fill("Corps" + u);
  await t.getByTestId("composition").locator("input[type=file]").setInputFiles({ name: "programme.pdf", mimeType: "application/pdf", buffer: PDF });
  await t.getByTestId("composition-envoyer").click();
  await t.getByTestId("fil-objet").waitFor({ timeout: 10000 });
  ok(S, "message envoyé (fil ouvert)", (await t.getByTestId("fil-objet").innerText()) === "Sujet" + u);

  const p = await connecter("parent");
  await p.goto(BASE + "/parent/messages");
  const ligne = p.locator("[data-testid^=conversation-]", { hasText: "Sujet" + u });
  await ligne.waitFor({ timeout: 15000 });
  ok(S, "message reçu, signalé non lu, avec pièce jointe", await ligne.getByTestId("non-lu").count() === 1
    && await ligne.getByLabel("Pièces jointes").count() === 1);
  ok(S, "badge de la boîte de réception", Number(await p.getByTestId("badge-reception").innerText()) >= 1);
  const convId = Number((await ligne.getAttribute("data-testid")).split("-")[1]);
  await ligne.click();
  await p.getByTestId("fil").waitFor();
  ok(S, "contenu lisible", (await p.getByTestId("fil").innerText()).includes("Corps" + u));
  const lien = p.getByTestId("piece-jointe").first();
  const href = await lien.getAttribute("href");
  ok(S, "pièce jointe par lien signé", href.startsWith("/api/files/"), href);
  const telechargement = await p.request.get(BASE + href);
  ok(S, "pièce jointe téléchargeable par le destinataire", telechargement.status() === 200, telechargement.status());
  await p.waitForTimeout(1500);
  ok(S, "lu à l'ouverture", await p.locator(`[data-testid=conversation-${convId}] [data-testid=non-lu]`).count() === 0);

  await p.getByTestId("reponse-texte").fill("Reponse" + u);
  await p.getByTestId("reponse-envoyer").click();
  await p.waitForTimeout(1500);
  await t.getByTestId("dossier-reception").click();
  const chezProf = t.locator(`[data-testid=conversation-${convId}]`);
  await chezProf.waitFor({ timeout: 15000 });
  await chezProf.click();
  await t.waitForTimeout(800);
  ok(S, "réponse reçue par l'enseignant", (await t.getByTestId("fil").innerText()).includes("Reponse" + u));

  // Dossiers personnels du parent : important, archive, corbeille, restauration.
  const conv = p.locator(`[data-testid=conversation-${convId}]`);
  await p.getByTestId("fil-important").click();
  await p.getByTestId("dossier-importants").click();
  await conv.waitFor({ timeout: 10000 });
  ok(S, "dossier Importants", await conv.count() === 1);
  await conv.click();
  await p.getByTestId("fil-restaurer").click().catch(() => {});      // dossier « reception » : pas de restauration
  await p.getByTestId("dossier-reception").click();
  await conv.click();
  await p.getByTestId("fil-archiver").click();
  await p.getByTestId("dossier-archives").click();
  await conv.waitFor({ timeout: 10000 });
  const chezEnseignant = (await api("GET", "/messages/conversations/?dossier=reception", jt)).donnees.some((c) => c.id === convId);
  ok(S, "archivée (état personnel : l'enseignant la garde)", chezEnseignant);
  await conv.click();
  await p.getByTestId("fil-corbeille").click();
  await p.getByTestId("dossier-corbeille").click();
  await conv.waitFor({ timeout: 10000 });
  await conv.click();
  await p.getByTestId("fil-restaurer").click();
  await p.getByTestId("dossier-reception").click();
  await conv.waitFor({ timeout: 10000 });
  ok(S, "corbeille puis restauration", await conv.count() === 1);

  await p.getByTestId("messagerie-recherche").fill("Corps" + u);
  await p.waitForTimeout(1500);
  ok(S, "recherche dans le contenu", await p.locator("[data-testid^=conversation-]").count() === 1);
  await p.getByTestId("messagerie-recherche").fill("");

  // Brouillon (parent → enseignant), repris depuis le dossier Brouillons.
  await p.getByTestId("nouveau-message").click();
  await p.getByTestId("composition").locator("[data-testid^=destinataire-]:not([data-testid$=recherche])").first().click();
  await p.getByLabel("Objet").fill("Brouillon" + u);
  await p.getByLabel("Message", { exact: true }).fill("A finir");
  await p.getByTestId("composition-brouillon").click();
  await p.waitForTimeout(1200);
  await p.keyboard.press("Escape");
  await p.getByTestId("dossier-brouillons").click();
  const brouillon = p.locator("[data-testid^=brouillon-]", { hasText: "Brouillon" + u });
  await brouillon.waitFor({ timeout: 10000 });
  await brouillon.locator("button").first().click();
  ok(S, "brouillon repris", (await p.getByLabel("Objet").inputValue()) === "Brouillon" + u);
  await p.keyboard.press("Escape");

  // Confidentialité : un autre parent ne lit pas la conversation, même en devinant l'identifiant.
  const autre = await api("GET", `/messages/conversations/${convId}/`, await jeton("parentAutre"));
  ok(S, "identifiant deviné : 404 pour un non-participant", autre.statut === 404, autre.statut);
  const admin = await api("GET", "/messages/conversations/?dossier=reception", await jeton("admin"));
  ok(S, "l'administration ne voit pas l'échange", !admin.donnees.some((c) => c.id === convId));

  ok(S, "aucune erreur", t.erreurs.length + p.erreurs.length === 0, [...t.erreurs, ...p.erreurs].join(" | "));
  await t.contexte.close();
  await p.contexte.close();

  // Mobile : liste puis lecture, retour.
  const m = await connecter("parent", { contexte: { viewport: { width: 390, height: 844 } } });
  await m.goto(BASE + "/parent/messages");
  const premiere = m.locator("[data-testid^=conversation-]").first();
  await premiere.waitFor({ timeout: 15000 });
  await premiere.click();
  await m.getByTestId("fil-retour").waitFor();
  const deborde = await m.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  ok(S, "390px : lecture plein écran, sans débordement", !deborde && !(await premiere.isVisible()), String(deborde));
  await m.getByTestId("fil-retour").click();
  ok(S, "390px : retour à la liste", await m.locator("[data-testid^=conversation-]").first().isVisible());
  ok(S, "390px : aucune erreur", m.erreurs.length === 0, m.erreurs);
  await m.contexte.close();
}
