import { describe, it, expect, beforeEach, vi } from "vitest";
import { estErreurChargementModule, rechargerUneFois } from "./versionPerimee";

describe("versionPerimee", () => {
  beforeEach(() => sessionStorage.clear());

  it("reconnaît les erreurs de module introuvable des navigateurs", () => {
    expect(estErreurChargementModule(new TypeError("Failed to fetch dynamically imported module: https://x/assets/index-CnWUVqyn.js"))).toBe(true);
    expect(estErreurChargementModule(new TypeError("Importing a module script failed."))).toBe(true);
    expect(estErreurChargementModule(new Error("error loading dynamically imported module"))).toBe(true);
    expect(estErreurChargementModule(new Error("Cannot read properties of undefined"))).toBe(false);
    expect(estErreurChargementModule(null)).toBe(false);
  });

  it("ne recharge qu'une fois (pas de boucle)", () => {
    const recharger = vi.fn();
    expect(rechargerUneFois(1_000_000, recharger)).toBe(true);
    expect(rechargerUneFois(1_010_000, recharger)).toBe(false);
    expect(recharger).toHaveBeenCalledTimes(1);
    expect(rechargerUneFois(1_040_000, recharger)).toBe(true);
  });
});
