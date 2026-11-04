// Cohérence du centre d'aide avec l'application : catégories, rôles, deux
// langues, liens vers des routes réelles, couverture de chaque écran du menu.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { ARTICLES, CATEGORIES, DEPANNAGE, FAQ, RACINES, ROLES } from "./articles";
import { TERMES } from "./glossaire";
import { articlesPour, categoriesPour, faqPour, glossairePour, lienPour, normaliser } from "./recherche";

const SRC = join(globalThis.process.cwd(), "src");
const routeur = readFileSync(join(SRC, "router/index.jsx"), "utf8");
const MENUS = { superadmin: "SuperAdminLayout", admin: "AdminLayout", teacher: "TeacherLayout", parent: "ParentLayout", student: "StudentLayout" };

/** Chemins déclarés sous la racine d'un rôle dans le routeur. */
function routesDu(role) {
  const debut = routeur.indexOf(`<Route path="${RACINES[role]}"`);
  const suite = routeur.slice(debut + 10);
  const fin = suite.search(/<Route path="\/[a-z]/);
  const bloc = suite.slice(0, fin === -1 ? undefined : fin);
  return new Set([...bloc.matchAll(/<Route path="([^"]+)"/g)].map((m) => m[1]));
}
/** Entrées de menu d'un rôle (chemin relatif à sa racine). */
function menuDu(role) {
  const src = readFileSync(join(SRC, `layouts/${MENUS[role]}.jsx`), "utf8");
  return [...src.matchAll(new RegExp(`to: "${RACINES[role]}/([^"]+)"`, "g"))].map((m) => m[1]);
}

const paire = (p) => Array.isArray(p) && p.length === 2 && p.every((x) => typeof x === "string" && x.trim().length > 0);

describe("contenu du centre d'aide", () => {
  it("identifiants uniques, catégories connues, rôles valides", () => {
    const ids = ARTICLES.map((a) => a.id);
    expect(new Set(ids).size).toBe(ids.length);
    const cats = new Set(CATEGORIES.map((c) => c.id));
    for (const a of ARTICLES) {
      expect(cats.has(a.categorie), a.id).toBe(true);
      expect(a.roles.length, a.id).toBeGreaterThan(0);
      for (const r of a.roles) expect(ROLES, a.id).toContain(r);
    }
  });

  it("chaque texte existe en français ET en anglais, sans copie de l'un dans l'autre", () => {
    for (const a of ARTICLES) {
      for (const champ of ["titre", "module", "objet", "resultat", "permissions"]) expect(paire(a[champ]), `${a.id}.${champ}`).toBe(true);
      expect(a.titre[0], a.id).not.toBe(a.titre[1]);
      expect(a.etapes.length, a.id).toBeGreaterThanOrEqual(2);
      for (const liste of [a.prerequis, a.etapes, a.champs]) for (const p of liste) expect(paire(p), a.id).toBe(true);
      for (const [pb, sol] of a.erreurs) expect(paire(pb) && paire(sol), a.id).toBe(true);
      expect(Array.isArray(a.consequences) && a.consequences.length === 0 || paire(a.consequences), a.id).toBe(true);
    }
    for (const x of [...FAQ, ...DEPANNAGE]) expect(paire(x.q) && paire(x.r)).toBe(true);
    for (const t of TERMES) {
      expect(paire(t.terme), t.id).toBe(true);
      for (const d of Object.values(t.definitions)) expect(d === null || paire(d), t.id).toBe(true);
    }
    for (const c of CATEGORIES) expect(paire(c.titre)).toBe(true);
  });

  it("les liens mènent à des routes réelles, seulement pour les rôles de l'article", () => {
    for (const a of ARTICLES) {
      for (const [role, chemin] of Object.entries({ ...a.liens })) {
        expect(a.roles, `${a.id} → ${role}`).toContain(role);
        expect(routesDu(role).has(chemin), `${a.id} : ${RACINES[role]}/${chemin}`).toBe(true);
      }
      for (const [role, chemins] of Object.entries(a.ecrans || {})) {
        expect(a.roles, `${a.id} → ${role}`).toContain(role);
        for (const c of chemins) expect(routesDu(role).has(c), `${a.id} : ${RACINES[role]}/${c}`).toBe(true);
      }
    }
  });

  it.each(ROLES)("%s : chaque écran du menu a son article d'aide", (role) => {
    const couverts = new Set(["aide"]);
    for (const a of ARTICLES.filter((x) => x.roles.includes(role))) {
      if (a.liens?.[role]) couverts.add(a.liens[role]);
      for (const c of a.ecrans?.[role] || []) couverts.add(c);
    }
    const manquants = menuDu(role).filter((c) => !couverts.has(c));
    expect(manquants).toEqual([]);
  });
});

describe("filtrage par profil", () => {
  it("un élève ne reçoit aucune procédure d'administration", () => {
    const ids = articlesPour("student").map((a) => a.id);
    expect(ids).toContain("passer-epreuve");
    for (const interdit of ["utilisateurs-creer", "reinitialiser-mdp", "bulletins-generer", "paiements", "incidents", "academies"]) {
      expect(ids).not.toContain(interdit);
    }
    expect(categoriesPour("student").map((c) => c.id)).not.toContain("administration");
  });
  it("un parent a son espace, sans la gestion", () => {
    const ids = articlesPour("parent").map((a) => a.id);
    expect(ids).toEqual(expect.arrayContaining(["famille-notes", "famille-paiements", "famille-vie", "messagerie"]));
    expect(ids).not.toContain("paiements");
  });
  it("un enseignant retrouve ses procédures pédagogiques, pas l'administration", () => {
    const ids = articlesPour("teacher").map((a) => a.id);
    expect(ids).toEqual(expect.arrayContaining(["notes-saisir", "notes-modifier", "epreuves", "absences", "devoirs", "suivi-eleve"]));
    expect(ids).not.toContain("utilisateurs-creer");
    expect(ids).not.toContain("bulletins-generer");
  });
  it("l'administration globale est réservée au super administrateur", () => {
    for (const id of ["academies", "incidents", "modules-pedagogiques", "administrateurs"]) {
      expect(articlesPour("superadmin").map((a) => a.id)).toContain(id);
      expect(articlesPour("admin").map((a) => a.id)).not.toContain(id);
    }
  });
  it("chaque profil a des questions fréquentes", () => {
    for (const r of ROLES) expect(faqPour(r).length).toBeGreaterThan(0);
  });
});

describe("recherche", () => {
  it("trouve sans tenir compte des accents ni de la casse", () => {
    expect(articlesPour("admin", { requete: "ELEVE" }).map((a) => a.id)).toContain("eleves");
    expect(normaliser("Élève")).toBe("eleve");
  });
  it("cherche dans la langue de l'interface", () => {
    expect(articlesPour("admin", { lang: "en", requete: "report card" }).map((a) => a.id)).toContain("bulletins-generer");
    expect(articlesPour("admin", { lang: "fr", requete: "bulletin" }).map((a) => a.id)).toContain("bulletins-generer");
  });
  it("exige tous les mots saisis", () => {
    const r = articlesPour("superadmin", { requete: "mot de passe superadmin" }).map((a) => a.id);
    expect(r).toContain("reinitialiser-mdp");
    expect(articlesPour("admin", { requete: "zzzz introuvable" })).toEqual([]);
  });
  it("filtre par catégorie", () => {
    const r = articlesPour("admin", { categorie: "finances" });
    expect(r.length).toBeGreaterThan(0);
    expect(r.every((a) => a.categorie === "finances")).toBe(true);
  });
  it("glossaire filtré par la recherche", () => {
    expect(glossairePour("admin", "fr", "coefficient").length).toBe(1);
  });
  it("lien construit sous la racine du rôle", () => {
    const a = ARTICLES.find((x) => x.id === "classes");
    expect(lienPour(a, "admin")).toBe("/admin/classes");
    expect(lienPour(a, "parent")).toBeNull();
  });
});
