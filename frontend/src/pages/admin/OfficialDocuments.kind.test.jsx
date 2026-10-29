/**
 * Production d'un document par TYPE : le serveur résout le gabarit de
 * l'académie de l'élève et dit ce qui manque ; l'écran n'autorise la
 * production qu'après une vérification favorable ET la confirmation de
 * l'académie émettrice.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("../../context/AcademyContext", () => ({ useAcademy: () => ({ academyKey: "academy:3" }) }));
vi.mock("react-hot-toast", () => ({ default: { success: vi.fn(), error: vi.fn() } }));
vi.mock("../../components/ui/SearchableSelect", () => ({
  default: ({ options, onChange }) => (
    <select data-testid="student-select" onChange={(e) => onChange(Number(e.target.value))}>
      <option value="">—</option>
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  ),
}));
vi.mock("../../api", () => ({
  documentsAPI: {
    templates: vi.fn(), list: vi.fn(), create: vi.fn(), issue: vi.fn(), revoke: vi.fn(),
    download: vi.fn(), check: vi.fn(), preview: vi.fn(), batch: vi.fn(), batchIssue: vi.fn(),
  },
  documentTemplatesAPI: { list: vi.fn() },
  studentsAPI: { list: vi.fn() },
  classesAPI: { list: vi.fn() },
}));

import { documentTemplatesAPI, documentsAPI, studentsAPI } from "../../api";
import AdminOfficialDocuments from "./OfficialDocuments";

const okCheck = {
  kind: "diploma", source: "uploaded", can_produce: true,
  academy: { code: "AC_X", name: "Académie X" }, template: { id: 4, version: 2 },
  values: { student_name: "Awa Kone", student_matricule: "X-1", document_number: "" },
  labels: { student_name: "Nom complet de l'élève", student_matricule: "Matricule",
            document_number: "Numéro de référence (attribué à la délivrance)" },
  inputs: [], missing: [], warnings: [], blockers: [],
};

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><AdminOfficialDocuments /></QueryClientProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
  documentsAPI.templates.mockResolvedValue({ data: { templates: [], academy: { code: "AC_X", name: "Académie X" }, consolidated: false } });
  documentsAPI.list.mockResolvedValue({ data: [] });
  studentsAPI.list.mockResolvedValue({ data: [{ id: 7, full_name: "Awa Kone" }] });
  documentsAPI.check.mockResolvedValue({ data: okCheck });
  documentsAPI.create.mockResolvedValue({ data: { id: 1 } });
  documentTemplatesAPI.list.mockResolvedValue({ data: { kinds: {
    diploma: { kind: "diploma", state: "active", pending: null, builtin: null,
               active: { version: 2, original_filename: "diplome.pdf" } },
    certificate: { kind: "certificate", state: "absent", active: null, pending: null,
                   builtin: { label: "Certificat FEBA", in_use: true, can_issue: false,
                              blockers: ["Le fond « certificat.png » n'est pas installé."] } },
  } } });
});

async function openAndPick() {
  renderPage();
  fireEvent.click(await screen.findByRole("button", { name: /Produire un document/ }));
  await waitFor(() => expect(screen.getByTestId("student-select").options.length).toBe(2));
  fireEvent.change(screen.getByTestId("student-select"), { target: { value: "7" } });
}

describe("État des gabarits sur l'écran de production", () => {
  it("annonce pour chaque type la source réellement utilisée et ses blocages", async () => {
    renderPage();
    const diploma = await screen.findByTestId("template-state-diploma");
    expect(diploma).toHaveTextContent("Gabarit téléversé de l'académie — version 2");
    const certificate = screen.getByTestId("template-state-certificate");
    expect(certificate).toHaveTextContent("Gabarit intégré « Certificat FEBA »");
    expect(certificate).toHaveTextContent("n'est pas installé");
  });
});

describe("Production par type de document", () => {
  it("vérifie auprès du serveur puis exige la confirmation de l'académie", async () => {
    await openAndPick();
    await waitFor(() => expect(documentsAPI.check).toHaveBeenCalledWith(
      { student: 7, kind: "diploma", values: {} }));
    expect(await screen.findByText("Gabarit téléversé de l'académie — version 2")).toBeInTheDocument();
    expect(screen.getByText("X-1")).toBeInTheDocument();
    const produce = screen.getByRole("button", { name: "Produire" });
    expect(produce).toBeDisabled();
    fireEvent.click(screen.getByLabelText(/Je confirme produire ce document au nom de Académie X/));
    expect(produce).not.toBeDisabled();
    fireEvent.click(produce);
    await waitFor(() => expect(documentsAPI.create).toHaveBeenCalledWith(
      { student: 7, kind: "diploma", values: {} }));
  });

  it("affiche les refus et données manquantes, et bloque la production", async () => {
    documentsAPI.check.mockResolvedValue({ data: { ...okCheck, can_produce: false,
      missing: ["Matricule"], blockers: ["Moyenne annuelle 7.33/20 inférieure au seuil requis (10.00/20)."] } });
    await openAndPick();
    expect(await screen.findByText(/inférieure au seuil requis/)).toBeInTheDocument();
    expect(screen.getByText("Donnée obligatoire manquante : Matricule")).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText(/Je confirme/));
    expect(screen.getByRole("button", { name: "Produire" })).toBeDisabled();
  });

  it("propose la saisie de la date d'obtention quand le gabarit l'affiche", async () => {
    documentsAPI.check.mockResolvedValue({ data: { ...okCheck, inputs: ["award_date"] } });
    await openAndPick();
    const input = await screen.findByLabelText("Date d'obtention");
    fireEvent.change(input, { target: { value: "2027-06-30" } });
    await waitFor(() => expect(documentsAPI.check).toHaveBeenLastCalledWith(
      { student: 7, kind: "diploma", values: { award_date: "2027-06-30" } }));
  });
});
