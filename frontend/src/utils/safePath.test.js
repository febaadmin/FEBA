import { describe, it, expect } from "vitest";
import { safeInternalPath } from "./safePath";

describe("safeInternalPath", () => {
  it("accepte les chemins internes", () => {
    expect(safeInternalPath("/parent/grades")).toBe("/parent/grades");
    expect(safeInternalPath("/admin/website?tab=prereg&reference=FEBA-2026-0007")).toBe(
      "/admin/website?tab=prereg&reference=FEBA-2026-0007");
  });
  it("refuse tout ce qui ferait quitter l'application", () => {
    for (const bad of ["//evil.example", "/\\evil.example", "https://evil.example", "javascript:alert(1)",
      "/a\\..\\b", "\n/x", "", null, undefined, 42]) {
      expect(safeInternalPath(bad)).toBeNull();
    }
  });
});
