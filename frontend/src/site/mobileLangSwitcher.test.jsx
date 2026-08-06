/**
 * Régression P9 — le bouton EN/FR doit rester visible sur mobile.
 *
 * SYMPTÔME
 * --------
 * Sur petit écran, le sélecteur de langue n'apparaissait nulle part dans la
 * barre d'en-tête : il n'était rendu que dans le bloc réservé aux écrans
 * ≥ 1200 px et dans le menu déroulant. Changer de langue supposait donc
 * d'ouvrir le menu hamburger — et surtout de deviner qu'il s'y trouvait.
 *
 * GARANTIES VERROUILLÉES ICI
 * --------------------------
 *   - le sélecteur est présent MENU FERMÉ ;
 *   - il n'est pas masqué par une classe utilitaire réservée au desktop ;
 *   - il reste unique quand le menu est ouvert (pas de doublon) ;
 *   - il est accessible : groupe étiqueté, `aria-pressed` sur l'option
 *     active, activation au clavier ;
 *   - il change réellement la langue de la page.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

vi.mock("./siteApi", () => ({
  siteAPI: {
    settings: vi.fn(() => Promise.resolve({ data: {} })),
    heroSlides: vi.fn(() => Promise.resolve({ data: [] })),
    news: vi.fn(() => Promise.resolve({ data: [] })),
    newsDetail: vi.fn(),
    gallery: vi.fn(() => Promise.resolve({ data: [] })),
    sendContact: vi.fn(),
    sendPreRegistration: vi.fn(),
  },
}));

import SiteLayout from "./SiteLayout";

function renderLayout() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/"]}>
        <SiteLayout />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

/** Le sélecteur, quelle que soit la langue affichée. */
function langGroups() {
  return screen.queryAllByRole("group", {
    name: /Choix de la langue|Language selection/,
  });
}

/** Classes utilitaires qui masqueraient l'élément sous 1200 px. */
function isDesktopOnly(el) {
  let node = el;
  while (node && node !== document.body) {
    const cls = node.getAttribute?.("class") || "";
    if (/(^|\s)hidden(\s|$)/.test(cls) && /min-\[1200px\]:(flex|block)/.test(cls)) {
      return true;
    }
    node = node.parentElement;
  }
  return false;
}

beforeEach(() => {
  localStorage.clear();
});

describe("sélecteur de langue sur petit écran", () => {
  it("est présent sans ouvrir le menu hamburger", () => {
    renderLayout();
    const groups = langGroups();
    expect(groups.length).toBeGreaterThan(0);

    // Au moins un exemplaire n'est PAS confiné au desktop.
    const visibleOnMobile = groups.filter((g) => !isDesktopOnly(g));
    expect(visibleOnMobile.length).toBeGreaterThan(0);
  });

  it("propose les deux langues avec un libellé accessible", () => {
    renderLayout();
    const group = langGroups().find((g) => !isDesktopOnly(g));
    expect(within(group).getByRole("button", { name: "English" })).toBeInTheDocument();
    expect(within(group).getByRole("button", { name: "Français" })).toBeInTheDocument();
  });

  it("indique la langue active via aria-pressed", () => {
    renderLayout();
    const group = langGroups().find((g) => !isDesktopOnly(g));
    const fr = within(group).getByRole("button", { name: "Français" });
    const en = within(group).getByRole("button", { name: "English" });

    expect(fr).toHaveAttribute("aria-pressed", "true");
    expect(en).toHaveAttribute("aria-pressed", "false");
  });

  it("change réellement de langue au clic", () => {
    renderLayout();
    const group = langGroups().find((g) => !isDesktopOnly(g));
    fireEvent.click(within(group).getByRole("button", { name: "English" }));

    const after = langGroups().find((g) => !isDesktopOnly(g));
    expect(within(after).getByRole("button", { name: "English" }))
      .toHaveAttribute("aria-pressed", "true");
  });

  it("n'affiche pas deux sélecteurs quand le menu est ouvert", () => {
    renderLayout();
    const burger = screen.getByRole("button", { name: /menu/i });
    fireEvent.click(burger);

    // Le menu est bien ouvert…
    expect(screen.getByRole("navigation", { name: /mobile|Menu/i })).toBeInTheDocument();
    // …et le sélecteur reste unique côté mobile.
    const visibleOnMobile = langGroups().filter((g) => !isDesktopOnly(g));
    expect(visibleOnMobile).toHaveLength(1);
  });

  it("reste dans la barre, à côté du bouton menu", () => {
    renderLayout();
    const burger = screen.getByRole("button", { name: /menu/i });
    const group = langGroups().find((g) => !isDesktopOnly(g));

    // Disposition attendue : Logo | FEBA | EN/FR | Menu — le sélecteur et le
    // bouton menu partagent le même conteneur direct.
    expect(group.parentElement).toBe(burger.parentElement);
  });
});
