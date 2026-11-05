import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

vi.mock("../../api", () => ({
  conversationsAPI: {
    list: vi.fn(), get: vi.fn(), create: vi.fn(), reply: vi.fn(), markRead: vi.fn(), compteurs: vi.fn(),
    correspondants: vi.fn(), marquer: vi.fn(), important: vi.fn(), deplacer: vi.fn(), supprimerDefinitivement: vi.fn(),
  },
  messageDraftsAPI: { list: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  authAPI: { recipients: vi.fn() },
}));
vi.mock("react-hot-toast", () => {
  const toast = Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() });
  return { default: toast, toast };
});

import { authAPI, conversationsAPI, messageDraftsAPI } from "../../api";
import { setLang } from "../../i18n";
import Messagerie, { dateCourte } from "./Messagerie";

const prof = { id: 2, full_name: "Tina Prof", role: "teacher" };
const parent = { id: 3, full_name: "Paul Parent", role: "parent" };
const resume = (o = {}) => ({ id: 7, subject: "Sortie au musée", correspondants: [prof], participants: [prof], updated_at: "2026-11-05T09:00:00Z",
  latest_message: { body: "Prévoir un pique-nique", sent_at: "2026-11-05T09:00:00Z", is_mine: false }, unread_count: 1,
  important: false, dossier: "reception", nb_messages: 1, a_pieces: true, ...o });
const fil = (o = {}) => ({ ...resume(o), messages: [
  { id: 1, sender: prof, body: "Prévoir un pique-nique", sent_at: "2026-11-05T09:00:00Z", is_mine: false,
    pieces: [{ id: 4, nom: "programme.pdf", taille: 2048, url: "/api/files/jeton/" }] }], ...o });

const monter = (url = "/teacher/messages") => render(
  <MemoryRouter initialEntries={[url]}>
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><Messagerie /></QueryClientProvider>
  </MemoryRouter>);

