/**
 * Phase 9 — « Message reçu » du site vitrine.
 *
 * Défauts reproduits : « Répondre par email » ouvrait l'application de messagerie
 * de l'ordinateur (lien mailto:), et le bouton WhatsApp disparaissait selon les
 * messages. Attendu : les deux boutons TOUJOURS présents ; WhatsApp sur le seul
 * numéro WhatsApp du contact (jamais le téléphone) ; e-mail dans l'éditeur interne,
 * envoyé par FEBA depuis contact@globalfeba.com, puis visible dans l'historique.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

vi.mock("../../api", () => ({
  websiteAdminAPI: {
    preregistrations: vi.fn(), contactMessages: vi.fn(), updateContact: vi.fn(), deleteContact: vi.fn(),
    news: vi.fn(), settings: vi.fn(), reponsesContact: vi.fn(), repondreContact: vi.fn(),
  },
  massEmailAPI: { signature: vi.fn() },
}));
const contexte = vi.hoisted(() => ({ features: { public_preregistrations: true } }));
vi.mock("../../hooks/useEntityContext", () => ({
  useAcademyKey: () => "FEBA",
  useEntityContext: () => ({ allEntitiesMode: false, entities: [], hasFeature: (f) => Boolean(contexte.features[f]) }),
}));

import { websiteAdminAPI, massEmailAPI } from "../../api";
import AdminWebsite, { ActionsContact } from "./Website";

const MSG = {
  id: 17, name: "Awa Dossou", email: "awa@example.org", phone: "+229 01 97 00 00 01", whatsapp: "",
  subject: "Inscription CE1", message: "Bonjour, je souhaite des informations.", is_read: false,
  created_at: "2026-11-05T09:30:00Z", entity_code: "FEBA", consent: true,
};

const monter = (ui) => render(
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter>{ui}</MemoryRouter>
  </QueryClientProvider>,
);

beforeEach(() => {
  vi.clearAllMocks();
  websiteAdminAPI.preregistrations.mockResolvedValue({ data: [] });
  websiteAdminAPI.contactMessages.mockResolvedValue({ data: [MSG] });
  websiteAdminAPI.updateContact.mockResolvedValue({ data: {} });
  websiteAdminAPI.news.mockResolvedValue({ data: [] });
  websiteAdminAPI.settings.mockResolvedValue({ data: {} });
  websiteAdminAPI.reponsesContact.mockResolvedValue({ data: [] });
  massEmailAPI.signature.mockResolvedValue({ data: { texte: "" } });
});

describe("ActionsContact — deux boutons toujours présents", () => {
  it("numéro WhatsApp valide : lien wa.me, e-mail actif, jamais de mailto", () => {
    const { container } = monter(<ActionsContact nom="Awa" sujet="Info" email="awa@example.org" whatsapp="+229 01 97 00 00 01" onEmail={() => {}} />);
    const wa = screen.getByTestId("repondre-whatsapp");
    expect(wa.getAttribute("href")).toMatch(/^https:\/\/wa\.me\/2290197000001\?text=/);
    expect(screen.getByTestId("repondre-email")).not.toBeDisabled();
    expect(container.querySelector('a[href^="mailto:"]')).toBeNull();
  });

  it("sans numéro WhatsApp : bouton visible, désactivé, raison affichée (le téléphone n'est pas utilisé)", () => {
    monter(<ActionsContact nom="Awa" sujet="Info" email="awa@example.org" whatsapp="" onEmail={() => {}} />);
    const wa = screen.getByTestId("repondre-whatsapp");
    expect(wa.tagName).toBe("BUTTON");
    expect(wa).toBeDisabled();
    expect(screen.getAllByText("Aucun numéro WhatsApp renseigné par le contact.").length).toBeGreaterThan(0);
  });

  it("numéro sans indicatif : refusé, jamais deviné", () => {
    monter(<ActionsContact nom="Awa" sujet="Info" email="awa@example.org" whatsapp="97 00 00 01" onEmail={() => {}} />);
    expect(screen.getByTestId("repondre-whatsapp")).toBeDisabled();
  });

  it("e-mail invalide : bouton e-mail visible et désactivé, avec explication", () => {
    monter(<ActionsContact nom="Awa" sujet="Info" email="pas-un-email" whatsapp="+22901970000001" onEmail={() => {}} />);
    expect(screen.getByTestId("repondre-email")).toBeDisabled();
    expect(screen.getByText("Adresse e-mail absente ou invalide.")).toBeInTheDocument();
  });

  it("les deux boutons partagent la même largeur minimale", () => {
    monter(<ActionsContact nom="A" sujet="B" email="" whatsapp="" onEmail={() => {}} />);
    for (const id of ["repondre-whatsapp", "repondre-email"]) expect(screen.getByTestId(id).className).toContain("min-w-[13rem]");
  });
});

describe("Réponse par e-mail depuis FEBA", () => {
  async function ouvrirReponse() {
    monter(<AdminWebsite />);
    fireEvent.click(await screen.findByRole("button", { name: /Messages reçus/i }));
    fireEvent.click(await screen.findByText("Awa Dossou"));
    fireEvent.click(await screen.findByTestId("repondre-email"));
    return screen.findByTestId("reponse-email");
  }

  it("ouvre l'éditeur interne prérempli, message d'origine visible", async () => {
    const form = await ouvrirReponse();
    expect(within(form).getByTestId("rep-a")).toHaveValue("awa@example.org");
    expect(within(form).getByLabelText("Objet")).toHaveValue("Re: Inscription CE1");
    expect(within(form).getByText("Bonjour, je souhaite des informations.")).toBeInTheDocument();
    expect(document.querySelector('a[href^="mailto:"]')).toBeNull();
  });

  it("envoie par l'API de FEBA (multipart) et n'annonce l'envoi qu'après acceptation", async () => {
    websiteAdminAPI.repondreContact.mockResolvedValue({ status: 201, data: { id: 9, statut: "sent" } });
    const form = await ouvrirReponse();
    expect(within(form).getByTestId("rep-envoyer")).toBeDisabled();
    fireEvent.change(within(form).getByTestId("editeur-texte"), { target: { value: "Bonjour Awa, voici les informations." } });
    fireEvent.click(within(form).getByTestId("rep-envoyer"));
    await waitFor(() => expect(websiteAdminAPI.repondreContact).toHaveBeenCalledTimes(1));
    const [id, fd] = websiteAdminAPI.repondreContact.mock.calls[0];
    expect(id).toBe(17);
    expect(fd.getAll("a")).toEqual(["awa@example.org"]);
    expect(fd.get("sujet")).toBe("Re: Inscription CE1");
    expect(fd.get("texte")).toBe("Bonjour Awa, voici les informations.");
    await waitFor(() => expect(screen.queryByTestId("reponse-email")).toBeNull());
    await waitFor(() => expect(websiteAdminAPI.reponsesContact.mock.calls.length).toBeGreaterThan(1));
  });

  it("refus du serveur : la fenêtre reste ouverte, le texte est conservé", async () => {
    websiteAdminAPI.repondreContact.mockRejectedValue({ response: { status: 400, data: { detail: "Adresse refusée." } } });
    const form = await ouvrirReponse();
    fireEvent.change(within(form).getByTestId("editeur-texte"), { target: { value: "Texte à garder" } });
    fireEvent.click(within(form).getByTestId("rep-envoyer"));
    await waitFor(() => expect(websiteAdminAPI.repondreContact).toHaveBeenCalled());
    expect(screen.getByTestId("reponse-email")).toBeInTheDocument();
    expect(within(form).getByTestId("editeur-texte")).toHaveValue("Texte à garder");
  });

  it("historique des réponses affiché dans le détail", async () => {
    websiteAdminAPI.reponsesContact.mockResolvedValue({ data: [
      { id: 3, date: "2026-11-05T10:00:00Z", a: ["awa@example.org"], cc: [], sujet: "Re: Inscription CE1", statut: "sent", statut_libelle: "", erreur: "", par: "Admin FEBA", nb_pieces: 0 },
      { id: 4, date: "2026-11-05T11:00:00Z", a: ["awa@example.org"], cc: [], sujet: "Re: relance", statut: "retry", statut_libelle: "Échec temporaire - nouvel essai programmé", erreur: "Connexion refusée", par: "", nb_pieces: 0 },
    ] });
    monter(<AdminWebsite />);
    fireEvent.click(await screen.findByRole("button", { name: /Messages reçus/i }));
    fireEvent.click(await screen.findByText("Awa Dossou"));
    const hist = await screen.findByTestId("reponses-envoyees");
    expect(within(hist).getByText("Accepté par le serveur d'envoi")).toBeInTheDocument();
    expect(within(hist).getByText("Connexion refusée")).toBeInTheDocument();
  });
});
