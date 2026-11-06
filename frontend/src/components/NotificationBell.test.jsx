import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route, Link } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import NotificationBell from "./NotificationBell";

const markAllRead = vi.fn(() => Promise.resolve({}));
const compte = vi.hoisted(() => ({ n: 3 }));
vi.mock("../api", () => ({
  notificationsAPI: {
    unreadCount: () => Promise.resolve({ data: { count: compte.n } }),
    list: () => Promise.resolve({ data: [{ id: 1, title: "Incident technique ERR-1", message: "x", is_read: false, related_url: "/superadmin/incidents/9" }] }),
    markAllRead: () => markAllRead(),
  },
}));
vi.mock("../hooks/useNonLusMessagerie", () => ({ usePretPourDonnees: () => true }));

function monter() {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={["/superadmin/dashboard"]}>
        <Routes>
          <Route path="/superadmin/dashboard" element={(
            <div>
              <NotificationBell toutVoir="/superadmin/incidents" toutVoirLibelle="tout" />
              <p data-testid="contenu">Tableau de bord</p>
              {/* Un composant qui arrête la propagation ne doit pas bloquer la fermeture. */}
              <div data-testid="isole" onPointerDown={(e) => e.stopPropagation()} onClick={(e) => e.stopPropagation()}>zone isolée</div>
              <Link to="/superadmin/academies" data-testid="lien">Académies</Link>
            </div>
          )} />
          <Route path="/superadmin/academies" element={<div><NotificationBell /><p>page académies</p></div>} />
          <Route path="/superadmin/incidents/:id" element={<p>fiche incident</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
const panneau = () => screen.queryByTestId("cloche-panneau");

describe("cloche des notifications", () => {
  beforeEach(() => { markAllRead.mockClear(); compte.n = 3; });

  it("affiche le nombre de non lues, les marque lues à l'ouverture et mène à l'élément", async () => {
    monter();
    await waitFor(() => expect(screen.getByTestId("cloche-compte").textContent).toBe("3"));
    fireEvent.click(screen.getByTestId("cloche"));
    await waitFor(() => expect(markAllRead).toHaveBeenCalledTimes(1));
    // Clic À L'INTÉRIEUR : l'action s'exécute (pas de fermeture prématurée).
    const item = await screen.findByText("Incident technique ERR-1");
    fireEvent.pointerDown(item);
    expect(panneau()).not.toBeNull();
    fireEvent.click(item);
    expect(screen.getByText("fiche incident")).toBeTruthy();
  });

  it("ouvre puis ferme en recliquant sur la cloche", async () => {
    monter();
    fireEvent.click(screen.getByTestId("cloche"));
    expect(panneau()).not.toBeNull();
    expect(screen.getByTestId("cloche").getAttribute("aria-expanded")).toBe("true");
    fireEvent.pointerDown(screen.getByTestId("cloche"));
    fireEvent.click(screen.getByTestId("cloche"));
    expect(panneau()).toBeNull();
  });

  it("se ferme au clic extérieur, même sur un élément qui arrête la propagation", async () => {
    monter();
    fireEvent.click(screen.getByTestId("cloche"));
    fireEvent.pointerDown(screen.getByTestId("contenu"));
    expect(panneau()).toBeNull();
    fireEvent.click(screen.getByTestId("cloche"));
    fireEvent.pointerDown(screen.getByTestId("isole"));
    expect(panneau()).toBeNull();
  });

  it("se ferme avec Échap et rend le focus à la cloche", () => {
    monter();
    fireEvent.click(screen.getByTestId("cloche"));
    fireEvent.keyDown(document, { key: "Escape" });
    expect(panneau()).toBeNull();
    expect(document.activeElement).toBe(screen.getByTestId("cloche"));
  });

  it("se ferme au changement de page", () => {
    monter();
    fireEvent.click(screen.getByTestId("cloche"));
    fireEvent.click(screen.getByTestId("lien"));
    expect(screen.getByText("page académies")).toBeTruthy();
    expect(panneau()).toBeNull();
  });

  it("fermer ne modifie pas le statut des notifications", async () => {
    compte.n = 0;
    monter();
    fireEvent.click(screen.getByTestId("cloche"));
    fireEvent.pointerDown(screen.getByTestId("contenu"));
    fireEvent.click(screen.getByTestId("cloche"));
    fireEvent.keyDown(document, { key: "Escape" });
    expect(markAllRead).not.toHaveBeenCalled();
  });
});
