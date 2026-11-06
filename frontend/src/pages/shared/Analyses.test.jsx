import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import Analyses, { changer, parametres, VIDES } from "./Analyses";
import { traducteur } from "../../components/analytics/presentation";
import { setLang } from "../../i18n";

const api = {};
vi.mock("../../api", () => ({ analyticsAPI: new Proxy({}, { get: (_, k) => (...a) => (api[k] ||= vi.fn())(...a) }) }));
const auth = { user: { role: "admin" } };
vi.mock("../../hooks/useAuth", () => ({ useAuth: () => auth }));
vi.mock("../../hooks/useEntityContext", () => ({ useAcademyKey: () => "1" }));
vi.mock("recharts", async (orig) => {
  const vrai = await orig();
  return { ...vrai, ResponsiveContainer: ({ children }) => <div style={{ width: 500, height: 200 }}>{children}</div> };
});

const options = { academie: { id: 1, nom: "FEBA" }, annees: [{ id: 3, nom: "2026-2027", en_cours: true }], periodes: [{ id: "T1", nom: "Trimestre 1" }],
  cycles: [], niveaux: [{ id: 2, nom: "CE1" }], classes: [{ id: 5, nom: "CE1-A" }, { id: 6, nom: "CE1-B" }], matieres: [],
  enseignants: [{ id: 9, nom: "Prof Un" }, { id: 10, nom: "Prof Deux" }], eleves: [] };
const ensemble = { annee: { id: 3, nom: "2026-2027" }, bareme: 10, bareme_mixte: false, seuil_pourcent: 50,
  kpi: { inscrits: 78, eleves_actifs: 79, eleves_notes: 30, notes: 600, moyenne: 6.4, mediane: 6.3, taux_reussite: 100,
    objectif_atteint: 30, a_accompagner: 0, taux_presence: null, appels: 0 },
  par_cycle: [{ cycle: "primaire", inscrits: 60 }], par_niveau: [], par_genre: {}, repartition: [{ de: 0, a: 2, eleves: 0 }],
  progression: [{ periode: "T1", moyenne: 6.4 }], classes: [{ id: 5, nom: "CE1-A", moyenne: 6.6, taux_reussite: 100, eleves_notes: 6 }],
  matieres_plus_hautes: [], matieres_difficultes: [],
  limites: [{ texte: "Aucun appel enregistré pour cette sélection : la présence ne peut pas être mesurée.", params: {} },
    { texte: "{n} élève(s) actif(s) sans inscription pour cette année ne sont pas comptés dans les effectifs.", params: { n: 1 } }] };
const AVERTISSEMENT = "Ces chiffres décrivent les notes attribuées et les résultats des élèves, pas la qualité d'un enseignement : le niveau de départ des élèves, l'effectif, la matière, le nombre et le type d'évaluations diffèrent d'une classe à l'autre. Ils ne permettent aucune conclusion sur un enseignant.";
const profil = (id, nom) => ({ id, nom, classes: ["CE1-A"], matieres: ["Maths"], eleves_evalues: 6, notes: 12, moyenne: 7, ecart_type: 1,
  taux_reussite: 100, repartition: [{ de: 0, a: 2, eleves: 0 }], evolution: [], affectations_sans_note: 0, detail: [] });
const monter = () => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter><Analyses /></MemoryRouter></QueryClientProvider>);

