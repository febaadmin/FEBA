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
    create: vi.fn(), campaign: vi.fn(), retryFailed: vi.fn(), signature: vi.fn(), majSignature: vi.fn(),
    brouillons: vi.fn(), creerBrouillon: vi.fn(), majBrouillon: vi.fn(), supprimerBrouillon: vi.fn(),
    ajouterPieces: vi.fn(), retirerPiece: vi.fn(),
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
  massEmailAPI.signature.mockResolvedValue({ data: { texte: "La direction" } });
  massEmailAPI.brouillons.mockResolvedValue({ data: { results: [] } });
  massEmailAPI.campaigns.mockResolvedValue({ data: { results: [] } });
  massEmailAPI.preview.mockResolvedValue({ data: {
    count: 2, skipped_count: 0, recipients: [], skipped: [], academy: { name: "FEBA" },
  } });
});

async function fillDraft() {
  renderPage();
  fireEvent.click(await screen.findByTestId("voir-groupes"));
  fireEvent.click(screen.getByTestId("format-texte"));
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
      adresses: { a: [], cc: [], cci: [] }, mode: "individuel", body_format: "texte", body: "Lundi 18 h.", body_html: "",
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

  it("À / Cc / Cci : adresses saisies et membres suggérés, message commun, aperçu HTML nettoyé par le serveur", async () => {
    massEmailAPI.preview.mockResolvedValue({ data: { count: 3, skipped_count: 0, recipients: [], skipped: [],
      academy: { name: "FEBA" }, par_champ: { a: 1, cc: 1, cci: 1 }, html_nettoye: "<p>Bonjour <strong>tous</strong></p>", texte: "Bonjour tous" } });
    renderPage();
    const a = await screen.findByTestId("champ-a-saisie");
    fireEvent.change(a, { target: { value: "Externe@Exemple.org; faux" } });
    fireEvent.keyDown(a, { key: "Enter" });
    expect(screen.getByRole("alert").textContent).toMatch(/Adresse\(s\) invalide\(s\) : faux/);
    fireEvent.click(screen.getByTestId("voir-copies"));
    const cc = screen.getByTestId("champ-cc-saisie");
    fireEvent.change(cc, { target: { value: "cy" } });
    fireEvent.click(await screen.findByTestId("champ-cc-suggestion-12"));
    const cci = screen.getByTestId("champ-cci-saisie");
    fireEvent.change(cci, { target: { value: "cache@exemple.org" } });
    fireEvent.keyDown(cci, { key: "," });
    fireEvent.click(screen.getByTestId("mode-commun"));
    fireEvent.change(screen.getByLabelText("Objet"), { target: { value: "Conseil" } });
    const editeur = screen.getByTestId("editeur-html");
    editeur.innerHTML = "<p>Bonjour <strong>tous</strong></p><script>x()</script>";
    fireEvent.input(editeur);
    fireEvent.click(screen.getByTestId("previsualiser"));
    await screen.findByTestId("apercu-email");
    expect(massEmailAPI.preview).toHaveBeenLastCalledWith(expect.objectContaining({
      adresses: { a: ["externe@exemple.org"], cc: [12], cci: ["cache@exemple.org"] }, mode: "commun", body_format: "html",
    }));
    expect(screen.getByTestId("apercu-champs").textContent).toMatch(/À : 1 · Cc : 1 · Cci : 1/);
    // L'aperçu affiche le HTML du SERVEUR (nettoyé), pas celui de l'éditeur.
    expect(screen.getByTestId("apercu-html").innerHTML).toBe("<p>Bonjour <strong>tous</strong></p>");
  });

  it("brouillon : enregistrement, pièces jointes envoyées au brouillon, signature insérée", async () => {
    massEmailAPI.creerBrouillon.mockResolvedValue({ data: { id: 9, pieces: [] } });
    massEmailAPI.ajouterPieces.mockResolvedValue({ data: { id: 9, pieces: [{ id: 1, nom: "note.pdf", taille: 2048, type: "application/pdf" }] } });
    renderPage();
    await screen.findByTestId("champ-a-saisie");
    fireEvent.click(screen.getByTestId("format-texte"));
    fireEvent.change(screen.getByLabelText("Objet"), { target: { value: "Sortie" } });
    fireEvent.change(screen.getByLabelText("Contenu"), { target: { value: "Bonjour" } });
    await waitFor(() => expect(massEmailAPI.signature).toHaveBeenCalled());
    await waitFor(() => { fireEvent.click(screen.getByTestId("inserer-signature")); expect(screen.getByLabelText("Contenu").value).toMatch(/-- \nLa direction$/); });
    const fichier = new File(["%PDF-1.4"], "note.pdf", { type: "application/pdf" });
    fireEvent.change(screen.getByLabelText("Pièces jointes"), { target: { files: [fichier] } });
    fireEvent.click(screen.getByTestId("enregistrer-brouillon"));
    await waitFor(() => expect(massEmailAPI.ajouterPieces).toHaveBeenCalledWith(9, 1, [fichier]));
    expect(massEmailAPI.creerBrouillon).toHaveBeenCalledWith(1, expect.objectContaining({ objet: "Sortie", format: "texte" }));
    expect(await screen.findByLabelText("Retirer note.pdf")).toBeTruthy();
    expect(screen.getByText("Brouillon")).toBeTruthy();
  });

  it("envoyés : recherche différée et filtre par statut envoyés au serveur", async () => {
    massEmailAPI.campaigns.mockResolvedValue({ data: { results: [{ id: 3, subject: "Cantine", status: "done", status_display: "Envoyé au fournisseur",
      created_at: "2026-11-05T10:00:00Z", counts: { sent: 2, failed: 0, retry: 0, rejected: 0 }, skipped_count: 0, attachments: [] }] } });
    renderPage();
    fireEvent.click(await screen.findByTestId("onglet-envoyes"));
    expect(await screen.findByTestId("envoi-3")).toBeTruthy();
    fireEvent.change(screen.getByTestId("envois-statut"), { target: { value: "failed" } });
    await waitFor(() => expect(massEmailAPI.campaigns).toHaveBeenLastCalledWith(1, { statut: "failed" }));
    fireEvent.change(screen.getByTestId("envois-recherche"), { target: { value: "cantine" } });
    await waitFor(() => expect(massEmailAPI.campaigns).toHaveBeenLastCalledWith(1, { q: "cantine", statut: "failed" }), { timeout: 2000 });
  });
});
