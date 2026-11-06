import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

vi.mock("../../api", () => ({
  remisesAPI: { list: vi.fn(), create: vi.fn(), update: vi.fn(), annuler: vi.fn(), reactiver: vi.fn(), impact: vi.fn() },
  paymentsAPI: { filtres: vi.fn() }, studentsAPI: { list: vi.fn() }, parentsAPI: { list: vi.fn() }, classesAPI: { list: vi.fn() },
  baremesAPI: { list: vi.fn(), importer: vi.fn() },
}));
vi.mock("../../hooks/useEntityContext", () => ({ useAcademyKey: () => "FEBA" }));

import { baremesAPI, remisesAPI, paymentsAPI, studentsAPI, parentsAPI, classesAPI } from "../../api";
import RemisesExonerations from "./RemisesExonerations";
import ImportBareme from "./ImportBareme";

const REGLE = { id: 4, nom: "Fratrie", genre: "remise", categorie: "fratrie", categorie_libelle: "Plusieurs enfants d'une même famille",
  mode: "pourcentage", pourcentage: "15.00", montant_affiche: "15.00 %", perimetre: [], en_vigueur: true, cumulable: true, autorise_par_nom: "Admin" };
const monter = (ui) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter>{ui}</MemoryRouter></QueryClientProvider>);

beforeEach(() => {
  vi.clearAllMocks();
  remisesAPI.list.mockResolvedValue({ data: [REGLE] });
  remisesAPI.annuler.mockResolvedValue({ data: {} });
  remisesAPI.create.mockResolvedValue({ data: {} });
  paymentsAPI.filtres.mockResolvedValue({ data: { annees: [], niveaux: [], classes: [] } });
  [studentsAPI, parentsAPI, classesAPI].forEach((a) => a.list.mockResolvedValue({ data: [] }));
});

describe("Remises et exonérations", () => {
  it("annuler exige un motif ; aucun bouton de suppression", async () => {
    monter(<RemisesExonerations />);
    expect(await screen.findByText("Fratrie")).toBeInTheDocument();
    expect(screen.queryByText(/Supprimer/)).toBeNull();
    vi.spyOn(window, "prompt").mockReturnValueOnce("").mockReturnValueOnce("Erreur de saisie");
    fireEvent.click(screen.getByTestId("regle-etat-4"));
    expect(remisesAPI.annuler).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId("regle-etat-4"));
    await waitFor(() => expect(remisesAPI.annuler).toHaveBeenCalledWith(4, "Erreur de saisie"));
  });

  it("exonération : justification demandée, valeur envoyée au serveur", async () => {
    monter(<RemisesExonerations />);
    fireEvent.click(await screen.findByTestId("genre-exoneration"));
    fireEvent.click(screen.getByTestId("regle-nouvelle"));
    const form = await screen.findByTestId("regle-formulaire");
    expect(form.querySelector("#r-just")).not.toBeNull();
    fireEvent.change(form.querySelector("#r-nom"), { target: { value: "Bourse" } });
    fireEvent.change(form.querySelector("#r-val"), { target: { value: "100" } });
    fireEvent.change(form.querySelector("#r-just"), { target: { value: "Conseil du 4/11" } });
    fireEvent.click(screen.getByTestId("regle-enregistrer"));
    await waitFor(() => expect(remisesAPI.create).toHaveBeenCalledWith(expect.objectContaining({
      nom: "Bourse", genre: "exoneration", pourcentage: "100", justification: "Conseil du 4/11", student: null })));
  });

  it("barème : import seulement après vérification explicite", async () => {
    baremesAPI.list.mockResolvedValue({ data: [{ fichier: "feba.json", annee: "2026-2027", source: "Affiche", annee_trouvee: true,
      a_confirmer: ["Jour exact des tranches"], niveaux_sans_tarif: [], lignes: [{ nature: "inscription", libelle: "Inscription", niveau: null,
        montant: "10 000 FCFA", echeances: [], action: "creer" }] }] });
    baremesAPI.importer.mockResolvedValue({ data: { crees: 1 } });
    monter(<ImportBareme />);
    fireEvent.click(await screen.findByTestId("bareme-apercu"));
    expect(screen.getByText("Jour exact des tranches")).toBeInTheDocument();
    expect(screen.getByTestId("bareme-importer")).toBeDisabled();
    fireEvent.click(screen.getByTestId("bareme-verifie"));
    fireEvent.click(screen.getByTestId("bareme-importer"));
    await waitFor(() => expect(baremesAPI.importer).toHaveBeenCalledWith("feba.json"));
  });
});
