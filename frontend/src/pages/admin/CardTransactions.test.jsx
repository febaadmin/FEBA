import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("../../api", () => ({ cardPaymentsAPI: { transactions: vi.fn(), refund: vi.fn() } }));
vi.mock("../../context/AcademyContext", () => ({ useAcademy: () => ({ academyKey: "1", isAllAcademies: false }) }));
vi.mock("react-hot-toast", () => {
  const toast = Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() });
  return { default: toast, toast };
});
import { cardPaymentsAPI } from "../../api";
import { setLang } from "../../i18n";
import AdminCardTransactions from "./CardTransactions";

const ligne = { id: 4, provider: "fedapay", academy_code: "FEBA", student: "Alice", created_at: "2026-11-05T10:00:00Z",
  amount_display: "50 000 FCFA", refunded_display: "0 FCFA", currency: "XOF", status: "succeeded", status_display: "Réussi",
  can_refund: true, refundable: true };

describe("transactions carte : remboursement FedaPay constaté", () => {
  beforeEach(() => {
    vi.clearAllMocks(); setLang("fr");
    cardPaymentsAPI.transactions.mockResolvedValue({ data: [ligne] });
    cardPaymentsAPI.refund.mockResolvedValue({ data: { refunded_total: "20 000 FCFA" } });
  });

  it("exige de confirmer le remboursement fait chez FedaPay, puis l'enregistre hors ligne", async () => {
    render(<QueryClientProvider client={new QueryClient()}><AdminCardTransactions /></QueryClientProvider>);
    fireEvent.click(await screen.findByText("Rembourser"));
    expect(screen.getByText(/FedaPay ne permet pas de rembourser depuis FEBA/)).toBeTruthy();
    const bouton = screen.getByRole("button", { name: "Enregistrer le remboursement" });
    expect(bouton.disabled).toBe(true);
    fireEvent.click(screen.getByTestId("remboursement-constate"));
    fireEvent.change(screen.getByLabelText(/Montant à rembourser/), { target: { value: "20000" } });
    fireEvent.click(bouton);
    await waitFor(() => expect(cardPaymentsAPI.refund).toHaveBeenCalledWith(4, "20000", true));
  });
});
