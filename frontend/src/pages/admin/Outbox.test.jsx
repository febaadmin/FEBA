/**
 * Boîte d'envoi : liste, détail, HTML isolé, pièces jointes, relance unique,
 * et libellé honnête d'un message capturé par Mailpit.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("../../api", () => ({
  outboxAPI: { list: vi.fn(), detail: vi.fn(), retry: vi.fn(), attachment: vi.fn(), config: vi.fn(), testSend: vi.fn() },
  massEmailAPI: {},
}));
vi.mock("../../hooks/useEntityContext", () => ({ useAcademyKey: () => "FEBA" }));
vi.mock("react-hot-toast", () => {
  const toast = Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() });
  return { default: toast, toast };
});

import { outboxAPI } from "../../api";
import { setLang } from "../../i18n";
import Outbox from "./Outbox";
import { AttachmentPicker } from "./MassEmail";

const ROW = {
  id: 7, created_at: "2026-10-10T09:15:00Z", academy: { id: 1, code: "FEBA", name: "FEBA" },
  to_email: "parent@ymail.com", subject: "Sortie scolaire", purpose: "academy_mass_email",
  purpose_label: "E-mail groupé", status: "sent", status_display: "Accepté par le serveur de messagerie",
  delivery_summary: "Capturé par le serveur de test (Mailpit) — non distribué sur Internet",
  used_real_provider: false, attachments_count: 1, transport: "capture",
  transport_display: "Serveur de test (Mailpit) — capturé, non distribué", attempts: 1,
};
const DETAIL = {
  ...ROW, from_email: "noreply@feba.bj", text_body: "Bonjour,\nVoir le programme.",
  html_body: "<p>Bonjour</p><script>alert(1)</script>", attachments: [
    { id: 3, name: "programme.pdf", content_type: "application/pdf", size: 2048, available: true, previewable: true },
  ], attempt_log: [{ at: "2026-10-10T09:15:00Z", outcome: "retry", error: "SMTPServerDisconnected", manual: false }],
  can_retry: true, content_note: null, tracking_id: "abc", message_id: "<x@y>",
};

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(<QueryClientProvider client={qc}><Outbox /></QueryClientProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
  setLang("fr");
  outboxAPI.list.mockResolvedValue({ data: { count: 1, page: 1, page_size: 25, results: [ROW], purposes: [] } });
  outboxAPI.detail.mockResolvedValue({ data: DETAIL });
  outboxAPI.config.mockResolvedValue({ data: {
    transport: "capture", transport_display: "Serveur de test (Mailpit) — capturé, non distribué",
    real_provider: false, explanation: "Les messages sont CAPTURÉS par le serveur de test (Mailpit).",
    capture_ui_url: "http://localhost:8025",
  } });
  globalThis.URL.createObjectURL = vi.fn(() => "blob:fichier");
  globalThis.URL.revokeObjectURL = vi.fn();
});

describe("Boîte d'envoi", () => {
  it("liste les envois et signale qu'un message capturé par Mailpit n'est pas distribué", async () => {
    renderPage();
    expect(await screen.findByText("Sortie scolaire")).toBeTruthy();
    expect(screen.getByText(/non distribué sur Internet/)).toBeTruthy();
    expect(await screen.findByText(/Ouvrir Mailpit/)).toBeTruthy();
  });

  it("ouvre le détail : texte, HTML sans script, pièce jointe, historique", async () => {
    renderPage();
    fireEvent.click(await screen.findByText("Sortie scolaire"));
    const dialog = await screen.findByRole("dialog");
    expect(await within(dialog).findByText(/Voir le programme/)).toBeTruthy();
    const frame = within(dialog).getByTitle("Version HTML");
    expect(frame.getAttribute("sandbox")).toBe("");
    expect(within(dialog).getByText("programme.pdf")).toBeTruthy();
    expect(within(dialog).getByText("SMTPServerDisconnected")).toBeTruthy();
  });

  it("aperçu d'une pièce jointe récupérée avec le jeton (API), jamais par URL publique", async () => {
    outboxAPI.attachment.mockResolvedValue({ data: new Blob(["%PDF"]) });
    renderPage();
    fireEvent.click(await screen.findByText("Sortie scolaire"));
    fireEvent.click(await screen.findByRole("button", { name: "Aperçu programme.pdf" }));
    await waitFor(() => expect(outboxAPI.attachment).toHaveBeenCalledWith(7, 3, true));
    expect(await screen.findByTitle("programme.pdf")).toBeTruthy();
  });

  it("la relance ne part qu'une fois malgré un double clic", async () => {
    outboxAPI.retry.mockReturnValue(new Promise(() => {}));
    renderPage();
    fireEvent.click(await screen.findByText("Sortie scolaire"));
    const button = await screen.findByRole("button", { name: /Relancer cet envoi/ });
    fireEvent.click(button);
    fireEvent.click(button);
    await waitFor(() => expect(outboxAPI.retry).toHaveBeenCalledTimes(1));
  });
});

describe("Sélecteur de pièces jointes", () => {
  const limits = { allowed_extensions: ["pdf", "png", "docx"], max_file_mb: 1, max_total_mb: 2, max_files: 3 };

  function Harness() {
    const [files, setFiles] = React.useState([]);
    return <AttachmentPicker files={files} onChange={setFiles} limits={limits} />;
  }

  it("ajoute plusieurs fichiers, refuse un format interdit, permet le retrait", async () => {
    render(<Harness />);
    const input = screen.getByLabelText("Pièces jointes");
    fireEvent.change(input, { target: { files: [
      new File(["%PDF"], "programme.pdf", { type: "application/pdf" }),
      new File(["x"], "photo.png", { type: "image/png" }),
      new File(["MZ"], "outil.exe"),
    ] } });
    expect(screen.getByText("programme.pdf")).toBeTruthy();
    expect(screen.getByText("photo.png")).toBeTruthy();
    expect(screen.getByRole("alert").textContent).toMatch(/outil\.exe/);
    fireEvent.click(screen.getByRole("button", { name: "Retirer programme.pdf" }));
    expect(screen.queryByText("programme.pdf")).toBeNull();
  });

  it("refuse un fichier trop volumineux", () => {
    render(<Harness />);
    const big = new File([new Uint8Array(2 * 1024 * 1024)], "gros.pdf", { type: "application/pdf" });
    fireEvent.change(screen.getByLabelText("Pièces jointes"), { target: { files: [big] } });
    expect(screen.getByRole("alert").textContent).toMatch(/dépasse 1 Mo/);
  });
});

import React from "react";
