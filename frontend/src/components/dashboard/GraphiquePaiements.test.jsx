import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import GraphiquePaiements from "./GraphiquePaiements";
import { setLang } from "../../i18n";

const tableauDeBord = vi.fn();
vi.mock("../../api", () => ({ paymentsAPI: { tableauDeBord: (...a) => tableauDeBord(...a) } }));
vi.mock("../../context/AcademyContext", () => ({ useAcademy: () => ({ academyKey: "all", businessDataEnabled: true }) }));
// recharts mesure son conteneur : sans dimensions en jsdom, on se contente du rendu des données.
vi.mock("recharts", async (orig) => {
  const vrai = await orig();
  return { ...vrai, ResponsiveContainer: ({ children }) => <div style={{ width: 600, height: 240 }}>{children}</div> };
});

const ind = (o = {}) => ({ encaisse_minor: 0, rembourse_minor: 0, nb_paiements: 0, annule_minor: 0, nb_annules: 0,
  en_attente_minor: 0, nb_en_attente: 0, echoue_minor: 0, nb_echoues: 0, attendu_minor: null, restant_minor: null,
  taux_recouvrement: null, ...o });
const reponse = {
  periode: { code: "12m", du: "2025-12-01", au: "2026-11-04", granularite: "mois" },
  devises: [
    { devise: "USD", academies: [{ id: 2, nom: "FHA" }], echeancier_configure: false,
      indicateurs: ind({ encaisse_minor: 10550, nb_paiements: 1, rembourse_minor: 2000 }),
      serie: [{ date: "2026-11-01", encaisse_minor: 10550, attendu_minor: null }] },
    { devise: "XOF", academies: [{ id: 1, nom: "FEBA" }], echeancier_configure: true,
      indicateurs: ind({ encaisse_minor: 210000, nb_paiements: 3, attendu_minor: 510000, restant_minor: 293000, taux_recouvrement: 42.5 }),
      serie: [{ date: "2026-09-01", encaisse_minor: 150000, attendu_minor: 300000 }] },
  ],
  par_academie: [{ id: 1, nom: "FEBA", devise: "XOF", encaisse_minor: 210000, nb_paiements: 3, restant_minor: 293000 },
    { id: 2, nom: "FHA", devise: "USD", encaisse_minor: 10550, nb_paiements: 1, restant_minor: null }],
};
const monter = () => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><GraphiquePaiements /></QueryClientProvider>);

describe("graphique des paiements", () => {
  beforeEach(() => { tableauDeBord.mockReset(); setLang("fr"); });
  afterEach(() => setLang("fr"));

  it("affiche les indicateurs du serveur, devise par devise, sans additionner XOF et USD", async () => {
    tableauDeBord.mockResolvedValue({ data: reponse });
    monter();
    await screen.findByTestId("ind-encaisse");
    expect(tableauDeBord).toHaveBeenCalledWith({ periode: "12m" });
    expect(screen.getByTestId("ind-encaisse").textContent).toMatch(/105[.,]50/);
    expect(screen.getByTestId("ind-attendu").textContent).toMatch(/Non calculable/);
    fireEvent.click(screen.getByTestId("devise-XOF"));
    expect(screen.getByTestId("ind-encaisse").textContent).toMatch(/210\s?000/);
    expect(screen.getByTestId("ind-restant").textContent).toMatch(/293\s?000.*42\.5 %/);
    expect(screen.getByTestId("paiements-par-academie").textContent).toMatch(/FHA.*Non calculable/);
  });

  it("change de période et exige les deux dates en mode personnalisé", async () => {
    tableauDeBord.mockResolvedValue({ data: reponse });
    monter();
    await screen.findByTestId("ind-encaisse");
    fireEvent.click(screen.getByTestId("periode-30j"));
    await waitFor(() => expect(tableauDeBord).toHaveBeenLastCalledWith({ periode: "30j" }));
    const appels = tableauDeBord.mock.calls.length;
    fireEvent.click(screen.getByTestId("periode-perso"));
    expect(screen.getByText(/Choisissez les deux dates/)).toBeTruthy();
    expect(tableauDeBord.mock.calls.length).toBe(appels);
  });

  it("état vide, erreur et anglais", async () => {
    tableauDeBord.mockResolvedValueOnce({ data: { ...reponse, devises: [{ ...reponse.devises[0], indicateurs: ind(), echeancier_configure: false }], par_academie: [] } });
    const { unmount } = monter();
    expect(await screen.findByTestId("paiements-vide")).toBeTruthy();
    unmount();
    tableauDeBord.mockRejectedValueOnce({ response: { status: 500, data: {} } });
    const second = monter();
    expect((await screen.findByRole("alert")).textContent).toMatch(/n'ont pas pu être chargés/);
    second.unmount();
    tableauDeBord.mockResolvedValue({ data: reponse });
    act(() => setLang("en"));
    monter();
    await screen.findByTestId("ind-encaisse");
    expect(screen.getByTestId("ind-attendu").textContent).toMatch(/Not computable/);
    expect(screen.getByTestId("ind-encaisse").textContent).toMatch(/Collected \(net of refunds\)/);
  });
});
