// Messagerie et notification : enseignant -> parent -> réponse.
import { BASE, connecter, ok, unique } from "../outils.mjs";

const S = "messagerie";
export default async function () {
  const u = unique();
  const t = await connecter("teacher");
  await t.goto(BASE + "/teacher/messages");
  await t.waitForTimeout(1400);
  await t.locator("main .btn-primary", { hasText: "Nouveau message" }).click();
  const d = t.locator("[role=dialog]");
  await d.getByRole("button", { name: /Rechercher/ }).first().click();
  const recherche = t.locator('input[placeholder="Rechercher..."]').last();
  await recherche.fill("David");
  await t.waitForTimeout(300);
  await recherche.locator("xpath=ancestor::div[3]").locator(".overflow-y-auto button").first().click();
  await d.locator("input:not([type=file])").last().fill("Sujet" + u);
  await d.locator("textarea").first().fill("Corps" + u);
  await d.locator("button[type=submit]").click();
  await t.waitForTimeout(1500);
  ok(S, "message envoyé", (await d.count()) === 0);

  const p = await connecter("parent");
  await p.goto(BASE + "/parent/messages");
  await p.waitForTimeout(1800);
  const page = await p.locator("main").innerText();
  ok(S, "message reçu et signalé non lu", page.includes("Sujet" + u) && /non lu/i.test(page));
  await p.getByText("Sujet" + u).first().click();
  await p.waitForTimeout(1200);
  ok(S, "contenu lisible", (await p.locator("main").innerText()).includes("Corps" + u));
  await p.locator("main textarea").last().fill("Reponse" + u);
  await p.getByRole("button", { name: "Envoyer" }).first().click();
  await p.waitForTimeout(1500);
  await t.goto(BASE + "/teacher/messages");
  await t.waitForTimeout(1600);
  await t.getByText("Sujet" + u).first().click();
  await t.waitForTimeout(1200);
  ok(S, "réponse reçue par l'enseignant", (await t.locator("main").innerText()).includes("Reponse" + u));
  ok(S, "aucune erreur", t.erreurs.length + p.erreurs.length === 0, [...t.erreurs, ...p.erreurs].join(" | "));
  await t.contexte.close();
  await p.contexte.close();
}
