import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Analyses, { changer, parametres, VIDES } from "./Analyses";
import { traducteur } from "../../components/analytics/presentation";
import { setLang } from "../../i18n";

const api = { filtres: vi.fn(), resultats: vi.fn(), enseignants: vi.fn(), effectifs: vi.fn(), matieres: vi.fn(), presences: vi.fn() };
vi.mock("../../api", () => ({ analyticsAPI: new Proxy({}, { get: (_, k) => (...a) => api[k](...a) }) }));
const auth = { user: { role: "admin" } };
vi.mock("../../hooks/useAuth", () => ({ useAuth: () => auth }));
vi.mock("../../hooks/useEntityContext", () => ({ useAcademyKey: () => "1" }));
vi.mock("recharts", async (orig) => {
  const vrai = await orig();
  return { ...vrai, ResponsiveContainer: ({ children }) => <div style={{ width: 500, height: 200 }}>{children}</div> };
});

const options = { academie: { id: 1, nom: "FEBA" }, annees: [{ id: 3, nom: "2026-2027" }], periodes: [{ id: "T1", nom: "Trimestre 1" }],
  cycles: [], niveaux: [{ id: 2, nom: "CE1" }], classes: [{ id: 5, nom: "CE1-A" }], matieres: [], enseignants: [{ id: 9, nom: "Prof Un" }], eleves: [] };
const resultats = { bareme: 10, bareme_mixte: false, seuil_pourcent: 50, min_evaluations: 3,
  synthese: { eleves_notes: 3, notes: 7, moyenne: 5.22, mediane: 5, ecart_type: 1.1, minimum: 3.67, maximum: 7, taux_reussite: 66.7 },
  repartition: [{ de: 0, a: 2, eleves: 0 }], maitrise: [{ min_pourcent: 80, libelle_fr: "Très bien", libelle_en: "Very good", eleves: 1 }],
  par_classe: [{ id: 5, nom: "CE1-A", eleves_notes: 2, notes: 5, moyenne: 5.33, taux_reussite: 50 }],
  progression: [{ periode: "T1", moyenne: 5.33 }], listes: null, listes_indisponibles: "x" };
const monter = () => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><Analyses /></QueryClientProvider>);

describe("centre d'analyse", () => {
  beforeEach(() => {
    Object.values(api).forEach((f) => f.mockReset());
    setLang("fr");
    try { sessionStorage.clear(); } catch { /* */ }
    auth.user = { role: "admin" };
    api.filtres.mockResolvedValue({ data: options });
    api.resultats.mockResolvedValue({ data: resultats });
    api.enseignants.mockResolvedValue({ data: { bareme: 10, avertissement: "Ces chiffres décrivent les notes attribuées et les résultats des élèves, pas la qualité d'un enseignement : le niveau de départ des élèves, l'effectif, la matière, le nombre et le type d'évaluations diffèrent d'une classe à l'autre. Ils ne permettent aucune conclusion sur un enseignant.", lignes: [] } });
  });

  it("filtres : seulement les valeurs choisies ; un choix efface ceux qui en dépendent", () => {
    expect(parametres(VIDES)).toEqual({});
    const f = { ...VIDES, niveau: "2", classe: "5", eleve: "8", matiere: "4", periode: "T1" };
    expect(changer(f, "niveau", "3")).toMatchObject({ niveau: "3", classe: "", eleve: "", matiere: "", periode: "T1" });
    expect(changer(f, "classe", "6")).toMatchObject({ classe: "6", eleve: "", matiere: "4" });
  });

  it("le mode de présentation change les libellés, pas les données", () => {
    expect(traducteur("fr")("Taux de réussite")).toBe("Taux de réussite");
    expect(traducteur("en")("Taux de réussite")).toBe("Success rate");
    expect(traducteur("bi")("Taux de réussite")).toBe("Taux de réussite / Success rate");
  });

  it("résultats, puis présentation anglaise et bilingue avec les mêmes chiffres et la même requête", async () => {
    monter();
    expect((await screen.findByTestId("res-reussite")).textContent).toMatch(/Taux de réussite66.7 %/);
    expect(api.resultats).toHaveBeenLastCalledWith({ seuil: 50 });
    const appels = api.resultats.mock.calls.length;
    fireEvent.click(screen.getByTestId("presentation-en"));
    expect(screen.getByTestId("res-reussite").textContent).toMatch(/Success rate66.7 %/);
    fireEvent.click(screen.getByTestId("presentation-bi"));
    expect(screen.getByTestId("res-reussite").textContent).toMatch(/Taux de réussite \/ Success rate66.7 %/);
    expect(screen.getByTestId("res-maitrise").textContent).toMatch(/Très bien \/ Very good/);
    expect(api.resultats.mock.calls.length).toBe(appels);           // aucune nouvelle requête
    fireEvent.change(screen.getByTestId("af-niveau"), { target: { value: "2" } });
    await waitFor(() => expect(api.resultats).toHaveBeenLastCalledWith({ niveau: "2", seuil: 50 }));
    expect(screen.getByTestId("af-actifs").textContent).toMatch(/CE1/);
  });

  it("enseignant : pas de filtre « Enseignant » ; onglet Enseignants avec avertissement", async () => {
    auth.user = { role: "teacher" };
    monter();
    await screen.findByTestId("res-reussite");
    expect(screen.queryByTestId("af-enseignant")).toBeNull();
    fireEvent.click(screen.getByTestId("onglet-enseignants"));
    expect((await screen.findByTestId("avertissement-enseignants")).textContent).toMatch(/aucune conclusion/);
  });

  it("erreur explicite (super administrateur sans académie)", async () => {
    api.filtres.mockRejectedValue({ response: { status: 400, data: { academie: ["Choisissez une académie dans le sélecteur."] } } });
    monter();
    expect((await screen.findByTestId("analyse-erreur")).textContent).toMatch(/Choisissez une académie/);
  });
});
