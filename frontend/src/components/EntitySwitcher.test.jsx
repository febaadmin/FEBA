import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Link } from "react-router-dom";
import EntitySwitcher from "./EntitySwitcher";

const mutate = vi.fn();
vi.mock("../hooks/useEntityContext", () => ({
  useEntityContext: () => ({
    isLoading: false, canSwitch: true, allEntitiesMode: false,
    activeEntity: { id: 1, name: "FEBA" },
    entities: [{ id: 1, name: "FEBA", code: "A" }, { id: 2, name: "FHA", code: "B" }],
  }),
  useEntitySwitch: () => ({ mutate, isPending: false, error: null }),
}));

function Page() {
  return (
    <MemoryRouter initialEntries={["/a"]}>
      <EntitySwitcher />
      <Link to="/b">Autre page</Link>
      <button type="button" onPointerDown={(e) => e.stopPropagation()}>Isolé</button>
      <main>Zone vide</main>
    </MemoryRouter>
  );
}
const ouvrir = () => { fireEvent.click(document.querySelector("[aria-haspopup]")); expect(screen.getByRole("listbox")).toBeTruthy(); };

describe("EntitySwitcher", () => {
  beforeEach(() => { mutate.mockClear(); render(<Page />); ouvrir(); });

  it("se ferme au clic sur une zone vide", () => {
    fireEvent.pointerDown(screen.getByText("Zone vide"));
    expect(screen.queryByRole("listbox")).toBeNull();
  });
  it("se ferme même si l'élément cliqué arrête la propagation", () => {
    fireEvent.pointerDown(screen.getByText("Isolé"));
    expect(screen.queryByRole("listbox")).toBeNull();
  });
  it("se ferme avec Échap", () => {
    fireEvent.keyDown(document.body, { key: "Escape" });
    expect(screen.queryByRole("listbox")).toBeNull();
  });
  it("se ferme quand le focus part ailleurs", () => {
    fireEvent.focusIn(screen.getByText("Autre page"));
    expect(screen.queryByRole("listbox")).toBeNull();
  });
  it("se ferme au changement de page et ne se rouvre pas", async () => {
    fireEvent.click(screen.getByText("Autre page"));
    await waitFor(() => expect(screen.queryByRole("listbox")).toBeNull());
  });
  it("reste ouvert sur un clic à l'intérieur, se ferme et bascule au choix", () => {
    fireEvent.pointerDown(screen.getByRole("listbox"));
    expect(screen.getByRole("listbox")).toBeTruthy();
    fireEvent.click(screen.getByText("FHA"));
    expect(mutate).toHaveBeenCalledWith(2, expect.anything());
    expect(screen.queryByRole("listbox")).toBeNull();
  });
  it("s'ouvre et se ferme par le bouton, plusieurs fois", () => {
    const bouton = document.querySelector("[aria-haspopup]");
    fireEvent.click(bouton); expect(screen.queryByRole("listbox")).toBeNull();
    fireEvent.click(bouton); expect(screen.getByRole("listbox")).toBeTruthy();
  });
});
