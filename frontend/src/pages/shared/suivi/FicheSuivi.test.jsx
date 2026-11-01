import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import FicheSuivi from "./FicheSuivi";

const vide = { has_data: false };
const fiche = {
  eleve: { id: 1, nom: "Élève Test", matricule: "M1", classe: "CM1" },
  progression: { ...vide, valeur: null, composantes: {} },
  assiduite: { ...vide, taux: null },
  participation: { ...vide, moyenne: null, nombre: 0 },
  competences: { ...vide, lignes: [], rang_max: 4 },
  evaluations: { ...vide, lignes: [], moyenne: null },
  objectifs: { ...vide, par_statut: {}, total: 0 },
  resultats_historiques: { ...vide, lignes: [] },
  plans_actifs: 0,
};
vi.mock("../../../api", () => {
  const liste = () => Promise.resolve({ data: { results: [] } });
  return {
    suiviAPI: new Proxy({ fiche: () => Promise.resolve({ data: fiche }), niveaux: () => Promise.resolve({ data: [] }) }, { get: (o, k) => o[k] || liste }),
    subjectsAPI: { list: liste },
  };
});
let role = "teacher";
vi.mock("../../../hooks/useAuth", () => ({ useAuth: () => ({ user: { role } }) }));

function afficher() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={["/x/suivi/1"]}><Routes><Route path="/x/suivi/:id" element={<FicheSuivi />} /></Routes></MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("FicheSuivi", () => {
  it("sans donnée, ne présente aucun chiffre inventé", async () => {
    afficher();
    expect(await screen.findByText("Élève Test")).toBeTruthy();
    expect(screen.getAllByText("Données insuffisantes").length).toBe(6);
    expect(document.body.textContent).not.toMatch(/\d+ %/);
  });
  it("sans action de saisie pour une famille", async () => {
    role = "parent";
    afficher();
    await screen.findByText("Élève Test");
    expect(screen.queryByRole("button", { name: /Évaluer/ })).toBeNull();
  });
});
