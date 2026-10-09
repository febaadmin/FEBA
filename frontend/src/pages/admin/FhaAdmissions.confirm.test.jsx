/**
 * P1 — « Envoi de mail de confirmation » : une ligne = un envoi.
 *
 * Défaut d'origine : un indicateur d'occupation UNIQUE (`isPending` d'une
 * seule mutation) était passé à toutes les lignes ; cliquer une ligne
 * désactivait toutes les autres et l'appel suivant écrasait le précédent.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent, within, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("../../api", () => ({
  websiteAdminAPI: {
    fhaApplications: vi.fn(), fhaApplication: vi.fn(), fhaChangeStatus: vi.fn(),
    exportFhaApplications: vi.fn(), fhaApplicationSheet: vi.fn(),
    fhaResendConfirmation: vi.fn(), fhaBulkResendConfirmation: vi.fn(),
    fhaPlacementTests: vi.fn(),
  },
}));
vi.mock("../../hooks/useEntityContext", () => ({
  useAcademyKey: () => "FEBA_FHA",
  useEntityContext: () => ({ allEntitiesMode: false }),
}));
vi.mock("react-hot-toast", () => {
  const toast = Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() });
  return { default: toast, toast };
});

import { websiteAdminAPI } from "../../api";
import { setLang } from "../../i18n";
import FhaAdmissions from "./FhaAdmissions";

const ROW = (id, ref, status = "form_received") => ({
  id, reference: ref, status, entity_code: "FEBA_FHA", child_first_name: `Enfant${id}`,
  child_last_name: "T", parent1_first_name: "P", parent1_last_name: String(id),
  parent1_email: `p${id}@example.org`, has_sheet: true, created_at: "2026-10-01T10:00:00Z",
  confirmation_email: { status: "sent", used_real_provider: true },
});
const ROWS = [ROW(1, "FHA-26-0001"), ROW(2, "FHA-26-0002"), ROW(3, "FHA-26-0003", "cancelled")];

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(<QueryClientProvider client={qc}><FhaAdmissions /></QueryClientProvider>);
}

const resendButton = (ref) => screen.getByRole("button", { name: `Renvoyer l'e-mail de confirmation ${ref}` });

beforeEach(() => {
  vi.clearAllMocks();
  setLang("fr");
  websiteAdminAPI.fhaApplications.mockResolvedValue({ data: { results: ROWS } });
});

describe("Confirmation par ligne", () => {
  it("un clic sur la 2e ligne n'envoie que la 2e, et n'occupe qu'elle", async () => {
    let resolve;
    websiteAdminAPI.fhaResendConfirmation.mockImplementation(() => new Promise((r) => { resolve = r; }));
    renderPage();
    await screen.findByText("FHA-26-0002");
    fireEvent.click(resendButton("FHA-26-0002"));
    fireEvent.click(resendButton("FHA-26-0002"));          // double clic
    expect(websiteAdminAPI.fhaResendConfirmation).toHaveBeenCalledTimes(1);
    expect(websiteAdminAPI.fhaResendConfirmation).toHaveBeenCalledWith(2);
    await waitFor(() => expect(resendButton("FHA-26-0002").disabled).toBe(true));
    expect(resendButton("FHA-26-0001").disabled).toBe(false);
    expect(resendButton("FHA-26-0003").disabled).toBe(false);
    await act(async () => {
      resolve({ data: { result: "sent", result_label: "Remis au serveur de messagerie", accepted: true, used_real_provider: true } });
    });
    expect(await screen.findByTestId("row-result-2")).toBeTruthy();
    expect(screen.queryByTestId("row-result-1")).toBeNull();
  });

  it("deux lignes différentes peuvent être envoyées indépendamment", async () => {
    websiteAdminAPI.fhaResendConfirmation.mockReturnValue(new Promise(() => {}));
    renderPage();
    await screen.findByText("FHA-26-0001");
    fireEvent.click(resendButton("FHA-26-0001"));
    fireEvent.click(resendButton("FHA-26-0003"));
    expect(websiteAdminAPI.fhaResendConfirmation.mock.calls).toEqual([[1], [3]]);
  });
});

describe("Envoi groupé", () => {
  it("n'envoie que les lignes sélectionnées et affiche le résultat de chacune", async () => {
    websiteAdminAPI.fhaBulkResendConfirmation.mockResolvedValue({ data: {
      results: [
        { id: 1, result: "sent", result_label: "Remis au serveur de messagerie" },
        { id: 3, result: "failed", result_label: "Échec" },
      ], summary: { sent: 1, failed: 1 },
    } });
    renderPage();
    await screen.findByText("FHA-26-0001");
    fireEvent.click(screen.getByLabelText("Sélectionner le dossier FHA-26-0001"));
    fireEvent.click(screen.getByLabelText("Sélectionner le dossier FHA-26-0003"));
    fireEvent.click(screen.getByRole("button", { name: /Envoyer les confirmations aux lignes sélectionnées \(2\)/ }));
    const dialog = screen.getByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Envoyer (2)" }));
    fireEvent.click(within(dialog).getByRole("button", { name: /Envoi|Envoyer/ }));
    await waitFor(() => expect(websiteAdminAPI.fhaBulkResendConfirmation).toHaveBeenCalledTimes(1));
    expect(websiteAdminAPI.fhaBulkResendConfirmation).toHaveBeenCalledWith([1, 3], true);
    expect(await screen.findByTestId("row-result-3")).toBeTruthy();
    expect(screen.queryByTestId("row-result-2")).toBeNull();

    // Reprise : seules les lignes en échec repartent.
    websiteAdminAPI.fhaBulkResendConfirmation.mockResolvedValue({ data: {
      results: [{ id: 3, result: "sent", result_label: "Remis au serveur de messagerie" }], summary: { sent: 1 },
    } });
    fireEvent.click(screen.getByRole("button", { name: "Relancer les échecs (1)" }));
    await waitFor(() => expect(websiteAdminAPI.fhaBulkResendConfirmation).toHaveBeenLastCalledWith([3], true));
  });

  it("sélectionner tout ne prend que les lignes affichées ; un filtre exclut les lignes masquées", async () => {
    websiteAdminAPI.fhaBulkResendConfirmation.mockResolvedValue({ data: { results: [], summary: {} } });
    renderPage();
    await screen.findByText("FHA-26-0001");
    fireEvent.click(screen.getByRole("button", { name: "Sélectionner les 3 dossiers affichés" }));
    expect(screen.getByText("3 dossier(s) sélectionné(s)")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Filtrer par statut"), { target: { value: "cancelled" } });
    expect(screen.getByText("1 dossier(s) sélectionné(s)")).toBeTruthy();
    expect(screen.getByText(/2 masqué\(s\) par le filtre, non inclus/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /lignes sélectionnées \(1\)/ }));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Envoyer (1)" }));
    await waitFor(() => expect(websiteAdminAPI.fhaBulkResendConfirmation).toHaveBeenCalledWith([3], true));
  });

  it("désélection individuelle et globale", async () => {
    renderPage();
    await screen.findByText("FHA-26-0001");
    const box = screen.getByLabelText("Sélectionner le dossier FHA-26-0002");
    fireEvent.click(box);
    expect(screen.getByText("1 dossier(s) sélectionné(s)")).toBeTruthy();
    fireEvent.click(box);
    expect(screen.getByText("0 dossier(s) sélectionné(s)")).toBeTruthy();
    fireEvent.click(screen.getByLabelText("Sélectionner toutes les lignes de ce tableau"));
    expect(screen.getByText("3 dossier(s) sélectionné(s)")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Tout désélectionner" }));
    expect(screen.getByText("0 dossier(s) sélectionné(s)")).toBeTruthy();
  });
});
