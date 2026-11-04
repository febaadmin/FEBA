import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import ResetPasswordModal from "./ResetPasswordModal";

const adminResetPassword = vi.fn(() => Promise.resolve({ data: { detail: "ok" } }));
vi.mock("../../api", () => ({ authAPI: { adminResetPassword: (...a) => adminResetPassword(...a) } }));
vi.mock("react-hot-toast", () => ({ default: { success: vi.fn(), error: vi.fn() } }));

const monter = (user) => render(
  <QueryClientProvider client={new QueryClient()}>
    <ResetPasswordModal user={user} onClose={() => {}} />
  </QueryClientProvider>,
);

async function remplir(container) {
  const [mdp, conf] = document.querySelectorAll('input[autocomplete="new-password"]');
  fireEvent.change(mdp, { target: { value: "Nouveau#2026x" } });
  fireEvent.change(conf, { target: { value: "Nouveau#2026x" } });
  fireEvent.click(document.querySelector('input[type="checkbox"]'));
}

describe("réinitialisation du mot de passe", () => {
  beforeEach(() => adminResetPassword.mockClear());

  it("superadmin : exige le mot de passe de l'auteur et l'envoie", async () => {
    monter({ id: 7, role: "superadmin", first_name: "A", last_name: "B", email: "a@b.c" });
    await remplir(document);
    fireEvent.click(screen.getByRole("button", { name: /Réinitialiser$/ }));
    await waitFor(() => expect(screen.getByText(/Saisissez votre propre mot de passe/)).toBeTruthy());
    expect(adminResetPassword).not.toHaveBeenCalled();
    fireEvent.change(document.querySelector("#requester_password"), { target: { value: "MonSecret#1" } });
    await new Promise((r) => setTimeout(r, 650)); // au-delà de la garde anti double clic
    fireEvent.click(screen.getByRole("button", { name: /Réinitialiser$/ }));
    await waitFor(() => expect(adminResetPassword).toHaveBeenCalledTimes(1));
    expect(adminResetPassword.mock.calls[0]).toEqual([7, { new_password: "Nouveau#2026x", confirm_password: "Nouveau#2026x", requester_password: "MonSecret#1" }]);
  });

  it("autre rôle : pas de ré-authentification", async () => {
    monter({ id: 8, role: "teacher", first_name: "A", last_name: "B", email: "a@b.c" });
    expect(document.querySelector("#requester_password")).toBeNull();
    await remplir(document);
    fireEvent.click(screen.getByRole("button", { name: /Réinitialiser$/ }));
    await waitFor(() => expect(adminResetPassword).toHaveBeenCalledTimes(1));
    expect(adminResetPassword.mock.calls[0][1]).not.toHaveProperty("requester_password");
  });
});
