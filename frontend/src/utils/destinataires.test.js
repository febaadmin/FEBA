import { describe, it, expect } from "vitest";
import { libelleCible } from "./destinataires";

describe("libelleCible", () => {
  it("traduit la valeur technique et garde une valeur inconnue", () => {
    expect(libelleCible("all")).toBe("Tous les profils");
    expect(libelleCible("autre")).toBe("autre");
  });
});
