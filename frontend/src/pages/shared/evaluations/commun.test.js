import { describe, it, expect } from "vitest";
import { construireQuestion, erreursQuestion, formulaireDepuis } from "./commun";

const base = { enonce: "Q", points: 1 };

describe("questions de la banque", () => {
  const choix = [{ texte: " 4 ", bon: true }, { texte: "5" }, { texte: "" }];
  it("construit le QCM sans les lignes vides", () => {
    expect(construireQuestion("qcm_unique", { choix })).toEqual({
      contenu: { choix: [{ id: "c0", texte: "4" }, { id: "c1", texte: "5" }] }, corrige: { bonne: "c0" },
    });
    expect(construireQuestion("qcm_multiple", { choix }).corrige).toEqual({ bonnes: ["c0"] });
  });
  it("explique chaque erreur sous le champ concerné", () => {
    expect(erreursQuestion("qcm_multiple", { ...base, choix: [{ texte: "test,test" }] }).reponses).toBe("Saisissez au moins deux réponses.");
    expect(erreursQuestion("qcm_unique", { ...base, choix: [{ texte: "a" }, { texte: "b" }] }).reponses).toBe("Cochez la bonne réponse.");
    expect(erreursQuestion("qcm_unique", { ...base, choix: [{ texte: "a", bon: true }, { texte: "A" }] }).reponses).toBe("Deux réponses sont identiques.");
    expect(erreursQuestion("qcm_multiple", { ...base, choix })).toEqual({});
    expect(erreursQuestion("ouverte", { points: 1 }).enonce).toBeTruthy();
    expect(erreursQuestion("association", { ...base, lignes: "a = b\nc" }).reponses).toMatch(/format/);
    expect(erreursQuestion("numerique", { ...base, valeur: "abc" }).valeur).toBeTruthy();
    expect(erreursQuestion("ouverte", base)).toEqual({});
  });
  it.each([
    ["qcm_unique", { choix: [{ texte: "a", bon: true }, { texte: "b" }] }],
    ["qcm_multiple", { choix: [{ texte: "a", bon: true }, { texte: "b", bon: true }] }],
    ["vrai_faux", { vrai: "faux" }],
    ["courte", { lignes: "a\nb" }],
    ["trous", { lignes: "a | b\nc" }],
    ["association", { lignes: "a = 1\nb = 2" }],
    ["classement", { lignes: "a\nb" }],
    ["numerique", { valeur: "3", tolerance: "0.1" }],
  ])("%s garde son corrigé après un aller-retour de modification", (type, f) => {
    const { contenu, corrige } = construireQuestion(type, f);
    const repris = formulaireDepuis({ type, version: { contenu, corrige } });
    expect(construireQuestion(type, repris).corrige).toEqual(corrige);
  });
});
