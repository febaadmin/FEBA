/**
 * Tests du site vitrine public (P4 v4) : rendu de l'accueil, menu et accès à
 * la connexion, formulaires publics (validation + succès + erreur API),
 * états vides des actualités, 404 publique. Aucune requête réseau réelle.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route } from "react-router-dom";

vi.mock("./siteApi", () => ({
  siteAPI: {
    settings: vi.fn(),
    heroSlides: vi.fn(),
    news: vi.fn(),
    newsDetail: vi.fn(),
    gallery: vi.fn(),
    sendContact: vi.fn(),
    sendPreRegistration: vi.fn(),
  },
}));
import { siteAPI } from "./siteApi";
import SiteLayout from "./SiteLayout";
import HomePage from "./pages/HomePage";
import NewsPage from "./pages/NewsPage";
import SiteNotFound from "./pages/SiteNotFound";
import { ContactForm, PreRegistrationForm } from "./components/PublicForms";

const SETTINGS = {
  school_name: "Faith Excellence Bilingual Academy",
  tagline: "Développer les talents, construire l'avenir.",
  signature: "FEBA, l'école autrement avec vous.",
  address: "Akpakpa, Cotonou, Bénin",
  phone: "", whatsapp: "", email: "", opening_hours: "",
  facebook_url: "", instagram_url: "", youtube_url: "",
  meta_title: "", meta_description: "", og_image: "",
  stat_students: null, stat_teachers: null, stat_years: null, stat_success_rate: null,
};

const SLIDES = [
  { id: 1, title: "Bienvenue à FEBA", subtitle: "École bilingue", cta_label: "Découvrir", cta_url: "/a-propos", image_src: "/site/img/hero-campus-1600.webp", order: 1 },
  { id: 2, title: "Admissions ouvertes", subtitle: "", cta_label: "", cta_url: "", image_src: "/site/img/hero-admissions-1600.webp", order: 2 },
];

function renderWithProviders(ui, { route = "/" } = {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  siteAPI.settings.mockResolvedValue({ data: SETTINGS });
  siteAPI.heroSlides.mockResolvedValue({ data: SLIDES });
  siteAPI.news.mockResolvedValue({ data: [] });
  siteAPI.gallery.mockResolvedValue({ data: [] });
});

describe("Site vitrine — layout et navigation", () => {
  it("affiche le header avec le menu complet et le bouton Connexion vers /login", async () => {
    renderWithProviders(
      <Routes>
        <Route element={<SiteLayout />}>
          <Route path="/" element={<HomePage />} />
        </Route>
      </Routes>,
    );
    for (const label of ["Accueil", "À propos", "Académique", "Admissions",
      "Vie scolaire", "FEBA Online", "Actualités", "Galerie", "Contact"]) {
      expect(screen.getAllByRole("link", { name: label }).length).toBeGreaterThan(0);
    }
    const login = screen.getByRole("link", { name: "Connexion" });
    expect(login).toHaveAttribute("href", "/login");
    expect(screen.getAllByRole("link", { name: "Inscrire mon enfant" }).length).toBeGreaterThan(0);
  });

  it("ouvre le menu mobile via le bouton hamburger (aria-expanded)", async () => {
    renderWithProviders(
      <Routes>
        <Route element={<SiteLayout />}>
          <Route path="/" element={<HomePage />} />
        </Route>
      </Routes>,
    );
    const burger = screen.getByRole("button", { name: "Ouvrir le menu" });
    expect(burger).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(burger);
    expect(screen.getByRole("button", { name: "Fermer le menu" }))
      .toHaveAttribute("aria-expanded", "true");
    expect(document.getElementById("site-mobile-menu")).toBeTruthy();
  });
});

describe("Site vitrine — page d'accueil", () => {
  it("rend le carrousel administrable et les sections sans crash", async () => {
    renderWithProviders(<HomePage />);
    await waitFor(() => {
      // Titre du slide (h1) + overline de la section présentation
      expect(screen.getAllByText("Bienvenue à FEBA").length).toBeGreaterThan(0);
    });
    // Présentation, valeurs, niveaux, bilinguisme, FEBA Online
    expect(screen.getAllByText(/Faith Excellence Bilingual Academy/).length).toBeGreaterThan(0);
    expect(screen.getByText("Excellence")).toBeInTheDocument();
    expect(screen.getByText("Pourquoi choisir FEBA ?")).toBeInTheDocument();
    expect(screen.getByText("FEBA Online")).toBeInTheDocument();
    // Stats nulles → aucune section chiffres inventée
    expect(screen.queryByText("Élèves épanouis")).not.toBeInTheDocument();
  });

  it("affiche la section chiffres uniquement quand renseignés par l'admin", async () => {
    siteAPI.settings.mockResolvedValue({ data: { ...SETTINGS, stat_students: 250 } });
    renderWithProviders(<HomePage />);
    await waitFor(() => {
      expect(screen.getByText("250")).toBeInTheDocument();
      expect(screen.getByText("Élèves épanouis")).toBeInTheDocument();
    });
  });
});

describe("Site vitrine — actualités", () => {
  it("affiche l'état vide sans fausse actualité", async () => {
    renderWithProviders(<NewsPage />);
    await waitFor(() => {
      expect(screen.getByText("Aucune publication pour le moment")).toBeInTheDocument();
    });
  });

  it("affiche l'erreur API proprement", async () => {
    siteAPI.news.mockRejectedValue(new Error("network"));
    renderWithProviders(<NewsPage />);
    // La page retente une fois (retry: 1) avant d'afficher l'erreur.
    await waitFor(() => {
      expect(screen.getByText(/Impossible de charger les actualités/)).toBeInTheDocument();
    }, { timeout: 5000 });
  });

  it("liste les publications réelles renvoyées par l'API", async () => {
    siteAPI.news.mockResolvedValue({ data: [{
      id: 1, kind: "event", title: "Journée portes ouvertes", slug: "jpo",
      excerpt: "Venez nous rencontrer", image_src: "", event_date: "2026-09-05T09:00:00Z",
      location: "Campus FEBA", published_at: "2026-08-20T08:00:00Z",
    }] });
    renderWithProviders(<NewsPage />);
    await waitFor(() => {
      expect(screen.getByText("Journée portes ouvertes")).toBeInTheDocument();
      expect(screen.getByText("Événement")).toBeInTheDocument();
    });
  });
});

describe("Site vitrine — formulaire de contact", () => {
  it("valide les champs obligatoires côté frontend", async () => {
    renderWithProviders(<ContactForm />);
    fireEvent.click(screen.getByRole("button", { name: /Envoyer le message/ }));
    await waitFor(() => {
      expect(screen.getByText("Votre nom est obligatoire.")).toBeInTheDocument();
      expect(screen.getByText("Votre email est obligatoire.")).toBeInTheDocument();
      expect(screen.getByText("Le sujet est obligatoire.")).toBeInTheDocument();
    });
    expect(siteAPI.sendContact).not.toHaveBeenCalled();
  });

  it("envoie le formulaire valide et affiche le message de succès", async () => {
    siteAPI.sendContact.mockResolvedValue({ data: { detail: "Merci ! Votre message a bien été envoyé." } });
    renderWithProviders(<ContactForm />);
    fireEvent.change(screen.getByLabelText(/Nom complet/), { target: { value: "Jean K" } });
    fireEvent.change(screen.getByLabelText(/Email/), { target: { value: "jean@exemple.bj" } });
    fireEvent.change(screen.getByLabelText(/Sujet/), { target: { value: "Infos" } });
    fireEvent.change(screen.getByLabelText(/Message/), { target: { value: "Bonjour" } });
    fireEvent.click(screen.getByLabelText(/J'accepte que mes informations/));
    fireEvent.click(screen.getByRole("button", { name: /Envoyer le message/ }));
    await waitFor(() => {
      expect(screen.getByText(/Merci ! Votre message a bien été envoyé/)).toBeInTheDocument();
    });
    expect(siteAPI.sendContact).toHaveBeenCalledTimes(1);
  });

  it("affiche les erreurs backend (ex: honeypot ou validation)", async () => {
    siteAPI.sendContact.mockRejectedValue({
      response: { data: { email: ["Format d'email invalide."] } },
    });
    renderWithProviders(<ContactForm />);
    fireEvent.change(screen.getByLabelText(/Nom complet/), { target: { value: "Jean" } });
    fireEvent.change(screen.getByLabelText(/Email/), { target: { value: "a@b.cd" } });
    fireEvent.change(screen.getByLabelText(/Sujet/), { target: { value: "X" } });
    fireEvent.change(screen.getByLabelText(/Message/), { target: { value: "Y" } });
    fireEvent.click(screen.getByLabelText(/J'accepte que mes informations/));
    fireEvent.click(screen.getByRole("button", { name: /Envoyer le message/ }));
    await waitFor(() => {
      expect(screen.getByText("Format d'email invalide.")).toBeInTheDocument();
    });
  });
});

describe("Site vitrine — formulaire de préinscription", () => {
  it("exige parent, téléphone, enfant et niveau", async () => {
    renderWithProviders(<PreRegistrationForm />);
    fireEvent.click(screen.getByRole("button", { name: /Envoyer ma demande/ }));
    await waitFor(() => {
      expect(screen.getByText("Le nom du parent est obligatoire.")).toBeInTheDocument();
      expect(screen.getByText("Le téléphone est obligatoire.")).toBeInTheDocument();
      expect(screen.getByText("Le nom de l'enfant est obligatoire.")).toBeInTheDocument();
      expect(screen.getByText("Le niveau souhaité est obligatoire.")).toBeInTheDocument();
    });
    expect(siteAPI.sendPreRegistration).not.toHaveBeenCalled();
  });

  it("envoie une demande valide", async () => {
    siteAPI.sendPreRegistration.mockResolvedValue({ data: { detail: "Merci ! Votre demande de préinscription a bien été enregistrée." } });
    renderWithProviders(<PreRegistrationForm />);
    fireEvent.change(screen.getByLabelText(/Nom du parent/), { target: { value: "Awa T" } });
    fireEvent.change(screen.getByLabelText(/Téléphone/), { target: { value: "+229 01 02 03 04" } });
    fireEvent.change(screen.getByLabelText(/Nom de l'enfant/), { target: { value: "Bintou" } });
    fireEvent.change(screen.getByLabelText(/Niveau souhaité/), { target: { value: "cp" } });
    fireEvent.click(screen.getByRole("button", { name: /Envoyer ma demande/ }));
    await waitFor(() => {
      expect(screen.getByText(/bien été enregistrée/)).toBeInTheDocument();
    });
    const payload = siteAPI.sendPreRegistration.mock.calls[0][0];
    expect(payload.desired_level).toBe("cp");
    expect(payload.child_age).toBeNull();
  });
});

describe("Site vitrine — 404 publique", () => {
  it("affiche la page introuvable avec retour à l'accueil", () => {
    renderWithProviders(<SiteNotFound />, { route: "/nimporte-quoi" });
    expect(screen.getByText("404")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Retour à l'accueil" })).toHaveAttribute("href", "/");
  });
});
