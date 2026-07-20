/**
 * Tests V6 — robustesse du carrousel et de la galerie.
 *
 * Le carrousel n'est JAMAIS une image statique et la galerie n'est JAMAIS
 * vide tant qu'il existe des médias packagés : quand l'API renvoie du
 * contenu on l'affiche, sinon on affiche les défauts (5 slides / albums
 * réels). Couvre : 0 slide, 1 slide, n slides, navigation, galerie vide/pleine.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

vi.mock("./siteApi", () => ({
  siteAPI: { gallery: vi.fn() },
}));
import { siteAPI } from "./siteApi";
import HeroCarousel from "./components/HeroCarousel";
import GalleryPage from "./pages/GalleryPage";
import { DEFAULT_SLIDES, DEFAULT_ALBUMS } from "./siteDefaults";

function wrap(ui) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("HeroCarousel — jamais d'image statique", () => {
  it("aucune slide administrée → 5 slides de repli (pas un hero figé)", () => {
    wrap(<HeroCarousel slides={[]} />);
    // Les 5 thèmes de repli sont présents comme onglets (indicateurs).
    const tabs = screen.getAllByRole("tab");
    expect(tabs).toHaveLength(DEFAULT_SLIDES.length);
    expect(screen.getByRole("region", { name: "À la une" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Slide suivant" })).toBeInTheDocument();
  });

  it("une seule slide → pas de flèches ni d'indicateurs, contenu affiché", () => {
    wrap(<HeroCarousel slides={[{ id: 1, title: "Bienvenue", image_src: "/site/img/hero-campus-1600.webp" }]} />);
    expect(screen.getByRole("heading", { name: "Bienvenue" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Slide suivant" })).toBeNull();
  });

  it("plusieurs slides administrées → priorité au contenu API", () => {
    const slides = [
      { id: 1, title: "Slide A", image_src: "/site/img/hero-campus-1600.webp", cta_label: "Voir", cta_url: "/a" },
      { id: 2, title: "Slide B", image_src: "/site/img/hero-bilingue-1600.webp" },
    ];
    wrap(<HeroCarousel slides={slides} />);
    expect(screen.getByRole("heading", { name: "Slide A" })).toBeInTheDocument();
    expect(screen.getAllByRole("tab")).toHaveLength(2);
    // Navigation manuelle : cliquer « suivant » sélectionne le 2e onglet.
    fireEvent.click(screen.getByRole("button", { name: "Slide suivant" }));
    expect(screen.getByRole("tab", { selected: true }))
      .toHaveAttribute("aria-label", expect.stringContaining("Slide B"));
  });

  it("slide sans bouton → pas de CTA rendu", () => {
    wrap(<HeroCarousel slides={[{ id: 1, title: "Sans bouton", image_src: "/site/img/hero-campus-1600.webp" }]} />);
    expect(screen.queryByRole("link")).toBeNull();
  });
});

describe("GalleryPage — jamais vide", () => {
  beforeEach(() => vi.clearAllMocks());

  it("API vide → albums de repli (médias packagés)", async () => {
    siteAPI.gallery.mockResolvedValue({ data: [] });
    wrap(<GalleryPage />);
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: DEFAULT_ALBUMS[0].title })).toBeInTheDocument();
    });
    // Aucun message « bientôt disponible »
    expect(screen.queryByText(/bientôt disponible/i)).toBeNull();
    // Des vignettes cliquables sont présentes
    expect(screen.getAllByRole("button").length).toBeGreaterThan(4);
  });

  it("API en erreur → repli sur les albums packagés", async () => {
    siteAPI.gallery.mockRejectedValue(new Error("réseau"));
    wrap(<GalleryPage />);
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: DEFAULT_ALBUMS[0].title })).toBeInTheDocument();
    }, { timeout: 4000 });
  });

  it("API pleine → priorité au contenu administré", async () => {
    siteAPI.gallery.mockResolvedValue({ data: [
      { id: 9, title: "Album administré", description: "", items: [
        { id: 1, kind: "image", caption: "Photo réelle", image_src: "/site/img/campus-facade-800.webp", focal: "50% 50%" },
      ] },
    ] });
    wrap(<GalleryPage />);
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Album administré" })).toBeInTheDocument();
    });
    expect(screen.queryByRole("heading", { name: DEFAULT_ALBUMS[0].title })).toBeNull();
  });
});

describe("siteDefaults — cohérence", () => {
  it("5 slides de repli, chacun avec image, titre, CTA et focal", () => {
    expect(DEFAULT_SLIDES).toHaveLength(5);
    for (const s of DEFAULT_SLIDES) {
      expect(s.image_src).toMatch(/^\/site\/img\/.+-1600\.webp$/);
      expect(s.title).toBeTruthy();
      expect(s.cta_url).toMatch(/^\//);
      expect(s.focal).toMatch(/^\d{1,3}% \d{1,3}%$/);
    }
  });

  it("aucun média n'apparaît deux fois dans l'ensemble des albums de repli", () => {
    const srcs = DEFAULT_ALBUMS.flatMap((a) => a.items.filter((i) => i.kind === "image").map((i) => i.image_src));
    expect(new Set(srcs).size).toBe(srcs.length);
  });
});
