// Aperçu PDF du bulletin sous la CSP de production (appliquée par outils.mjs) : il doit
// réellement s'afficher (pages dessinées), sans cadre bloqué ni violation de CSP.
import { BASE, api, connecter, jeton, ok } from "../outils.mjs";

const S = "apercu_pdf";

export default async function () {
  // Super administrateur en « Toutes les Académies » : message explicite, aucun aperçu ambigu.
  const js = await jeton("superadmin");
  await api("POST", "/auth/entity-context/switch/", js, { entity_id: null });
  const t = await connecter("superadmin");
  await t.goto(BASE + "/superadmin/bulletins");
  await t.waitForTimeout(2500);
  if (await t.locator('button[title="Aperçu du bulletin"]').count()) {
    await t.locator('button[title="Aperçu du bulletin"]').first().click();
    await t.waitForTimeout(800);
    ok(S, "superadmin « Toutes les Académies » : demande de choisir une académie",
      (await t.getByTestId("bulletin-preview-dialog").innerText()).includes("Sélectionnez d'abord une académie"));
  }
  await t.contexte.close();
  const entites = (await api("GET", "/auth/entity-context/", js)).donnees.entities;
  await api("POST", "/auth/entity-context/switch/", js, { entity_id: (entites.find((e) => e.currency === "XOF") || entites[0]).id });

  for (const role of ["admin", "superadmin"]) {
    const p = await connecter(role);
    await p.goto(BASE + `${p.racine}/bulletins`);
    await p.waitForTimeout(2500);
    const boutons = p.locator('button[title="Aperçu du bulletin"]');
    ok(S, `${role} : au moins un bulletin à prévisualiser`, await boutons.count() > 0);
    if (!(await boutons.count())) { await p.contexte.close(); continue; }
    await boutons.first().click();
    const apercu = p.getByTestId("preview-frame");
    const dialogue = p.getByTestId("bulletin-preview-dialog");
    // Premier rendu : génération du PDF côté serveur (LibreOffice), parfois lente sous charge.
    for (let i = 0; i < 120 && !(await apercu.count()) && !(await dialogue.locator("[role=alert]").count()); i++) await p.waitForTimeout(500);
    if (!(await apercu.count())) {
      ok(S, `${role} : aperçu affiché`, false, (await dialogue.locator("[role=alert]").allInnerTexts()).join(" ") || "aucun aperçu après 60 s");
      await p.contexte.close();
      continue;
    }
    for (let i = 0; i < 60 && (await apercu.getAttribute("data-etat")) === "chargement"; i++) await p.waitForTimeout(500);
    const etat = await apercu.getAttribute("data-etat");
    const pages = Number(await apercu.getAttribute("data-pages"));
    ok(S, `${role} : aperçu affiché (pages dessinées)`, etat === "pret" && pages > 0 && await apercu.locator("canvas").count() === pages, `${etat} ${pages}`);
    const encre = await apercu.locator("canvas").first().evaluate((c) => {
      const d = c.getContext("2d").getImageData(0, 0, c.width, c.height).data;
      let fonce = 0;
      for (let i = 0; i < d.length; i += 4 * 97) if (d[i] < 128 && d[i + 3] > 0) fonce++;
      return fonce;
    }).catch(() => 0);
    ok(S, `${role} : la page contient du texte (pas une zone vide)`, encre > 20, encre);
    ok(S, `${role} : aucun cadre (iframe) dans l'aperçu`, await p.locator("[data-testid=bulletin-preview-dialog] iframe").count() === 0);
    // Actualisation après modification du commentaire.
    const zone = p.locator("[data-testid=bulletin-preview-dialog] textarea");
    if (await zone.count()) {
      await zone.fill(`Aperçu E2E ${Date.now() % 1000}`);
      await p.getByRole("button", { name: "Actualiser l'aperçu" }).click();
      await p.waitForTimeout(800);
      for (let i = 0; i < 60 && (await apercu.getAttribute("data-etat")) !== "pret"; i++) await p.waitForTimeout(500);
      ok(S, `${role} : aperçu actualisé après changement du commentaire`, (await apercu.getAttribute("data-etat")) === "pret");
    }
    const lien = p.getByTestId("official-pdf-link");
    if (await lien.count()) {
      const href = await lien.getAttribute("href");
      const r = await p.request.get(new URL(href, BASE).href);
      ok(S, `${role} : « Ouvrir le PDF officiel » sert bien le PDF`, r.status() === 200 && (r.headers()["content-type"] || "").includes("pdf"), `${r.status()} ${href}`);
    }
    ok(S, `${role} : aucune violation de CSP ni erreur JS ou 5xx`, p.erreurs.length === 0, p.erreurs.join(" | "));
    await p.contexte.close();
  }
  await api("POST", "/auth/entity-context/switch/", js, { entity_id: null });
}
