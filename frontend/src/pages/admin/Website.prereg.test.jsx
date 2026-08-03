/**
 * P2 — Le tableau des préinscriptions et la fiche complète du dossier.
 *
 * LE DÉFAUT REPRODUIT
 * -------------------
 * Le tableau affichait six colonnes : date, enfant, niveau, parent,
 * téléphone, statut. L'e-mail, le WhatsApp, l'âge, l'année scolaire, le
 * message et l'adresse n'apparaissaient nulle part — ni ici, ni ailleurs.
 * Aucune fiche PDF n'était produite et aucun bouton ne permettait d'en
 * télécharger une.
 *
 * Ces tests vérifient les deux moitiés de la correction : le tableau
 * reste lisible (une vingtaine de colonnes serait illisible et ne
 * réglerait rien), et la fiche montre TOUT, sans troncature.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

// `fireEvent` plutôt que `user-event` : cette dernière n'est pas une
// dépendance du projet, et en ajouter une pour un test reviendrait à
// alourdir la livraison pour un confort d'écriture.
const clic = (element) => fireEvent.click(element);
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

vi.mock("../../api", () => ({
  websiteAdminAPI: {
    preregistrations: vi.fn(),
    prereg: vi.fn(),
    updatePrereg: vi.fn(),
    deletePrereg: vi.fn(),
    preregSheet: vi.fn(),
    regeneratePreregSheet: vi.fn(),
    exportPreregs: vi.fn(),
    contactMessages: vi.fn(),
    updateContact: vi.fn(),
    deleteContact: vi.fn(),
    news: vi.fn(),
    settings: vi.fn(),
  },
}));

vi.mock("../../hooks/useEntityContext", () => ({
  useAcademyKey: () => "FEBA",
  useEntityContext: () => ({ allEntitiesMode: false, isOnlineAcademy: false }),
}));

import { websiteAdminAPI } from "../../api";
import AdminWebsite from "./Website";

const MESSAGE_5000 =
  "Bonjour,\n\nNous souhaitons inscrire notre fille <en urgence> & en " +
  "internat.\n" + "Précision de la famille. ".repeat(210) +
  "\n\nCordialement,\nFamille Adjovi-Bokô";
const MOT_300 = "M" + "o".repeat(298) + "T";
const ADRESSE =
  "Carrefour Saint-Michel, derrière la pharmacie\nLot 42, parcelle B\n" +
  "Akpakpa, Cotonou, Bénin";

const DEMANDE = {
  id: 7,
  reference: "FEBA-2026-0007",
  created_at: "2026-08-01T10:22:00Z",
  parent_name: "Chris Adjovi-Bokô",
  phone: "+229 01 02 03 04",
  phone_secondary: "+229 05 06 07 08",
  whatsapp: "+229 09 10 11 12",
  email: "chris.adjovi@example.org",
  address: ADRESSE,
  child_name: "Amélie Adjovi-Bokô",
  child_age: 8,
  child_birth_date: "2017-04-12",
  desired_level: "ce1",
  desired_level_display: "CE1",
  school_year: "2026-2027",
  message: MESSAGE_5000,
  status: "new",
  status_display: "Nouvelle",
  academy_code: "FEBA",
  academy_name: "Faith & Excellence Bilingual Academy",
  sheet_available: true,
  sheet_error: "",
};

function monter() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <AdminWebsite />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

/** Ouvre l'onglet Préinscriptions puis attend la première ligne. */
async function ouvrirOnglet() {
  clic(await screen.findByRole("button", { name: /Préinscriptions/i }));
  await screen.findByText("FEBA-2026-0007");
}

