// Audit responsive : chaque page de chaque profil, à plusieurs largeurs.
// Relève le défilement horizontal de la page (et les éléments qui débordent, hors
// conteneurs défilants prévus), les erreurs JavaScript / 5xx et les cibles tactiles
// trop petites sur téléphone. Usage : node audit_responsive.mjs [largeurs] > rapport.json
import { readFileSync } from "node:fs";
import { lancer, fermer, connecter, BASE } from "./outils.mjs";

const ROUTES = JSON.parse(readFileSync(new URL("./routes.json", import.meta.url)));
const TAILLES = { 320: 640, 360: 800, 390: 844, 430: 932, 768: 1024, 1024: 768, 1280: 800, 1440: 900, 1920: 1080, 2560: 1440 };
const largeurs = (process.argv[2] || "320,390,768,1024,1440").split(",").map(Number);
const profils = (process.argv[3] || "superadmin,admin,teacher,parent,student").split(",");

await lancer();
const constats = [];
for (const role of profils) {
  const p = await connecter(role);
  for (const w of largeurs) {
    await p.setViewportSize({ width: w, height: TAILLES[w] || 900 });
    for (const route of ROUTES[role]) {
      p.erreurs.length = 0;
      try {
        await p.goto(BASE + route, { waitUntil: "domcontentloaded" });
        await p.waitForTimeout(1100);
      } catch (e) { constats.push({ role, w, route, type: "chargement", detail: String(e).slice(0, 120) }); continue; }
      const r = await p.evaluate((largeur) => {
        const deborde = document.documentElement.scrollWidth - window.innerWidth;
        const fautifs = [];
        if (deborde > 1) {
          for (const el of document.querySelectorAll("body *")) {
            const b = el.getBoundingClientRect();
            if (b.width === 0 || b.right <= window.innerWidth + 1) continue;
            let parent = el.parentElement, cache = false;
            while (parent) {
              const st = getComputedStyle(parent);
              if (["auto", "scroll", "hidden", "clip"].includes(st.overflowX)) { cache = true; break; }
              parent = parent.parentElement;
            }
            if (cache) continue;
            fautifs.push(`${el.tagName.toLowerCase()}.${String(el.className).split(" ").slice(0, 4).join(".")} [${Math.round(b.right)}px] ${el.textContent.trim().slice(0, 40)}`);
            if (fautifs.length > 4) break;
          }
        }
        const petits = largeur < 768 ? [...document.querySelectorAll("main button, main a[href], main [role=button]")]
          .filter((el) => { const b = el.getBoundingClientRect(); return b.width > 0 && b.height > 0 && (b.height < 24 || b.width < 24); }).length : 0;
        return { deborde, fautifs, petits };
      }, w);
      if (r.deborde > 1) constats.push({ role, w, route, type: "debordement", px: r.deborde, fautifs: r.fautifs });
      if (r.petits > 6) constats.push({ role, w, route, type: "cibles_tactiles", nombre: r.petits });
      if (p.erreurs.length) constats.push({ role, w, route, type: "erreurs", detail: [...new Set(p.erreurs)].slice(0, 3) });
    }
  }
  await p.contexte.close();
}
await fermer();
console.log(JSON.stringify({ largeurs, profils, pages: profils.reduce((n, r) => n + ROUTES[r].length, 0), constats }, null, 1));
