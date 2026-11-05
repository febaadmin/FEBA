// Formulaires : champ obligatoire, double envoi sous latence, création persistée, tableau (recherche, tri, pagination).
import { BASE, choisir, connecter, latence, messages, ok, unique } from "../outils.mjs";

const S = "formulaires";
export default async function () {
  const u = unique();
  const p = await connecter("admin");
  await p.goto(BASE + "/admin/classes");
  await p.waitForTimeout(1500);
  await p.locator("main .btn-primary", { hasText: "Nouvelle classe" }).click();
  const d = p.locator("[role=dialog]");
  await d.locator("input").first().fill("Vide" + u);
  const t = await messages(p, () => d.locator("button[type=submit]").click());
  ok(S, "champ obligatoire vide : message, pas d'envoi", t.some((x) => /obligatoires/i.test(x)) && (await d.count()) === 1, JSON.stringify(t));
  await p.keyboard.press("Escape");
  await p.contexte.close();

  // Double clic avec 500 ms de latence sur les écritures : une seule requête.
  const q = await connecter("admin");
  await latence(q, 500, (r) => r.method() !== "GET");
  const envois = {};
  q.on("request", (r) => { if (r.method() === "POST" && r.url().includes("/api/")) { const k = r.url().split("/api")[1]; envois[k] = (envois[k] || 0) + 1; } });
  const remplir = async (zone) => {
    for (const f of await zone.locator("input[type=number]").all()) if (!(await f.inputValue())) await f.fill("1000");
    for (const f of await zone.locator("input[type=date]").all()) if (!(await f.inputValue())) await f.fill("2026-11-02");
    for (const s of await zone.locator("select").all()) {
      if (await s.inputValue()) continue;
      const o = await s.locator("option").evaluateAll((a) => a.map((x) => x.value).filter(Boolean));
      if (o.length) { await s.selectOption(o[0]); await q.waitForTimeout(200); }
    }
  };
  const cas = [
    ["/admin/payments", "Nouveau paiement", "/payments/", async (z) => { await choisir(q, z, /Rechercher un élève/); await remplir(z); }],
    ["/admin/classes", "Nouvelle classe", "/classes/", async (z) => { await z.locator("input").first().fill("Classe" + u); await choisir(q, z, /Rechercher un niveau/); }],
    ["/admin/announcements", "Nouvelle annonce", "/announcements/", async (z) => { await z.locator("input").first().fill("Annonce" + u); await z.locator("textarea").first().fill("Contenu"); }],
  ];
  for (const [route, bouton, chemin, remplit] of cas) {
    for (const k of Object.keys(envois)) delete envois[k];
    await q.goto(BASE + route);
    await q.waitForTimeout(1500);
    await q.locator("main .btn-primary", { hasText: bouton }).first().click();
    const z = q.locator("[role=dialog]");
    await remplit(z);
    await z.locator("button[type=submit]").dblclick();
    await q.waitForTimeout(1800);
    ok(S, `double clic ${route} : une seule requête`, envois[chemin] === 1, JSON.stringify(envois));
  }
  await q.goto(BASE + "/admin/classes");
  await q.waitForTimeout(1500);
  // Recherche comme un utilisateur : la liste est paginée et la base de test s'enrichit à chaque passage.
  const recherche = q.locator('main input[placeholder^="Rechercher"]').first();
  if (await recherche.count()) { await recherche.fill("Classe" + u); await q.waitForTimeout(600); }
  ok(S, "classe créée visible après rechargement", (await q.getByText("Classe" + u).count()) > 0);
  ok(S, "aucune erreur", q.erreurs.length === 0, q.erreurs.join(" | "));
  await q.contexte.close();

  // Recherche, tri, pagination sur la liste des élèves.
  const e = await connecter("admin");
  await e.goto(BASE + "/admin/students");
  await e.waitForTimeout(1800);
  const lignes = () => e.locator("tbody tr").count();
  const n0 = await lignes();
  await e.locator('main input[placeholder^="Rechercher"]').first().fill("Estelle");
  await e.waitForTimeout(300);
  const n1 = await lignes();
  ok(S, "recherche", n1 > 0 && n1 < n0, `${n0} -> ${n1}`);
  await e.locator('main input[placeholder^="Rechercher"]').first().fill("");
  const entete = e.getByRole("columnheader", { name: /Nom complet/ });
  await entete.click();
  const a = await e.locator("tbody tr").first().innerText();
  await entete.press("Enter");
  await e.waitForTimeout(200);
  ok(S, "tri, y compris au clavier", a !== (await e.locator("tbody tr").first().innerText()));
  const suivante = e.getByRole("button", { name: "Page suivante" });
  if (await suivante.count()) {
    const avant = await e.locator("tbody tr").first().innerText();
    await suivante.click();
    await e.waitForTimeout(200);
    ok(S, "pagination", avant !== (await e.locator("tbody tr").first().innerText()));
  }
  await e.contexte.close();
}