beforeEach(() => {
  vi.clearAllMocks();
  websiteAdminAPI.preregistrations.mockResolvedValue({ data: [DEMANDE] });
  websiteAdminAPI.prereg.mockResolvedValue({ data: DEMANDE });
  websiteAdminAPI.contactMessages.mockResolvedValue({ data: [] });
  websiteAdminAPI.news.mockResolvedValue({ data: [] });
  websiteAdminAPI.settings?.mockResolvedValue?.({ data: {} });
  websiteAdminAPI.preregSheet.mockResolvedValue({ data: new Blob(["%PDF-"]) });
  websiteAdminAPI.regeneratePreregSheet.mockResolvedValue({ data: DEMANDE });
  websiteAdminAPI.exportPreregs.mockResolvedValue({ data: new Blob(["ref;"]) });
  // jsdom n'implémente pas createObjectURL. On passe par `globalThis`,
  // défini partout, plutôt que par `global`, qui n'existe que sous Node.
  globalThis.URL.createObjectURL = vi.fn(() => "blob:test");
  globalThis.URL.revokeObjectURL = vi.fn();
});

describe("Tableau des préinscriptions", () => {
  it("affiche le numéro de dossier, absent de l'ancienne version", async () => {
    monter();
    await ouvrirOnglet();
    expect(screen.getByText("FEBA-2026-0007")).toBeTruthy();
  });

  it("garde les colonnes de travail du secrétariat", async () => {
    monter();
    await ouvrirOnglet();
    for (const entete of [/Reçue le/, /Dossier/, /Enfant/, /Niveau/,
                          /Parent/, /Téléphone/, /Académie/, /Statut/]) {
      expect(screen.getAllByText(entete).length).toBeGreaterThan(0);
    }
  });

  it("reste compact : le message long n'est PAS dans le tableau", async () => {
    monter();
    await ouvrirOnglet();
    // Une vingtaine de colonnes serait illisible et ne réglerait rien :
    // l'essentiel s'y perdrait exactement comme il se perdait par
    // l'absence de colonnes.
    const tableau = document.querySelector("table");
    expect(tableau.textContent).not.toContain("Précision de la famille.");
  });

  it("montre l'académie de chaque ligne", async () => {
    monter();
    await ouvrirOnglet();
    expect(screen.getAllByText(/Faith & Excellence|FEBA/).length).toBeGreaterThan(0);
  });

  it("propose le téléchargement de la fiche sur chaque ligne", async () => {
    monter();
    await ouvrirOnglet();
    expect(screen.getByTitle(/Télécharger la fiche PDF/i)).toBeTruthy();
  });

  it("télécharge réellement la fiche au clic", async () => {
    monter();
    await ouvrirOnglet();
    clic(screen.getByTitle(/Télécharger la fiche PDF/i));
    await waitFor(() => {
      expect(websiteAdminAPI.preregSheet).toHaveBeenCalledWith(7);
    });
  });

  it("exporte le CSV depuis le serveur, pas depuis la page", async () => {
    monter();
    await ouvrirOnglet();
    clic(screen.getByRole("button", { name: /Exporter en CSV/i }));
    // Un export construit dans le navigateur ne contiendrait que les
    // colonnes affichées — c'est-à-dire, exactement, celles qui
    // manquaient.
    await waitFor(() => expect(websiteAdminAPI.exportPreregs).toHaveBeenCalled());
  });
});

