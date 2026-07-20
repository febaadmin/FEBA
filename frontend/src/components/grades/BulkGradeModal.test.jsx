/**
 * Tests du BulkGradeModal (saisie GROUPÉE de notes — V6).
 *
 * Couvre le flux de sauvegarde côté frontend sans réseau :
 * - la charge utile POST /grades/bulk-create/ est bien ATOMIQUE (un élève,
 *   un tableau `grades` complet en une requête) ;
 * - succès → toast + onSaved(data) + fermeture ;
 * - erreurs par ligne { grades: [ {}, {champ:[...]} ] } → message affiché sur
 *   la bonne ligne, modal NON fermé (pas d'écriture partielle silencieuse) ;
 * - validation cliente légère : champ obligatoire manquant → aucune requête.
 *
 * La source de vérité des permissions et de l'appréciation reste le backend :
 * on vérifie seulement le contrat d'appel et le rendu, pas les règles métier.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { setLang } from "../../i18n";

vi.mock("../../api", () => ({
  gradesAPI: { bulkCreate: vi.fn() },
}));
vi.mock("react-hot-toast", () => ({
  default: { success: vi.fn(), error: vi.fn() },
}));
// Modal → passe-plat (évite portail / piège de focus en jsdom)
vi.mock("../ui/Modal", () => ({
  default: ({ open, title, children }) =>
    open ? (
      <div role="dialog" aria-label={title}>
        {children}
      </div>
    ) : null,
}));
// SearchableSelect → <select> natif nommé par son placeholder
vi.mock("../ui/SearchableSelect", () => ({
  default: ({ options, value, onChange, placeholder }) => (
    <select
      aria-label={placeholder}
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      <option value="">{placeholder}</option>
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  ),
}));

import toast from "react-hot-toast";
import { gradesAPI } from "../../api";
import BulkGradeModal from "./BulkGradeModal";

const STUDENTS = [
  { value: 26, label: "Ayo Codjo — 3ème-A", classId: 7 },
  { value: 27, label: "Nadège Ahouansou — 3ème-A", classId: 7 },
];
const SUBJECTS = [
  { value: 1, label: "Mathématiques (coeff 4)" },
  { value: 8, label: "Mathematics (coeff 3)" },
];
const CLASSES = [{ value: 7, label: "3ème-A" }];

function renderModal(props = {}) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const onClose = vi.fn();
  const onSaved = vi.fn();
  render(
    <QueryClientProvider client={qc}>
      <BulkGradeModal
        open
        onClose={onClose}
        onSaved={onSaved}
        studentOptions={STUDENTS}
        subjectOptions={SUBJECTS}
        classOptions={CLASSES}
        schoolYearId={3}
        {...props}
      />
    </QueryClientProvider>,
  );
  return { onClose, onSaved };
}

beforeEach(() => {
  vi.clearAllMocks();
  setLang("fr");
});

describe("BulkGradeModal — rendu", () => {
  it("affiche le message d'atomicité et une ligne initiale", () => {
    renderModal();
    expect(
      screen.getByText(/Tout est enregistré ensemble, ou rien en cas d'erreur/),
    ).toBeInTheDocument();
    // Une seule ligne au départ : un seul <select> matière.
    expect(screen.getAllByLabelText("Matière…")).toHaveLength(1);
    expect(screen.getByText("1 note(s) à enregistrer")).toBeInTheDocument();
  });

  it("« Ajouter une matière » ajoute une ligne", () => {
    renderModal();
    fireEvent.click(screen.getByText("Ajouter une matière"));
    expect(screen.getAllByLabelText("Matière…")).toHaveLength(2);
    expect(screen.getByText("2 note(s) à enregistrer")).toBeInTheDocument();
  });
});

describe("BulkGradeModal — sauvegarde atomique", () => {
  it("envoie UNE charge utile groupée { student, grades:[…] } et gère le succès", async () => {
    gradesAPI.bulkCreate.mockResolvedValue({
      data: { created: 2, detail: "2 note(s) ajoutée(s) avec succès pour Ayo Codjo." },
    });
    const { onClose, onSaved } = renderModal();

    // Élève
    fireEvent.change(screen.getByLabelText("Choisir un élève…"), { target: { value: "26" } });
    // Ligne 1 : Maths = 15.5
    fireEvent.change(screen.getAllByLabelText("Matière…")[0], { target: { value: "1" } });
    fireEvent.change(screen.getByPlaceholderText("0–20"), { target: { value: "15.5" } });
    // Ligne 2 : Mathematics = 12, période T2 (distincte)
    fireEvent.click(screen.getByText("Ajouter une matière"));
    fireEvent.change(screen.getAllByLabelText("Matière…")[1], { target: { value: "8" } });
    const valueInputs = screen.getAllByPlaceholderText("0–20");
    fireEvent.change(valueInputs[1], { target: { value: "12" } });

    fireEvent.click(screen.getByText("Enregistrer toutes les notes"));

    await waitFor(() => expect(gradesAPI.bulkCreate).toHaveBeenCalledTimes(1));
    const payload = gradesAPI.bulkCreate.mock.calls[0][0];
    expect(payload.student).toBe(26);
    expect(payload.school_year).toBe(3);
    expect(payload.grades).toHaveLength(2);
    expect(payload.grades[0]).toMatchObject({
      subject: 1, period: "T1", value: "15.5", note_type: "devoir", note_coefficient: 1,
    });
    expect(payload.grades[1]).toMatchObject({ subject: 8, value: "12" });

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(toast.success).toHaveBeenCalledWith(
      "2 note(s) ajoutée(s) avec succès pour Ayo Codjo.",
    );
    expect(onSaved).toHaveBeenCalledWith(
      expect.objectContaining({ created: 2 }),
    );
  });

  it("mappe une erreur backend par ligne au bon endroit et NE ferme PAS (pas d'écriture partielle)", async () => {
    // Erreur métier que la validation cliente ne peut PAS détecter (permission
    // matière) : les deux lignes ont des valeurs valides, seul le backend
    // rejette la ligne 1 → écriture entièrement annulée, modal maintenu.
    gradesAPI.bulkCreate.mockRejectedValue({
      response: {
        data: {
          grades: [
            {}, // ligne 0 : OK
            {
              subject: [
                "Vous n'êtes pas autorisé à noter en Histoire-Géo. Vous pouvez uniquement noter vos propres matières.",
              ],
            }, // ligne 1 : refus backend
          ],
        },
      },
    });
    const { onClose } = renderModal();

    fireEvent.change(screen.getByLabelText("Choisir un élève…"), { target: { value: "26" } });
    fireEvent.change(screen.getAllByLabelText("Matière…")[0], { target: { value: "1" } });
    fireEvent.change(screen.getByPlaceholderText("0–20"), { target: { value: "14" } });
    fireEvent.click(screen.getByText("Ajouter une matière"));
    fireEvent.change(screen.getAllByLabelText("Matière…")[1], { target: { value: "8" } });
    fireEvent.change(screen.getAllByPlaceholderText("0–20")[1], { target: { value: "12" } });

    fireEvent.click(screen.getByText("Enregistrer toutes les notes"));

    // L'API a bien été appelée (validation cliente franchie)…
    await waitFor(() => expect(gradesAPI.bulkCreate).toHaveBeenCalledTimes(1));
    // …et le message d'erreur backend s'affiche sur la ligne fautive.
    expect(
      await screen.findByText(/Vous n'êtes pas autorisé à noter en Histoire-Géo/),
    ).toBeInTheDocument();
    // Bandeau global + modal maintenu ouvert (aucune écriture partielle validée)
    expect(
      screen.getByText(/Certaines lignes comportent des erreurs/),
    ).toBeInTheDocument();
    expect(onClose).not.toHaveBeenCalled();
    expect(toast.success).not.toHaveBeenCalled();
  });

  it("bloque la soumission (aucune requête) si un champ obligatoire manque", async () => {
    renderModal();
    // Élève sélectionné mais matière/note laissées vides
    fireEvent.change(screen.getByLabelText("Choisir un élève…"), { target: { value: "26" } });
    fireEvent.click(screen.getByText("Enregistrer toutes les notes"));

    expect(await screen.findByText("Matière obligatoire.")).toBeInTheDocument();
    expect(screen.getByText("Note obligatoire.")).toBeInTheDocument();
    expect(gradesAPI.bulkCreate).not.toHaveBeenCalled();
  });

  it("exige un élève avant toute soumission", async () => {
    renderModal();
    fireEvent.change(screen.getAllByLabelText("Matière…")[0], { target: { value: "1" } });
    fireEvent.change(screen.getByPlaceholderText("0–20"), { target: { value: "15" } });
    fireEvent.click(screen.getByText("Enregistrer toutes les notes"));

    expect(await screen.findByText("Sélectionnez un élève.")).toBeInTheDocument();
    expect(gradesAPI.bulkCreate).not.toHaveBeenCalled();
  });
});