describe("centre de pilotage", () => {
  beforeEach(() => {
    for (const k of Object.keys(api)) delete api[k];
    setLang("fr");
    try { sessionStorage.clear(); } catch { /* stockage indisponible */ }
    auth.user = { role: "admin" };
    api.filtres = vi.fn().mockResolvedValue({ data: options });
    api.vueEnsemble = vi.fn().mockResolvedValue({ data: ensemble });
    api.enseignantsProfils = vi.fn(async (p) => ({ data: { bareme: 10, avertissement: AVERTISSEMENT,
      profils: (p.enseignant || "9").split(",").map((id) => profil(Number(id), id === "9" ? "Prof Un" : "Prof Deux")) } }));
  });

  it("paramètres : listes jointes ; un choix de structure efface ceux qui en dépendent", () => {
    expect(parametres(VIDES)).toEqual({});
    expect(parametres({ ...VIDES, classe: ["5", "6"], type_evaluation: ["examen"], periode: "T1" }))
      .toEqual({ classe: "5,6", type_evaluation: "examen", periode: "T1" });
    const f = { ...VIDES, niveau: "2", classe: ["5"], eleve: "8", matiere: ["4"], periode: "T1" };
    expect(changer(f, "niveau", "3")).toMatchObject({ niveau: "3", classe: [], eleve: "", matiere: [], periode: "T1" });
    expect(changer(f, "classe", ["6"])).toMatchObject({ classe: ["6"], eleve: "", matiere: ["4"] });
  });

  it("présentation : libellés seulement", () => {
    expect(traducteur("en")("Taux de réussite")).toBe("Success rate");
    expect(traducteur("bi")("Taux de réussite")).toBe("Taux de réussite / Success rate");
  });

  it("vue d'ensemble : KPI explicites, limites traduites, période et population ; anglais sans nouvelle requête", async () => {
    monter();
    expect((await screen.findByTestId("kpi-inscrits")).textContent).toMatch(/Élèves inscrits78/);
    expect(screen.getByTestId("kpi-presence").textContent).toMatch(/Non mesurable.*aucun appel enregistré/);
    expect(screen.getByTestId("analyse-limites").textContent).toMatch(/1 élève\(s\) actif\(s\) sans inscription/);
    expect(screen.getByTestId("ens-classes").textContent).toMatch(/2026-2027 · toutes périodes · 1 classes · Unité : moyenne sur 10/);
    expect(screen.getByTestId("ens-progression").textContent).toMatch(/Une seule période notée/);
    // Plus de second sélecteur de langue : les actions utiles le remplacent.
    expect(screen.queryByTestId("presentation-en")).toBeNull();
    expect(screen.getByTestId("analyse-imprimer")).toBeInTheDocument();
    expect(screen.getByTestId("analyse-exporter")).toBeInTheDocument();
  });

  it("actions : lien avec onglet et filtres, relu à l'ouverture ; valeurs inconnues ignorées", async () => {
    const { lienAnalyse, lireLien } = await import("../../components/analytics/ActionsAnalyse");
    const VIDES = { annee: "", classe: [], genre: "" };
    const url = lienAnalyse("https://x/admin/analyses", "classes", { annee: "3", classe: ["5", "6"], genre: "" });
    expect(url).toBe("https://x/admin/analyses?onglet=classes&filtres=%7B%22annee%22%3A%223%22%2C%22classe%22%3A%5B%225%22%2C%226%22%5D%7D");
    const lu = lireLien(url.split("?")[1], VIDES, ["ensemble", "classes"]);
    expect(lu).toEqual({ onglet: "classes", filtres: { annee: "3", classe: ["5", "6"], genre: "" } });
    expect(lireLien("onglet=pirate&filtres=%7B%22inconnu%22%3A1%2C%22annee%22%3A5%7D", VIDES, ["ensemble"]))
      .toEqual({ onglet: null, filtres: { annee: "", classe: [], genre: "" } });
  });

  it("export CSV des tableaux du rapport, avec titres et protection des formules", async () => {
    const { tableauxEnCsv } = await import("../../utils/exportTableaux");
    const div = document.createElement("div");
    div.innerHTML = '<figure><figcaption><p>Moyennes</p></figcaption><table><tr><th>Classe</th><th>Moyenne</th></tr><tr><td>=HACK()</td><td>7,5 / 10</td></tr></table></figure>';
    const { csv, tableaux } = tableauxEnCsv(div, ["En-tête"]);
    expect(tableaux).toBe(1);
    expect(csv).toContain("Moyennes\nClasse;Moyenne\n'=HACK();7,5 / 10");
  });

  it("sélection multiple de classes : requête combinée, puce lisible, réinitialisation", async () => {
    monter();
    await screen.findByTestId("kpi-inscrits");
    fireEvent.click(screen.getByTestId("af-classe"));
    fireEvent.click(screen.getByTestId("af-classe-5"));
    fireEvent.click(screen.getByTestId("af-classe-6"));
    await waitFor(() => expect(api.vueEnsemble).toHaveBeenLastCalledWith({ classe: "5,6" }));
    expect(screen.getByTestId("af-actifs").textContent).toMatch(/Classes : CE1-A, CE1-B/);
    expect(screen.getByTestId("af-classe").textContent).toMatch(/2 sélectionnés/);
    fireEvent.click(screen.getByTestId("af-reinitialiser"));
    await waitFor(() => expect(api.vueEnsemble).toHaveBeenLastCalledWith({}));
  });

  it("enseignants : avertissement, choix visuel, comparaison descriptive de deux profils", async () => {
    monter();
    await screen.findByTestId("kpi-inscrits");
    fireEvent.click(screen.getByTestId("onglet-enseignants"));
    expect((await screen.findByTestId("avertissement-enseignants")).textContent).toMatch(/aucune conclusion/);
    fireEvent.click(screen.getByTestId("ens-choix-9"));
    fireEvent.click(screen.getByTestId("ens-choix-10"));
    await waitFor(() => expect(api.enseignantsProfils).toHaveBeenLastCalledWith({ enseignant: "9,10" }));
    expect(await screen.findByTestId("ens-comparaison")).toBeTruthy();
    expect(within(screen.getByTestId("ens-profil-9")).getByText("Prof Un")).toBeTruthy();
    expect(screen.getByTestId("ens-profil-10")).toBeTruthy();
  });

  it("enseignant connecté : pas de filtre ni de choix d'enseignant", async () => {
    auth.user = { role: "teacher" };
    monter();
    await screen.findByTestId("kpi-inscrits");
    expect(screen.queryByTestId("af-enseignant")).toBeNull();
    fireEvent.click(screen.getByTestId("onglet-enseignants"));
    await screen.findByTestId("avertissement-enseignants");
    expect(screen.queryByTestId("ens-selection")).toBeNull();
  });

  it("erreur explicite (super administrateur sans académie)", async () => {
    api.filtres = vi.fn().mockRejectedValue({ response: { status: 400, data: { academie: ["Choisissez une académie dans le sélecteur."] } } });
    monter();
    expect((await screen.findByTestId("analyse-erreur")).textContent).toMatch(/Choisissez une académie/);
  });
});
