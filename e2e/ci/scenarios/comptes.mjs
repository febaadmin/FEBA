// Comptes : logo de la page de connexion vers l'accueil public, réinitialisation
// du mot de passe d'un superadmin (compte de test créé pour l'occasion).
import { randomBytes } from "node:crypto";
import { API, BASE, COMPTES, api, connecter, jeton, liste, messages, motDePasse, ok, page, unique } from "../outils.mjs";

const S = "comptes";
const secret = () => randomBytes(9).toString("base64url") + "#7a";

async function logo(vp, lang, connecte) {
  const p = connecte ? await connecter("parent", { contexte: { viewport: vp } }) : await page({ viewport: vp });
  if (lang) await p.evaluate((l) => localStorage.setItem("feba-lang", l), lang).catch(() => {});
  let posts = 0;
  p.on("request", (r) => { if (r.url().includes("/auth/login/") && r.method() === "POST") posts += 1; });
  await p.goto(BASE + "/login");
  await p.waitForTimeout(400);
  const lien = p.getByTestId("logo-accueil");
  const visible = await lien.isVisible().catch(() => false);
  if (visible) {
    // Clic au bord de la pastille, pas seulement au centre de l'image.
    const b = await lien.boundingBox();
    await p.mouse.click(b.x + b.width * 0.2, b.y + b.height * 0.5);
    for (let i = 0; i < 30 && new URL(p.url()).pathname !== "/"; i++) await p.waitForTimeout(100);
  }
  const chemin = new URL(p.url()).pathname;
  const nom = `logo ${vp.width}px${lang ? " " + lang : ""}${connecte ? " avec session" : ""} : accueil public`;
  ok(S, nom, visible && chemin === "/" && posts === 0 && p.erreurs.length === 0, `${chemin} posts=${posts} ${p.erreurs}`);
  await p.contexte.close();
}

export default async function () {
  for (const vp of [{ width: 1366, height: 900 }, { width: 820, height: 1180 }, { width: 390, height: 800 }]) await logo(vp);
  await logo({ width: 1366, height: 900 }, "en");
  await logo({ width: 1366, height: 900 }, null, true);

  // Superadmin de test, isolé (base jetable de la CI).
  const jt = await jeton("superadmin");
  const email = `sa.e2e.${unique()}@feba.test`;
  const initial = secret();
  const cree = await api("POST", "/auth/users/", jt, { email, username: email.split("@")[0], first_name: "Essai", last_name: "Superadmin",
    role: "superadmin", password: initial, password2: initial, school: null });
  ok(S, "superadmin de test créé", cree.statut === 201, cree.statut + " " + cree.brut.slice(0, 200));
  // La réponse de création ne renvoie pas l'identifiant : on le relit. L'académie active
  // d'un superadmin est mémorisée côté serveur : on se place en « Toutes les Académies »
  // (les superadmins n'ont pas d'académie), sans dépendre de l'ordre des scénarios.
  await api("POST", "/auth/entity-context/switch/", jt, { entity_id: null });
  const tous = await api("GET", "/auth/users/?page_size=500", jt);
  const cible = liste(tous.donnees).find((u) => u.email === email) || {};
  ok(S, "superadmin de test retrouvé", Boolean(cible.id), tous.statut);

  const p = await connecter("superadmin");
  await p.goto(BASE + "/superadmin/users");
  await p.waitForTimeout(800);
  // Les superadmins n'ont pas d'académie : ils sont listés en mode « Toutes les Académies ».
  await p.locator("header [aria-haspopup=listbox]").click();
  await p.locator("[role=listbox] [role=option]", { hasText: /Toutes les Acad/ }).first().locator("button").click();
  await p.waitForTimeout(800);
  await p.getByRole("button", { name: "Super Admin", exact: true }).first().click();
  await p.waitForTimeout(800);
  const soi = p.locator("tr", { hasText: COMPTES.superadmin[0] });
  ok(S, "pas de réinitialisation sur son propre compte", await soi.count() > 0 && await soi.locator('button[title="Réinitialiser le mot de passe"]').count() === 0);
  const ligne = p.locator("tr", { hasText: email });
  const bouton = ligne.locator('button[title="Réinitialiser le mot de passe"]');
  ok(S, "bouton de réinitialisation sur un autre superadmin", await bouton.count() === 1);

  const nouveau = secret();
  const remplir = async (moi) => {
    await bouton.click();
    await p.waitForTimeout(400);
    const champs = p.locator('[role=dialog] input[autocomplete="new-password"]');
    await champs.nth(0).fill(nouveau);
    await champs.nth(1).fill(nouveau);
    await p.locator("#requester_password").fill(moi);
    await p.locator('[role=dialog] input[type="checkbox"]').check();
    return messages(p, () => p.locator('[role=dialog] button[type=submit]').click(), 1500);
  };
  let textes = await remplir("PasLeBon!" + unique());
  ok(S, "mauvais mot de passe de l'auteur : refus explicite", textes.some((t) => /incorrect/i.test(t)), JSON.stringify(textes));
  let essai = await fetch(API + "/auth/login/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password: nouveau }) });
  ok(S, "après refus, le mot de passe n'a pas changé", essai.status !== 200, essai.status);
  await p.keyboard.press("Escape");
  await p.waitForTimeout(700);

  textes = await remplir(motDePasse("superadmin"));
  ok(S, "réinitialisation confirmée à l'écran", textes.some((t) => /réinitialisé/i.test(t)), JSON.stringify(textes));
  essai = await fetch(API + "/auth/login/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password: nouveau }) });
  const corps = await essai.json().catch(() => ({}));
  ok(S, "le superadmin se connecte avec le nouveau mot de passe, changement imposé", essai.status === 200 && corps.must_change_password === true,
    essai.status + " " + JSON.stringify(Object.keys(corps)).slice(0, 120));
  // Écriture refusée : le motif du serveur s'affiche (auparavant : rien, la fenêtre restait ouverte).
  await p.goto(BASE + "/superadmin/users");
  await p.waitForTimeout(900);
  await p.getByRole("button", { name: "Super Admin", exact: true }).first().click();
  await p.waitForTimeout(700);
  await p.locator("tr", { hasText: email }).locator("button").nth(1).click();
  await p.waitForTimeout(500);
  const champEmail = p.locator('[role=dialog] input[type=email], [role=dialog] input[name=email]').first();
  await champEmail.fill(COMPTES.admin[0]);
  const refusAffiche = await messages(p, () => p.locator('[role=dialog] button[type=submit]').click(), 1500);
  ok(S, "écriture refusée : motif affiché", refusAffiche.length > 0, JSON.stringify(refusAffiche));
  await p.keyboard.press("Escape");
  await p.waitForTimeout(500);
  ok(S, "l'auteur reste connecté", (await api("GET", "/auth/me/", await jeton("superadmin"))).statut === 200);
  ok(S, "aucune erreur JS ni 5xx", p.erreurs.length === 0, p.erreurs.join(" | "));
  await p.contexte.close();

  // Un admin ne peut pas réinitialiser un superadmin, même par l'API.
  const refus = await api("POST", `/auth/users/${cible.id}/reset-password/`, await jeton("admin"),
    { new_password: secret(), confirm_password: "x", requester_password: motDePasse("admin") });
  ok(S, "admin → superadmin refusé (403)", refus.statut === 403, refus.statut);
  await api("DELETE", `/auth/users/${cible.id}/`, jt);
}
