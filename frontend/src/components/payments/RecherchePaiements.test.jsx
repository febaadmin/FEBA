import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import RecherchePaiements, { FILTRES_PAGE, parametresPage } from "./RecherchePaiements";
import { setLang } from "../../i18n";

const recherche = vi.fn();
const filtresAPI = vi.fn();
const exportXlsx = vi.fn();
vi.mock("../../api", () => ({ paymentsAPI: {
  recherche: (...a) => recherche(...a), filtres: (...a) => filtresAPI(...a), exportXlsx: (...a) => exportXlsx(...a),
} }));
const academie = { academyKey: "1" };
vi.mock("../../context/AcademyContext", () => ({ useAcademy: () => academie }));

const paiement = (id, o = {}) => ({ id, reference_number: `PAY-${id}`, student_name: "Alice Élève", student_matricule: "M-1",
  student_class: "CE1-A", payment_type: "mensualite", payment_type_label: "Mensualité", payment_method: "cash",
  payment_method_label: "Espèces", amount_minor: 150000, currency: "XOF", is_confirmed: true, has_time: true,
  paid_at_display: "20/09/2026 10:00", payment_date: "2026-09-20", ...o });
const reponse = (n = 2, page = [paiement(1), paiement(2, { is_confirmed: false, amount_minor: 40000 })]) => ({ data: {
  count: n, results: page,
  totaux: [{ devise: "XOF", confirme_minor: 150000, nb_confirmes: 1, annule_minor: 40000, nb_annules: 1, rembourse_minor: 0, net_minor: 150000 }],
} });
const monter = (props = {}) => render(
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <RecherchePaiements onOuvrir={vi.fn()} onRecu={vi.fn()} onSupprimer={vi.fn()} onSupprimerSelection={vi.fn()} rafraichir={0} {...props} />
  </QueryClientProvider>);

