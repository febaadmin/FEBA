/**
 * Menus et en-têtes : aucune identité d'académie écrite en dur.
 *
 * Défauts couverts :
 *  - l'en-tête affichait « FEBA » / « FEBA Academy » pour TOUTE académie ;
 *  - « Admissions FEBA FHA » et « Rapports mensuels » apparaissaient pour
 *    toute académie en ligne (et, chez le super administrateur, pour toute
 *    académie sélectionnée), sur la foi de `placement_tests`.
 *
 * L'académie « testete » au nom long et accentué représente une académie
 * créée après coup, que le code ne connaît pas.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const ctx = vi.hoisted(() => ({ value: null }));

vi.mock("../context/AcademyContext", () => ({ useAcademy: () => ctx.value }));
vi.mock("../hooks/useAuth", () => ({
  useAuth: () => ({ user: { first_name: "Awa", last_name: "Test", role: "admin" }, logout: vi.fn() }),
}));
vi.mock("../api", () => ({
  notificationsAPI: { unreadCount: vi.fn(() => Promise.resolve({ data: { count: 0 } })),
    list: vi.fn(() => Promise.resolve({ data: [] })), markAllRead: vi.fn() },
  conversationsAPI: { unreadCount: vi.fn(() => Promise.resolve({ data: { count: 0 } })) },
  messagesAPI: { inbox: vi.fn(() => Promise.resolve({ data: [] })) },
}));
vi.mock("../components/AcademyLogo", () => ({ default: () => null }));
vi.mock("../components/EntitySwitcher", () => ({ default: () => null }));
vi.mock("../components/AcademyScopedOutlet", () => ({ default: () => null }));
vi.mock("../components/ui/LanguageSwitcher", () => ({ default: () => null }));

import AdminLayout from "./AdminLayout";
import SuperAdminLayout from "./SuperAdminLayout";
import StudentLayout from "./StudentLayout";
import TeacherLayout from "./TeacherLayout";
import ParentLayout from "./ParentLayout";

const LONG = "Académie Évangélique Saint-Éloi de Natitingou - Programme Francophone";
const TESTETE = {
  id: 3, code: "TESTETE", name: LONG, short_name: LONG, entity_type: "online",
  features: { placement_tests: true, online_admissions: false, monthly_reports: false },
};
const FHA = {
  id: 2, code: "FEBA_FHA", name: "FEBA French Heritage Academy", short_name: "FEBA FHA", entity_type: "online",
  features: { placement_tests: true, online_admissions: true, monthly_reports: true },
};
const FEBA = {
  id: 1, code: "FEBA", name: "Faith & Excellence Bilingual Academy", short_name: "FEBA", entity_type: "campus",
  features: { placement_tests: false, online_admissions: false, monthly_reports: false },
};

function academyCtx(active, { all = false, allowed = [FEBA, FHA, TESTETE] } = {}) {
  const features = active?.features || {};
  return {
    activeAcademy: active, isAllAcademies: all, allowedAcademies: allowed,
    canSwitchAcademy: true, features, hasFeature: (f) => Boolean(features[f]),
    scopeReady: true, academyKey: `academy:${active?.id ?? "all"}`,
  };
}

function mount(Layout) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}><MemoryRouter><Layout /></MemoryRouter></QueryClientProvider>,
  );
}

beforeEach(() => { ctx.value = academyCtx(TESTETE); });

describe("en-tête : nom de l'académie active", () => {
  for (const [role, Layout] of [["admin", AdminLayout], ["superadmin", SuperAdminLayout],
    ["élève", StudentLayout], ["enseignant", TeacherLayout], ["parent", ParentLayout]]) {
    it(`${role} : affiche « testete » (nom long, accentué), jamais « FEBA »`, () => {
      mount(Layout);
      const name = screen.getByTestId("layout-academy-name");
      expect(name.textContent).toBe(LONG);
      expect(name.className).toMatch(/truncate/);       // ne déborde pas du menu
      expect(name.getAttribute("title")).toBe(LONG);    // nom complet en info-bulle
      expect(name.textContent).not.toMatch(/^FEBA/);
    });
  }

  it("super administrateur en mode « Toutes les Académies »", () => {
    ctx.value = academyCtx(null, { all: true });
    mount(SuperAdminLayout);
    expect(screen.getByTestId("layout-academy-name").textContent).toBe("Toutes les Académies");
  });
});

describe("entrées liées à une fonctionnalité", () => {
  const menuText = () => document.body.textContent;

  it("admin d'une académie en ligne SANS canal d'admission (testete) : ni admissions ni rapports", () => {
    mount(AdminLayout);
    expect(menuText()).not.toMatch(/Admissions/);
    expect(menuText()).not.toMatch(/Rapports mensuels/);
    expect(menuText()).not.toMatch(/FEBA FHA/);
  });

  it("admin de l'académie rattachée au site public : « Admissions en ligne », sans nom en dur", () => {
    ctx.value = academyCtx(FHA);
    mount(AdminLayout);
    expect(screen.getByText("Admissions en ligne")).toBeTruthy();
    expect(screen.getByText("Rapports mensuels")).toBeTruthy();
    expect(screen.queryByText(/Admissions FEBA FHA/)).toBeNull();
  });

  it("super administrateur sur testete : les entrées suivent testete, pas une autre académie", () => {
    mount(SuperAdminLayout);
    expect(menuText()).not.toMatch(/Admissions/);
    expect(menuText()).not.toMatch(/Rapports mensuels/);
  });

  it("super administrateur sur FEBA (présentiel) : aucune entrée en ligne", () => {
    ctx.value = academyCtx(FEBA);
    mount(SuperAdminLayout);
    expect(menuText()).not.toMatch(/Admissions en ligne/);
  });

  it("« Toutes les Académies » : présentes dès qu'UNE académie accessible les possède", () => {
    ctx.value = academyCtx(null, { all: true });
    mount(SuperAdminLayout);
    expect(screen.getByText("Admissions en ligne")).toBeTruthy();
    ctx.value = academyCtx(null, { all: true, allowed: [FEBA, TESTETE] });
    const { container } = mount(SuperAdminLayout);
    expect(within(container).queryByText("Admissions en ligne")).toBeNull();
  });
});
