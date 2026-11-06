/**
 * Situation financière (clôture) : état « non calculable », KPI expliqués, trois vues,
 * filtres transmis au serveur, clic sur une classe → vue par élève filtrée, fiche, export.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

vi.mock("recharts", async () => {
  const vrai = await vi.importActual("recharts");
  return { ...vrai, ResponsiveContainer: ({ children }) => <div style={{ width: 600, height: 200 }}>{children}</div> };
});
vi.mock("../../api", () => ({
  paymentsAPI: { situation: vi.fn(), situationEleve: vi.fn(), situationExport: vi.fn(), filtres: vi.fn() },
}));
vi.mock("../../hooks/useAuth", () => ({ useAuth: () => ({ user: { role: "admin" } }) }));
vi.mock("../../hooks/useEntityContext", () => ({ useAcademyKey: () => "FEBA" }));
vi.mock("../../context/AcademyContext", () => ({ useAcademy: () => ({ isAllAcademies: false }) }));

import { paymentsAPI } from "../../api";
import SituationFinanciere from "./SituationFinanciere";

const tot = (o = {}) => ({ theorique_minor: 679300, theorique_affiche: "679 300 FCFA", remises_minor: 32980, remises_affiche: "32 980 FCFA",
  exonerations_minor: 0, exonerations_affiche: "0 FCFA", net_minor: 646320, net_affiche: "646 320 FCFA", attendu_affiche: "646 320 FCFA",
  paye_minor: 150000, paye_affiche: "150 000 FCFA", restant_minor: 496320, restant_affiche: "496 320 FCFA", retard_minor: 210000,
  retard_affiche: "210 000 FCFA", taux_recouvrement: 23.2, taux_recouvrement_echu: 41.7, encaisse_total_affiche: "180 000 FCFA", ...o });
const ACAD = (o = {}) => ({
  academie: { id: 1, nom: "FEBA" }, devise: "XOF", date_reference: "2026-12-15", calculable: true, echeancier_configure: true,
  raison_non_calculable: null, totaux: tot(), anomalies: [],
  kpi: { effectif: 79, eleves_concernes: 2, eleves_soldes: 0, eleves_partiels: 1, eleves_aucun_paiement: 1, eleves_exoneres: 0, eleves_en_retard: 2 },
  groupes: [{ id: 5, nom: "CE1-A", niveau: "CE1", eleves: 1, eleves_a_jour: 0, eleves_en_retard: 1, ...tot() }],
  eleves: [{ id: 11, matricule: "M-11", nom: "Alice Élève", classe: "CE1-A", niveau: "CE1", statut: "partiel", statut_libelle: "Paiement partiel",
    en_retard: true, jours_retard: 15, prochaine_echeance: null, ...tot() }],
  eleves_total: 1, page: 1, pages: 1,
  graphiques: { repartition: [{ cle: "encaisse", montant_minor: 150000 }, { cle: "a_echoir", montant_minor: 286320 }, { cle: "retard", montant_minor: 210000 }],
    statuts: [{ cle: "solde", libelle: "Soldé", nombre: 0 }, { cle: "partiel", libelle: "Paiement partiel", nombre: 1 }],
    encaissements_mensuels: [{ mois: "2026-09", montant_minor: 150000 }], ajustements: [] },
  ...o,
});

const monter = () => render(
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter><SituationFinanciere /></MemoryRouter>
  </QueryClientProvider>,
);

beforeEach(() => {
  vi.clearAllMocks();
  paymentsAPI.filtres.mockResolvedValue({ data: { annees: [{ id: 1, nom: "2026-2027" }], cycles: [], niveaux: [{ id: 3, nom: "CE1" }], classes: [{ id: 5, nom: "CE1-A" }] } });
  paymentsAPI.situation.mockResolvedValue({ data: { academies: [ACAD()] } });
  paymentsAPI.situationEleve.mockResolvedValue({ data: { eleve: { matricule: "M-11" }, totaux: tot(), echeancier_configure: false, tarifs: [], echeances: [], paiements: [], historique: [], explication: null } });
});

describe("Situation financière", () => {
  it("sans tarif : non calculable, jamais un montant nul", async () => {
    paymentsAPI.situation.mockResolvedValue({ data: { academies: [ACAD({ calculable: false, raison_non_calculable: "Aucun tarif avec échéances n'est configuré pour cette académie : le montant attendu et le reste à payer ne peuvent pas être calculés (ce n'est pas un montant nul)." })] } });
    monter();
    expect(await screen.findByTestId("situation-sans-tarif")).toBeInTheDocument();
    expect(within(screen.getByTestId("kpi-net")).getByText("Non calculable")).toBeInTheDocument();
    expect(screen.queryByTestId("situation-graphiques")).toBeNull();
  });

  it("KPI expliqués et taux de recouvrement", async () => {
    monter();
    const kpi = await screen.findByTestId("situation-kpi");
    expect(within(kpi).getByText("646 320 FCFA")).toBeInTheDocument();
    expect(within(screen.getByTestId("kpi-taux")).getByText("23.2 %")).toBeInTheDocument();
    fireEvent.click(within(screen.getByTestId("kpi-taux")).getByRole("button", { name: "Explication" }));
    expect(screen.getByRole("tooltip").textContent).toMatch(/encaissé divisé par le montant net attendu/);
  });

  it("clic sur une classe : vue par élève filtrée sur cette classe", async () => {
    monter();
    const ligne = await screen.findByText("CE1-A", { selector: "button" });
    fireEvent.click(ligne);
    await waitFor(() => expect(paymentsAPI.situation).toHaveBeenLastCalledWith(expect.objectContaining({ groupe: "eleve", classe: "5", page: 1 })));
    expect(await screen.findByTestId("situation-eleves")).toBeInTheDocument();
  });

  it("filtres transmis au serveur et fiche de l'élève", async () => {
    monter();
    fireEvent.click(await screen.findByTestId("groupe-eleve"));
    fireEvent.change(screen.getByTestId("filtre-statut"), { target: { value: "en_retard" } });
    await waitFor(() => expect(paymentsAPI.situation).toHaveBeenLastCalledWith(expect.objectContaining({ statut: "en_retard", groupe: "eleve" })));
    fireEvent.click(await screen.findByTestId("eleve-11"));
    expect(await screen.findByTestId("releve-eleve")).toBeInTheDocument();
    expect(paymentsAPI.situationEleve).toHaveBeenCalledWith(11);
  });

  it("export CSV avec les filtres actifs", async () => {
    paymentsAPI.situationExport.mockResolvedValue({ data: new Blob(["a;b"]) });
    globalThis.URL.createObjectURL = vi.fn(() => "blob:x");
    globalThis.URL.revokeObjectURL = vi.fn();
    monter();
    fireEvent.change(await screen.findByTestId("filtre-nature"), { target: { value: "mensualite" } });
    fireEvent.click(await screen.findByTestId("situation-export"));
    await waitFor(() => expect(paymentsAPI.situationExport).toHaveBeenCalledWith({ nature: "mensualite" }));
  });
});
