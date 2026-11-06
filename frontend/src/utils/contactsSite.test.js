import { describe, expect, it } from "vitest";
import { emailValide, lienWhatsApp, numeroWhatsApp } from "./contactsSite";

describe("coordonnées du site vitrine (données réelles de production)", () => {
  it.each([
    ["+22995458921", "22995458921"], ["+229 0197947742", "2290197947742"], ["+34691696416", "34691696416"],
    ["0195458921", "2290195458921"], ["0166188106", "2290166188106"], ["00229 01 97 07 96 78", "2290197079678"],
  ])("%s → wa.me/%s", (brut, attendu) => {
    expect(numeroWhatsApp(brut)).toEqual({ valide: true, numero: attendu });
  });
  it.each([["", /Aucun numéro/], ["07053252128", /sans indicatif/], ["+12", /invalide/], ["abc", /sans indicatif/]])(
    "%s refusé, raison expliquée", (brut, raison) => {
      const r = numeroWhatsApp(brut);
      expect(r.valide).toBe(false);
      expect(r.raison).toMatch(raison);
    });
  it("e-mail et lien", () => {
    expect(emailValide("enarawrites@gmail.com")).toBe(true);
    expect(emailValide("")).toBe(false);
    expect(emailValide("pas une adresse")).toBe(false);
    expect(lienWhatsApp("22995458921", "Bonjour")).toBe("https://wa.me/22995458921?text=Bonjour");
  });
});
