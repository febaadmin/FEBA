import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import ApercuPdf from "./ApercuPdf";

const rendu = vi.fn(() => ({ promise: Promise.resolve() }));
const getDocument = vi.fn();
vi.mock("pdfjs-dist", () => ({ GlobalWorkerOptions: {}, getDocument: (...a) => getDocument(...a) }));
vi.mock("pdfjs-dist/build/pdf.worker.min.mjs?url", () => ({ default: "/assets/pdf.worker.min.mjs" }));

beforeEach(() => {
  rendu.mockClear();
  getDocument.mockReset();
  HTMLCanvasElement.prototype.getContext = vi.fn(() => ({}));
});

describe("aperçu PDF sans cadre", () => {
  it("dessine chaque page dans un canvas, sans eval ni requête réseau", async () => {
    const page = { getViewport: ({ scale }) => ({ width: 600 * scale, height: 800 * scale }), render: rendu };
    getDocument.mockReturnValue({ promise: Promise.resolve({ numPages: 2, getPage: async () => page, destroy: vi.fn() }) });
    const { container } = render(<ApercuPdf donnees={new Blob(["%PDF-1.4"])} titre="Bulletin" testid="apercu" />);
    await waitFor(() => expect(screen.getByTestId("apercu").dataset.etat).toBe("pret"));
    expect(container.querySelectorAll("canvas")).toHaveLength(2);
    expect(container.querySelector("iframe")).toBeNull();
    const options = getDocument.mock.calls[0][0];
    expect(options.isEvalSupported).toBe(false);
    expect(options.data).toBeInstanceOf(Uint8Array);
    expect(options.url).toBeUndefined();
    expect(container.querySelector("canvas").getAttribute("aria-label")).toMatch(/Bulletin · page 1 sur 2/);
  });

  it("PDF illisible : message clair au lieu d'un cadre vide", async () => {
    getDocument.mockReturnValue({ promise: Promise.reject(new Error("Invalid PDF")) });
    render(<ApercuPdf donnees={new Blob(["x"])} testid="apercu" />);
    expect((await screen.findByRole("alert")).textContent).toMatch(/n'a pas pu être affiché/);
  });
});
