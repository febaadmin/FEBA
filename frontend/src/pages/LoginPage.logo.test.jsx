import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import LoginPage from "./LoginPage";

const login = vi.fn();
vi.mock("../hooks/useAuth", () => ({ useAuth: () => ({ login, loading: false }) }));
vi.mock("../hooks/useBranding", () => ({ useBranding: () => ({ logoSrc: "/logo.png" }) }));

describe("logo de la page de connexion", () => {
  it("ramène à l'accueil public sans soumettre le formulaire", () => {
    render(
      <MemoryRouter initialEntries={["/login"]}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<p>accueil public</p>} />
        </Routes>
      </MemoryRouter>,
    );
    const lien = screen.getByTestId("logo-accueil");
    expect(lien.getAttribute("href")).toBe("/");
    expect(lien.closest("form")).toBeNull();
    fireEvent.click(lien.querySelector("img"));
    expect(screen.getByText("accueil public")).toBeTruthy();
    expect(login).not.toHaveBeenCalled();
  });
});
