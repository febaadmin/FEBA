/**
 * La liste des salles : ouverture en onglet, ciblage, listes déroulantes.
 *
 * CE QUE CES TESTS EMPÊCHENT DE REVENIR
 * -------------------------------------
 *  1. La conférence s'ouvrait dans une MODALE, sur une page qui
 *     rafraîchissait sa liste toutes les 30 secondes et emportait la
 *     conférence à chaque passage. Il ne doit plus rester de modale de
 *     conférence dans cette page.
 *  2. Le menu « Classe » d'une nouvelle salle ne proposait que « Toute
 *     l'école » alors que l'académie avait bien trois classes : le filtre
 *     par défaut du backend les écartait toutes (voir
 *     apps/schools/academic_year.py). Ce test tient le bout frontend.
 *  3. `window.open` appelé après un `await` est bloqué silencieusement
 *     par le navigateur. Il doit partir DANS le gestionnaire de clic.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, act, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

vi.mock("../../api", () => ({
  virtualAPI: {
    list: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn(),
    join: vi.fn(), end: vi.fn(), leave: vi.fn(),
  },
  classesAPI: { list: vi.fn() },
  subjectsAPI: { list: vi.fn() },
}));
vi.mock("../../components/JitsiInfrastructureBanner", () => ({
  default: () => <div data-testid="banniere" />,
}));
// Le composant <Toaster/> vit dans App.jsx : sans lui, aucun toast n'est
// rendu dans l'arbre de test. On observe donc l'appel lui-même.
vi.mock("react-hot-toast", () => {
  const toast = Object.assign(vi.fn(), {
    success: vi.fn(), error: vi.fn(), loading: vi.fn(), dismiss: vi.fn(),
  });
  return { default: toast, toast };
});

import toast from "react-hot-toast";
import { virtualAPI, classesAPI, subjectsAPI } from "../../api";
import { useAuthStore } from "../../store/authStore";
import { setLang } from "../../i18n";
import VirtualRooms from "./VirtualRooms";

const SALLE = {
  id: 7, name: "Cours de français", description: "",
  class_obj: 3, class_name: "French Ambassadors", subject: null,
  status: "live", scheduled_at: null, duration_minutes: 60,
  participants_count: 0, target_roles: [],
};

const CLASSES = [
  { id: 1, name: "Junior Roots" },
  { id: 2, name: "French Explorers" },
  { id: 3, name: "French Ambassadors" },
];

function afficher() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <VirtualRooms />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

let ouvertures = [];

beforeEach(() => {
  vi.clearAllMocks();
  setLang("fr");
  ouvertures = [];
  virtualAPI.list.mockResolvedValue({ data: { results: [SALLE] } });
  classesAPI.list.mockResolvedValue({ data: { results: CLASSES } });
  subjectsAPI.list.mockResolvedValue({ data: { results: [] } });
  useAuthStore.setState({
    user: { id: 1, username: "prof", role: "teacher", first_name: "A", last_name: "K" },
  });
  vi.stubGlobal("open", vi.fn((...args) => {
    ouvertures.push(args);
    return { focus() {} }; // un onglet non bloqué
  }));
});

afterEach(() => {
  vi.unstubAllGlobals();
  useAuthStore.setState({ user: null });
});

describe("Rejoindre — ouverture dans un nouvel onglet", () => {
  it("ouvre la route plein écran de la salle, pas une modale", async () => {
    afficher();
    const bouton = await screen.findByRole("button", { name: /Rejoindre/i });
    await act(async () => { bouton.click(); });

    expect(ouvertures).toHaveLength(1);
    const [url, cible, options] = ouvertures[0];
    expect(url).toBe("/virtual-room/7/join");
    expect(cible).toBe("_blank");
    expect(options).toContain("noopener");
  });

  it("n'appelle PAS join : c'est l'onglet ouvert qui adhère", async () => {
    // Adhérer ici puis transmettre le jeton à l'onglet mettrait le JWT
    // dans l'URL et enregistrerait deux participations.
    afficher();
    const bouton = await screen.findByRole("button", { name: /Rejoindre/i });
    await act(async () => { bouton.click(); });
    expect(virtualAPI.join).not.toHaveBeenCalled();
  });

  it("ouvre l'onglet SYNCHRONEMENT, sans attendre le réseau", async () => {
    // Un `window.open` postérieur à un `await` est bloqué en silence par
    // le bloqueur de fenêtres surgissantes.
    afficher();
    const bouton = await screen.findByRole("button", { name: /Rejoindre/i });
    bouton.click();                 // pas de `await` : on observe l'instant du clic
    expect(ouvertures).toHaveLength(1);
    await act(async () => {});
  });

  it("explique quoi faire quand le navigateur bloque l'ouverture", async () => {
    vi.stubGlobal("open", vi.fn(() => null));  // fenêtre surgissante bloquée
    afficher();
    const bouton = await screen.findByRole("button", { name: /Rejoindre/i });
    await act(async () => { bouton.click(); });

    // Pas d'échec muet : le message dit la cause ET le remède.
    await waitFor(() => expect(toast.error).toHaveBeenCalled());
    const message = toast.error.mock.calls.at(-1)[0];
    expect(message).toMatch(/bloqué l'ouverture de la salle/i);
    expect(message).toMatch(/Autorisez les fenêtres surgissantes/i);
  });
});

describe("Plus de conférence dans la page", () => {
  it("n'affiche aucune conférence intégrée après le clic", async () => {
    afficher();
    const bouton = await screen.findByRole("button", { name: /Rejoindre/i });
    await act(async () => { bouton.click(); });

    // La conférence vit dans l'autre onglet : rien ne doit la monter ici,
    // sinon elle retombe sous le `refetchInterval` de cette page.
    expect(screen.queryByTestId("jitsi-container")).toBeNull();
    expect(screen.queryByTestId("virtual-room-session")).toBeNull();
  });
});

describe("Formulaire d'une nouvelle salle", () => {
  it("propose les classes de l'académie, pas seulement « Toute l'école »", async () => {
    afficher();
    const nouvelle = await screen.findByRole("button", { name: /Nouvelle salle/i });
    await act(async () => { nouvelle.click(); });

    await waitFor(() => expect(screen.getByText("Toute l'école")).toBeTruthy());
    for (const c of CLASSES) {
      expect(screen.getByRole("option", { name: c.name })).toBeTruthy();
    }
  });

  it("permet de réserver la salle à certains profils", async () => {
    afficher();
    const nouvelle = await screen.findByRole("button", { name: /Nouvelle salle/i });
    await act(async () => { nouvelle.click(); });

    await waitFor(() => expect(screen.getByText(/Réservée à/i)).toBeTruthy());
    for (const profil of ["Administration", "Enseignants", "Élèves", "Parents"]) {
      expect(screen.getByRole("checkbox", { name: profil })).toBeTruthy();
    }
    // Aucune case cochée doit rester un choix explicite et documenté.
    expect(screen.getByText(/ouverte à tous les profils autorisés/i)).toBeTruthy();
  });

  it("envoie target_roles en LISTE, même vide", async () => {
    // Un groupe de cases à cocher renvoie `false` quand rien n'est coché :
    // le backend recevait `false` et refusait la création.
    virtualAPI.create.mockResolvedValue({ data: { id: 9 } });
    afficher();
    const nouvelle = await screen.findByRole("button", { name: /Nouvelle salle/i });
    await act(async () => { nouvelle.click(); });

    const nom = await screen.findByPlaceholderText(/Cours de Mathématiques/i);
    // `fireEvent.change` passe par le setter natif de React : une
    // affectation directe de `.value` reste invisible pour react-hook-form,
    // et la validation `required` refusait alors l'envoi.
    await act(async () => {
      fireEvent.change(nom, { target: { value: "Réunion parents" } });
    });
    const enregistrer = screen.getByRole("button", { name: /^Enregistrer$/i });
    await act(async () => { enregistrer.click(); });

    await waitFor(() => expect(virtualAPI.create).toHaveBeenCalled());
    const envoye = virtualAPI.create.mock.calls[0][0];
    expect(Array.isArray(envoye.target_roles)).toBe(true);
  });
});