describe("page Paiements : recherche et filtres", () => {
  beforeEach(() => {
    recherche.mockReset(); filtresAPI.mockReset(); exportXlsx.mockReset(); setLang("fr");
    recherche.mockResolvedValue(reponse());
    filtresAPI.mockResolvedValue({ data: { structure_disponible: true, annees: [{ id: 3, nom: "2026-2027" }], cycles: [],
      niveaux: [], classes: [{ id: 5, nom: "CE1-A" }], eleves: [],
      natures: [{ id: "mensualite", nom: "Mensualité", nb: 3 }, { id: "cantine", nom: "Cantine", nb: 1 }],
      modes: [{ id: "cash", nom: "Espèces", nb: 4 }] } });
  });

  it("paramètres : listes jointes, toutes années quand une période est choisie, dates seulement en personnalisée", () => {
    expect(parametresPage(FILTRES_PAGE, "", "-date", 1, 25)).toEqual({ page: 1, page_size: 25, tri: "-date" });
    expect(parametresPage({ ...FILTRES_PAGE, periode: "mois", du: "2026-01-01", nature: ["cantine", "mensualite"] }, " bob ", "montant", 2, 50))
      .toEqual({ page: 2, page_size: 50, tri: "montant", all_years: 1, periode: "mois", nature: "cantine,mensualite", q: "bob" });
    expect(parametresPage({ ...FILTRES_PAGE, periode: "perso", du: "2026-01-01", au: "2026-01-31", annee: "3" }, "", "-date", 1, 25))
      .toEqual({ page: 1, page_size: 25, tri: "-date", periode: "perso", du: "2026-01-01", au: "2026-01-31", annee: "3" });
  });

  it("affiche le nombre de résultats et le récapitulatif de toute la sélection", async () => {
    monter();
    await screen.findByTestId("paiement-1");
    expect(screen.getByTestId("paiements-total").textContent).toMatch(/2 paiement\(s\)/);
    expect(screen.getByTestId("totaux-XOF").textContent).toMatch(/150[\s  .]?000.*encaissé net.*1 confirmé.*1 annulé/);
    expect(screen.getByTestId("paiement-2").textContent).toMatch(/Annulé/);
  });

  it("recherche différée : une requête après la pause de saisie, pas une par caractère", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      monter();
      await screen.findByTestId("paiements-total");
      const avant = recherche.mock.calls.length;
      const champ = screen.getByTestId("paiements-recherche");
      for (const v of ["e", "eb", "ebe", "ebene"]) fireEvent.change(champ, { target: { value: v } });
      await act(async () => { vi.advanceTimersByTime(400); });
      await waitFor(() => expect(recherche).toHaveBeenLastCalledWith(expect.objectContaining({ q: "ebene" })));
      const qs = recherche.mock.calls.slice(avant).map(([p]) => p.q);
      expect(qs.filter(Boolean)).toEqual(["ebene"]);
    } finally {
      vi.useRealTimers();
    }
  });

  it("filtres combinables, puces, tri, réinitialisation et export avec les mêmes filtres", async () => {
    monter();
    await screen.findByTestId("paiements-total");
    fireEvent.change(screen.getByTestId("pf-periode"), { target: { value: "mois" } });
    fireEvent.click(screen.getByTestId("pf-nature"));
    fireEvent.click(screen.getByTestId("pf-nature-cantine"));
    fireEvent.change(screen.getByTestId("pf-statut"), { target: { value: "confirme" } });
    fireEvent.click(screen.getByTestId("tri-montant"));
    await waitFor(() => expect(recherche).toHaveBeenLastCalledWith({ page: 1, page_size: 25, tri: "montant", all_years: 1,
      periode: "mois", nature: "cantine", statut: "confirme" }));
    expect(screen.getByTestId("pf-puce-nature").textContent).toMatch(/Type de paiement : Cantine/);
    expect(screen.getByTestId("pf-puce-periode").textContent).toMatch(/Ce mois/);
    fireEvent.click(screen.getByTestId("tri-montant"));
    await waitFor(() => expect(recherche).toHaveBeenLastCalledWith(expect.objectContaining({ tri: "-montant" })));
    exportXlsx.mockResolvedValue({ data: new Blob(["x"]) });
    global.URL.createObjectURL = vi.fn(() => "blob:x");
    global.URL.revokeObjectURL = vi.fn();
    fireEvent.click(screen.getByTestId("paiements-export"));
    await waitFor(() => expect(exportXlsx).toHaveBeenCalledWith({ tri: "-montant", all_years: 1, periode: "mois",
      nature: "cantine", statut: "confirme" }));
    fireEvent.click(screen.getByTestId("pf-reinitialiser"));
    await waitFor(() => expect(recherche).toHaveBeenLastCalledWith({ page: 1, page_size: 25, tri: "-montant" }));
  });

  it("pagination stable : la page suivante garde les filtres, un nouveau filtre ramène à la page 1", async () => {
    recherche.mockResolvedValue(reponse(60));
    monter();
    await screen.findByTestId("paiement-1");
    fireEvent.click(screen.getByTestId("page-suivante"));
    await waitFor(() => expect(recherche).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2 })));
    expect(screen.getByTestId("paiements-pagination").textContent).toMatch(/26–50 sur 60/);
    fireEvent.change(screen.getByTestId("pf-statut"), { target: { value: "annule" } });
    await waitFor(() => expect(recherche).toHaveBeenLastCalledWith(expect.objectContaining({ page: 1, statut: "annule" })));
  });

  it("erreur de filtre explicite (400) et sélection vide expliquée", async () => {
    recherche.mockRejectedValueOnce({ response: { status: 400, data: { detail: "Filtre invalide.", montant: "Montant invalide." } } });
    monter();
    expect((await screen.findByTestId("paiements-erreur")).textContent).toMatch(/Filtre invalide\. Montant exact : Montant invalide/);
    recherche.mockResolvedValue({ data: { count: 0, results: [], totaux: [] } });
    fireEvent.change(screen.getByTestId("pf-statut"), { target: { value: "annule" } });
    expect((await screen.findByTestId("paiements-vide")).textContent).toMatch(/Aucun paiement ne correspond/);
  });
});
