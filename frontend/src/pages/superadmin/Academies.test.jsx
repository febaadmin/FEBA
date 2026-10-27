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
  schoolsAPI: { list: vi.fn(), createAcademy: vi.fn(), update: vi.fn(), deleteAcademy: vi.fn(), setupStatus: vi.fn(),
    languageDiagnostic: vi.fn() },
}));

import toast from "react-hot-toast";
import { schoolsAPI } from "../../api";
import SuperAdminAcademies from "./Academies";

const LIST = [
  { id: 1, name: "FEBA", code: "FEBA", academy_type: null, curriculum_language_mode: null, is_active: true, students_count: 120,
    classification: { suggested_type: null, reason: "niveaux de primaire ET de secondaire" } },
  { id: 2, name: "FEBA FHA", code: "FEBA_FHA", academy_type: "online", curriculum_language_mode: "bilingual",
    is_active: true, students_count: 30 },
  { id: 3, name: "Académie Évangélique Saint-Éloi de Natitingou", code: "TESTETE", academy_type: "physical_primary",
    curriculum_language_mode: "french_only", is_active: true, students_count: 4 },
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

  it("affiche le programme linguistique, ou « À configurer » s'il est vide", async () => {
    renderPage();
    expect((await screen.findByTestId("academy-curriculum-FEBA")).textContent).toBe("À configurer");
    expect(screen.getByTestId("academy-curriculum-FEBA_FHA").textContent).toBe("Bilingue français-anglais");
    expect(screen.getByTestId("academy-curriculum-TESTETE").textContent).toBe("Français uniquement");
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
    expect(screen.getByTestId("academy-submit").disabled).toBe(true);        // pas de programme
    fireEvent.click(screen.getByTestId("academy-curriculum-english_only"));
    expect(screen.getByTestId("academy-submit").disabled).toBe(false);
    fireEvent.change(screen.getByTestId("academy-name"), { target: { value: "Lycée de Parakou" } });
    expect(screen.getByTestId("academy-code").value).toBe("LYCEE_DE_PARAKOU");  // code proposé
    fireEvent.change(screen.getByTestId("academy-address"), { target: { value: "Zongo" } });
    fireEvent.change(screen.getByTestId("academy-city"), { target: { value: "Parakou" } });
    fireEvent.change(screen.getByTestId("academy-country"), { target: { value: "Bénin" } });
    fireEvent.click(screen.getByTestId("academy-submit"));
    await waitFor(() => expect(schoolsAPI.createAcademy).toHaveBeenCalledTimes(1));
    expect(schoolsAPI.createAcademy.mock.calls[0][0]).toMatchObject({
      academy_type: "physical_secondary", curriculum_language_mode: "english_only",
      name: "Lycée de Parakou", code: "LYCEE_DE_PARAKOU",
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
    fireEvent.click(screen.getByTestId("academy-curriculum-bilingual"));
    fireEvent.change(screen.getByTestId("academy-name"), { target: { value: "FEBA" } });
    fireEvent.change(screen.getByTestId("academy-address"), { target: { value: "En ligne" } });
    fireEvent.click(screen.getByTestId("academy-submit"));
    expect(await screen.findByText(/déjà utilisé par une autre académie/)).toBeTruthy();
    expect(screen.queryByTestId("academy-created")).toBeNull();
    expect(toast.success).not.toHaveBeenCalled();
  });
});

describe("changement de programme linguistique", () => {
  it("montre le diagnostic et exige une confirmation explicite avant d'envoyer", async () => {
    schoolsAPI.languageDiagnostic.mockResolvedValue({ data: { mode: "french_only", ok: false,
      subjects: [{ id: 7, name: "English Reading", language: "en" }],
      classes: [{ id: 4, name: "CM2 B", school_year: "2026-2027", reasons: ["matières English Reading"] }],
      grades: 12 } });
    schoolsAPI.update.mockResolvedValue({ data: {} });
    renderPage();
    fireEvent.click(await screen.findByTestId("academy-edit-FEBA_FHA"));
    fireEvent.change(screen.getByTestId("academy-edit-curriculum"), { target: { value: "french_only" } });
    const box = await screen.findByTestId("curriculum-diagnostic");
    expect(schoolsAPI.languageDiagnostic).toHaveBeenCalledWith(2, "french_only");
    expect(box.textContent).toMatch(/English Reading/);
    expect(box.textContent).toMatch(/CM2 B \(2026-2027\)/);
    expect(box.textContent).toMatch(/12/);
    expect(box.textContent).toMatch(/rien ne sera supprimé/);
    expect(screen.getByTestId("academy-edit-submit").disabled).toBe(true);
    fireEvent.click(screen.getByTestId("academy-confirm-curriculum"));
    fireEvent.click(screen.getByTestId("academy-edit-submit"));
    await waitFor(() => expect(schoolsAPI.update).toHaveBeenCalledTimes(1));
    expect(schoolsAPI.update.mock.calls[0][1]).toMatchObject({
      curriculum_language_mode: "french_only", confirm_curriculum_change: true });
  });

  it("sans conflit, envoie le changement sans confirmation ; sans changement, n'envoie pas le champ", async () => {
    schoolsAPI.languageDiagnostic.mockResolvedValue({ data: { ok: true, subjects: [], classes: [], grades: 0 } });
    schoolsAPI.update.mockResolvedValue({ data: {} });
    renderPage();
    fireEvent.click(await screen.findByTestId("academy-edit-TESTETE"));
    fireEvent.click(screen.getByTestId("academy-edit-submit"));
    await waitFor(() => expect(schoolsAPI.update).toHaveBeenCalledTimes(1));
    expect(schoolsAPI.update.mock.calls[0][1]).not.toHaveProperty("curriculum_language_mode");
    expect(schoolsAPI.languageDiagnostic).not.toHaveBeenCalled();

    fireEvent.click(await screen.findByTestId("academy-edit-TESTETE"));
    fireEvent.change(screen.getByTestId("academy-edit-curriculum"), { target: { value: "bilingual" } });
    await screen.findByTestId("curriculum-diagnostic-ok");
    expect(screen.queryByTestId("academy-confirm-curriculum")).toBeNull();
    fireEvent.click(screen.getByTestId("academy-edit-submit"));
    await waitFor(() => expect(schoolsAPI.update).toHaveBeenCalledTimes(2));
    expect(schoolsAPI.update.mock.calls[1][1]).toMatchObject({ curriculum_language_mode: "bilingual" });
    expect(schoolsAPI.update.mock.calls[1][1]).not.toHaveProperty("confirm_curriculum_change");
  });

  it("une académie à configurer ne propose pas de revenir à vide une fois choisi", async () => {
    renderPage();
    fireEvent.click(await screen.findByTestId("academy-edit-FEBA_FHA"));
    const options = [...screen.getByTestId("academy-edit-curriculum").options].map((o) => o.value);
    expect(options).toEqual(["french_only", "english_only", "bilingual"]);
  });
});
