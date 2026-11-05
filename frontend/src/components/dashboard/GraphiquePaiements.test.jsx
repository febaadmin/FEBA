import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import GraphiquePaiements, { changerFiltre, parametres, FILTRES_VIDES } from "./GraphiquePaiements";
import { setLang } from "../../i18n";

const tableauDeBord = vi.fn();
const filtresAPI = vi.fn();
const detailAPI = vi.fn();
vi.mock("../../api", () => ({ paymentsAPI: {
  tableauDeBord: (...a) => tableauDeBord(...a),
  tableauDeBordFiltres: (...a) => filtresAPI(...a),
  tableauDeBordDetail: (...a) => detailAPI(...a),
  tableauDeBordExport: vi.fn(),
} }));
const academie = { academyKey: "all", businessDataEnabled: true };
vi.mock("../../context/AcademyContext", () => ({ useAcademy: () => academie }));
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
      couverture: { eleves_actifs: 80, eleves_avec_echeances: 76, eleves_sans_tarif: 4, academies_sans_tarif: [] },
      indicateurs: ind({ encaisse_minor: 210000, nb_paiements: 3, attendu_minor: 510000, restant_minor: 293000, taux_recouvrement: 42.5 }),
      serie: [{ date: "2026-09-01", encaisse_minor: 150000, attendu_minor: 300000 }] },
  ],
  par_academie: [{ id: 1, nom: "FEBA", devise: "XOF", encaisse_minor: 210000, nb_paiements: 3, restant_minor: 293000 },
    { id: 2, nom: "FHA", devise: "USD", encaisse_minor: 10550, nb_paiements: 1, restant_minor: null }],
};
const monter = () => render(<MemoryRouter><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><GraphiquePaiements /></QueryClientProvider></MemoryRouter>);

