// Sélecteur d'académie : fermeture fiable, menu au-dessus de la page, bascule persistée.
import { connecter, ok } from "../outils.mjs";

const S = "sélecteur";

/** Point de la page hors du menu et hors de tout élément actif (une ligne de tableau ouvrirait sa fiche). */
const pointNeutre = (p) => p.evaluate(() => {
  const u = document.querySelector("[role=listbox]")?.getBoundingClientRect();
  for (let y = innerHeight - 20; y > 80; y -= 15) {
    for (let x = 20; x < innerWidth - 20; x += 25) {
      if (u && x > u.left && x < u.right && y > u.top && y < u.bottom) continue;
      const e = document.elementFromPoint(x, y);
      if (e && e.closest("main") && !e.closest("a,button,input,select,textarea,label,tr,[role=button],[role=tab]")) return [x, y];
    }
  }
  return [5, innerHeight - 5];
});
export default async function () {
  for (const [nom, vp] of [["ordinateur", { width: 1366, height: 800 }], ["téléphone", { width: 390, height: 800 }]]) {
    const p = await connecter("superadmin", { contexte: { viewport: vp } });
    const bouton = p.locator("header [aria-haspopup=listbox]");
    const menu = p.locator("[role=listbox]");
    const ouvrir = async () => { await bouton.click(); await p.waitForTimeout(150); };
    await p.goto(p.url().split("/superadmin")[0] + "/superadmin/grades");
    await p.waitForTimeout(1500);
    await ouvrir();
    const dessus = await p.evaluate(() => {
      const u = document.querySelector("[role=listbox]"); const r = u.getBoundingClientRect(); const v = [];
      for (let y = r.top + 5; y < r.bottom; y += 20) for (let x = r.left + 5; x < r.right; x += 40) v.push(u.contains(document.elementFromPoint(x, y)));
      return v.every(Boolean);
    });
    ok(S, `${nom} : menu au-dessus de la page`, dessus);
    await p.mouse.click(...(await pointNeutre(p)));
    await p.waitForTimeout(200);
    ok(S, `${nom} : clic dans une zone vide`, (await menu.count()) === 0);
    await ouvrir();
    await p.keyboard.press("Escape");
    await p.waitForTimeout(200);
    ok(S, `${nom} : Échap`, (await menu.count()) === 0);
    await ouvrir();
    const cible = await p.evaluate(() => {
      const u = document.querySelector("[role=listbox]").getBoundingClientRect();
      // N'importe quel bouton visible de la page, hors du menu.
      const dedans = (r) => r.left < u.right && r.right > u.left && r.top < u.bottom && r.bottom > u.top;
      const b = [...document.querySelectorAll("main button")].map((x) => x.getBoundingClientRect())
        .find((r) => r.width > 0 && r.top >= 0 && r.bottom < innerHeight && !dedans(r));
      return b && { x: b.left + b.width / 2, y: b.top + b.height / 2 };
    });
    if (cible) { await p.mouse.click(cible.x, cible.y); await p.waitForTimeout(250); }
    ok(S, `${nom} : clic sur un autre bouton`, Boolean(cible) && (await menu.count()) === 0, cible ? "" : "aucun bouton visible");
    await p.keyboard.press("Escape");
    if (vp.width > 768) {
      await ouvrir();
      const avant = p.url();
      await p.locator("aside a").nth(2).click();
      await p.waitForTimeout(500);
      ok(S, `${nom} : navigation par le menu latéral`, (await menu.count()) === 0 && p.url() !== avant);
    }
    await ouvrir();
    const libelle = await bouton.innerText();
    await menu.locator("li[aria-selected=false] button").first().click();
    await p.waitForTimeout(2200);
    const apres = await bouton.innerText();
    ok(S, `${nom} : bascule d'académie appliquée, menu fermé`, libelle !== apres && (await menu.count()) === 0, `${libelle} -> ${apres}`);
    await p.reload();
    await p.waitForTimeout(1800);
    ok(S, `${nom} : académie conservée au rechargement`, (await bouton.innerText()) === apres);
    ok(S, `${nom} : aucune erreur`, p.erreurs.length === 0, p.erreurs.join(" | "));
    await p.contexte.close();
  }
  const a = await connecter("admin");
  ok(S, "administrateur : pas de sélecteur", (await a.locator("header [aria-haspopup=listbox]").count()) === 0);
  await a.contexte.close();
}
