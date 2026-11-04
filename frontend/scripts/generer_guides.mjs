// Génère les guides utilisateur FR et EN à partir du centre d'aide de l'application
// (frontend/src/aide/articles.js), pour que guide et application ne divergent jamais.
//   node frontend/scripts/generer_guides.mjs <dossier de sortie>
import { writeFileSync } from "node:fs";
import { join } from "node:path";
import { ARTICLES, CATEGORIES, DEPANNAGE, FAQ, GLOSSAIRE, LIBELLES_ROLES, RACINES } from "../src/aide/articles.js";

const sortie = process.argv[2] || ".";
const T = {
  fr: { titre: "Guide utilisateur FEBA", intro: "Ce guide reprend le centre d'aide intégré à FEBA (menu « Aide »), généré depuis la même source.", sommaire: "Sommaire",
    objet: "À quoi ça sert", qui: "Qui peut l'utiliser", prerequis: "Prérequis", ou: "Où la trouver", etapes: "Étapes", champs: "Champs importants",
    resultat: "Résultat attendu", erreurs: "Erreurs fréquentes", consequences: "Effets sur les autres modules", permissions: "Permissions",
    faq: "Questions fréquentes", depannage: "Dépannage", glossaire: "Glossaire", menu: "Menu", module: "module optionnel de l'académie" },
  en: { titre: "FEBA user guide", intro: "This guide mirrors the help centre built into FEBA (\"Help\" menu), generated from the same source.", sommaire: "Contents",
    objet: "What it is for", qui: "Who can use it", prerequis: "Prerequisites", ou: "Where to find it", etapes: "Steps", champs: "Important fields",
    resultat: "Expected result", erreurs: "Common errors", consequences: "Effects on other modules", permissions: "Permissions",
    faq: "Frequently asked questions", depannage: "Troubleshooting", glossaire: "Glossary", menu: "Menu", module: "optional academy module" },
};

function guide(lang) {
  const i = lang === "fr" ? 0 : 1;
  const L = (p) => (Array.isArray(p) ? p[i] : p || "");
  const t = T[lang];
  const l = [`# ${t.titre}`, "", t.intro, "", `## ${t.sommaire}`, ""];
  for (const c of CATEGORIES) {
    const as = ARTICLES.filter((a) => a.categorie === c.id);
    if (!as.length) continue;
    l.push(`- **${L(c.titre)}**`);
    for (const a of as) l.push(`  - [${L(a.titre)}](#${a.id})`);
  }
  for (const c of CATEGORIES) {
    const as = ARTICLES.filter((a) => a.categorie === c.id);
    if (!as.length) continue;
    l.push("", `## ${L(c.titre)}`);
    for (const a of as) {
      l.push("", `<a id="${a.id}"></a>`, `### ${L(a.titre)}`, "");
      l.push(`**${t.objet}.** ${L(a.objet)}`, "");
      l.push(`**${t.qui}.** ${a.roles.map((r) => L(LIBELLES_ROLES[r])).join(", ")}`, "");
      if (a.prerequis.length) l.push(`**${t.prerequis}.**`, "", ...a.prerequis.map((p) => `- ${L(p)}`), "");
      const ou = Object.entries(a.liens || {}).map(([r, c2]) => `\`${RACINES[r]}/${c2}\``).join(", ");
      l.push(`**${t.ou}.** ${t.menu} « ${L(a.module)} »${a.feature ? ` (${t.module})` : ""}${ou ? ` : ${ou}` : ""}`, "");
      l.push(`**${t.etapes}.**`, "", ...a.etapes.map((e, n) => `${n + 1}. ${L(e)}`), "");
      if (a.champs.length) l.push(`**${t.champs}.**`, "", ...a.champs.map((c2) => `- ${L(c2)}`), "");
      l.push(`**${t.resultat}.** ${L(a.resultat)}`, "");
      if (a.erreurs.length) l.push(`**${t.erreurs}.**`, "", ...a.erreurs.map(([pb, sol]) => `- *${L(pb)}* : ${L(sol)}`), "");
      if (L(a.consequences)) l.push(`**${t.consequences}.** ${L(a.consequences)}`, "");
      l.push(`**${t.permissions}.** ${L(a.permissions)}`);
    }
  }
  l.push("", `## ${t.faq}`, "", ...FAQ.flatMap((x) => [`**${L(x.q)}**`, "", L(x.r), ""]));
  l.push(`## ${t.depannage}`, "", ...DEPANNAGE.flatMap((x) => [`**${L(x.q)}**`, "", L(x.r), ""]));
  l.push(`## ${t.glossaire}`, "", ...GLOSSAIRE.map(([m, d]) => `- **${L(m)}** : ${L(d)}`), "");
  return l.join("\n");
}

writeFileSync(join(sortie, "GUIDE_UTILISATEUR_FEBA_FR.md"), guide("fr"));
writeFileSync(join(sortie, "FEBA_USER_GUIDE_EN.md"), guide("en"));
console.log(`${ARTICLES.length} articles → GUIDE_UTILISATEUR_FEBA_FR.md, FEBA_USER_GUIDE_EN.md`);
