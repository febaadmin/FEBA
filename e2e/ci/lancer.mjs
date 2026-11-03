// Lance les scénarios (tous, ou ceux nommés en argument) et sort en échec si un contrôle échoue.
import { fermer, lancer, ok, resultats } from "./outils.mjs";

const TOUS = ["connexion", "selecteur", "navigation", "formulaires", "messagerie", "donnees", "modules", "suivi", "examens", "flash"];
const choisis = process.argv.slice(2).length ? process.argv.slice(2) : TOUS;
await lancer();
for (const nom of choisis) {
  const debut = Date.now();
  try {
    const { default: scenario } = await import(`./scenarios/${nom}.mjs`);
    await scenario();
  } catch (e) {
    const ligne = (e.stack || "").split("\n").find((x) => x.includes("/scenarios/")) || "";
    ok(nom, "le scénario s'exécute jusqu'au bout", false, `${e.message.split("\n")[0]} ${ligne.trim()}`);
  }
  console.log(`-- ${nom} : ${Math.round((Date.now() - debut) / 1000)} s`);
}
await fermer();
const echecs = resultats.filter((r) => !r.vrai);
console.log(`\n${resultats.length} contrôles, ${echecs.length} échec(s)`);
for (const e of echecs) console.log(`  KO [${e.scenario}] ${e.nom} ${e.detail}`);
process.exit(echecs.length ? 1 : 0);
