/**
 * Aperçu du bulletin : rendu du commentaire SAISI, enregistrement sans
 * génération, génération uniquement après confirmation explicite.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("../../context/AcademyContext", () => ({ useAcademy: () => ({ isAllAcademies: false }) }));
vi.mock("../../api", () => ({
  studentsAPI: { list: () => Promise.resolve({ data: [{ id: 7, first_name: "Naomi", last_name: "Adjovi" }] }) },
  schoolsAPI: { years: () => Promise.resolve({ data: [{ id: 1, name: "2026-2027", is_current: true }] }) },
  bulletinsAPI: { commentPreview: vi.fn(), preview: vi.fn(), commentTarget: vi.fn(), generate: vi.fn() },
}));

import { bulletinsAPI } from "../../api";
import BulletinPreviewDialog from "./BulletinPreviewDialog";

function open(initial = { studentId: 7, yearId: 1, period: "T1" }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><BulletinPreviewDialog open onClose={() => {}} initial={initial} /></QueryClientProvider>);
}

/** État « serveur » : ce que commentPreview renvoie, mis à jour par les écritures simulées. */
let server;
function serve(bulletin) {
  server = { has_grades: true, bulletin };
  bulletinsAPI.commentPreview.mockImplementation(() => Promise.resolve({ data: server }));
}

beforeEach(() => {
  vi.clearAllMocks();
  globalThis.URL.createObjectURL = vi.fn(() => `blob:pdf-${Math.random()}`);
  globalThis.URL.revokeObjectURL = vi.fn();
  bulletinsAPI.preview.mockResolvedValue({ data: new Blob(["%PDF"], { type: "application/pdf" }) });
});

describe("aperçu avant la première génération", () => {
  beforeEach(() => serve(null));

  it("affiche l'aperçu, rend le commentaire SAISI, et ne génère rien sans confirmation", async () => {
    open();
    expect(await screen.findByTestId("preview-frame")).toBeInTheDocument();
    expect(bulletinsAPI.preview).toHaveBeenCalledWith(expect.objectContaining({ student_id: 7, period: "T1", comment: "" }));
    fireEvent.change(screen.getByLabelText(/Commentaire du Directeur/), { target: { value: "Très bon début" } });
    fireEvent.click(screen.getByRole("button", { name: /Actualiser l'aperçu/ }));
    await waitFor(() => expect(bulletinsAPI.preview).toHaveBeenLastCalledWith(
      expect.objectContaining({ comment: "Très bon début" })));
    expect(bulletinsAPI.generate).not.toHaveBeenCalled();
    expect(bulletinsAPI.commentTarget).not.toHaveBeenCalled();
  });

  it("enregistre le commentaire SANS générer, puis génère après confirmation", async () => {
    bulletinsAPI.commentTarget.mockImplementation(() => {
      server = { ...server, bulletin: { id: 3, general_comment: "Bravo", pdf_url: null, generated_at: "2026-10-26T10:00:00Z" } };
      return Promise.resolve({ data: { bulletin: server.bulletin, result: { failed: 0 } } });
    });
    bulletinsAPI.generate.mockImplementation(() => {
      server = { ...server, bulletin: { id: 3, general_comment: "Bravo", pdf_url: "/media/bulletins/b_new.pdf",
        generated_at: "2026-10-26T10:05:00Z" } };
      return Promise.resolve({ data: server.bulletin });
    });
    open();
    await screen.findByTestId("preview-frame");
    fireEvent.change(screen.getByLabelText(/Commentaire du Directeur/), { target: { value: "Bravo" } });
    fireEvent.click(screen.getByRole("button", { name: /Enregistrer le commentaire/ }));
    expect(await screen.findByTestId("preview-notice")).toHaveTextContent("enregistré par le serveur");
    expect(bulletinsAPI.commentTarget).toHaveBeenCalledWith(expect.objectContaining({ comment: "Bravo", regenerate: false }));
    expect(bulletinsAPI.generate).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: /Générer le bulletin définitif/ }));
    expect(screen.getByTestId("generate-confirm")).toBeInTheDocument();
    expect(bulletinsAPI.generate).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: /Confirmer la génération/ }));
    await waitFor(() => expect(bulletinsAPI.generate).toHaveBeenCalledWith({ student_id: 7, school_year_id: 1, period: "T1" }));
    expect(await screen.findByTestId("official-pdf-link")).toHaveAttribute("href", "/media/bulletins/b_new.pdf");
  });

  it("un échec d'enregistrement n'est jamais présenté comme une réussite et garde la saisie", async () => {
    bulletinsAPI.commentTarget.mockRejectedValue({ response: { status: 500, data: { error: "Base indisponible" } } });
    open();
    await screen.findByTestId("preview-frame");
    fireEvent.change(screen.getByLabelText(/Commentaire du Directeur/), { target: { value: "À garder" } });
    fireEvent.click(screen.getByRole("button", { name: /Enregistrer le commentaire/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Une erreur interne est survenue");
    expect(screen.queryByTestId("preview-notice")).toBeNull();
    expect(screen.getByLabelText(/Commentaire du Directeur/).value).toBe("À garder");
  });
});

describe("bulletin existant", () => {
  it("charge le commentaire enregistré ; un commentaire saisi est enregistré AVANT la régénération", async () => {
    serve({ id: 9, general_comment: "Ancien", pdf_url: "/media/bulletins/old.pdf", generated_at: "2026-10-25T10:00:00Z" });
    const calls = [];
    bulletinsAPI.commentTarget.mockImplementation((d) => {
      calls.push("save");
      server = { ...server, bulletin: { ...server.bulletin, general_comment: d.comment } };
      return Promise.resolve({ data: { bulletin: server.bulletin, result: { failed: 0 } } });
    });
    bulletinsAPI.generate.mockImplementation(() => {
      calls.push("generate");
      server = { ...server, bulletin: { ...server.bulletin, pdf_url: "/media/bulletins/new.pdf",
        generated_at: "2026-10-26T10:00:00Z" } };
      return Promise.resolve({ data: server.bulletin });
    });
    open();
    await waitFor(() => expect(screen.getByLabelText(/Commentaire du Directeur/).value).toBe("Ancien"));
    expect(screen.getByTestId("official-pdf-link")).toHaveAttribute("href", "/media/bulletins/old.pdf");
    fireEvent.change(screen.getByLabelText(/Commentaire du Directeur/), { target: { value: "Nouveau" } });
    fireEvent.click(screen.getByRole("button", { name: /Générer le bulletin définitif/ }));
    fireEvent.click(screen.getByRole("button", { name: /Confirmer la génération/ }));
    await waitFor(() => expect(calls).toEqual(["save", "generate"]));
    expect(bulletinsAPI.commentTarget).toHaveBeenCalledWith(expect.objectContaining({
      comment: "Nouveau", expected_comment: "Ancien", regenerate: false }));
    expect(await screen.findByTestId("official-pdf-link")).toHaveAttribute("href", "/media/bulletins/new.pdf");
  });
});