describe("messagerie interne", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setLang("fr");
    conversationsAPI.list.mockResolvedValue({ data: [resume()] });
    conversationsAPI.get.mockResolvedValue({ data: fil() });
    conversationsAPI.markRead.mockResolvedValue({ data: { marked_read: 1 } });
    conversationsAPI.compteurs.mockResolvedValue({ data: { reception_non_lus: 1, brouillons: 2 } });
    conversationsAPI.correspondants.mockResolvedValue({ data: [prof] });
    messageDraftsAPI.list.mockResolvedValue({ data: [] });
    authAPI.recipients.mockResolvedValue({ data: [prof, parent] });
  });

  it("dates courtes : heure aujourd'hui, jour cette semaine, date ensuite", () => {
    const maintenant = new Date("2026-11-05T15:00:00");
    expect(dateCourte("2026-11-05T09:30:00", maintenant)).toMatch(/09:30/);
    expect(dateCourte("2026-10-20T09:30:00", maintenant)).toMatch(/20/);
  });

  it("liste : non lu, importance, pièce jointe, compteurs ; ouvrir marque comme lu et affiche les pièces jointes", async () => {
    monter();
    const ligne = await screen.findByTestId("conversation-7");
    expect(within(ligne).getByTestId("non-lu")).toBeTruthy();
    expect(within(ligne).getByLabelText("Pièces jointes")).toBeTruthy();
    expect((await screen.findByTestId("badge-reception")).textContent).toBe("1");
    expect(screen.getByTestId("badge-brouillons").textContent).toBe("2");
    fireEvent.click(ligne);
    expect((await screen.findByTestId("fil-objet")).textContent).toBe("Sortie au musée");
    await waitFor(() => expect(conversationsAPI.markRead).toHaveBeenCalledWith(7));
    expect(screen.getByTestId("piece-jointe").getAttribute("href")).toBe("/api/files/jeton/");
  });

  it("ouvre directement la conversation d'une notification (?conversation=)", async () => {
    monter("/teacher/messages?conversation=7");
    expect(await screen.findByTestId("fil-objet")).toBeTruthy();
    expect(conversationsAPI.get).toHaveBeenCalledWith(7);
  });

  it("dossiers et filtres envoyés au serveur", async () => {
    monter();
    await screen.findByTestId("conversation-7");
    fireEvent.click(screen.getByTestId("dossier-archives"));
    await waitFor(() => expect(conversationsAPI.list).toHaveBeenLastCalledWith({ dossier: "archives" }));
    fireEvent.click(screen.getByTestId("filtre-non-lus"));
    await waitFor(() => expect(conversationsAPI.list).toHaveBeenLastCalledWith({ dossier: "archives", non_lus: 1 }));
    fireEvent.change(screen.getByTestId("filtre-correspondant"), { target: { value: "2" } });
    await waitFor(() => expect(conversationsAPI.list).toHaveBeenLastCalledWith({ dossier: "archives", non_lus: 1, correspondant: "2" }));
    fireEvent.change(screen.getByTestId("messagerie-recherche"), { target: { value: "musée" } });
    await waitFor(() => expect(conversationsAPI.list).toHaveBeenLastCalledWith(expect.objectContaining({ q: "musée" })), { timeout: 2000 });
  });

  it("actions : important, archiver, corbeille puis suppression définitive confirmée", async () => {
    conversationsAPI.important.mockResolvedValue({ data: { important: true } });
    conversationsAPI.deplacer.mockResolvedValue({ data: {} });
    monter("/teacher/messages?conversation=7");
    await screen.findByTestId("fil-objet");
    fireEvent.click(screen.getByTestId("fil-important"));
    await waitFor(() => expect(conversationsAPI.important).toHaveBeenCalledWith(7, { important: true }));
    fireEvent.click(screen.getByTestId("fil-archiver"));
    await waitFor(() => expect(conversationsAPI.deplacer).toHaveBeenCalledWith(7, { dossier: "archives" }));
    conversationsAPI.get.mockResolvedValue({ data: fil({ dossier: "corbeille" }) });
    conversationsAPI.supprimerDefinitivement.mockResolvedValue({ data: {} });
    fireEvent.click(await screen.findByTestId("conversation-7"));
    fireEvent.click(await screen.findByTestId("fil-supprimer"));
    expect(screen.queryByTestId("reponse")).toBeNull();              // pas de réponse depuis la corbeille
    const dialogue = await screen.findByRole("dialog");
    const bouton = within(dialogue).getByRole("button", { name: "Supprimer" });
    fireEvent.click(bouton);
    await waitFor(() => expect(conversationsAPI.supprimerDefinitivement).toHaveBeenCalledWith(7));
  });

  it("répondre à tous / à l'expéditeur seul dans un échange de groupe", async () => {
    conversationsAPI.get.mockResolvedValue({ data: fil({ correspondants: [prof, parent] }) });
    conversationsAPI.reply.mockResolvedValue({ data: { conversation: 9 } });
    monter("/admin/messages?conversation=7");
    await screen.findByTestId("fil-objet");
    fireEvent.click(screen.getByTestId("repondre-expediteur"));
    fireEvent.change(screen.getByTestId("reponse-texte"), { target: { value: "Question privée" } });
    fireEvent.click(screen.getByTestId("reponse-envoyer"));
    await waitFor(() => expect(conversationsAPI.reply).toHaveBeenCalled());
    const fd = conversationsAPI.reply.mock.calls[0][1];
    expect([fd.get("body"), fd.get("a_tous")]).toEqual(["Question privée", "false"]);
    await waitFor(() => expect(conversationsAPI.get).toHaveBeenCalledWith(9));     // le tête-à-tête s'ouvre
  });

  it("nouveau message à plusieurs destinataires, avec pièces jointes ; brouillon enregistré", async () => {
    conversationsAPI.create.mockResolvedValue({ data: { id: 11 } });
    messageDraftsAPI.create.mockResolvedValue({ data: { id: 5 } });
    monter();
    fireEvent.click(await screen.findByTestId("nouveau-message"));
    fireEvent.click(await screen.findByTestId("destinataire-2"));
    fireEvent.click(screen.getByTestId("destinataire-3"));
    expect(screen.getAllByTestId("destinataire-pastille")).toHaveLength(2);
    fireEvent.change(screen.getByLabelText("Objet"), { target: { value: "Réunion" } });
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Lundi 18 h" } });
    fireEvent.click(screen.getByTestId("composition-brouillon"));
    await waitFor(() => expect(messageDraftsAPI.create).toHaveBeenCalledWith({ destinataires: [2, 3], objet: "Réunion", corps: "Lundi 18 h" }));
    const f = new File(["%PDF"], "ordre.pdf", { type: "application/pdf" });
    fireEvent.change(screen.getAllByLabelText("Joindre des fichiers")[0], { target: { files: [f] } });
    fireEvent.click(screen.getByTestId("composition-envoyer"));
    await waitFor(() => expect(conversationsAPI.create).toHaveBeenCalled());
    const fd = conversationsAPI.create.mock.calls[0][0];
    expect(fd.getAll("recipient_ids")).toEqual(["2", "3"]);
    expect(fd.getAll("attachments").map((x) => x.name)).toEqual(["ordre.pdf"]);
    expect(fd.get("brouillon_id")).toBe("5");
  });

  it("états vides et erreur d'accès compréhensibles", async () => {
    conversationsAPI.list.mockResolvedValue({ data: [] });
    monter();
    await waitFor(() => expect(screen.getAllByTestId("messagerie-vide")[0].textContent).toMatch(/Aucune conversation dans la boîte de réception/));
    conversationsAPI.get.mockRejectedValue({ response: { status: 404, data: {} } });
    monter("/teacher/messages?conversation=99");
    expect((await screen.findByRole("alert")).textContent).toMatch(/introuvable ou inaccessible/);
  });
});

