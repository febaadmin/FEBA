import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import toast from "react-hot-toast";
import { useForm } from "./useFormulaire";
import Modal from "../components/ui/Modal";

vi.mock("react-hot-toast", () => ({ default: { error: vi.fn(), success: vi.fn() } }));

function Formulaire({ envoyer }) {
  const { register, handleSubmit } = useForm();
  return <form onSubmit={handleSubmit(envoyer)}><input aria-label="nom" {...register("nom", { required: true })} /><button>OK</button></form>;
}

describe("useForm", () => {
  it("prévient quand un champ obligatoire bloque l'envoi", async () => {
    const envoyer = vi.fn();
    render(<Formulaire envoyer={envoyer} />);
    fireEvent.click(screen.getByText("OK"));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Renseignez les champs obligatoires avant d'enregistrer."));
    expect(envoyer).not.toHaveBeenCalled();
  });

  it("envoie sans message quand le formulaire est valide", async () => {
    toast.error.mockClear();
    const envoyer = vi.fn();
    render(<Formulaire envoyer={envoyer} />);
    fireEvent.change(screen.getByLabelText("nom"), { target: { value: "x" } });
    fireEvent.click(screen.getByText("OK"));
    await waitFor(() => expect(envoyer).toHaveBeenCalled());
    expect(toast.error).not.toHaveBeenCalled();
  });
});

describe("Modal", () => {
  it("se rend dans body, hors d'un ancêtre transformé, et prend le focus", () => {
    render(<div data-testid="parent" style={{ transform: "translateY(1px)" }}><Modal open onClose={() => {}} title="T">x</Modal></div>);
    const fenetre = screen.getByRole("dialog");
    expect(screen.getByTestId("parent").contains(fenetre)).toBe(false);
    expect(document.activeElement).toBe(fenetre);
  });
});
