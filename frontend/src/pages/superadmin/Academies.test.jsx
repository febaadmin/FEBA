/**
 * Écran « Académies » : type obligatoire, données envoyées, succès et liste
 * de configuration affichés seulement après la réponse du serveur, erreurs
 * du serveur affichées au bon champ, académie non classée signalée.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("react-hot-toast", () => ({ default: { success: vi.fn(), error: vi.fn() } }));
vi.mock("../../api", () => ({
  schoolsAPI: { list: vi.fn(), createAcademy: vi.fn(), update: vi.fn(), deleteAcademy: vi.fn(), setupStatus: vi.fn() },
}));

import toast from "react-hot-toast";
import { schoolsAPI } from "../../api";
import SuperAdminAcademies from "./Academies";

const LIST = [
  { id: 1, name: "FEBA", code: "FEBA", academy_type: null, is_active: true, students_count: 120,
    classification: { suggested_type: null, reason: "niveaux de primaire ET de secondaire" } },
  { id: 2, name: "FEBA FHA", code: "FEBA_FHA", academy_type: "online", is_active: true, students_count: 30 },
];

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><SuperAdminAcademies /></QueryClientProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
  schoolsAPI.list.mockResolvedValue({ data: LIST });
});

describe("liste", () => {
  it("affiche le type et signale une académie non classée avec son motif", async () => {
    renderPage();
    const feba = await screen.findByTestId("academy-row-FEBA");
    expect(feba.textContent).toMatch(/Non classée/);
    expect(feba.textContent).toMatch(/primaire ET de secondaire/);
    expect(screen.getByTestId("academy-row-FEBA_FHA").textContent).toMatch(/Académie en ligne/);
  });
});

describe("création", () => {
  it("exige un type, envoie les données, puis affiche la configuration restante", async () => {
    let resolve;
    schoolsAPI.createAcademy.mockReturnValue(new Promise((r) => { resolve = r; }));
    renderPage();
    fireEvent.click(await screen.findByTestId("academy-create"));
    expect(screen.getByTestId("academy-submit").disabled).toBe(true);        // pas de type
    fireEvent.click(screen.getByTestId("academy-type-physical_secondary"));
    fireEvent.change(screen.getByTestId("academy-name"), { target: { value: "Lycée de Parakou" } });
    expect(screen.getByTestId("academy-code").value).toBe("LYCEE_DE_PARAKOU");  // code proposé
    fireEvent.change(screen.getByTestId("academy-address"), { target: { value: "Zongo" } });
    fireEvent.change(screen.getByTestId("academy-city"), { target: { value: "Parakou" } });
    fireEvent.change(screen.getByTestId("academy-country"), { target: { value: "Bénin" } });
    fireEvent.click(screen.getByTestId("academy-submit"));
    await waitFor(() => expect(schoolsAPI.createAcademy).toHaveBeenCalledTimes(1));
    expect(schoolsAPI.createAcademy.mock.calls[0][0]).toMatchObject({
      academy_type: "physical_secondary", name: "Lycée de Parakou", code: "LYCEE_DE_PARAKOU",
      address: "Zongo", city: "Parakou", country: "Bénin", currency_code: "XOF", default_language: "fr",
    });
    expect(schoolsAPI.createAcademy.mock.calls[0][0]).not.toHaveProperty("school_year_name");
    expect(toast.success).not.toHaveBeenCalled();
    resolve({ data: { id: 9, name: "Lycée de Parakou", code: "LYCEE_DE_PARAKOU", academy_type: "physical_secondary",
      setup_status: { checks: [
        { key: "levels", label: "Niveaux", done: true, action: "" },
        { key: "school_year", label: "Année scolaire active", done: false, action: "Créer l'année dans « Paramètres »." },
      ] } } });
    const created = await screen.findByTestId("academy-created");
    expect(within(created).getByTestId("setup-checklist").textContent).toMatch(/Créer l'année/);
    expect(toast.success).toHaveBeenCalled();
  });

  it("affiche l'erreur du serveur au bon champ", async () => {
    schoolsAPI.createAcademy.mockRejectedValue({ response: { status: 400,
      data: { code: ["Le code « FEBA » est déjà utilisé par une autre académie."] } } });
    renderPage();
    fireEvent.click(await screen.findByTestId("academy-create"));
    fireEvent.click(screen.getByTestId("academy-type-online"));
    fireEvent.change(screen.getByTestId("academy-name"), { target: { value: "FEBA" } });
    fireEvent.change(screen.getByTestId("academy-address"), { target: { value: "En ligne" } });
    fireEvent.click(screen.getByTestId("academy-submit"));
    expect(await screen.findByText(/déjà utilisé par une autre académie/)).toBeTruthy();
    expect(screen.queryByTestId("academy-created")).toBeNull();
    expect(toast.success).not.toHaveBeenCalled();
  });
});
