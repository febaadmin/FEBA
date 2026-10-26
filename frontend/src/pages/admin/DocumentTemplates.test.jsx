/**
 * Écran « Gabarits des documents » : deux espaces distincts, états exacts
 * (jamais « prêt » au seul téléversement), téléversement multipart,
 * vérification, activation, académie obligatoire.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

let academy = { academyKey: "academy:3", isAllAcademies: false };
vi.mock("../../context/AcademyContext", () => ({ useAcademy: () => academy }));
vi.mock("react-hot-toast", () => ({ default: { success: vi.fn(), error: vi.fn() } }));
vi.mock("../../api", () => ({
  documentTemplatesAPI: {
    list: vi.fn(), upload: vi.fn(), action: vi.fn(), configure: vi.fn(), remove: vi.fn(),
    background: vi.fn(), original: vi.fn(), preview: vi.fn(), get: vi.fn(),
  },
}));

import toast from "react-hot-toast";
import { documentTemplatesAPI } from "../../api";
import DocumentTemplates from "./DocumentTemplates";

const version = (over = {}) => ({
  id: 11, kind: "diploma", kind_display: "Diplôme", version: 1, status: "draft",
  status_display: "Téléversé, non validé", original_filename: "diplome.pdf", file_format: "pdf",
  file_format_display: "PDF (fond vectoriel)", file_size: 120000, page_count: 1, page_index: 0,
  page_width_mm: 297, page_height_mm: 210, orientation: "landscape", fields: [], options: {},
  validation_report: {}, is_editable: true, documents_count: 0, uploaded_by: "Admin",
  created_at: "2026-10-26T10:00:00Z", activated_at: null, ...over,
});
const kindSummary = (kind, over = {}) => ({
  kind, kind_display: kind === "diploma" ? "Diplôme" : "Certificat", state: "absent",
  active: null, pending: null, versions: [], builtin: null, ...over,
});
const payload = (kinds) => ({
  data: {
    academy: { id: 3, code: "AC_X", name: "Académie X" },
    kinds: { diploma: kindSummary("diploma"), certificate: kindSummary("certificate"), ...kinds },
    catalog: [{ name: "student_name", label: "Nom complet de l'élève", kinds: ["diploma", "certificate"] }],
    eligibility_rules: { diploma: ["admin_decision", "annual_average"], certificate: ["enrolled", "admin_decision"] },
  },
});

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><DocumentTemplates /></QueryClientProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
  academy = { academyKey: "academy:3", isAllAcademies: false };
  documentTemplatesAPI.list.mockResolvedValue(payload({}));
  documentTemplatesAPI.background.mockResolvedValue({ data: new Blob(["x"]) });
  globalThis.URL.createObjectURL = vi.fn(() => "blob:x");
  globalThis.URL.revokeObjectURL = vi.fn();
});

describe("Gabarits des documents", () => {
  it("affiche deux espaces distincts, absents par défaut", async () => {
    renderPage();
    expect(await screen.findByText("Gabarit du diplôme")).toBeInTheDocument();
    expect(screen.getByText("Gabarit du certificat")).toBeInTheDocument();
    expect(screen.getByTestId("state-diploma")).toHaveTextContent("Absent");
    expect(screen.getByTestId("state-certificate")).toHaveTextContent("Absent");
  });

  it("un fichier téléversé n'est jamais présenté comme prêt", async () => {
    const draft = version();
    documentTemplatesAPI.list.mockResolvedValue(payload({
      diploma: kindSummary("diploma", { state: "uploaded", pending: draft, versions: [draft] }),
    }));
    renderPage();
    const space = within(await screen.findByTestId("kind-diploma"));
    expect(space.getByTestId("state-diploma")).toHaveTextContent("Téléversé, non validé");
    expect(space.queryByRole("button", { name: /Activer/ })).not.toBeInTheDocument();
    expect(space.getByRole("button", { name: /Vérifier/ })).toBeInTheDocument();
  });

  it("une version validée peut être activée ; l'activation passe par le serveur", async () => {
    const ready = version({ status: "validated", status_display: "Valide, prêt à être activé",
      validation_report: { ok: true, errors: [], warnings: [], checked_at: "2026-10-26T10:05:00Z" } });
    documentTemplatesAPI.list.mockResolvedValue(payload({
      diploma: kindSummary("diploma", { state: "ready", pending: ready, versions: [ready] }),
    }));
    documentTemplatesAPI.action.mockResolvedValue({ data: { ...ready, status: "active" } });
    renderPage();
    const space = within(await screen.findByTestId("kind-diploma"));
    fireEvent.click(space.getByRole("button", { name: /Activer/ }));
    await waitFor(() => expect(documentTemplatesAPI.action).toHaveBeenCalledWith(11, "activate"));
    expect(toast.success).toHaveBeenCalled();
  });

  it("affiche les erreurs de vérification renvoyées par le serveur", async () => {
    const invalid = version({ status: "invalid", status_display: "Invalide ou incompatible",
      validation_report: { ok: false, errors: ["Le nom de l'élève n'est pas placé sur le gabarit."] } });
    documentTemplatesAPI.list.mockResolvedValue(payload({
      diploma: kindSummary("diploma", { state: "invalid", pending: invalid, versions: [invalid] }),
    }));
    renderPage();
    expect(await screen.findByText("Le nom de l'élève n'est pas placé sur le gabarit.")).toBeInTheDocument();
    expect(screen.getByTestId("state-diploma")).toHaveTextContent("Invalide ou incompatible");
  });

  it("téléverse le fichier en multipart avec son type de document", async () => {
    documentTemplatesAPI.upload.mockResolvedValue({ data: version({ id: 12 }) });
    renderPage();
    const space = within(await screen.findByTestId("kind-certificate"));
    fireEvent.click(space.getByRole("button", { name: /Téléverser/ }));
    const file = new File(["%PDF-1.7"], "certificat.pdf", { type: "application/pdf" });
    fireEvent.change(await screen.findByTestId("template-file"), { target: { files: [file] } });
    const dialog = screen.getByText("Téléverser le gabarit du certificat").closest("div.relative");
    fireEvent.click(within(dialog).getByRole("button", { name: "Téléverser" }));
    await waitFor(() => expect(documentTemplatesAPI.upload).toHaveBeenCalled());
    const form = documentTemplatesAPI.upload.mock.calls[0][0];
    expect(form.get("kind")).toBe("certificate");
    expect(form.get("file").name).toBe("certificat.pdf");
    expect(form.get("page_format")).toBeNull(); // un PDF garde sa taille de page
  });

  it("dit que le gabarit intégré sert tant qu'aucun téléversé n'est actif", async () => {
    documentTemplatesAPI.list.mockResolvedValue(payload({
      diploma: kindSummary("diploma", { builtin: { id: "diploma_feba", label: "Diplôme FEBA",
        can_issue: true, in_use: true, blockers: [] } }),
    }));
    renderPage();
    expect(await screen.findByText(/le gabarit intégré « Diplôme FEBA »/)).toBeInTheDocument();
  });

  it("exige une académie en mode « Toutes les académies »", async () => {
    academy = { academyKey: "academy:all", isAllAcademies: true };
    renderPage();
    expect(await screen.findByText(/Sélectionnez une académie/)).toBeInTheDocument();
    expect(documentTemplatesAPI.list).not.toHaveBeenCalled();
  });

  it("une version ayant servi n'offre pas la suppression", async () => {
    const active = version({ status: "active", status_display: "Actif — utilisé pour les documents",
      is_editable: false, documents_count: 3 });
    documentTemplatesAPI.list.mockResolvedValue(payload({
      diploma: kindSummary("diploma", { state: "active", active, versions: [active] }),
    }));
    renderPage();
    const card = within(await screen.findByTestId("version-11"));
    expect(card.queryByRole("button", { name: /Supprimer/ })).not.toBeInTheDocument();
    expect(card.getByRole("button", { name: /Désactiver/ })).toBeInTheDocument();
    expect(card.getByRole("button", { name: /Voir la configuration/ })).toBeInTheDocument();
  });
});
