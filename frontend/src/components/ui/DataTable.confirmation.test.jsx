import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import DataTable from "./DataTable";

vi.mock("../../context/AcademyContext", () => ({ useAcademy: () => ({ isAllAcademies: true }) }));

const lignes = [{ id: 1, nom: "Awa", academy_code: "FEBA", academy_short_name: "FEBA" }];
const colonnes = [{ key: "nom", label: "Nom", accessor: "nom" }];

describe("DataTable", () => {
  it("demande confirmation dans la fenêtre commune, jamais avec la boîte du navigateur", () => {
    const natif = vi.spyOn(window, "confirm");
    const supprimer = vi.fn();
    render(<DataTable columns={colonnes} data={lignes} selectable onBulkDelete={supprimer} />);
    fireEvent.click(screen.getAllByRole("checkbox")[1]);
    fireEvent.click(screen.getByRole("button", { name: /Supprimer la sélection/ }));
    expect(natif).not.toHaveBeenCalled();
    expect(supprimer).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Supprimer" }));
    expect(supprimer).toHaveBeenCalledWith([1]);
  });

  it("n'affiche qu'une colonne Académie en mode toutes académies", () => {
    render(<DataTable columns={colonnes} data={lignes} />);
    expect(screen.getAllByRole("columnheader", { name: "Académie" })).toHaveLength(1);
  });

  it("le tri se déclenche au clavier", () => {
    render(<DataTable columns={colonnes} data={lignes} />);
    const entete = screen.getByRole("columnheader", { name: "Nom" });
    fireEvent.keyDown(entete, { key: "Enter" });
    expect(entete.getAttribute("aria-sort")).toBe("ascending");
  });
});
