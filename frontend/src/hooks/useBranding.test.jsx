/**
 * useBranding : logo et favicons de l'académie AFFICHÉE, même sans connexion.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

let academy = { activeAcademy: null };
vi.mock("../context/AcademyContext", () => ({ useAcademy: () => academy }));
vi.mock("../api", () => ({ schoolsAPI: { publicBranding: vi.fn() } }));

import { schoolsAPI } from "../api";
import { applyFavicons, useBranding } from "./useBranding";

const payload = (code, v) => ({
  academy_code: code, meeting_title: `${code} titre`, version: v,
  logo_url: `/api/schools/public-branding/${code}/logo/?v=${v}`,
  favicon_16_url: `/api/schools/public-branding/${code}/favicon-16.png?v=${v}`,
  favicon_32_url: `/api/schools/public-branding/${code}/favicon-32.png?v=${v}`,
  apple_touch_icon_url: `/api/schools/public-branding/${code}/favicon-180.png?v=${v}`,
});

function Logo({ code }) {
  const { logoSrc } = useBranding(code);
  return <img alt="logo" src={logoSrc} />;
}

function renderWith(ui, qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })) {
  return { qc, ...render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>) };
}

beforeEach(() => {
  vi.clearAllMocks();
  academy = { activeAcademy: null };
  document.head.innerHTML = '<link rel="icon" type="image/svg+xml" href="/favicon.svg" />';
});

describe("useBranding", () => {
  it("charge l'identité publique SANS jeton (site public, connexion) et applique les favicons", async () => {
    schoolsAPI.publicBranding.mockResolvedValue({ data: payload("FEBA", "v1") });
    renderWith(<Logo />);
    await waitFor(() => expect(screen.getByAltText("logo").getAttribute("src"))
      .toBe("/api/schools/public-branding/FEBA/logo/?v=v1"));
    expect(schoolsAPI.publicBranding).toHaveBeenCalledWith("FEBA");
    expect(document.head.querySelector('link[href="/favicon.svg"]')).toBeNull();     // ancienne icône retirée
    expect(document.head.querySelector('link[data-feba-favicon="32"]').getAttribute("href"))
      .toBe("/api/schools/public-branding/FEBA/favicon-32.png?v=v1");
  });

  it("suit l'académie demandée (FEBA FHA) et l'académie active du contexte", async () => {
    schoolsAPI.publicBranding.mockImplementation((code) => Promise.resolve({ data: payload(code, "v9") }));
    renderWith(<Logo code="FEBA_FHA" />);
    await waitFor(() => expect(screen.getByAltText("logo").getAttribute("src")).toContain("/FEBA_FHA/logo/"));
    academy = { activeAcademy: { code: "FEBA_FHA" } };
    renderWith(<Logo />);
    await waitFor(() => expect(schoolsAPI.publicBranding).toHaveBeenLastCalledWith("FEBA_FHA"));
  });

  it("une nouvelle activation (nouvelle version) change l'URL du logo", async () => {
    schoolsAPI.publicBranding.mockResolvedValueOnce({ data: payload("FEBA", "v1") });
    const { qc } = renderWith(<Logo code="FEBA" />);
    await waitFor(() => expect(screen.getByAltText("logo").getAttribute("src")).toContain("v=v1"));
    schoolsAPI.publicBranding.mockResolvedValueOnce({ data: payload("FEBA", "v2") });
    await qc.invalidateQueries({ queryKey: ["branding-public"] });
    await waitFor(() => expect(screen.getByAltText("logo").getAttribute("src")).toContain("v=v2"));
  });

  it("avant la réponse : URL de CETTE académie, jamais le logo d'une autre", () => {
    schoolsAPI.publicBranding.mockReturnValue(new Promise(() => {}));
    renderWith(<Logo code="FEBA_FHA" />);
    expect(screen.getByAltText("logo").getAttribute("src")).toBe("/api/schools/public-branding/FEBA_FHA/logo/");
  });

  it("applyFavicons est idempotent", () => {
    applyFavicons(payload("FEBA", "v1"));
    applyFavicons(payload("FEBA", "v1"));
    expect(document.head.querySelectorAll("link[data-feba-favicon]").length).toBe(3);
  });
});