describe("messagerie : finitions phase 8", () => {
  beforeEach(() => {
    vi.clearAllMocks(); setLang("fr");
    conversationsAPI.list.mockResolvedValue({ data: [] });
    conversationsAPI.compteurs.mockResolvedValue({ data: { reception_non_lus: 0, brouillons: 0 } });
    conversationsAPI.correspondants.mockResolvedValue({ data: [] });
    authAPI.recipients.mockResolvedValue({ data: [{ id: 2, full_name: "Tina Prof", role: "teacher" }] });
  });

  it("état vide avec action, dossier « Non lus », tri", async () => {
    monter();
    fireEvent.click(await screen.findByTestId("vide-action"));
    expect(await screen.findByTestId("composition")).toBeTruthy();
    fireEvent.click(screen.getByTestId("dossier-non_lus"));
    await waitFor(() => expect(conversationsAPI.list).toHaveBeenLastCalledWith({ dossier: "non_lus" }));
    fireEvent.click(screen.getByTestId("tri"));
    await waitFor(() => expect(conversationsAPI.list).toHaveBeenLastCalledWith({ dossier: "non_lus", tri: "date" }));
  });

  it("bouton d'envoi : aide, puis « Envoyé » seulement après la réponse du serveur ; « Réessayer » en cas d'erreur", async () => {
    conversationsAPI.create.mockRejectedValueOnce({ response: { status: 404, data: { recipient_ids: "Destinataire introuvable." } } });
    monter();
    fireEvent.click(await screen.findByTestId("nouveau-message"));
    expect(screen.getByTestId("composition-aide").textContent).toMatch(/au moins un destinataire/);
    fireEvent.click(await screen.findByTestId("destinataire-2"));
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Bonjour" } });
    const bouton = screen.getByTestId("composition-envoyer");
    fireEvent.click(bouton);
    await waitFor(() => expect(bouton.dataset.etat).toBe("erreur"));
    expect(bouton.textContent).toMatch(/Réessayer/);
    conversationsAPI.create.mockResolvedValueOnce({ data: { id: 3 } });
    fireEvent.click(bouton);
    await waitFor(() => expect(bouton.dataset.etat).toBe("envoye"));
    expect(conversationsAPI.create).toHaveBeenCalledTimes(2);
  });
});
