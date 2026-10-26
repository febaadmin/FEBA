/**
 * Éditeur de gabarit : un champ ajouté garde son NOM (défaut trouvé en
 * navigateur réel : la liste était remise à zéro avant que l'ajout ne soit
 * appliqué, et la zone créée n'avait plus de nom), et la configuration
 * envoyée est en millimètres.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("react-hot-toast", () => ({ default: { success: vi.fn(), error: vi.fn() } }));
vi.mock("../../api", () => ({
  documentTemplatesAPI: {
    background: vi.fn(), configure: vi.fn(), action: vi.fn(), preview: vi.fn(),
  },
}));

import { documentTemplatesAPI } from "../../api";
import TemplateEditor from "./TemplateEditor";

const template = {
  id: 5, kind: "certificate", kind_display: "Certificat", version: 1, is_editable: true,
  page_width_mm: 210, page_height_mm: 297, page_count: 1, page_index: 0, fields: [],
  options: { eligibility: { rule: "enrolled" } },
};
const catalog = [
  { name: "student_name", label: "Nom complet de l'élève", kinds: ["diploma", "certificate"] },
  { name: "class_name", label: "Classe", kinds: ["diploma", "certificate"] },
  { name: "award_date", label: "Date d'obtention (saisie à la production)", kinds: ["diploma"] },
];

function renderEditor(over = {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <TemplateEditor template={{ ...template, ...over }} catalog={catalog}
                      rules={["enrolled", "admin_decision"]} onClose={vi.fn()} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  documentTemplatesAPI.background.mockResolvedValue({ data: new Blob(["x"]) });
  documentTemplatesAPI.configure.mockResolvedValue({ data: {} });
  globalThis.URL.createObjectURL = vi.fn(() => "blob:x");
  globalThis.URL.revokeObjectURL = vi.fn();
});

describe("TemplateEditor", () => {
  it("un champ ajouté garde son nom et apparaît sur la page", async () => {
    renderEditor();
    const select = screen.getByLabelText("Champ à placer");
    // Seuls les champs du type de document sont proposés.
    expect(screen.queryByRole("option", { name: /Date d'obtention/ })).not.toBeInTheDocument();
    fireEvent.change(select, { target: { value: "student_name" } });
    fireEvent.click(screen.getByTitle("Placer ce champ"));
    expect(await screen.findByTestId("zone-student_name")).toBeInTheDocument();
    expect(screen.queryByText("Le nom de l'élève doit être placé.")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Nom complet de l'élève \*/ })).toBeInTheDocument();
  });

  it("envoie des coordonnées en millimètres, dans la page", async () => {
    renderEditor();
    fireEvent.change(screen.getByLabelText("Champ à placer"), { target: { value: "student_name" } });
    fireEvent.click(screen.getByTitle("Placer ce champ"));
    fireEvent.change(screen.getByLabelText("Champ à placer"), { target: { value: "class_name" } });
    fireEvent.click(screen.getByTitle("Placer ce champ"));
    fireEvent.click(screen.getByRole("button", { name: /^Enregistrer$/ }));
    await waitFor(() => expect(documentTemplatesAPI.configure).toHaveBeenCalled());
    const [id, body] = documentTemplatesAPI.configure.mock.calls[0];
    expect(id).toBe(5);
    expect(body.fields.map((f) => f.name)).toEqual(["student_name", "class_name"]);
    body.fields.forEach((f) => {
      expect(f.x_mm + f.width_mm).toBeLessThanOrEqual(210);
      expect(f.y_mm + f.height_mm).toBeLessThanOrEqual(297);
    });
    expect(body.options.eligibility).toEqual({ rule: "enrolled" });
  });

  it("une version en lecture seule ne propose ni ajout ni enregistrement", () => {
    renderEditor({ is_editable: false, status: "active",
      fields: [{ name: "student_name", x_mm: 10, y_mm: 10, width_mm: 100, height_mm: 20,
                 font: "serif", font_size_pt: 20, min_font_size_pt: 10, align: "center",
                 color: "#000000", max_lines: 2, required: true }] });
    expect(screen.queryByLabelText("Champ à placer")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Enregistrer$/ })).not.toBeInTheDocument();
    expect(screen.getByText(/lecture seule/)).toBeInTheDocument();
  });
});
