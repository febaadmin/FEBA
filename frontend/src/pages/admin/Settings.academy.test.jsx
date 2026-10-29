/**
 * Paramètres : l'établissement modifié est celui de l'ACADÉMIE ACTIVE.
 *
 * Défaut corrigé : la page prenait le premier établissement de la liste.
 * Pour un super administrateur, la liste contient toutes les académies :
 * « Enregistrer » écrasait le nom et l'adresse d'une autre académie.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

let ctx;
vi.mock("../../hooks/useEntityContext", () => ({
  useAcademyKey: () => "academy:test",
  useEntityContext: () => ctx,
}));
vi.mock("../../components/AcademyBadge", () => ({ default: () => null }));
vi.mock("react-hot-toast", () => ({ default: { success: vi.fn(), error: vi.fn() } }));
vi.mock("../../api", () => {
  const empty = () => Promise.resolve({ data: [] });
  return {
  schoolsAPI: {
    list: vi.fn(), update: vi.fn(() => Promise.resolve({ data: {} })),
    years: empty, rooms: empty, roomTypes: empty,
  },
  subjectsAPI: { list: empty },
  classesAPI: { list: empty },
  };
});

import { schoolsAPI } from "../../api";
import AdminSettings from "./Settings";

const ALL = [
  { id: 1, name: "Académie Alpha", address: "A", city: "", phone: "", email: "" },
  { id: 2, name: "Lycée de Parakou", address: "B", city: "", phone: "", email: "" },
];

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><AdminSettings /></QueryClientProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
  schoolsAPI.list.mockResolvedValue({ data: ALL });
});

describe("Paramètres — académie active", () => {
  it("modifie l'académie sélectionnée, pas la première de la liste", async () => {
    ctx = { allEntitiesMode: false, activeEntity: { id: 2 } };
    renderPage();
    await waitFor(() => expect(screen.getByDisplayValue("Lycée de Parakou")).toBeTruthy());
    fireEvent.submit(screen.getByTestId("school-form"));
    await waitFor(() => expect(schoolsAPI.update).toHaveBeenCalledTimes(1));
    expect(schoolsAPI.update.mock.calls[0][0]).toBe(2);
  });

  it("en vue « toutes les académies », ne propose aucun formulaire", async () => {
    ctx = { allEntitiesMode: true, activeEntity: null };
    renderPage();
    expect(await screen.findByText("Sélectionnez une académie pour modifier ses informations.")).toBeTruthy();
    expect(screen.queryByTestId("school-form")).toBeNull();
  });
});
