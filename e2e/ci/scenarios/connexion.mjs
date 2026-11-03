// Connexion : première tentative sous latence, 5 profils, erreurs réseau, sessions.
import { BASE, COMPTES, connecter, latence, messages, motDePasse, ok, page } from "../outils.mjs";

const S = "connexion";
const faux = (t) => t.some((x) => /incorrects|invalid credentials/i.test(x));

async function tente(role, { lat = 250, vp, lang, mdp, email, panne, action = "clic" } = {}) {
  const p = await page(vp ? { viewport: vp } : {});
  if (lang) await p.contexte.addInitScript((l) => localStorage.setItem("feba-lang", l), lang);
  if (lat) await latence(p, lat);
  if (panne) await p.route(panne.url, panne.reponse);
  const st = { post: 0, annulees: 0 };
  p.on("request", (r) => { if (r.url().includes("/auth/login/") && r.method() === "POST") st.post += 1; });
  p.on("requestfailed", (r) => { if (r.url().includes("/auth/me/")) st.annulees += 1; });
  await p.goto(BASE + "/login");
  await p.locator("#login-email").fill(email || COMPTES[role][0]);
  await p.locator("#login-password").fill(mdp || motDePasse(role));
  const textes = await messages(p, async () => {
    const bouton = p.locator("button[type=submit]");
    if (action === "entree") await p.locator("#login-password").press("Enter");
    else if (action === "double") await bouton.dblclick();
    else await bouton.click();
    for (let i = 0; i < 40 && p.url().includes("/login"); i++) await p.waitForTimeout(150);
  }, 1000);
  const session = await p.evaluate(() => { try { return Boolean(JSON.parse(localStorage.getItem("feba-auth")).state.accessToken); } catch { return false; } });
  return { p, textes, session, ...st };
}

export default async function () {
  for (const lat of [0, 250, 600]) {
    for (const role of ["superadmin", "admin", "teacher", "parent", "student"]) {
      const r = await tente(role, { lat });
      ok(S, `${role}, ${lat} ms : première tentative`, r.p.url().includes(COMPTES[role][2]) && !faux(r.textes) && r.post === 1 && r.annulees === 0,
        `${r.p.url()} ${JSON.stringify(r.textes)} post=${r.post} annulees=${r.annulees}`);
      await r.p.contexte.close();
    }
  }
  let r = await tente("parent", { action: "double" });
  ok(S, "double clic : une seule requête", r.post === 1 && r.p.url().includes("/parent"), `post=${r.post}`);
  await r.p.contexte.close();
  r = await tente("student", { action: "entree" });
  ok(S, "touche Entrée", r.p.url().includes("/student"));
  await r.p.contexte.close();
  r = await tente("admin", { vp: { width: 390, height: 800 } });
  ok(S, "téléphone", r.p.url().includes("/admin") && !faux(r.textes));
  await r.p.contexte.close();
  r = await tente("teacher", { lang: "en" });
  ok(S, "anglais", r.p.url().includes("/teacher") && !faux(r.textes));
  await r.p.contexte.close();

  r = await tente("admin", { mdp: "MauvaisMotDePasse!9" });
  ok(S, "mauvais mot de passe refusé", r.p.url().includes("/login") && faux(r.textes) && !r.session, JSON.stringify(r.textes));
  await r.p.contexte.close();
  r = await tente("admin", { email: "personne@feba.bj", mdp: "Inconnu!12345" });
  ok(S, "compte inconnu refusé", r.p.url().includes("/login") && faux(r.textes) && !r.session);
  await r.p.contexte.close();

  const pannes = [
    ["coupure de la connexion", "**/auth/login/", (x) => x.abort("failed")],
    ["coupure du profil", "**/auth/me/", (x) => x.abort("failed")],
    ["502", "**/auth/login/", (x) => x.fulfill({ status: 502, body: "x" })],
    ["504", "**/auth/login/", (x) => x.fulfill({ status: 504, body: "x" })],
  ];
  for (const [nom, url, reponse] of pannes) {
    r = await tente("admin", { lat: 0, panne: { url, reponse } });
    ok(S, `${nom} : pas de faux « identifiants incorrects », pas de session`, !faux(r.textes) && r.p.url().includes("/login") && !r.session, JSON.stringify(r.textes));
    await r.p.contexte.close();
  }
  r = await tente("admin", { lat: 0, panne: { url: "**/auth/login/", reponse: (x) => x.fulfill({ status: 429, contentType: "application/json", body: '{"detail":"x"}' }) } });
  ok(S, "429 : limite annoncée", r.textes.some((x) => /tentatives/i.test(x)), JSON.stringify(r.textes));
  await r.p.contexte.close();

  // Rechargement, déconnexion, reconnexion dans le même onglet.
  const p = await connecter("admin");
  await p.reload();
  await p.waitForTimeout(1500);
  ok(S, "session gardée au rechargement", p.url().includes("/admin"));
  await p.getByText("Déconnexion").first().click();
  await p.waitForTimeout(1200);
  ok(S, "déconnexion", p.url().includes("/login"));
  await connecter("admin", { page: p });
  ok(S, "reconnexion dans le même onglet", p.url().includes("/admin"));
  ok(S, "aucune erreur JS ni 5xx", p.erreurs.length === 0, p.erreurs.join(" | "));
  await p.contexte.close();

  // Session expirée : des jetons invalides en mémoire n'empêchent pas une nouvelle connexion.
  const q = await page();
  await q.goto(BASE + "/login");
  await q.evaluate(() => localStorage.setItem("feba-auth", JSON.stringify({ state: { user: { role: "admin" }, accessToken: "a.b.c", refreshToken: "a.b.c" }, version: 0 })));
  await q.reload();
  await q.waitForTimeout(1500);
  if (!q.url().includes("/login")) await q.goto(BASE + "/login");
  await connecter("admin", { page: q });
  ok(S, "session expirée puis connexion", q.url().includes("/admin"), q.url());
  await q.contexte.close();
}
