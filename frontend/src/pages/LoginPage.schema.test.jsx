/**
 * Formulaire de connexion après la montée zod 3 → 4 et @hookform/resolvers 3 → 5
 * (vulnérabilité zod GHSA-mrhx-c7xc-m3w5) : mêmes règles, mêmes messages.
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("../hooks/useAuth", () => ({ useAuth: () => ({ login: vi.fn(), isLoading: false }) }));
vi.mock("../hooks/useBranding", () => ({ useBranding: () => ({ logoSrc: null, brandingData: null }) }));

import LoginPage from "./LoginPage";

function mount() {
  const qc = new QueryClient();
  return render(<QueryClientProvider client={qc}><MemoryRouter><LoginPage /></MemoryRouter></QueryClientProvider>);
}

describe("validation du formulaire de connexion (zod 4)", () => {
  it("refuse un e-mail invalide et un mot de passe trop court, avec les messages attendus", async () => {
    mount();
    fireEvent.change(document.querySelector("input[type=email], input[name=email]"), { target: { value: "pas-un-email" } });
    fireEvent.change(document.querySelector("input[type=password]"), { target: { value: "12" } });
    fireEvent.submit(document.querySelector("form"));
    const alerts = await screen.findAllByRole("alert");
    const text = alerts.map((a) => a.textContent).join(" | ");
    expect(text).toMatch(/Email invalide/);
    expect(text).toMatch(/Mot de passe requis/);
  });
});
