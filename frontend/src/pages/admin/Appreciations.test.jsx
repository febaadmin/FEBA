/**
 * Écran « Appréciations » : brouillon, validation locale, enregistrement
 * du barème ENTIER, erreurs serveur affichées, succès seulement après la
 * réponse, aperçu sur 10 et sur 20, académie obligatoire.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

let academy = { activeAcademy: { id: 3, name: "École Parakou" }, isAllAcademies: false };
vi.mock("../../context/AcademyContext", () => ({ useAcademy: () => academy }));
vi.mock("react-hot-toast", () => ({ default: { success: vi.fn(), error: vi.fn() } }));
vi.mock("../../api", () => ({
  appreciationsAPI: { get: vi.fn(), save: vi.fn(), preview: vi.fn(), reset: vi.fn() },
}));

import toast from "react-hot-toast";
import { appreciationsAPI } from "../../api";
import AdminAppreciations, { localErrors } from "./Appreciations";

const RULES = [
  { id: 1, min_percent: "95.00", label_fr: "EXCELLENT", label_en: "EXCELLENT", is_active: true, used_by_bulletins: 2 },
  { id: 2, min_percent: "55.00", label_fr: "PEUT MIEUX FAIRE", label_en: "CAN DO BETTER", is_active: true, used_by_bulletins: 0 },
  { id: 3, min_percent: "0.00", label_fr: "TRÈS FAIBLE", label_en: "VERY WEAK", is_active: true, used_by_bulletins: 0 },
];
const payload = (rules = RULES) => ({
  data: { academy: { id: 3 }, cycle: "", rules, effective: rules, cycles_with_override: [] },
});

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><AdminAppreciations /></QueryClientProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
  academy = { activeAcademy: { id: 3, name: "École Parakou" }, isAllAcademies: false };
  appreciationsAPI.get.mockResolvedValue(payload());
});

describe("validation locale", () => {
  const row = (min, label, active = true) => ({ min_percent: min, label_fr: label, label_en: "", is_active: active });
  it("refuse seuils en double, absence de 0 %, libellé vide", () => {
    expect(localErrors([row("50", "A"), row("50", "B"), row("0", "C")]).join(" ")).toMatch(/même seuil/);
    expect(localErrors([row("50", "A")]).join(" ")).toMatch(/0 %/);
    expect(localErrors([row("0", " ")]).join(" ")).toMatch(/libellé français/);
    expect(localErrors([row("0", "A"), row("50", "a")]).join(" ")).toMatch(/en double/);
    expect(localErrors([row("0", "A"), row("120", "B")]).join(" ")).toMatch(/entre 0 et 100/);
    expect(localErrors([row("95", "E"), row("0", "F")])).toEqual([]);
  });
});

describe("écran", () => {
  it("exige une académie sélectionnée", () => {
    academy = { activeAcademy: null, isAllAcademies: true };
    renderPage();
    expect(screen.getByRole("alert").textContent).toMatch(/Sélectionnez d'abord l'académie/);
    expect(appreciationsAPI.get).not.toHaveBeenCalled();
  });

  it("affiche le barème et les intervalles sur 20 et sur 10", async () => {
    renderPage();
    const table = await screen.findByTestId("appreciations-table");
    expect(within(table).getAllByDisplayValue("EXCELLENT")).toHaveLength(2);   // FR et EN
    expect(table.textContent).toContain("/20 : 19–20");
    expect(table.textContent).toContain("/10 : 9,5–10".replace(",", (0.5).toLocaleString().charAt(1)));
    expect(screen.getByTestId("appreciations-save").disabled).toBe(true);   // rien à enregistrer
  });

  it("enregistre le barème entier, puis annonce le succès après la réponse", async () => {
    let resolve;
    appreciationsAPI.save.mockReturnValue(new Promise((r) => { resolve = r; }));
    renderPage();
    const row = await screen.findByTestId("appreciation-row-1");
    fireEvent.change(within(row).getAllByLabelText("Libellé (français)")[0], { target: { value: "À AMÉLIORER" } });
    fireEvent.click(screen.getByTestId("appreciations-add"));
    const added = screen.getByTestId("appreciation-row-3");
    fireEvent.change(within(added).getByLabelText("Libellé (français)"), { target: { value: "BIEN" } });
    fireEvent.change(within(added).getByLabelText("Seuil (%)"), { target: { value: "75" } });
    expect(screen.getByTestId("appreciations-dirty")).toBeTruthy();
    fireEvent.click(screen.getByTestId("appreciations-save"));
    await waitFor(() => expect(appreciationsAPI.save).toHaveBeenCalledTimes(1));
    const [cycle, rules] = appreciationsAPI.save.mock.calls[0];
    expect(cycle).toBe("");
    expect(rules).toHaveLength(4);
    expect(rules[1]).toMatchObject({ id: 2, label_fr: "À AMÉLIORER" });
    expect(rules[3]).toMatchObject({ id: null, min_percent: "75", label_fr: "BIEN" });
    expect(toast.success).not.toHaveBeenCalled();                     // pas avant la réponse
    resolve(payload([...RULES.slice(0, 1), { ...RULES[1], label_fr: "À AMÉLIORER" }, RULES[2],
      { id: 9, min_percent: "75.00", label_fr: "BIEN", label_en: "", is_active: true, used_by_bulletins: 0 }]));
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Barème enregistré."));
  });

  it("affiche les erreurs du serveur et n'annonce pas de succès", async () => {
    appreciationsAPI.save.mockRejectedValue({ response: { status: 409, data: { errors: ["« EXCELLENT » figure sur 2 bulletin(s) déjà émis"] } } });
    renderPage();
    const row = await screen.findByTestId("appreciation-row-1");
    fireEvent.change(within(row).getByLabelText("Libellé (français)"), { target: { value: "AUTRE" } });
    fireEvent.click(screen.getByTestId("appreciations-save"));
    expect((await screen.findByTestId("appreciations-errors")).textContent).toMatch(/déjà émis/);
    expect(toast.success).not.toHaveBeenCalled();
    expect(toast.error).toHaveBeenCalled();
  });

  it("empêche de supprimer une appréciation déjà utilisée", async () => {
    renderPage();
    const used = await screen.findByTestId("appreciation-row-0");
    expect(within(used).getByTitle(/désactivez-la/).disabled).toBe(true);
  });

  it("bloque l'enregistrement d'un barème incohérent", async () => {
    renderPage();
    const row = await screen.findByTestId("appreciation-row-2");
    fireEvent.change(within(row).getByLabelText("Seuil (%)"), { target: { value: "10" } });
    expect(screen.getByTestId("appreciations-errors").textContent).toMatch(/0 %/);
    expect(screen.getByTestId("appreciations-save").disabled).toBe(true);
  });

  it("aperçu d'une note avec le barème affiché", async () => {
    appreciationsAPI.preview.mockResolvedValue({ data: { value: "9.5", max_value: "10", percent: "95.00", label_fr: "EXCELLENT", label_en: "EXCELLENT" } });
    renderPage();
    await screen.findByTestId("appreciations-table");
    fireEvent.change(screen.getByTestId("appreciations-preview-value"), { target: { value: "9.5" } });
    fireEvent.change(screen.getByDisplayValue("20"), { target: { value: "10" } });
    fireEvent.click(screen.getByTestId("appreciations-preview"));
    expect((await screen.findByTestId("appreciations-preview-result")).textContent).toContain("EXCELLENT");
    expect(appreciationsAPI.preview.mock.calls[0][0]).toMatchObject({ value: "9.5", max_value: "10" });
    expect(appreciationsAPI.preview.mock.calls[0][0].rules).toHaveLength(3);
  });
});
