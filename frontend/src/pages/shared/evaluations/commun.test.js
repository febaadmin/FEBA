import { describe, it, expect } from "vitest";
import { construireQuestion, erreurChoix } from "./commun";

describe("QCM de la banque", () => {
  const choix = [{ texte: " 4 ", bon: true }, { texte: "5" }, { texte: "" }];
  it("construit le contenu et le corrigé sans les lignes vides", () => {
    expect(construireQuestion("qcm_unique", { choix })).toEqual({
      contenu: { choix: [{ id: "c0", texte: "4" }, { id: "c1", texte: "5" }] }, corrige: { bonne: "c0" },
    });
    expect(construireQuestion("qcm_multiple", { choix }).corrige).toEqual({ bonnes: ["c0"] });
  });
  it("explique ce qui manque avant l'envoi", () => {
    expect(erreurChoix("qcm_unique", [{ texte: "a" }])).toBe("Saisissez au moins deux réponses.");
    expect(erreurChoix("qcm_unique", [{ texte: "a" }, { texte: "b" }])).toBe("Cochez la bonne réponse.");
    expect(erreurChoix("qcm_multiple", choix)).toBeNull();
    expect(erreurChoix("ouverte", [])).toBeNull();
  });
});
