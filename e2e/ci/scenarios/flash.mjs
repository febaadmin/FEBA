// Aucun flash : l'opacité du voile du menu mobile ne retombe jamais en fin d'animation.
import { connecter, ok } from "../outils.mjs";

export default async function () {
  const p = await connecter("superadmin", { contexte: { viewport: { width: 640, height: 900 } } });
  await p.evaluate(() => {
    window.__s = [];
    const tic = () => {
      const voiles = [...document.querySelectorAll(".fixed.inset-0")].filter((e) => getComputedStyle(e).backgroundColor !== "rgba(0, 0, 0, 0)");
      window.__s.push(voiles.map((e) => +getComputedStyle(e).opacity)[0]);
      requestAnimationFrame(tic);
    };
    requestAnimationFrame(tic);
  });
  let chutes = 0;
  for (let i = 0; i < 5; i++) {
    await p.evaluate(() => { window.__s = []; });
    await p.locator("button:has(svg.lucide-menu)").first().click();
    await p.waitForTimeout(700);
    let max = 0;
    for (const v of await p.evaluate(() => window.__s)) {
      if (v === undefined || v === null) continue;
      if (max > 0.3 && v < max - 0.2) chutes += 1;
      max = Math.max(max, v);
    }
    await p.locator("aside a").nth(i + 1).click();
    await p.waitForTimeout(700);
  }
  ok("flash", "voile du menu : aucune chute d'opacité sur 5 ouvertures", chutes === 0, `chutes=${chutes}`);
  await p.contexte.close();
}
