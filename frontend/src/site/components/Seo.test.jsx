/** Titres des pages publiques selon l'académie de la page. */
import { describe, it, expect } from "vitest";
import { fullPageTitle } from "./Seo";

describe("fullPageTitle", () => {
  it("pages FEBA : identité FEBA", () => {
    expect(fullPageTitle("Admissions", "/admissions")).toBe("Admissions — FEBA | Faith & Excellence Bilingual Academy");
    expect(fullPageTitle(undefined, "/")).toContain("FEBA — Faith & Excellence Bilingual Academy");
  });
  it("pages FEBA FHA : jamais l'identité de l'école de Cotonou", () => {
    expect(fullPageTitle("Contact", "/feba-fha/contact")).toBe("Contact — FEBA FHA | FEBA French Heritage Academy");
    expect(fullPageTitle("Fiche envoyée — FEBA FHA", "/feba-fha/enroll"))
      .toBe("Fiche envoyée — FEBA FHA | FEBA French Heritage Academy");
    expect(fullPageTitle("Contact", "/feba-fha/contact")).not.toContain("Bilingual Academy");
  });
});
