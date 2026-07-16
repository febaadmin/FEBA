/**
 * Tests de rendu de ParentHome — reproduisent le scénario exact de la page
 * blanche « t2 is not a function » (moyennes trimestrielles T1/T2/T3) et
 * couvrent les états valide / vide / null / partiel / chargement / erreur.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { setLang } from "../../i18n";

// Mock de la couche API (aucun réseau en test unitaire)
vi.mock("../../api", () => ({
  dashboardAPI: { parent: vi.fn() },
  announcementsAPI: { list: vi.fn() },
}));
import { dashboardAPI, announcementsAPI } from "../../api";
import ParentHome from "./Home";

const CHILD = {
  id: 1,
  name: "Awa Kone",
  class: "CM2-A",
  level: "CM2",
  average: 14.5,
  appreciation: "Très bien",
  absent_count: 1,
  pending_homework: 2,
  average_t1: 13.2,   // ← les valeurs qui déclenchaient le .map(([t, v]) …)
  average_t2: 15.1,
  average_t3: null,
  progression: 1.9,
  bilingual: { fr_average: 14.0, en_average: 15.0, bilingual_average: 14.4 },
  subject_averages: [
    { subject_id: 10, subject_name: "Mathématiques", language: "fr", average: 16, has_notes: true },
    { subject_id: 11, subject_name: "English", language: "en", average: null, has_notes: false },
  ],
};

function renderHome() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <ParentHome />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  setLang("fr");
  announcementsAPI.list.mockResolvedValue({ data: { results: [] } });
});

describe("ParentHome — données valides", () => {
  it("rend les moyennes trimestrielles SANS crash (régression « t2 is not a function »)", async () => {
    dashboardAPI.parent.mockResolvedValue({ data: { children: [CHILD] } });
    renderHome();
    // Le crash originel se produisait ici : t("Moy.") dans le .map des trimestres.
    expect(await screen.findByText("Moy. T1")).toBeInTheDocument();
    expect(screen.getByText("Moy. T2")).toBeInTheDocument();
    expect(screen.getByText("Moy. T3")).toBeInTheDocument();
    expect(screen.getByText("13.20")).toBeInTheDocument();
    expect(screen.getByText("15.10")).toBeInTheDocument();
  });

  it("affiche l'enfant, sa moyenne générale et ses moyennes FR/EN", async () => {
    dashboardAPI.parent.mockResolvedValue({ data: { children: [CHILD] } });
    renderHome();
    expect(await screen.findByText("Awa Kone")).toBeInTheDocument();
    expect(screen.getByText("14.50/20")).toBeInTheDocument();
    expect(screen.getByText("Français")).toBeInTheDocument();
    expect(screen.getByText("Anglais")).toBeInTheDocument();
    expect(screen.getByText("14.00/20")).toBeInTheDocument();
    expect(screen.getByText("15.00/20")).toBeInTheDocument();
  });

  it("rend plusieurs enfants", async () => {
    dashboardAPI.parent.mockResolvedValue({
      data: { children: [CHILD, { ...CHILD, id: 2, name: "Sory Kone" }] },
    });
    renderHome();
    expect(await screen.findByText("Awa Kone")).toBeInTheDocument();
    expect(screen.getByText("Sory Kone")).toBeInTheDocument();
  });

  it("traduit le tableau de bord en anglais après setLang('en')", async () => {
    setLang("en");
    dashboardAPI.parent.mockResolvedValue({ data: { children: [CHILD] } });
    renderHome();
    expect(await screen.findByText("Avg. T1")).toBeInTheDocument();
    expect(screen.getByText("Overall average")).toBeInTheDocument();
  });
});

describe("ParentHome — données dégradées", () => {
  it("gère un enfant sans aucune moyenne (valeurs null) sans crash", async () => {
    dashboardAPI.parent.mockResolvedValue({
      data: {
        children: [{
          id: 3, name: "Neo Sans-Note", class: "CI-A", level: "CI",
          average: null, absent_count: 0, pending_homework: 0,
          average_t1: null, average_t2: null, average_t3: null,
          bilingual: null, subject_averages: [], progression: null,
        }],
      },
    });
    renderHome();
    expect(await screen.findByText("Neo Sans-Note")).toBeInTheDocument();
    expect(screen.getByText("Moy. T1")).toBeInTheDocument();
  });

  it("affiche l'état vide quand le parent n'a aucun enfant", async () => {
    dashboardAPI.parent.mockResolvedValue({ data: { children: [] } });
    renderHome();
    expect(await screen.findByText("Aucun enfant associé à votre compte.")).toBeInTheDocument();
  });

  it("gère une réponse sans children (undefined) comme un état vide, sans crash", async () => {
    dashboardAPI.parent.mockResolvedValue({ data: {} });
    renderHome();
    expect(await screen.findByText("Aucun enfant associé à votre compte.")).toBeInTheDocument();
  });

  it("affiche l'état d'erreur (profil introuvable) quand l'API échoue", async () => {
    dashboardAPI.parent.mockRejectedValue({ response: { status: 404 } });
    renderHome();
    expect(await screen.findByText("Profil parent introuvable")).toBeInTheDocument();
  });

  it("affiche le squelette de chargement au premier rendu", async () => {
    dashboardAPI.parent.mockReturnValue(new Promise(() => {}));
    const { container } = renderHome();
    expect(container.querySelectorAll(".skeleton").length).toBeGreaterThan(0);
  });
});

describe("ParentHome — annonces", () => {
  it("affiche les annonces récentes", async () => {
    dashboardAPI.parent.mockResolvedValue({ data: { children: [CHILD] } });
    announcementsAPI.list.mockResolvedValue({
      data: { results: [{ id: 1, title: "Rentrée scolaire", content: "…", created_at: "2026-07-16T00:00:00" }] },
    });
    renderHome();
    expect(await screen.findByText("Rentrée scolaire")).toBeInTheDocument();
    expect(screen.getByText("Annonces récentes")).toBeInTheDocument();
  });
});
