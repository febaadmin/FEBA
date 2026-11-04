// Glossaire personnalisé : chaque profil ne voit que les termes qui le concernent,
// avec la définition écrite pour lui ; le super administrateur voit tout.
import { describe, expect, it } from "vitest";
import { ROLES } from "./articles";
import { TERMES, definitionPour, termesPour } from "./glossaire";
import { glossairePour } from "./recherche";

const ids = (role, actif) => termesPour(role, actif).map((t) => t.id);
const def = (role, id, lang = 0) => termesPour(role).find((t) => t.id === id)?.definition[lang];

describe("glossaire par profil", () => {
  it("identifiants uniques et toutes les définitions en FR et EN", () => {
    expect(new Set(TERMES.map((t) => t.id)).size).toBe(TERMES.length);
    for (const t of TERMES) for (const d of Object.values(t.definitions).filter(Boolean)) {
      expect(d[0].trim() && d[1].trim() && d[0] !== d[1], t.id).toBeTruthy();
    }
  });

  it("le super administrateur voit tous les termes, quelle que soit l'académie", () => {
    expect(ids("superadmin", () => false).length).toBe(TERMES.length);
  });

  it("un élève ne voit aucune notion d'administration ni de finance", () => {
    const eleve = ids("student");
    for (const interdit of ["academie", "toutes-academies", "module", "incident", "gabarit", "tarif", "echeance",
      "reste-a-payer", "exoneration", "recouvrement", "devise", "inscription", "referentiel", "justificatif", "annee-active"]) {
      expect(eleve, interdit).not.toContain(interdit);
    }
    for (const attendu of ["classe", "note-officielle", "bulletin", "devoir", "absence", "matiere", "moyenne"]) {
      expect(eleve).toContain(attendu);
    }
  });

  it("un parent voit le suivi de son enfant et ses paiements, pas l'administration", () => {
    const parent = ids("parent");
    expect(parent).toEqual(expect.arrayContaining(["bulletin", "absence", "reste-a-payer", "echeance", "recu", "tarif"]));
    for (const interdit of ["academie", "incident", "gabarit", "exoneration", "quiz", "tentative", "referentiel"]) {
      expect(parent, interdit).not.toContain(interdit);
    }
  });

  it("un enseignant voit la pédagogie, pas les finances", () => {
    const prof = ids("teacher");
    expect(prof).toEqual(expect.arrayContaining(["classe", "note-officielle", "transfert", "tentative", "referentiel", "absence", "devoir"]));
    for (const interdit of ["tarif", "echeance", "reste-a-payer", "recu", "academie", "incident", "gabarit"]) {
      expect(prof, interdit).not.toContain(interdit);
    }
  });

  it("un administrateur gère son académie, sans supervision globale", () => {
    const admin = ids("admin");
    expect(admin).toEqual(expect.arrayContaining(["academie", "tarif", "exoneration", "gabarit"]));
    expect(admin).not.toContain("incident");
    expect(admin).not.toContain("toutes-academies");
  });

  it("une même notion, une définition adaptée à chaque profil", () => {
    const classe = new Set(ROLES.map((r) => def(r, "classe")));
    expect(classe.size).toBe(5);
    expect(def("student", "classe")).toMatch(/^Ton groupe/);
    expect(def("parent", "classe")).toMatch(/votre enfant/);
    expect(def("teacher", "classe", 1)).toMatch(/assigned to you/);
    expect(definitionPour(TERMES.find((t) => t.id === "classe"), "superadmin")[0]).toMatch(/académie/);
  });

  it("un module désactivé masque ses termes (sauf pour le super administrateur)", () => {
    const sansSuivi = (t) => t.feature !== "suivi_pedagogique";
    expect(ids("teacher", sansSuivi)).not.toContain("competence");
    expect(ids("teacher")).toContain("competence");
    expect(ids("superadmin", sansSuivi)).toContain("competence");
  });

  it("la recherche du glossaire respecte le profil et la langue", () => {
    expect(glossairePour("student", "fr", "académie")).toEqual([]);
    expect(glossairePour("admin", "fr", "académie").map((t) => t.id)).toContain("academie");
    expect(glossairePour("parent", "en", "receipt").map((t) => t.id)).toContain("recu");
  });
});
