import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import NotificationBell from "./NotificationBell";

const markAllRead = vi.fn(() => Promise.resolve({}));
vi.mock("../api", () => ({
  notificationsAPI: {
    unreadCount: () => Promise.resolve({ data: { count: 3 } }),
    list: () => Promise.resolve({ data: [{ id: 1, title: "Incident technique ERR-1", message: "x", is_read: false, related_url: "/superadmin/incidents/9" }] }),
    markAllRead: () => markAllRead(),
  },
}));

describe("cloche des notifications", () => {
  it("affiche le nombre de non lues, les marque lues et mène à l'élément", async () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={["/superadmin/dashboard"]}>
          <Routes>
            <Route path="/superadmin/dashboard" element={<NotificationBell toutVoir="/superadmin/incidents" toutVoirLibelle="tout" />} />
            <Route path="/superadmin/incidents/:id" element={<p>fiche incident</p>} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("cloche-compte").textContent).toBe("3"));
    fireEvent.click(screen.getByTestId("cloche"));
    await waitFor(() => expect(markAllRead).toHaveBeenCalledTimes(1));
    fireEvent.click(await screen.findByText("Incident technique ERR-1"));
    expect(screen.getByText("fiche incident")).toBeTruthy();
  });
});
