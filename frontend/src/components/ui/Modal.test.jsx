import { describe, it, expect, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import Modal from "./Modal";

describe("fenêtre modale", () => {
  it("Échap ne ferme que la fenêtre du dessus", () => {
    const fermerA = vi.fn();
    const fermerB = vi.fn();
    // Parcours réel : la seconde fenêtre s'ouvre après la première (clic dans la première).
    const { rerender } = render(<Modal open onClose={fermerA} title="A">a<Modal open={false} onClose={fermerB} title="B">b</Modal></Modal>);
    rerender(<Modal open onClose={fermerA} title="A">a<Modal open onClose={fermerB} title="B">b</Modal></Modal>);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(fermerB).toHaveBeenCalledTimes(1);
    expect(fermerA).not.toHaveBeenCalled();
    rerender(<Modal open onClose={fermerA} title="A">a<Modal open={false} onClose={fermerB} title="B">b</Modal></Modal>);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(fermerA).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("dialog", { name: "A" })).toBeInTheDocument();
  });
});
