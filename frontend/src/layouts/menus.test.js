import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { MENU_ADMIN, MENU_ELEVE, MENU_ENSEIGNANT, MENU_PARENT, MENU_SUPERADMIN, entrees } from "./menus";

// Le parcours E2E « navigation » visite routes.json : chaque entrée de menu doit y figurer.
const ROUTES = JSON.parse(readFileSync(resolve(process.cwd(), "../e2e/ci/routes.json"), "utf8"));

describe("menus et parcours de navigation", () => {
  it("chaque entrée de menu est visitée par le parcours E2E", () => {
    for (const [role, menu] of [["superadmin", MENU_SUPERADMIN], ["admin", MENU_ADMIN], ["teacher", MENU_ENSEIGNANT],
      ["parent", MENU_PARENT], ["student", MENU_ELEVE]]) {
      const absentes = entrees(menu).map((i) => i.to).filter((to) => !ROUTES[role].includes(to));
      expect(absentes, role).toEqual([]);
    }
  });
});
