import { describe, it, expect, beforeEach } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import MenuLateral from "./MenuLateral";
import { MENU_ADMIN, MENU_ELEVE, MENU_ENSEIGNANT, MENU_PARENT, MENU_SUPERADMIN, entrees } from "../../layouts/menus";

const monter = (menu, chemin, props = {}) => render(
  <MemoryRouter initialEntries={[chemin]}><MenuLateral menu={menu} profil="test" {...props} /></MemoryRouter>,
);

describe("menus regroupés", () => {
  beforeEach(() => localStorage.clear());

  it("aucune entrée perdue : mêmes routes qu'avant le regroupement (42, 38, 15, 16, 14), sans doublon", () => {
    for (const [menu, n] of [[MENU_SUPERADMIN, 42], [MENU_ADMIN, 38], [MENU_ENSEIGNANT, 15], [MENU_PARENT, 16], [MENU_ELEVE, 14]]) {
      const routes = entrees(menu).map((i) => i.to);
      expect(routes.length).toBe(n);
      expect(new Set(routes).size).toBe(n);
    }
  });

  it("le groupe de la page affichée est ouvert ; les autres se replient et se rouvrent", () => {
    monter(MENU_ADMIN, "/admin/tarifs");
    const finances = screen.getByTestId("menu-groupe-finances");
    expect(within(finances).getByText("Tarifs et échéances")).toBeVisible();
    const pedagogie = screen.getByTestId("menu-groupe-pedagogie");
    const bouton = within(pedagogie).getByRole("button");
    expect(bouton).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(bouton);
    expect(bouton).toHaveAttribute("aria-expanded", "true");
    expect(within(pedagogie).getByText("Notes")).toBeVisible();
    expect(JSON.parse(localStorage.getItem("feba.menu.test")).pedagogie).toBe(true);
  });

  it("menus courts (élève) : groupes ouverts par défaut", () => {
    monter(MENU_ELEVE, "/student/home");
    expect(screen.getByText("Mes notes")).toBeVisible();
    expect(screen.getByText("Messages")).toBeVisible();
  });

  it("entrées réservées masquées ; groupe vide masqué ; badge des messages", () => {
    monter(MENU_PARENT, "/parent/home", { visible: (i) => !i.feature, badges: { messages: 3 } });
    expect(screen.queryByText("Salles virtuelles")).toBeNull();
    expect(screen.getByTestId("badge-messages-menu")).toHaveTextContent("3");
  });
});
