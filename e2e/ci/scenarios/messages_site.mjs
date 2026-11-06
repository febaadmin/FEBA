// Phase 9 — messages du site vitrine et compteur « Messages ».
// Réponse par e-mail dans l'éditeur INTERNE (jamais mailto ni application externe),
// deux boutons toujours présents, WhatsApp sur le seul numéro WhatsApp, historique ;
// badge du menu exact et mis à jour après lecture ; onglet resté ouvert pendant un
// déploiement (module JavaScript introuvable) : rechargement unique, pas d'écran d'erreur.
// Backend E2E en locmem : aucun e-mail ne sort ; destinataires fictifs @exemple.org.
import { API, BASE, api, connecter, jeton, ok, unique } from "../outils.mjs";

const S = "messages_site";

async function deposer(nom, email, whatsapp, sujet) {
  const r = await fetch(API + "/website/contact/", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: nom, email, phone: "+229 01 97 00 00 01", whatsapp, subject: sujet, message: `Bonjour, ${sujet}.`, consent: true }) });
  return r.status;
}

export default async function () {
  const u = unique();
  const ja = await jeton("admin");
  ok(S, "message déposé sur le site (sans WhatsApp)", await deposer(`Sans WA ${u}`, `sanswa${u}@exemple.org`, "", `Infos ${u}`) === 201);
  ok(S, "message déposé sur le site (avec WhatsApp)", await deposer(`Avec WA ${u}`, `avecwa${u}@exemple.org`, "+229 01 96 11 22 33", `Tarifs ${u}`) === 201);

  const p = await connecter("admin");
  const externes = [];
  p.contexte.on("page", (n) => externes.push(n.url()));
  p.on("request", (r) => { if (/^mailto:|mail\.google\.com/.test(r.url())) externes.push(r.url()); });
  await p.goto(BASE + "/admin/website");
  await p.getByRole("button", { name: /Messages reçus/i }).click();

  // Avec WhatsApp : lien wa.me sur le numéro WhatsApp (pas le téléphone).
  await p.getByText(`Avec WA ${u}`).click();
  const wa = p.getByTestId("repondre-whatsapp");
  await wa.waitFor({ timeout: 10000 });
  ok(S, "WhatsApp : numéro WhatsApp normalisé", (await wa.getAttribute("href") || "").startsWith("https://wa.me/2290196112233?"), await wa.getAttribute("href"));
  const [l1, l2] = [await wa.boundingBox(), await p.getByTestId("repondre-email").boundingBox()];
  ok(S, "deux boutons de même hauteur", Math.abs(l1.height - l2.height) < 1, `${l1.height}/${l2.height}`);
  await p.keyboard.press("Escape");
  await p.waitForTimeout(400);

  // Sans WhatsApp : bouton présent et désactivé, raison affichée ; e-mail interne.
  await p.getByText(`Sans WA ${u}`).click();
  await p.getByTestId("actions-contact").waitFor({ timeout: 10000 });
  ok(S, "WhatsApp absent : bouton visible et désactivé", await p.getByTestId("repondre-whatsapp").isDisabled());
  ok(S, "raison affichée", await p.getByText("Aucun numéro WhatsApp renseigné par le contact.").first().isVisible());
  ok(S, "aucun lien mailto dans la fiche", await p.locator('a[href^="mailto:"]').count() === 0);
  await p.getByTestId("repondre-email").click();
  const f = p.getByTestId("reponse-email");
  await f.waitFor({ timeout: 10000 });
  ok(S, "éditeur interne prérempli (destinataire)", await f.getByTestId("rep-a").inputValue() === `sanswa${u}@exemple.org`);
  ok(S, "objet « Re: … »", await f.getByLabel("Objet").inputValue() === `Re: Infos ${u}`);
  ok(S, "message d'origine visible", (await f.innerText()).includes(`Bonjour, Infos ${u}.`));
  await f.getByTestId("editeur-texte").fill(`Bonjour, voici la réponse ${u}.`);
  await f.getByTestId("rep-envoyer").click();
  await f.waitFor({ state: "detached", timeout: 15000 });
  const hist = p.getByTestId("reponses-envoyees");
  await hist.waitFor({ timeout: 10000 });
  ok(S, "historique : réponse acceptée par le serveur d'envoi", (await hist.innerText()).includes("Accepté par le serveur d'envoi"));
  ok(S, "aucune redirection externe (mailto, Gmail, nouvel onglet)", externes.length === 0, externes.join(" "));

  const msgs = (await api("GET", "/website/admin/contact-messages/", ja)).donnees;
  const m = (msgs.results || msgs).find((x) => x.name === `Sans WA ${u}`);
  const reps = (await api("GET", `/website/admin/contact-messages/${m.id}/reponses/`, ja)).donnees;
  ok(S, "API : réponse reliée au message d'origine", reps.length === 1 && reps[0].a[0] === `sanswa${u}@exemple.org` && m.nb_reponses === 1);
  const envoyes = (await api("GET", `/boite-mail/messages/?dossier=envoyes&q=${encodeURIComponent(`Infos ${u}`)}`, await jeton("superadmin"))).donnees;
  ok(S, "boîte contact : réponse dans « Envoyés »", (envoyes.results || []).some((x) => x.origine === "site_vitrine"), JSON.stringify(envoyes).slice(0, 200));

  // Téléphone : les deux boutons restent utilisables, sans débordement horizontal.
  await p.setViewportSize({ width: 375, height: 812 });
  await p.waitForTimeout(400);
  const deborde = await p.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  ok(S, "mobile : pas de défilement horizontal", !deborde);
  await p.screenshot({ path: `/tmp/e2e-messages-site-mobile.png` }).catch(() => {});
  await p.setViewportSize({ width: 1366, height: 900 });

  // Badge du menu : enseignant → parent, puis lecture → badge à jour sans recharger.
  const jp = await jeton("parent");
  const parentId = (await api("GET", "/auth/me/", jp)).donnees.id;
  const avant = (await api("GET", "/messages/conversations/unread_count/", jp)).donnees.count;
  const fd = new FormData();
  fd.append("recipient_ids", String(parentId)); fd.append("subject", `Badge ${u}`); fd.append("body", "Bonjour");
  const cree = await api("POST", "/messages/conversations/", await jeton("teacher"), fd);
  const conv = cree.donnees;
  ok(S, "conversation créée (enseignant → parent)", cree.statut === 201, `${cree.statut} ${cree.brut.slice(0, 160)}`);
  const par = await connecter("parent");
  // Page d'accueil du parent (/parent/home), ouverte par la connexion.
  const badge = par.getByTestId("badge-messages-menu");
  await par.waitForTimeout(2500);                                  // premier rafraîchissement du compteur après connexion
  await badge.waitFor({ timeout: 15000 });
  ok(S, "badge = conversations non lues (API)", Number(await badge.innerText()) === Math.min(avant + 1, 9) || (avant + 1 > 9 && (await badge.innerText()) === "9+"));
  await par.goto(BASE + "/parent/messages");
  await par.locator(`[data-testid=conversation-${conv.id}]`).click();
  await par.getByTestId("fil").waitFor();
  await par.waitForTimeout(2000);
  const apres = (await api("GET", "/messages/conversations/unread_count/", jp)).donnees.count;
  const visible = await badge.count() ? Number(await badge.innerText()) : 0;
  ok(S, "badge mis à jour après lecture, sans rechargement", apres === avant && visible === Math.min(apres, 9), `${avant}/${apres}/${visible}`);

  // Les cinq profils : badge du menu = compteur de l'API (0 = pas de badge).
  for (const role of ["superadmin", "admin", "teacher", "parent", "student"]) {
    const attendu = (await api("GET", "/messages/conversations/unread_count/", await jeton(role))).donnees.count;
    const x = await connecter(role);
    await x.waitForTimeout(2500);
    const b = x.getByTestId("badge-messages-menu");
    const affiche = await b.count() ? (await b.innerText()).trim() : "0";
    ok(S, `badge exact (${role})`, affiche === (attendu > 9 ? "9+" : String(attendu)), `${affiche} / API ${attendu}`);
    await x.contexte.close();
  }

  // Version périmée : le module de la page répond 404 une fois (comme après un déploiement).
  const s = await connecter("superadmin");
  let coupes = 0;
  const debutChunk = Date.now();
  await s.route(/\/assets\/Messages-[\w-]+\.js$/, (r) => (coupes++ === 0 ? r.fulfill({ status: 404, body: "" }) : r.continue()));
  await s.getByRole("link", { name: /^Messages/ }).first().click();
  await s.waitForTimeout(4000);
  const ecranErreur = await s.getByText("Une erreur est survenue.").count();
  ok(S, "module introuvable : rechargement unique puis page affichée", coupes >= 1 && ecranErreur === 0 && s.url().includes("/messages"), `coupes=${coupes} erreur=${ecranErreur} ${s.url()}`);
  const js = await jeton("superadmin");
  const recents = (await api("GET", "/incidents/?module=frontend", js)).donnees.results || [];
  const details = await Promise.all(recents.slice(0, 5).map((i) => api("GET", `/incidents/${i.id}/`, js).then((r) => r.donnees)));
  const recentes = details.filter((d) => Date.parse(d.last_seen_at || d.created_at) > debutChunk - 2000);
  ok(S, "incident « version périmée » enregistré côté serveur", recentes.some((d) => JSON.stringify(d).includes("version périmée")));
  ok(S, "aucune erreur d'affichage trompeuse après le rechargement", !recentes.some((d) => JSON.stringify(d).includes("Erreur d'affichage")),
    recentes.map((d) => d.message || d.title).join(" | "));

  for (const x of [p, par, s]) ok(S, `aucune erreur JS / 5xx (${x.racine})`, x.erreurs.length === 0, x.erreurs.join(" | "));
}
