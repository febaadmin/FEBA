// Toutes les pages des 5 profils, sur ordinateur et téléphone : erreurs JS, 5xx, débordement.
import { readFileSync } from "node:fs";
import { BASE, connecter, ok } from "../outils.mjs";

// Pages de chaque profil : routes.json, qui contient toutes les entrées des menus
// (contrôlé par frontend/src/layouts/menus.test.js : une entrée absente fait échouer le test).
const ROUTES = JSON.parse(readFileSync(new URL("../routes.json", import.meta.url)));
const S = "navigation";
export default async function () {
  for (const role of Object.keys(ROUTES)) {
    for (const vp of [{ width: 1366, height: 800 }, { width: 390, height: 800 }]) {
      const p = await connecter(role, { contexte: { viewport: vp } });
      const defauts = [];
      for (const route of ROUTES[role]) {
        p.erreurs.length = 0;
        await p.goto(BASE + route, { timeout: 30000 }).catch(() => {});
        await p.waitForTimeout(700);
        const deborde = await p.evaluate(() => document.documentElement.scrollWidth > innerWidth + 2);
        // Le défilement se fait dans <main> : si le DOCUMENT défile, toute l'application
        // remonte et laisse un espace blanc en bas (anomalie du tableau de bord, phase 6).
        const decale = await p.evaluate(() => document.scrollingElement.scrollHeight > innerHeight + 2);
        if (p.erreurs.length || (vp.width < 500 && deborde) || decale || p.url().includes("/login")) defauts.push(`${route} ${p.erreurs.join(",")} ${deborde ? "débordement" : ""} ${decale ? "document défilant" : ""} ${p.url().includes("/login") ? "déconnecté" : ""}`);
      }
      ok(S, `${role} ${vp.width} px : ${ROUTES[role].length} pages`, defauts.length === 0, defauts.slice(0, 5).join(" | "));
      await p.contexte.close();
    }
  }
}
