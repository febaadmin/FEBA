import { describe, expect, it } from "vitest";
import { tarifApplicable } from "./Tarifs";

const f = (id, level, school_year, payment_type = "mensualite", is_active = true) => ({ id, level, school_year, payment_type, is_active });

describe("résolution du tarif affiché dans la grille (comme le serveur)", () => {
  const fees = [f(1, null, null), f(2, null, 10), f(3, 5, 10), f(4, 6, null), f(5, 7, 10, "mensualite", false)];
  it("niveau et année > niveau seul > année > permanent", () => {
    expect(tarifApplicable(fees, 5, 10, "mensualite").id).toBe(3);
    expect(tarifApplicable(fees, 6, 10, "mensualite").id).toBe(4);
    expect(tarifApplicable(fees, 8, 10, "mensualite").id).toBe(2);
    expect(tarifApplicable(fees, 8, 11, "mensualite").id).toBe(1);
  });
  it("un tarif désactivé est ignoré ; une autre nature ne compte pas", () => {
    expect(tarifApplicable(fees, 7, 10, "mensualite").id).toBe(2);
    expect(tarifApplicable(fees, 5, 10, "cantine")).toBeNull();
  });
});
