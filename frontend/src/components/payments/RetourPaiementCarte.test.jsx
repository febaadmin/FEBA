import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("../../api", () => ({ cardPaymentsAPI: { verifier: vi.fn() } }));
import { cardPaymentsAPI } from "../../api";
import { setLang } from "../../i18n";
import RetourPaiementCarte from "./RetourPaiementCarte";

const monter = (id = 5) => render(
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><RetourPaiementCarte transactionId={id} /></QueryClientProvider>);

describe("retour du prestataire de paiement", () => {
  beforeEach(() => { vi.clearAllMocks(); setLang("fr"); });

  it("demande une vérification au serveur ; « en cours » tant que le prestataire n'a rien confirmé", async () => {
    cardPaymentsAPI.verifier.mockResolvedValue({ data: { status: "pending" } });
    monter();
    await waitFor(() => expect(cardPaymentsAPI.verifier).toHaveBeenCalledWith(5));
    expect(screen.getByTestId("retour-paiement").textContent).toMatch(/en cours de vérification/);
    expect(screen.getByTestId("retour-paiement").textContent).not.toMatch(/confirmé/);
  });

  it("confirmé seulement si le serveur l'a constaté", async () => {
    cardPaymentsAPI.verifier.mockResolvedValue({ data: { status: "succeeded", amount_display: "50 000 FCFA" } });
    monter();
    await waitFor(() => expect(screen.getByTestId("retour-paiement").dataset.statut).toBe("succeeded"));
    expect(screen.getByTestId("retour-paiement").textContent).toMatch(/Paiement confirmé.*50 000 FCFA/);
  });

  it("refus et abandon expliqués", async () => {
    cardPaymentsAPI.verifier.mockResolvedValue({ data: { status: "cancelled", reason: "Paiement abandonné." } });
    monter();
    await waitFor(() => expect(screen.getByTestId("retour-paiement").textContent).toMatch(/Paiement abandonné.*Rien n'a été encaissé/));
  });
});
