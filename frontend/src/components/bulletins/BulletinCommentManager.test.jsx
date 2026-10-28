/**
 * Gestion du commentaire du directeur : l'interface affiche ce que le
 * serveur a réellement fait (nouveau lien PDF, bilan d'opération), et
 * n'agit jamais sans académie sélectionnée.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

let academy = { activeAcademy: { name: "FEBA" }, isAllAcademies: false };
vi.mock("../../context/AcademyContext", () => ({ useAcademy: () => academy }));
vi.mock("../../api", () => ({
  studentsAPI: { list: () => Promise.resolve({ data: [{ id: 7, first_name: "Naomi", last_name: "Adjovi" }] }) },
  classesAPI: { list: () => Promise.resolve({ data: [{ id: 3, name: "CE1-A" }] }) },
  schoolsAPI: { years: () => Promise.resolve({ data: [{ id: 1, name: "2026-2027", is_current: true }] }) },
  bulletinsAPI: {
    commentPreview: vi.fn(),
    comment: vi.fn(),
    commentTarget: vi.fn(),
    createOperation: vi.fn(),
    operation: vi.fn(),
  },
}));

import { bulletinsAPI } from "../../api";
import BulletinCommentManager from "./BulletinCommentManager";

const bulletin = (over = {}) => ({
  id: 11, general_comment: "", generated_at: "2026-10-25T10:00:00Z",
  pdf_url: "/media/bulletins/bulletin_old.pdf", pdf_outdated: false, ...over,
});

function renderManager(initial) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <BulletinCommentManager open onClose={() => {}} initial={initial} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  academy = { activeAcademy: { name: "FEBA" }, isAllAcademies: false };
});

describe("commentaire d'un élève", () => {
  it("charge le commentaire, l'enregistre et affiche le NOUVEAU lien PDF", async () => {
    bulletinsAPI.commentPreview.mockResolvedValue({ data: {
      student: { id: 7, name: "Naomi Adjovi" }, bulletin: bulletin({ general_comment: "Ancien" }),
    } });
    bulletinsAPI.commentTarget.mockResolvedValue({ data: {
      bulletin: bulletin({ general_comment: "Très bon trimestre", pdf_url: "/media/bulletins/bulletin_new.pdf" }),
      result: { failed: 0, failures: [], items: [{ outcome: "commentaire enregistré, PDF régénéré" }] },
    } });
    renderManager({ scope: "student", studentId: 7, yearId: 1, period: "T1" });

    const box = await screen.findByLabelText(/Commentaire du Directeur/);
    await waitFor(() => expect(box.value).toBe("Ancien"));
    expect(screen.getByTestId("pdf-link").getAttribute("href")).toBe("/media/bulletins/bulletin_old.pdf");

    fireEvent.change(box, { target: { value: "Très bon trimestre" } });
    fireEvent.click(screen.getByRole("button", { name: /Enregistrer et régénérer le PDF/ }));

    await waitFor(() => expect(screen.getByTestId("pdf-link").getAttribute("href"))
      .toBe("/media/bulletins/bulletin_new.pdf"));
    expect(bulletinsAPI.commentTarget).toHaveBeenCalledWith({
      student_id: 7, school_year_id: 1, period: "T1",
      comment: "Très bon trimestre", regenerate: true, expected_comment: "Ancien",
    });
    expect(screen.getByTestId("save-confirmation")).toBeInTheDocument();
  });

  it("supprime le commentaire sans supprimer le bulletin", async () => {
    bulletinsAPI.commentPreview.mockResolvedValue({ data: { bulletin: bulletin({ general_comment: "À retirer" }) } });
    bulletinsAPI.commentTarget.mockResolvedValue({ data: { bulletin: bulletin(), result: { failed: 0, failures: [] } } });
    renderManager({ scope: "student", studentId: 7, yearId: 1, period: "T1" });
    const btn = await screen.findByRole("button", { name: /Supprimer le commentaire/ });
    await waitFor(() => expect(btn).not.toBeDisabled());
    fireEvent.click(btn);
    await waitFor(() => expect(bulletinsAPI.commentTarget).toHaveBeenCalledWith(expect.objectContaining({ comment: "" })));
  });

  it("signale un échec de régénération au lieu d'annoncer une réussite", async () => {
    bulletinsAPI.commentPreview.mockResolvedValue({ data: { bulletin: bulletin() } });
    bulletinsAPI.commentTarget.mockResolvedValue({ data: {
      bulletin: bulletin({ general_comment: "X", pdf_outdated: true }),
      result: { failed: 1, failures: [{ reason: "PDF non régénéré (panne) ; l'ancien PDF est conservé" }] },
    } });
    renderManager({ scope: "student", studentId: 7, yearId: 1, period: "T1" });
    const box = await screen.findByLabelText(/Commentaire du Directeur/);
    await waitFor(() => expect(bulletinsAPI.commentPreview).toHaveBeenCalled());
    fireEvent.change(box, { target: { value: "X" } });
    fireEvent.click(screen.getByRole("button", { name: /Enregistrer et régénérer/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("ancien PDF est conservé");
    expect(screen.getByText(/PDF à régénérer/)).toBeInTheDocument();
  });
});

describe("bulletin pas encore généré", () => {
  it("enregistre le commentaire sans exiger la génération, puis affiche la confirmation du serveur", async () => {
    bulletinsAPI.commentPreview.mockResolvedValue({ data: { bulletin: null, has_grades: false } });
    bulletinsAPI.commentTarget.mockResolvedValue({ data: {
      bulletin: { id: 40, general_comment: "Avant génération", pdf_url: null, generated_at: "2026-10-26T10:00:00Z",
        comment_updated_at: "2026-10-26T10:00:00Z", pdf_outdated: true },
      result: { failed: 0, failures: [], items: [{ outcome: "commentaire enregistré, PDF non généré (aucune note)" }] },
    } });
    renderManager({ scope: "student", studentId: 7, yearId: 1, period: "T2" });
    expect(await screen.findByTestId("bulletin-state")).toHaveTextContent("pas encore généré");
    fireEvent.change(screen.getByLabelText(/Commentaire du Directeur/), { target: { value: "Avant génération" } });
    fireEvent.click(screen.getByRole("button", { name: /Enregistrer le commentaire/ }));
    expect(await screen.findByTestId("save-confirmation")).toHaveTextContent("PDF non généré");
    expect(bulletinsAPI.commentTarget).toHaveBeenCalledWith(expect.objectContaining({
      student_id: 7, period: "T2", comment: "Avant génération", expected_comment: "" }));
    await waitFor(() => expect(screen.getByLabelText(/Commentaire du Directeur/).value).toBe("Avant génération"));
  });

  it("une erreur serveur n'est jamais présentée comme un succès", async () => {
    bulletinsAPI.commentPreview.mockResolvedValue({ data: { bulletin: null, has_grades: true } });
    bulletinsAPI.commentTarget.mockRejectedValue({ response: { status: 500, data: { error: "Base indisponible" } } });
    renderManager({ scope: "student", studentId: 7, yearId: 1, period: "T2" });
    await screen.findByTestId("bulletin-state");
    fireEvent.change(screen.getByLabelText(/Commentaire du Directeur/), { target: { value: "X" } });
    fireEvent.click(screen.getByRole("button", { name: /Enregistrer/ }));
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.queryByTestId("save-confirmation")).toBeNull();
  });
});

describe("opération groupée", () => {
  it("montre la portée, demande confirmation, puis le bilan partiel tel quel", async () => {
    bulletinsAPI.commentPreview.mockResolvedValue({ data: {
      academy: { id: 1, name: "FEBA" }, school_year: { id: 1, name: "2026-2027" },
      class: { id: 3, name: "CE1-A" }, students: 25, existing_bulletins: 24, with_comment: 3,
      missing_with_grades: 1, missing_without_grades: 0, bulletin: null,
    } });
    bulletinsAPI.createOperation.mockResolvedValue({ data: { id: 99, status: "queued" } });
    bulletinsAPI.operation.mockResolvedValue({ data: { id: 99, status: "partial", result: {
      targeted: 25, processed: 24, comments_set: 23, comments_cleared: 0, pdf_generated: 23,
      bulletins_created: 0, failed: 1, skipped: 1,
      failures: [{ student_id: 5, student: "Kofi Mensah", reason: "police introuvable" }],
      skipped_items: [{ student_id: 6, student: "Ama B", reason: "bulletin pas encore généré" }],
    } } });
    renderManager({ scope: "class", classId: 3, yearId: 1, period: "T1" });

    expect(await screen.findByTestId("scope-preview")).toHaveTextContent("Classe CE1-A");
    expect(screen.getByTestId("scope-preview")).toHaveTextContent("25 élève(s)");
    fireEvent.change(screen.getByLabelText(/Commentaire du Directeur/), { target: { value: "Bravo" } });
    fireEvent.click(screen.getByRole("button", { name: /Vérifier et appliquer/ }));
    expect(screen.getByTestId("confirm-box")).toHaveTextContent("24 bulletin(s) existant(s)");
    expect(bulletinsAPI.createOperation).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: /^Confirmer$/ }));

    const report = await screen.findByTestId("operation-report");
    await waitFor(() => expect(report).toHaveTextContent("Opération terminée avec des échecs"));
    expect(report).toHaveTextContent("Kofi Mensah — police introuvable");
    expect(bulletinsAPI.createOperation).toHaveBeenCalledWith(expect.objectContaining({
      scope: "class", class_id: 3, action: "set_comment", comment: "Bravo", school_year_id: 1,
    }));
  });

  it("sans académie sélectionnée : rien n'est demandé au serveur", async () => {
    academy = { activeAcademy: null, isAllAcademies: true };
    bulletinsAPI.commentPreview.mockResolvedValue({ data: {} });
    renderManager({ scope: "academy", yearId: 1, period: "T1" });
    expect(await screen.findByText(/Sélectionnez d'abord une académie/)).toBeInTheDocument();
    expect(bulletinsAPI.commentPreview).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: /Vérifier et appliquer/ })).toBeDisabled();
  });
});