describe("graphique des paiements", () => {
  beforeEach(() => {
    tableauDeBord.mockReset(); detailAPI.mockReset(); filtresAPI.mockReset(); setLang("fr");
    academie.academyKey = "all";
    filtresAPI.mockResolvedValue({ data: { structure_disponible: false, annees: [], cycles: [], niveaux: [], classes: [], eleves: [],
      natures: [{ id: "mensualite", nom: "Mensualité" }], modes: [{ id: "cash", nom: "Espèces" }] } });
  });
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

  it("paramètres : seulement les filtres renseignés ; un choix de structure efface ceux qui en dépendent", () => {
    expect(parametres("12m", "", "", FILTRES_VIDES, false)).toEqual({ periode: "12m" });
    expect(parametres("perso", "2026-01-01", "2026-01-31", { ...FILTRES_VIDES, classe: "4", mode: "cash" }, true))
      .toEqual({ periode: "perso", du: "2026-01-01", au: "2026-01-31", comparer: 1, classe: "4", mode: "cash" });
    const f = { ...FILTRES_VIDES, annee: "1", cycle: "primaire", niveau: "2", classe: "3", eleve: "9", nature: "cantine" };
    expect(changerFiltre(f, "niveau", "5")).toMatchObject({ annee: "1", cycle: "primaire", niveau: "5", classe: "", eleve: "", nature: "cantine" });
    expect(changerFiltre(f, "cycle", "")).toMatchObject({ niveau: "", classe: "", eleve: "" });
    expect(changerFiltre(f, "annee", "7")).toMatchObject({ niveau: "2", classe: "", eleve: "" });
  });

  it("structure désactivée en « Toutes les Académies » ; filtres dépendants, puces et réinitialisation pour une académie", async () => {
    tableauDeBord.mockResolvedValue({ data: reponse });
    const { unmount } = monter();
    await screen.findByTestId("ind-encaisse");
    await waitFor(() => expect(screen.getByTestId("filtre-classe").disabled).toBe(true));
    unmount();
    academie.academyKey = "1";
    filtresAPI.mockImplementation(async (p) => ({ data: { structure_disponible: true,
      annees: [{ id: 1, nom: "2026-2027" }], cycles: [{ id: "primaire", nom: "Primaire" }],
      niveaux: [{ id: 2, nom: "CE1" }], classes: p.niveau ? [{ id: 3, nom: "CE1-A" }] : [{ id: 3, nom: "CE1-A" }, { id: 4, nom: "CM1-A" }],
      eleves: p.classe ? [{ id: 9, nom: "Alice Élève" }] : [], natures: [{ id: "mensualite", nom: "Mensualité" }], modes: [] } }));
    monter();
    await screen.findByTestId("ind-encaisse");
    await waitFor(() => expect(screen.getByTestId("filtre-classe").disabled).toBe(false));
    expect(screen.getByTestId("filtre-eleve").disabled).toBe(true);           // il faut d'abord une classe
    fireEvent.change(screen.getByTestId("filtre-niveau"), { target: { value: "2" } });
    await waitFor(() => expect(filtresAPI).toHaveBeenLastCalledWith({ niveau: "2" }));
    await waitFor(() => expect(screen.getByTestId("filtre-classe").querySelectorAll("option").length).toBe(2));
    fireEvent.change(screen.getByTestId("filtre-classe"), { target: { value: "3" } });
    await waitFor(() => expect(tableauDeBord).toHaveBeenLastCalledWith({ periode: "12m", niveau: "2", classe: "3" }));
    await waitFor(() => expect(screen.getByTestId("filtre-eleve").disabled).toBe(false));
    expect(screen.getByTestId("filtres-actifs").textContent).toMatch(/Niveau : CE1.*Classe : CE1-A/);
    fireEvent.click(screen.getByRole("button", { name: /Retirer le filtre Niveau/ }));
    await waitFor(() => expect(tableauDeBord).toHaveBeenLastCalledWith({ periode: "12m" }));   // la classe dépendait du niveau
    fireEvent.click(screen.getByTestId("filtres-plus"));
    fireEvent.change(screen.getByTestId("filtre-statut"), { target: { value: "annule" } });
    await waitFor(() => expect(tableauDeBord).toHaveBeenLastCalledWith({ periode: "12m", statut: "annule" }));
    fireEvent.click(screen.getByTestId("filtres-reinitialiser"));
    await waitFor(() => expect(tableauDeBord).toHaveBeenLastCalledWith({ periode: "12m" }));
    expect(screen.queryByTestId("filtres-actifs")).toBeNull();
  });

  it("comparaison : variation affichée, « non calculable » sans base ; message 400 explicite", async () => {
    const xof = { ...reponse.devises[1], precedent: ind({ encaisse_minor: 300000 }),
      variations: { encaisse_minor: -30, nb_paiements: 50, attendu_minor: null, restant_minor: null } };
    tableauDeBord.mockImplementation(async (p) => (p.comparer
      ? { data: { ...reponse, devises: [xof], periode_precedente: { du: "2024-12-01", au: "2025-11-30" } } }
      : { data: reponse }));
    monter();
    await screen.findByTestId("ind-encaisse");
    fireEvent.click(screen.getByTestId("comparer"));
    await waitFor(() => expect(screen.getByTestId("ind-encaisse-variation").textContent).toMatch(/-30 % vs période précédente/));
    expect(screen.getByTestId("ind-attendu-variation").textContent).toMatch(/variation non calculable/);
    expect(screen.getByTestId("periode-precedente").textContent).toMatch(/300\s?000/);
    tableauDeBord.mockRejectedValue({ response: { status: 400, data: { detail: "Filtre invalide.", nature: "Valeur inconnue : x." } } });
    fireEvent.click(screen.getByTestId("periode-7j"));
    expect((await screen.findByRole("alert")).textContent).toMatch(/Filtre invalide\. Nature de frais : Valeur inconnue/);
  });

  it("clic sur une barre : détail des paiements de cette case, avec les mêmes filtres", async () => {
    tableauDeBord.mockResolvedValue({ data: reponse });
    detailAPI.mockResolvedValue({ data: { du: "2026-11-01", au: "2026-11-30", total: 1, tronque: false, paiements: [
      { id: 5, date: "2026-11-03", eleve: "Cyril Élève", classe: null, nature_libelle: "Mensualité", mode_libelle: "Carte bancaire",
        montant_minor: 12550, rembourse_minor: 2000, devise: "USD", statut: "confirme" }] } });
    monter();
    await screen.findByTestId("ind-encaisse");
    fireEvent.click(screen.getByTestId("case-2026-11-01"));
    await screen.findByTestId("detail-paiements");
    expect(detailAPI).toHaveBeenCalledWith({ periode: "12m", case: "2026-11-01" });
    expect(screen.getByTestId("detail-total").textContent).toBe("1");
    expect(screen.getByTestId("detail-paiements").textContent).toMatch(/Cyril Élève.*125[.,]50.*remboursé.*20[.,]00.*Confirmé/);
  });

  it("explique l'absence de tarif (lien direct) et signale les données partielles", async () => {
    tableauDeBord.mockResolvedValue({ data: reponse });
    monter();
    await screen.findByTestId("ind-encaisse");
    expect(screen.getByTestId("tarifs-absents").textContent).toMatch(/Aucun échéancier n'est configuré pour cette période/);
    expect(screen.getByTestId("lien-tarifs").getAttribute("href")).toBe("/superadmin/tarifs");
    fireEvent.click(screen.getByTestId("devise-XOF"));
    expect(screen.queryByTestId("tarifs-absents")).toBeNull();
    expect(screen.getByTestId("tarifs-partiels").textContent).toMatch(/4 élève\(s\) actif\(s\) sans tarif applicable sur 80/);
  });
});
