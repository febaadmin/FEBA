/**
 * Consentement SMS : choix personnel, état du numéro tel que les SMS
 * l'utiliseront, et aucun SMS tant que rien n'est choisi.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("../api", () => ({ authAPI: { me: vi.fn(), updateMe: vi.fn() } }));
vi.mock("react-hot-toast", () => {
  const toast = Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() });
  return { default: toast, toast };
});

import { authAPI } from "../api";
import { setLang } from "../i18n";
import SmsPreferencesCard from "./SmsPreferencesCard";

function renderCard() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><SmsPreferencesCard /></QueryClientProvider>);
}

beforeEach(() => { vi.clearAllMocks(); setLang("fr"); });

describe("Préférences SMS", () => {
  it("sans choix : explique qu'aucun SMS n'est envoyé et signale un numéro invalide", async () => {
    authAPI.me.mockResolvedValue({ data: { sms_consent: "unknown", sms_phone: { e164: "", problem: "invalid_phone" } } });
    renderCard();
    expect(await screen.findByText(/aucun SMS ne vous est envoyé/)).toBeTruthy();
    expect(screen.getByText(/indicatif du pays/)).toBeTruthy();
  });

  it("accepter les SMS envoie le choix au serveur et affiche le numéro utilisé", async () => {
    authAPI.me.mockResolvedValue({ data: { sms_consent: "refused", sms_phone: { e164: "+2290196697363", problem: "" } } });
    authAPI.updateMe.mockResolvedValue({ data: {} });
    renderCard();
    expect(await screen.findByText("+2290196697363")).toBeTruthy();
    fireEvent.click(screen.getByLabelText("J'accepte les SMS"));
    await waitFor(() => expect(authAPI.updateMe).toHaveBeenCalledWith({ sms_consent: "granted" }));
  });
});
