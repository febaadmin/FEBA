/**
 * P0 — Fiche de renseignements FEBA FHA : sexe de l'enfant.
 *
 * Le champ manquait à l'étape 1/12. On vérifie le parcours côté navigateur :
 * affichage FR/EN, validation bloquante, brouillon local sauvegardé puis
 * restauré, récapitulatif, et valeur réellement transmise au serveur.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

vi.mock("./siteApi", () => ({
  siteAPI: { sendFhaEnrollment: vi.fn() },
}));
import { siteAPI } from "./siteApi";
import FhaEnrollPage from "./pages/FhaEnrollPage";

const DRAFT_KEY = "feba-fha-enroll-draft";

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <FhaEnrollPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const COMPLETE = {
  child_first_name: "Shakirath", child_last_name: "Bouari",
  child_birth_date: "2012-05-17", child_gender: "F",
  parent1_first_name: "Awa", parent1_last_name: "Bouari",
  parent1_email: "awa@test.io", parent1_phone: "+1 718 555 0100",
  consent_rules: true, consent_privacy: true,
  consent_data_processing: true, consent_parental_authorization: true,
};

beforeEach(() => {
  cleanup();
  vi.clearAllMocks();
  localStorage.clear();
  localStorage.setItem("feba-fha-lang", "fr");
});

describe("Fiche FHA - sexe de l'enfant", () => {
  it("affiche le champ Sexe obligatoire avec Féminin et Masculin", () => {
    renderPage();
    const select = screen.getByTestId("child-gender");
    const options = [...select.options].map((o) => [o.value, o.textContent]);
    expect(options).toEqual([["", "Choisir"], ["F", "Féminin"], ["M", "Masculin"]]);
    expect(screen.getByText("Sexe")).toBeTruthy();
  });

  it("est traduit en anglais", () => {
    localStorage.setItem("feba-fha-lang", "en");
    renderPage();
    const select = screen.getByTestId("child-gender");
    expect([...select.options].map((o) => o.textContent)).toEqual(["Select", "Female", "Male"]);
    expect(screen.getByText("Sex")).toBeTruthy();
  });

  it("bloque le passage à l'étape 2 tant que le sexe n'est pas choisi", () => {
    localStorage.setItem(DRAFT_KEY, JSON.stringify({ ...COMPLETE, child_gender: "" }));
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /Suivant/ }));
    expect(screen.getByText("Sexe obligatoire.")).toBeTruthy();
    expect(screen.getByText(/Étape 1\/12/)).toBeTruthy();
    fireEvent.change(screen.getByTestId("child-gender"), { target: { value: "M" } });
    fireEvent.click(screen.getByRole("button", { name: /Suivant/ }));
    expect(screen.getByText(/Étape 2\/12/)).toBeTruthy();
  });

  it("enregistre le choix dans le brouillon et le restaure au rechargement", () => {
    renderPage();
    fireEvent.change(screen.getByTestId("child-gender"), { target: { value: "F" } });
    expect(JSON.parse(localStorage.getItem(DRAFT_KEY)).child_gender).toBe("F");
    cleanup();
    renderPage();
    expect(screen.getByTestId("child-gender").value).toBe("F");
  });

  it("transmet le sexe au serveur et l'affiche dans le récapitulatif", async () => {
    siteAPI.sendFhaEnrollment.mockResolvedValue({
      data: { reference: "FHA-2026-0042", detail: "Fiche reçue." },
    });
    localStorage.setItem(DRAFT_KEY, JSON.stringify(COMPLETE));
    renderPage();
    for (let i = 0; i < 12; i += 1) {
      fireEvent.click(screen.getByRole("button", { name: /Suivant|Récapitulatif/ }));
    }
    const recap = screen.getByText("Sexe").closest("div");
    expect(recap.textContent).toContain("Féminin");
    fireEvent.click(screen.getByRole("button", { name: /Envoyer ma fiche/ }));
    await waitFor(() => expect(siteAPI.sendFhaEnrollment).toHaveBeenCalledTimes(1));
    expect(siteAPI.sendFhaEnrollment.mock.calls[0][0].child_gender).toBe("F");
    await screen.findByText("FHA-2026-0042");
    expect(localStorage.getItem(DRAFT_KEY)).toBeNull();
  });

  it("un brouillon antérieur au champ (clé absente) est repris sans valeur inventée", () => {
    const legacy = { ...COMPLETE };
    delete legacy.child_gender;
    localStorage.setItem(DRAFT_KEY, JSON.stringify(legacy));
    renderPage();
    expect(screen.getByTestId("child-gender").value).toBe("");
    // Le reste du brouillon est bien repris…
    expect(screen.getByDisplayValue("Shakirath")).toBeTruthy();
    // … mais la famille doit choisir avant de continuer.
    fireEvent.click(screen.getByRole("button", { name: /Suivant/ }));
    expect(screen.getByText("Sexe obligatoire.")).toBeTruthy();
    expect(siteAPI.sendFhaEnrollment).not.toHaveBeenCalled();
  });
});
