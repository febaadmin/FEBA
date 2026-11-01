import { describe, expect, it } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";

import DataTable from "../components/ui/DataTable";
import { ageColumn, ageSortValue, ageText, studentOptionLabel } from "./age";

/**
 * P1 — Âge des élèves dans les listes.
 *
 * Le calcul est fait par le serveur ; ces tests vérifient que l'interface
 * l'AFFICHE fidèlement, signale les données absentes ou incohérentes au
 * lieu d'inventer une valeur, et trie numériquement (9 avant 10).
 */
describe("ageText", () => {
  it("affiche l'âge en années", () => {
    expect(ageText(9, "ok")).toBe("9 ans");
    expect(ageText(1, "ok")).toBe("1 an");
  });

  it("signale une date de naissance absente", () => {
    expect(ageText(null, "missing")).toBe("Non renseigné");
    expect(ageText(undefined, undefined)).toBe("Non renseigné");
  });

  it("signale une date incohérente sans afficher d'âge négatif", () => {
    expect(ageText(null, "invalid")).toBe("Date invalide");
  });
});

describe("ageSortValue", () => {
  it("rend un nombre pour un âge connu, null sinon", () => {
    expect(ageSortValue(10, "ok")).toBe(10);
    expect(ageSortValue(null, "missing")).toBeNull();
    expect(ageSortValue(null, "invalid")).toBeNull();
  });
});

describe("studentOptionLabel", () => {
  it("ajoute l'âge au libellé du sélecteur", () => {
    expect(studentOptionLabel({ full_name: "Ana B", class_name: "CE1", age: 7, age_status: "ok" }))
      .toBe("Ana B - CE1 · 7 ans");
    expect(studentOptionLabel({ full_name: "Ana B", matricule: "FEBA-26-0001", age_status: "missing" },
                              { withMatricule: true }))
      .toBe("Ana B - FEBA-26-0001 (?) · Non renseigné");
  });
});

describe("DataTable + ageColumn", () => {
  const rows = [
    { id: 1, full_name: "Dix", age: 10, age_status: "ok" },
    { id: 2, full_name: "Neuf", age: 9, age_status: "ok" },
    { id: 3, full_name: "Inconnu", age: null, age_status: "missing" },
    { id: 4, full_name: "Onze", age: 11, age_status: "ok" },
  ];
  const columns = [{ key: "name", label: "Nom", accessor: "full_name" }, ageColumn()];

  const namesInOrder = () =>
    screen.getAllByRole("row").slice(1).map((r) => within(r).getAllByRole("cell")[0].textContent);

  it("affiche la colonne Âge pour chaque ligne", () => {
    render(<DataTable columns={columns} data={rows} />);
    expect(screen.getByText("Âge")).toBeTruthy();
    expect(screen.getByText("10 ans")).toBeTruthy();
    expect(screen.getByText("Non renseigné")).toBeTruthy();
  });

  it("trie numériquement et laisse les âges inconnus en fin de liste", () => {
    render(<DataTable columns={columns} data={rows} />);
    fireEvent.click(screen.getByText("Âge"));
    expect(namesInOrder()).toEqual(["Neuf", "Dix", "Onze", "Inconnu"]);
    fireEvent.click(screen.getByText("Âge"));
    expect(namesInOrder()).toEqual(["Onze", "Dix", "Neuf", "Inconnu"]);
  });

  it("ageColumn('student_age') lit les champs de l'objet porteur", () => {
    render(<DataTable columns={[ageColumn("student_age")]}
                      data={[{ id: 1, student_age: 8, student_age_status: "ok" }]} />);
    expect(screen.getByText("8 ans")).toBeTruthy();
  });
});
