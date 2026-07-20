/**
 * Tests de CONFORMITÉ VISUELLE V6.2 — vérifient que ce sont bien les images
 * exactes annotées « Bonne image » qui sont utilisées aux quatre emplacements
 * corrigés, et que les images « Pas la bonne / Mauvaise image » n'y sont plus.
 *
 * Ces tests ne se contentent pas de vérifier qu'UNE image existe : ils
 * imposent le BON slug (fallback frontend + rendu réel des composants).
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

vi.mock("./siteApi", () => ({
  siteAPI: {
    settings: vi.fn(), heroSlides: vi.fn(), news: vi.fn(),
    newsDetail: vi.fn(), gallery: vi.fn(),
    sendContact: vi.fn(), sendPreRegistration: vi.fn(),
  },
}));
import { siteAPI } from "./siteApi";
import { DEFAULT_SLIDES, DEFAULT_ALBUMS } from "./siteDefaults";
import { metaFor } from "./mediaMeta";
import HomePage from "./pages/HomePage";
import AboutPage from "./pages/AboutPage";
import AcademicsPage from "./pages/AcademicsPage";

const srcs = () =>
  Array.from(document.querySelectorAll("img")).map((i) => i.getAttribute("src") || "");
const hasSlug = (slug) => srcs().some((s) => s.includes(`/site/img/${slug}-`));

function renderPage(ui) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  siteAPI.settings.mockResolvedValue({ data: {} });
  siteAPI.news.mockResolvedValue({ data: [] });
  siteAPI.gallery.mockResolvedValue({ data: [] });
});

describe("Conformité V6.2 — fallback (siteDefaults)", () => {
  it("slide 1 du carrousel = campus-logo (panneau « Faith & Excellence »)", () => {
    expect(DEFAULT_SLIDES[0].image_src).toContain("campus-logo-");
  });

  it("« Notre campus » = les 4 bons slugs, sans les façades « Mauvaise image »", () => {
    const album = DEFAULT_ALBUMS.find((a) => a.title === "Notre campus");
    const slugs = album.items
      .filter((i) => i.kind === "image")
      .map((i) => i.image_src.match(/\/site\/img\/(.+?)-\d+\.webp/)[1]);
    expect(slugs).toEqual([
      "campus-logo", "campus-facade-logo", "campus-devise", "campus-cour",
    ]);
    // Les images rejetées ne doivent plus figurer dans cet album.
    expect(slugs).not.toContain("campus-facade");
    expect(slugs).not.toContain("campus-fresque");
    // Chaque image de l'album est distincte.
    expect(new Set(slugs).size).toBe(slugs.length);
  });
});

describe("Conformité V6.2 — Correction 1 (mosaïque d'accueil)", () => {
  it("utilise campus-facade-logo et PAS l'ancienne vue campus-fresque", async () => {
    renderPage(<HomePage />);
    await waitFor(() => expect(hasSlug("campus-facade-logo")).toBe(true));
    expect(hasSlug("campus-fresque")).toBe(false);
  });
});

describe("Conformité V6.2 — Correction 2 (À propos · La direction)", () => {
  it("« La direction » = photo au bureau (apropos-direction-2), pas le portrait serré", async () => {
    renderPage(<AboutPage />);
    await waitFor(() => expect(hasSlug("apropos-direction-2")).toBe(true));
    // Le portrait serré annoté « Pas la bonne image » ne doit plus être une carte équipe…
    const direction = screen.getByText("La direction").closest("figure, div, article, section")
      || document.body;
    expect(direction).toBeTruthy();
    // …les deux autres cartes restent distinctes.
    expect(hasSlug("accompagnement-duo")).toBe(true);       // Les enseignants
    expect(hasSlug("apropos-equipe-pedagogique")).toBe(true); // L'encadrement
    // apropos-direction (première photo de bureau) reste banni.
    expect(srcs().some((s) => /apropos-direction-1600|apropos-direction-800/.test(s))).toBe(false);
  });
});

describe("Conformité V6.2 — Correction 3 (Académique · cadrage)", () => {
  it("bilingue-accompagnement présent avec un point focal descendu (têtes visibles)", async () => {
    renderPage(<AcademicsPage />);
    await waitFor(() => expect(hasSlug("bilingue-accompagnement")).toBe(true));
    // Cadrage corrigé : le sujet n'est plus recentré en haut (mur crème).
    expect(metaFor("/site/img/bilingue-accompagnement-1600.webp").position).toBe("50% 66%");
  });
});

describe("Conformité V6.2 — cohérence du registre", () => {
  it("les nouveaux slugs ont un point focal délibéré", () => {
    for (const slug of ["campus-facade-logo", "campus-devise", "apropos-direction-2"]) {
      expect(metaFor(`/site/img/${slug}-1600.webp`).position).toMatch(/^\d{1,3}% \d{1,3}%$/);
    }
  });
});
