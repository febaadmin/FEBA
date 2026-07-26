/**
 * Régression V7 — la note saisie n'est jamais altérée.
 * « 10 » DOIT rester « 10 » (le bug enregistrait 9,5 / 9,75).
 */
import { describe, it, expect } from "vitest";
import { normalizeGradeInput, isValidGrade, gradePayloadValue } from "./gradeInput";

describe("normalizeGradeInput — aucune altération de la valeur", () => {
  it("laisse 10 strictement égal à 10", () => {
    expect(normalizeGradeInput("10")).toBe("10");
    expect(gradePayloadValue("10")).toBe("10");
  });
  it("conserve les décimales exactes", () => {
    for (const v of ["0", "0.25", "0.5", "9.5", "9.75", "10", "10.25", "10.5", "10.75", "15", "19.75", "20"]) {
      expect(normalizeGradeInput(v)).toBe(v);
      expect(gradePayloadValue(v)).toBe(v);
    }
  });
  it("convertit la virgule française en point sans changer la valeur", () => {
    expect(normalizeGradeInput("10,5")).toBe("10.5");
    expect(normalizeGradeInput("10,00")).toBe("10.00");
    expect(gradePayloadValue("10,5")).toBe("10.5");
  });
  it("supprime les caractères parasites et les points multiples", () => {
    expect(normalizeGradeInput("1o")).toBe("1");        // lettre supprimée
    expect(normalizeGradeInput("10.5.5")).toBe("10.55"); // un seul séparateur
    expect(normalizeGradeInput(" 10 ")).toBe("10");
  });
});

describe("isValidGrade — bornes 0..20", () => {
  it("accepte 0 → 20 et les décimales", () => {
    for (const v of ["0", "0.25", "10", "10.75", "19.99", "20"]) expect(isValidGrade(v)).toBe(true);
  });
  it("rejette hors bornes et vide", () => {
    for (const v of ["", ".", "20.01", "21", "abc"]) expect(isValidGrade(v)).toBe(false);
  });
  it("neutralise le signe négatif (le « - » est retiré à la saisie)", () => {
    expect(normalizeGradeInput("-1")).toBe("1"); // pas de note négative possible
    expect(isValidGrade("-1")).toBe(true);
  });
});

describe("gradePayloadValue — null si invalide", () => {
  it("renvoie null pour une saisie invalide (pas de valeur inventée)", () => {
    expect(gradePayloadValue("")).toBeNull();
    expect(gradePayloadValue("21")).toBeNull();
  });
});
