// Examen de bout en bout : 9 types de questions, droits, rechargement, coupure, remise, correction, publication.
import { BASE, connecter, ok, unique } from "../outils.mjs";

const S = "examens";
export default async function () {
  const t = await connecter("teacher");
  const tag = "E" + unique();
  const heure = (h) => new Date(Date.now() + h * 3600e3 - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  const carte = (p) => p.locator("div.rounded-2xl").filter({ hasText: tag });
  await t.goto(BASE + "/teacher/evaluations/banque");
  await t.waitForTimeout(1800);
  const question = async (type, texte, remplir) => {
    await t.getByRole("button", { name: "Nouvelle question" }).first().click();
    await t.waitForTimeout(250);
    await t.locator("#q-type").selectOption(type);
    await t.locator("#q-enonce").fill(`${tag} ${texte}`);
    await remplir();
    await t.locator("form").getByRole("button", { name: "Enregistrer" }).click();
    await t.waitForTimeout(700);
  };
  const lignes = (x) => async () => t.locator("#q-lignes").fill(x);
  await question("qcm_unique", "unique", async () => { await t.getByLabel("Réponse 1", { exact: true }).fill("bon"); await t.getByLabel("Réponse 2", { exact: true }).fill("faux"); await t.getByLabel("Bonne réponse 1").check(); });
  await question("qcm_multiple", "multiple", async () => { await t.getByLabel("Réponse 1", { exact: true }).fill("m1"); await t.getByLabel("Réponse 2", { exact: true }).fill("m2"); await t.getByLabel("Réponse 3", { exact: true }).fill("mx"); await t.getByLabel("Bonne réponse 1").check(); await t.getByLabel("Bonne réponse 2").check(); });
  await question("vrai_faux", "vraifaux", async () => {});
  await question("ouverte", "ouverte", async () => {});
  await question("courte", "courte", lignes("Paris"));
  await question("numerique", "numero", async () => { await t.locator("#q-val").fill("3"); });
  await question("trous", "trous", lignes("chat"));
  await question("association", "assoc", lignes("A = 1\nB = 2"));
  await question("classement", "classe", lignes("un\ndeux"));

  await t.goto(BASE + "/teacher/evaluations");
  await t.waitForTimeout(1500);
  await t.getByRole("button", { name: "Nouvelle épreuve" }).first().click();
  await t.getByLabel("Titre *").fill(tag);
  await t.getByLabel("Matière *").selectOption({ index: 1 });
  await t.getByLabel("Classe *").selectOption({ label: "CE1-A" });
  await t.getByLabel("Ouverture *").fill(heure(24));
  await t.getByLabel("Fermeture *").fill(heure(48));
  await t.getByLabel("Consignes").fill("Lisez bien.");
  await t.getByLabel("Montrer le corrigé avec les résultats").check();
  await t.locator("form").getByRole("button", { name: "Créer" }).click();
  await t.waitForTimeout(2000);
  const url = t.url();
  const id = url.split("/").pop();
  const ajouter = t.locator("li").filter({ hasText: tag }).getByRole("button", { name: "Ajouter", exact: true });
  for (let c = await ajouter.count(); c > 0; c--) { await ajouter.first().click(); await t.waitForTimeout(450); }
  await t.getByRole("button", { name: "Publier l'épreuve" }).click();
  await t.waitForTimeout(900);
  ok(S, "épreuve créée avec 9 types et publiée", (await t.getByText(/Questions \(9\)/).count()) === 1);

  const s = await connecter("student");
  await s.goto(BASE + "/student/evaluations");
  await s.waitForTimeout(2500);
  ok(S, "élève : visible avec sa date d'ouverture, sans bouton", (await carte(s).innerText()).includes("S'ouvre le") && (await carte(s).getByRole("link", { name: "Commencer" }).count()) === 0);
  const h = await connecter("studentAutre");
  await h.goto(BASE + "/student/evaluations");
  await h.waitForTimeout(1800);
  ok(S, "élève d'une autre classe : invisible", (await h.getByText(tag).count()) === 0);
  await h.goto(BASE + `/student/evaluations/${id}/passer`);
  await h.waitForTimeout(1500);
  ok(S, "élève d'une autre classe : adresse directe refusée", (await h.locator("body").innerText()).includes("n'est pas disponible"));
  await h.contexte.close();

  await t.getByRole("button", { name: "Ouvrir maintenant" }).click();
  await t.waitForTimeout(900);
  await s.goto(BASE + "/student/evaluations");
  await s.waitForTimeout(2000);
  await carte(s).getByRole("link", { name: "Commencer" }).click();
  await s.waitForTimeout(1200);
  ok(S, "consignes avant le chronomètre", (await s.getByText("Lisez bien.").count()) === 1 && (await s.getByRole("timer").count()) === 0);
  await s.getByRole("button", { name: "Commencer l'épreuve" }).click();
  await s.waitForTimeout(1600);
  const repondre = async (q) => {
    if (q.includes("unique")) await s.getByLabel("bon", { exact: true }).check();
    else if (q.includes("multiple")) { await s.getByLabel("m1").check(); await s.getByLabel("m2").check(); }
    else if (q.includes("vraifaux")) await s.getByLabel("Vrai", { exact: true }).check();
    else if (q.includes("ouverte")) await s.getByLabel("Votre réponse").fill("Rédaction");
    else if (q.includes("courte")) await s.getByLabel("Votre réponse").fill("paris");
    else if (q.includes("numero")) await s.getByLabel("Votre réponse").fill("3");
    else if (q.includes("trous")) await s.getByLabel("Trou 1").fill("chat");
    else if (q.includes("assoc")) { await s.getByLabel("A", { exact: true }).selectOption({ label: "1" }); await s.getByLabel("B", { exact: true }).selectOption({ label: "2" }); }
    else if (q.includes("classe")) {
      const premier = await s.locator("ol li").first().innerText();
      await s.getByRole("button", { name: "Descendre" }).first().click();
      if (premier.includes("un")) { await s.waitForTimeout(100); await s.getByRole("button", { name: "Monter" }).nth(1).click(); }
    }
    await s.waitForTimeout(1000);
  };
  for (let i = 0; i < 9; i++) {
    await repondre(await s.locator("p.text-base").textContent());
    if (i === 3) {
      await s.reload();
      await s.waitForTimeout(2300);
      ok(S, "rechargement : réponses et chronomètre conservés", (await s.getByText("4 réponse(s) sur 9").count()) === 1);
      for (let k = 0; k < 4; k++) { await s.getByRole("button", { name: "Suivante" }).click(); await s.waitForTimeout(220); }
      continue;
    }
    if (i === 5) { await s.contexte.setOffline(true); await s.waitForTimeout(300); await s.contexte.setOffline(false); await s.evaluate(() => window.dispatchEvent(new Event("online"))); await s.waitForTimeout(800); }
    if (i < 8) { await s.getByRole("button", { name: "Suivante" }).click(); await s.waitForTimeout(250); }
  }
  ok(S, "coupure réseau : 9 réponses sur 9", (await s.getByText("9 réponse(s) sur 9").count()) === 1);
  await s.getByRole("button", { name: "Remettre ma copie" }).click();
  await s.waitForTimeout(400);
  await s.locator("[class*=fixed]").getByRole("button", { name: "Remettre ma copie" }).last().dblclick();
  await s.waitForTimeout(1800);
  ok(S, "remise unique malgré le double clic, reçu affiché", (await s.getByText("Reçu de remise").count()) === 1);
  await s.goto(BASE + `/student/evaluations/${id}/passer`);
  await s.waitForTimeout(1500);
  ok(S, "nouvelle tentative refusée", (await s.locator("body").innerText()).includes("attente de correction"));

  await t.goto(url);
  await t.waitForTimeout(2000);
  await t.locator('a[href*="/copies/"]').first().click();
  await t.waitForTimeout(1800);
  const brut = (await t.locator("body").innerText()).match(/Résultat brut\s+([\d.]+)/)?.[1];
  ok(S, "correction automatique : 8 points sur 9", Number(brut) === 8, brut);
  const manuelle = t.locator("div.border").filter({ hasText: "Correction manuelle" }).first();
  await manuelle.getByRole("spinbutton").fill("1");
  await manuelle.getByRole("button", { name: "Enregistrer" }).click();
  await t.waitForTimeout(900);
  await t.getByRole("button", { name: "Valider la copie" }).click();
  await t.waitForTimeout(900);
  await t.goto(url);
  await t.waitForTimeout(1800);
  await t.getByRole("button", { name: "Publier les résultats" }).click();
  await t.waitForTimeout(350);
  await t.locator("[class*=fixed]").getByRole("button", { name: "Publier les résultats" }).last().click();
  await t.waitForTimeout(900);
  // Le corrigé n'est montré qu'une fois l'épreuve close.
  await t.getByRole("button", { name: "Clore l'épreuve" }).click();
  await t.waitForTimeout(350);
  await t.locator("[class*=fixed]").getByRole("button", { name: "Clore l'épreuve" }).last().click();
  await t.waitForTimeout(900);
  await s.goto(BASE + "/student/evaluations");
  await s.waitForTimeout(2000);
  await carte(s).getByRole("link", { name: "Consulter le résultat" }).click();
  await s.waitForTimeout(1800);
  const resultat = await s.locator("body").innerText();
  ok(S, "élève : 20 / 20 et corrigé", resultat.includes("20 / 20") && resultat.includes("Bonne réponse"), (await s.locator("main").innerText()).replace(/\n/g, " | ").slice(0, 280));
  const pa = await connecter("parent");
  await pa.goto(BASE + "/parent/evaluations");
  await pa.waitForTimeout(1800);
  ok(S, "parent de l'élève : résultat visible", (await pa.getByText(tag).count()) === 1);
  const pb = await connecter("parentAutre");
  await pb.goto(BASE + "/parent/evaluations");
  await pb.waitForTimeout(1800);
  ok(S, "autre parent : invisible", (await pb.getByText(tag).count()) === 0);
  ok(S, "aucune erreur", t.erreurs.length + s.erreurs.length === 0, [...t.erreurs, ...s.erreurs].join(" | "));
  for (const x of [t, s, pa, pb]) await x.contexte.close();
}
