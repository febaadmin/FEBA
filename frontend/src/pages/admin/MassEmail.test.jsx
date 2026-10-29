/**
 * Écran « E-mails groupés » — garde-fous côté interface.
 *
 *  1. Pas de bouton d'envoi sans aperçu calculé par le serveur.
 *  2. Toute modification du brouillon invalide l'aperçu.
 *  3. La confirmation envoie UNE requête, avec le nombre affiché et un
 *     jeton anti double-clic ; un second clic pendant l'envoi ne part pas.
 *  4. Le navigateur n'envoie que des règles (rôles, inclusions), jamais
 *     une liste d'adresses.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("../../api", () => ({
  massEmailAPI: {
    options: vi.fn(), recipients: vi.fn(), preview: vi.fn(), campaigns: vi.fn(),
    create: vi.fn(), campaign: vi.fn(), retryFailed: vi.fn(),
  },
}));
vi.mock("../../context/AcademyContext", () => ({
  useAcademy: () => ({ activeAcademy: { id: 1, timezone: "Africa/Porto-Novo" }, isAllAcademies: false }),
}));
vi.mock("react-hot-toast", () => {
  const toast = Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() });
  return { default: toast, toast };
});

import { massEmailAPI } from "../../api";
import { setLang } from "../../i18n";
import MassEmail from "./MassEmail";

const USERS = [
  { id: 10, full_name: "Ana Parent", email: "ana@test.io", role: "parent", sendable: true, status: "pending" },
  { id: 11, full_name: "Bo Parent", email: "bo@test.io", role: "parent", sendable: true, status: "pending" },
  { id: 12, full_name: "Cy Prof", email: "cy@test.io", role: "teacher", sendable: true, status: "pending" },
];

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(<QueryClientProvider client={qc}><MassEmail /></QueryClientProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
  setLang("fr");
  massEmailAPI.options.mockResolvedValue({ data: {
    academy: { id: 1, name: "FEBA" }, academies: [{ id: 1, name: "FEBA" }],
    roles: [{ role: "parent", label: "Parents", count: 2, active_count: 2 },
            { role: "teacher", label: "Enseignants", count: 1, active_count: 1 }],
    provider_configured: true, max_recipients: 2000,
  } });
  massEmailAPI.recipients.mockResolvedValue({ data: { results: USERS } });
  massEmailAPI.campaigns.mockResolvedValue({ data: { results: [] } });
  massEmailAPI.preview.mockResolvedValue({ data: {
    count: 2, skipped_count: 0, recipients: [], skipped: [], academy: { name: "FEBA" },
  } });
});

async function fillDraft() {
  renderPage();
  const parents = await screen.findByLabelText(/^Parents/);
  fireEvent.click(parents);
  fireEvent.change(screen.getByLabelText("Objet"), { target: { value: "Réunion" } });
  fireEvent.change(screen.getByLabelText("Contenu"), { target: { value: "Lundi 18 h." } });
}

describe("E-mails groupés", () => {
  it("n'offre l'envoi qu'après un aperçu, et l'invalide si le brouillon change", async () => {
    await fillDraft();
    expect(screen.queryByText(/Envoyer à/)).toBeNull();
    fireEvent.click(screen.getByText("Prévisualiser"));
    expect(await screen.findByText("Envoyer à 2 destinataire(s)")).toBeTruthy();
    expect(massEmailAPI.preview).toHaveBeenCalledWith({
      academy_id: 1, roles: ["parent"], all_profiles: false, include_ids: [], exclude_ids: [],
    });
    fireEvent.change(screen.getByLabelText("Objet"), { target: { value: "Réunion modifiée" } });
    expect(screen.queryByText(/Envoyer à/)).toBeNull();
  });

  it("confirme le nombre affiché et n'envoie qu'une fois", async () => {
    let resolve;
    massEmailAPI.create.mockImplementation(() => new Promise((r) => { resolve = r; }));
    await fillDraft();
    fireEvent.click(screen.getByText("Prévisualiser"));
    fireEvent.click(await screen.findByText("Envoyer à 2 destinataire(s)"));
    const confirm = await screen.findByRole("button", { name: /Confirmer l'envoi/ });
    fireEvent.click(confirm);
    fireEvent.click(confirm);
    await waitFor(() => expect(massEmailAPI.create).toHaveBeenCalledTimes(1));
    const body = massEmailAPI.create.mock.calls[0][0];
    expect(body).toMatchObject({ confirm: true, expected_count: 2, roles: ["parent"], subject: "Réunion" });
    expect(body.client_token).toMatch(/^[0-9a-f]{16,64}$/);
    expect(body).not.toHaveProperty("emails");
    resolve({ data: { id: 5, total_recipients: 2 } });
    massEmailAPI.campaign.mockResolvedValue({ data: {
      id: 5, status: "done", status_display: "Terminé", subject: "Réunion",
      counts: { sent: 2, pending: 0, sending: 0, failed: 0, retry: 0 }, skipped_count: 0, recipients: [],
    } });
    expect(await screen.findByText("Rapport d'envoi")).toBeTruthy();
  });

  it("décocher un parent l'exclut des règles envoyées", async () => {
    await fillDraft();
    fireEvent.click(await screen.findByLabelText("Sélectionner Ana Parent"));
    fireEvent.click(screen.getByText("Prévisualiser"));
    await screen.findByText("Envoyer à 2 destinataire(s)");
    expect(massEmailAPI.preview).toHaveBeenLastCalledWith(expect.objectContaining({ exclude_ids: [10] }));
  });
});
