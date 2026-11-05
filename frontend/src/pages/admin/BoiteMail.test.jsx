import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("../../api", () => ({
  boiteMailAPI: { etat: vi.fn(), messages: vi.fn(), message: vi.fn(), action: vi.fn(), actions: vi.fn(), piece: vi.fn(),
    envoyer: vi.fn(), synchroniser: vi.fn(), acces: vi.fn(), majAcces: vi.fn(), journal: vi.fn() },
  outboxAPI: {},
}));
vi.mock("./Outbox", () => ({ default: () => <div data-testid="journal-envois" /> }));
vi.mock("react-hot-toast", () => {
  const toast = Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() });
  return { default: toast, toast };
});
import { boiteMailAPI } from "../../api";
import { setLang } from "../../i18n";
import BoiteMail from "./BoiteMail";

const etat = { acces: true, configuree: true, adresse: "contact@globalfeba.com", fournisseur: "Hostinger Email (IMAP)",
  droits: { lire: true, envoyer: true, supprimer: true, gerer: true }, non_lus: { reception: 2 }, synchro: [] };
const ligne = { id: 5, dossier: "reception", sujet: "Inscription", expediteur: { nom: "Parent Dupont", email: "parent@exemple.org" },
  a: [{ email: "contact@globalfeba.com" }], date: "2026-11-05T10:00:00Z", extrait: "Bonjour", lu: false, important: false, nb_pieces: 1 };
const detail = { ...ligne, cc: [], texte: "Bonjour", html: "<p>Bonjour <b>FEBA</b></p>", a_images_distantes: true,
  pieces: [{ id: 9, nom: "fiche.pdf", taille: 2048, non_copiee: false }], repondre_a: "", message_id: "<a@b>" };
const monter = () => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><BoiteMail /></QueryClientProvider>);

describe("boîte mail contact@globalfeba.com", () => {
  beforeEach(() => {
    vi.clearAllMocks(); setLang("fr");
    boiteMailAPI.etat.mockResolvedValue({ data: etat });
    boiteMailAPI.messages.mockResolvedValue({ data: { count: 1, page: 1, pages: 1, results: [ligne] } });
    boiteMailAPI.message.mockResolvedValue({ data: detail });
    boiteMailAPI.action.mockResolvedValue({ data: {} });
  });

  it("liste, ouverture : contenu nettoyé, images masquées, pièce jointe, marqué lu chez le fournisseur", async () => {
    monter();
    fireEvent.click(await screen.findByTestId("bm-message-5"));
    expect((await screen.findByTestId("bm-html")).innerHTML).toBe("<p>Bonjour <b>FEBA</b></p>");
    expect(screen.getByTestId("bm-images")).toBeTruthy();
    expect(screen.getByTestId("bm-piece").textContent).toMatch(/fiche\.pdf/);
    await waitFor(() => expect(boiteMailAPI.action).toHaveBeenCalledWith(5, "lu"));
    fireEvent.click(screen.getByTestId("bm-images"));
    await waitFor(() => expect(boiteMailAPI.message).toHaveBeenLastCalledWith(5, true));
  });

  it("dossiers, recherche et filtres envoyés au serveur", async () => {
    monter();
    await screen.findByTestId("bm-message-5");
    fireEvent.click(screen.getByTestId("bm-dossier-envoyes"));
    await waitFor(() => expect(boiteMailAPI.messages).toHaveBeenLastCalledWith({ dossier: "envoyes", page: 1 }));
    fireEvent.click(screen.getByTestId("bm-non-lus"));
    await waitFor(() => expect(boiteMailAPI.messages).toHaveBeenLastCalledWith({ dossier: "envoyes", non_lus: 1, page: 1 }));
    fireEvent.change(screen.getByTestId("bm-recherche"), { target: { value: "dupont" } });
    await waitFor(() => expect(boiteMailAPI.messages).toHaveBeenLastCalledWith(expect.objectContaining({ q: "dupont" })), { timeout: 2000 });
  });

  it("répondre : destinataire et objet préremplis, envoi multipart", async () => {
    boiteMailAPI.envoyer.mockResolvedValue({ status: 201, data: { id: 7 } });
    monter();
    fireEvent.click(await screen.findByTestId("bm-message-5"));
    fireEvent.click(await screen.findByTestId("bm-repondre"));
    expect(screen.getByTestId("bm-a").value).toBe("parent@exemple.org");
    expect(screen.getByLabelText("Objet").value).toBe("Re: Inscription");
    fireEvent.change(screen.getByTestId("bm-cci"), { target: { value: "archive@exemple.org" } });
    fireEvent.click(screen.getByTestId("bm-envoyer"));
    await waitFor(() => expect(boiteMailAPI.envoyer).toHaveBeenCalled());
    const fd = boiteMailAPI.envoyer.mock.calls[0][0];
    expect([fd.get("mode"), fd.get("origine"), fd.getAll("a"), fd.getAll("cci")]).toEqual(["repondre", "5", ["parent@exemple.org"], ["archive@exemple.org"]]);
  });

  it("sans droit : message explicite, journal technique toujours accessible", async () => {
    boiteMailAPI.etat.mockResolvedValue({ data: { acces: false, droits: {} } });
    monter();
    expect((await screen.findByTestId("bm-sans-acces")).textContent).toMatch(/super administrateur peut vous l'accorder/);
    fireEvent.click(screen.getByTestId("bm-onglet-journal"));
    expect(screen.getByTestId("journal-envois")).toBeTruthy();
  });
});
