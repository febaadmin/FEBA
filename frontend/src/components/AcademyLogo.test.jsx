/**
 * Logo des barres latérales : une académie sans logo (créée depuis l'écran
 * « Académies ») affichait une image cassée. Elle affiche désormais son
 * monogramme ; une image qui échoue aussi.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

let academy;
vi.mock("../context/AcademyContext", () => ({ useAcademy: () => academy }));
vi.mock("../api", () => ({ schoolsAPI: { publicBranding: vi.fn() } }));

import { schoolsAPI } from "../api";
import { monogramOf } from "../hooks/useBranding";
import AcademyLogo from "./AcademyLogo";

const base = (extra) => ({
  academy_code: "LYCEE_PARAKOU", display_name: "Lycée de Parakou", short_name: "LYCEE PARAKOU",
  meeting_title: "x", version: "v1", logo_url: null,
  favicon_16_url: "/f16", favicon_32_url: "/f32", apple_touch_icon_url: "/f180", ...extra,
});

function renderLogo() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><AcademyLogo /></QueryClientProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
  academy = { activeAcademy: { code: "LYCEE_PARAKOU", name: "Lycée de Parakou", short_name: "LYCEE PARAKOU" } };
});

describe("AcademyLogo", () => {
  it("sans logo activé : monogramme de l'académie, aucune image", async () => {
    schoolsAPI.publicBranding.mockResolvedValue({ data: base() });
    renderLogo();
    const mono = await screen.findByTestId("academy-monogram");
    expect(mono.textContent).toBe("LP");
    expect(mono.getAttribute("aria-label")).toBe("Lycée de Parakou");
    expect(document.querySelector("img")).toBeNull();
  });

  it("avec un logo : l'image, avec le nom de l'académie comme texte alternatif", async () => {
    schoolsAPI.publicBranding.mockResolvedValue({ data: base({ logo_url: "/logo.png?v=1" }) });
    renderLogo();
    await waitFor(() => expect(screen.getByAltText("Lycée de Parakou").getAttribute("src")).toBe("/logo.png?v=1"));
    const img = screen.getByAltText("Lycée de Parakou");
    fireEvent.error(img);                                   // image injoignable
    expect(screen.getByTestId("academy-monogram").textContent).toBe("LP");
  });

  it("initiales", () => {
    expect(monogramOf("Lycée de Parakou")).toBe("LP");
    expect(monogramOf("FEBA_FHA")).toBe("FF");
    expect(monogramOf("")).toBe("?");
  });
});
