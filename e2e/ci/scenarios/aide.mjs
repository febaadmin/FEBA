// Centre d'aide : visible pour les 5 profils, filtré par profil, recherche,
// catégories, français et anglais, liens vers les modules, téléphone.
import { BASE, connecter, ok } from "../outils.mjs";

const S = "aide";
const ATTENDUS = {
  superadmin: { present: "reinitialiser-mdp", absent: null, aussi: ["famille-paiements", "passer-epreuve"] },
  admin: { present: "bulletins-generer", absent: "academies" },
  teacher: { present: "notes-saisir", absent: "utilisateurs-creer" },
  parent: { present: "famille-paiements", absent: "paiements" },
  student: { present: "passer-epreuve", absent: "bulletins-generer" },
};

export default async function () {
  for (const [role, { present, absent, aussi = [] }] of Object.entries(ATTENDUS)) {
    const p = await connecter(role);
    // L'entrée « Aide » existe dans le menu, quel que soit le module activé.
    const menu = p.locator(`a[href="${p.racine}/aide"]`).first();
    ok(S, `${role} : entrée Aide dans le menu`, await menu.count() === 1);
    await p.goto(BASE + p.racine + "/aide");
    await p.waitForTimeout(800);
    const ids = await p.locator("[data-testid=aide-article]").evaluateAll((l) => l.map((e) => e.dataset.article));
    ok(S, `${role} : articles du profil`, ids.includes(present) && (!absent || !ids.includes(absent)) && aussi.every((i) => ids.includes(i)), `${ids.length} articles`);
    ok(S, `${role} : FAQ et glossaire`, await p.getByTestId("aide-faq").count() === 1 && await p.getByTestId("aide-glossaire").count() === 1);
    // Glossaire personnalisé : « Académie » est une notion d'administration.
    const termes = await p.locator("[data-testid=aide-glossaire] dt").allInnerTexts();
    const admin = ["superadmin", "admin"].includes(role);
    ok(S, `${role} : glossaire adapté au profil`, termes.includes("Académie") === admin && termes.length > 5, termes.join(", ").slice(0, 200));

    // Ouvrir un article et suivre son lien vers le module.
    const article = p.locator(`[data-article="${present}"]`);
    await article.locator("button[aria-expanded]").click();
    const deplie = await article.locator("button[aria-expanded=true]").count() === 1;
    const etapes = await article.locator("ol li").count();
    ok(S, `${role} : article déplié avec ses étapes`, deplie && etapes >= 2, `étapes=${etapes}`);
    const lien = article.getByTestId("aide-lien");
    if (await lien.count()) {
      const cible = await lien.getAttribute("href");
      await lien.click();
      await p.waitForTimeout(900);
      ok(S, `${role} : le lien ouvre le module`, new URL(p.url()).pathname === cible && p.erreurs.length === 0, `${p.url()} ${p.erreurs}`);
      await p.goBack();
      await p.waitForTimeout(600);
    }
    ok(S, `${role} : aucune erreur JS ni 5xx`, p.erreurs.length === 0, p.erreurs.join(" | "));
    await p.contexte.close();
  }

  // Recherche, catégories et anglais (administrateur).
  const p = await connecter("admin");
  await p.goto(BASE + "/admin/aide");
  await p.waitForTimeout(700);
  await p.getByTestId("aide-recherche").fill("bulletin");
  await p.waitForTimeout(300);
  let ids = await p.locator("[data-testid=aide-article]").evaluateAll((l) => l.map((e) => e.dataset.article));
  ok(S, "recherche « bulletin »", ids.includes("bulletins-generer") && !ids.includes("absences"), ids.join(","));
  // Recherche classée : « message » ne doit plus remonter tout article qui contient le mot.
  await p.getByTestId("aide-recherche").fill("message");
  await p.waitForTimeout(300);
  ids = await p.locator("[data-testid=aide-article]").evaluateAll((l) => l.map((e) => e.dataset.article));
  ok(S, "recherche « message » : messagerie en tête, peu de résultats", ids[0] === "messagerie" && ids.length <= 3, ids.join(","));
  ok(S, "terme surligné dans le titre", await p.locator('[data-article="messagerie"] mark').count() > 0);
  await p.getByTestId("aide-recherche").fill("bulettin");
  await p.waitForTimeout(300);
  ids = await p.locator("[data-testid=aide-article]").evaluateAll((l) => l.map((e) => e.dataset.article));
  ok(S, "faute de frappe « bulettin » corrigée", ids[0] === "bulletins-generer", ids.join(","));
  await p.getByTestId("aide-recherche").fill("bultinzz");
  await p.waitForTimeout(300);
  ok(S, "aucun résultat : message et suggestions", await p.getByTestId("aide-aucun").count() === 1);
  await p.getByTestId("aide-recherche").fill("eleve");
  await p.waitForTimeout(300);
  ids = await p.locator("[data-testid=aide-article]").evaluateAll((l) => l.map((e) => e.dataset.article));
  ok(S, "recherche sans accent", ids.includes("eleves"));
  await p.getByTestId("aide-recherche").fill("");
  await p.locator('[data-testid=aide-categorie][data-categorie="finances"]').click();
  await p.waitForTimeout(300);
  ids = await p.locator("[data-testid=aide-article]").evaluateAll((l) => l.map((e) => e.dataset.article));
  ok(S, "catégorie Paiements", ids.length > 0 && ids.every((i) => ["paiements", "tarifs", "situation-financiere", "graphique-paiements", "transactions-carte", "relances"].includes(i)), ids.join(","));
  ok(S, "catégorie dans l'adresse", new URL(p.url()).searchParams.get("categorie") === "finances");
  await p.getByRole("button", { name: "English", exact: true }).first().click();
  await p.waitForTimeout(500);
  const titre = await p.locator("h1").first().innerText();
  const texte = await p.locator("main").innerText();
  ok(S, "anglais : titres traduits", titre.trim() === "Help" && /Payments/.test(texte) && !/Comment enregistrer un paiement/.test(texte), titre);
  await p.getByTestId("aide-recherche").fill("receipt");
  await p.waitForTimeout(300);
  ids = await p.locator("[data-testid=aide-article]").evaluateAll((l) => l.map((e) => e.dataset.article));
  ok(S, "anglais : recherche « receipt »", ids.includes("paiements"), ids.join(","));
  await p.getByRole("button", { name: "Français", exact: true }).first().click();
  await p.waitForTimeout(500);
  await p.contexte.close();

  // Lien direct vers un article et téléphone.
  const m = await connecter("teacher", { contexte: { viewport: { width: 390, height: 800 } } });
  await m.goto(BASE + "/teacher/aide?article=notes-modifier");
  await m.waitForTimeout(800);
  const ouvert = await m.locator('[data-article="notes-modifier"] button[aria-expanded=true]').count() === 1;
  const deborde = await m.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  const visible = await m.evaluate(() => { const r = document.getElementById("article-notes-modifier").getBoundingClientRect(); return r.top >= 0 && r.top < window.innerHeight; });
  ok(S, "téléphone : l'article demandé est amené à l'écran", visible);
  ok(S, "téléphone : article ouvert par lien direct, sans débordement", ouvert && !deborde, `ouvert=${ouvert} deborde=${deborde}`);
  await m.contexte.close();
}