describe("Fiche complète du dossier", () => {
  async function ouvrirFiche() {
    monter();
    await ouvrirOnglet();
    clic(screen.getByTitle(/Voir le dossier/i));
    // On attend le CORPS chargé, pas le titre : le titre du panneau est
    // rendu immédiatement, avant que la requête ne réponde. Attendre le
    // titre ferait passer un panneau resté vide.
    await screen.findByRole("button", { name: /Régénérer la fiche/i });
  }

  it("recharge le dossier depuis le serveur", async () => {
    await ouvrirFiche();
    // La ligne du tableau vient d'une liste qui peut dater ; une fiche
    // officielle doit montrer l'état actuel.
    expect(websiteAdminAPI.prereg).toHaveBeenCalledWith(7);
  });

  it("affiche CHAQUE champ collecté par le formulaire", async () => {
    await ouvrirFiche();
    const attendus = [
      "FEBA-2026-0007",
      "Chris Adjovi-Bokô",
      "+229 01 02 03 04",
      "+229 05 06 07 08",
      "+229 09 10 11 12",
      "chris.adjovi@example.org",
      "Amélie Adjovi-Bokô",
      "2017-04-12",
      "8 ans",
      "CE1",
      "2026-2027",
    ];
    for (const valeur of attendus) {
      expect(screen.getAllByText(valeur).length,
             `« ${valeur} » absent de la fiche`).toBeGreaterThan(0);
    }
  });

  it("affiche l'adresse en conservant ses retours à la ligne", async () => {
    await ouvrirFiche();
    const blocs = screen.getAllByTestId("long-text");
    const adresse = blocs.find((b) => b.textContent.includes("Saint-Michel"));
    expect(adresse).toBeTruthy();
    expect(adresse.textContent).toBe(ADRESSE);
    expect(adresse.style.whiteSpace).toBe("pre-wrap");
  });

  it("affiche le message de 5 000 caractères EN ENTIER", async () => {
    await ouvrirFiche();
    const blocs = screen.getAllByTestId("long-text");
    const message = blocs.find((b) => b.textContent.includes("Précision de la famille."));
    expect(message.textContent).toBe(MESSAGE_5000);
    expect(message.textContent).toContain("Famille Adjovi-Bokô");
    expect(message.textContent.endsWith("…")).toBe(false);
  });

  it("n'applique ni troncature ni hauteur fixe aux textes longs", async () => {
    await ouvrirFiche();
    for (const bloc of screen.getAllByTestId("long-text")) {
      expect(bloc.className).not.toContain("truncate");
      expect(bloc.className).not.toContain("line-clamp");
      expect(bloc.style.maxHeight).toBe("");
      expect(bloc.style.overflowWrap).toBe("anywhere");
    }
  });

  it("marque explicitement les champs non renseignés", async () => {
    websiteAdminAPI.prereg.mockResolvedValue({
      data: { ...DEMANDE, whatsapp: "", email: "", address: "", message: "" },
    });
    await ouvrirFiche();
    // Sur une fiche officielle, une ligne absente et une réponse vide se
    // confondent : il faut pouvoir dire « la question a été posée ».
    expect(screen.getAllByText(/Non renseigné|Aucun message/).length)
      .toBeGreaterThan(0);
  });

  it("dit si la fiche PDF existe réellement", async () => {
    await ouvrirFiche();
    expect(screen.getByText(/Fiche PDF disponible/i)).toBeTruthy();
  });

  it("signale une fiche absente et montre le motif de l'échec", async () => {
    websiteAdminAPI.prereg.mockResolvedValue({
      data: { ...DEMANDE, sheet_available: false,
              sheet_error: "RuntimeError: police introuvable" },
    });
    await ouvrirFiche();
    expect(screen.getByText(/Fiche PDF absente/i)).toBeTruthy();
    expect(screen.getByText(/police introuvable/i)).toBeTruthy();
  });

  it("permet de régénérer la fiche", async () => {
    await ouvrirFiche();
    clic(screen.getByRole("button", { name: /Régénérer la fiche/i }));
    await waitFor(() =>
      expect(websiteAdminAPI.regeneratePreregSheet).toHaveBeenCalledWith(7));
  });

  it("permet de télécharger la fiche depuis le dossier", async () => {
    await ouvrirFiche();
    const boutons = screen.getAllByRole("button", { name: /Télécharger la fiche PDF/i });
    clic(boutons[boutons.length - 1]);
    await waitFor(() => expect(websiteAdminAPI.preregSheet).toHaveBeenCalledWith(7));
  });

  it("ne laisse aucun mot indivisible élargir le panneau", async () => {
    websiteAdminAPI.prereg.mockResolvedValue({
      data: { ...DEMANDE, message: MOT_300 },
    });
    await ouvrirFiche();
    const blocs = screen.getAllByTestId("long-text");
    const mot = blocs.find((b) => b.textContent.startsWith("Mo"));
    expect(mot.textContent).toHaveLength(300);
    expect(mot.style.wordBreak).toBe("break-word");
    expect(mot.style.minWidth).toBe("0px");
  });
});
