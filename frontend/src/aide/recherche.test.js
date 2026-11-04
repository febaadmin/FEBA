// Non-régression du moteur de recherche et de la visibilité de l'aide.
// Une modification des articles ou du moteur qui dégrade un de ces résultats fait échouer la CI.
import { describe, expect, it } from "vitest";
import { ARTICLES, ROLES } from "./articles";
import { analyser, articlesPour, categoriesPour, distance, faqPour, glossairePour, peutVoir, racine, suggestions } from "./recherche";

const ids = (role, requete, lang = "fr", extra = {}) => articlesPour(role, { lang, requete, ...extra }).map((a) => a.id);

describe("visibilité par profil", () => {
  it("le super administrateur voit toute la documentation, quelle que soit l'académie", () => {
    expect(articlesPour("superadmin", { moduleActif: () => false }).length).toBe(ARTICLES.length);
    for (const id of ["famille-paiements", "passer-epreuve", "famille-suivi", "academies", "incidents"]) {
      expect(ids("superadmin", "")).toContain(id);
    }
  });
  it("les autres profils ne voient que leurs articles", () => {
    for (const role of ROLES.filter((r) => r !== "superadmin")) {
      for (const a of articlesPour(role)) expect(a.roles).toContain(role);
    }
  });
  it("un module désactivé masque ses articles pour un administrateur, pas pour le super administrateur", () => {
    const sansSuivi = (a) => a.feature !== "suivi_pedagogique";
    expect(ids("admin", "", "fr", { moduleActif: sansSuivi })).not.toContain("referentiels");
    expect(ids("admin", "", "fr", { moduleActif: () => true })).toContain("referentiels");
    expect(ids("superadmin", "", "fr", { moduleActif: sansSuivi })).toContain("referentiels");
    expect(peutVoir(ARTICLES.find((a) => a.id === "absences"), "teacher", () => false)).toBe(true); // sans module optionnel
  });
  it("les catégories suivent la visibilité", () => {
    expect(categoriesPour("student").map((c) => c.id)).not.toContain("administration");
    expect(categoriesPour("superadmin").map((c) => c.id)).toContain("famille");
  });
});

describe("pertinence : le bon article en tête, sans articles hors sujet", () => {
  const CAS = [
    // [profil, requête, langue, article attendu en tête, nombre maximal de résultats]
    ["superadmin", "message", "fr", "messagerie", 3],
    ["superadmin", "mess", "fr", "messagerie", 3],
    ["superadmin", "paiement", "fr", "paiements", 7],
    ["superadmin", "payer", "fr", "situation-financiere", 7], // « ce que chaque élève doit encore payer »,
    ["superadmin", "bulletin", "fr", "bulletins-generer", 4],
    ["superadmin", "absence", "fr", "absences", 3],
    ["superadmin", "note", "fr", "notes-saisir", 5],
    ["superadmin", "classe", "fr", "classes", 5],
    ["superadmin", "élève", "fr", "eleves", 5],
    ["superadmin", "enseignant", "fr", "enseignants", 3],
    ["superadmin", "emploi du temps", "fr", "emploi-du-temps", 3],
    ["superadmin", "visioconférence", "fr", "salles-virtuelles", 2],
    ["superadmin", "visio", "fr", "salles-virtuelles", 2],
    ["superadmin", "payment", "en", "paiements", 7],
    ["superadmin", "report card", "en", "bulletins-generer", 4],
    ["superadmin", "comment créer une classe", "fr", "classes", 10],
    ["admin", "réinitialiser mot de passe", "fr", "reinitialiser-mdp", 4],
    ["admin", "payment", "en", "paiements", 6],
    ["teacher", "saisir une note", "fr", "notes-saisir", 4],
    ["teacher", "homework", "en", "devoirs", 3],
    ["parent", "message", "fr", "messagerie", 1],
    ["parent", "paiement", "fr", "famille-paiements", 1],
    ["parent", "bulletin", "fr", "famille-notes", 1],
    ["parent", "payment", "en", "famille-paiements", 1],
    ["student", "épreuve", "fr", "passer-epreuve", 3],
    ["student", "exam", "en", "passer-epreuve", 3],
    ["student", "timetable", "en", "emploi-du-temps", 3],
  ];
  it.each(CAS)("%s « %s » (%s) → %s", (role, requete, lang, attendu, max) => {
    const r = ids(role, requete, lang);
    expect(r[0]).toBe(attendu);
    expect(r.length).toBeLessThanOrEqual(max);
  });
});

describe("tolérance", () => {
  it("accents, majuscules et racines", () => {
    expect(ids("admin", "ELEVE")[0]).toBe("eleves");
    expect(ids("admin", "paiements")).toEqual(ids("admin", "paiement"));
    expect(racine("paiements")).toBe("paiement");
    expect(racine("classes")).toBe(racine("classe"));
  });
  it("fautes de frappe corrigées vers le mot le plus proche seulement", () => {
    expect(ids("superadmin", "bulettin")[0]).toBe("bulletins-generer");
    expect(ids("parent", "paiemnt")).toEqual(["famille-paiements"]);
    expect(ids("superadmin", "paiemnt")).not.toContain("parents");
    expect(distance("bulletin", "bulettin")).toBe(2);
  });
  it("un mot réel n'est jamais traité comme une faute de frappe", () => {
    expect(analyser("paiement")[0].flou).toBe(false);
    expect(ids("parent", "paiement")).toEqual(["famille-paiements"]);
  });
  it("termes anglais dans l'interface française, et inversement", () => {
    expect(ids("superadmin", "password", "fr")).toContain("reinitialiser-mdp");
    expect(ids("superadmin", "mot de passe", "en")).toContain("reinitialiser-mdp");
  });
  it("tous les mots significatifs doivent être trouvés", () => {
    expect(ids("admin", "zzzz introuvable")).toEqual([]);
    expect(ids("admin", "bulletin zzzz")).toEqual([]);
  });
  it("aucun résultat : suggestions de mots de l'aide", () => {
    expect(ids("admin", "bulltinzz")).toEqual([]);
    expect(suggestions("bultin")).toContain("bulletin");
  });
});

describe("FAQ, dépannage et glossaire classés aussi", () => {
  it("trouvent par synonyme et respectent le profil", () => {
    expect(faqPour("parent", "fr", "password").length).toBeGreaterThan(0);
    expect(glossairePour("parent", "fr", "coefficient").length).toBe(1);
    expect(faqPour("superadmin").length).toBeGreaterThanOrEqual(faqPour("parent").length);
  });
});
