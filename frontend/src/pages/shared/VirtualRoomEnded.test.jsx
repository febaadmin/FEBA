/**
 * Retour de plugNmeet : la session FEBA n'est jamais effacée, le départ
 * est signalé une seule fois, et l'utilisateur peut revenir à FEBA.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { StrictMode } from "react";

vi.mock("../../api", () => ({ virtualAPI: { leave: vi.fn(() => Promise.resolve({})) } }));

import { virtualAPI } from "../../api";
import { useAuthStore } from "../../store/authStore";
import VirtualRoomEnded from "./VirtualRoomEnded";

beforeEach(() => {
  vi.clearAllMocks();
  useAuthStore.setState({ user: { role: "teacher" }, accessToken: "a", refreshToken: "r", _hasHydrated: true });
});

describe("fin de réunion plugNmeet", () => {
  it("garde la session, signale le départ une fois, propose le retour", () => {
    render(
      <StrictMode>
        <MemoryRouter initialEntries={["/virtual-room/9/ended"]}>
          <Routes><Route path="/virtual-room/:id/ended" element={<VirtualRoomEnded />} /></Routes>
        </MemoryRouter>
      </StrictMode>,
    );
    expect(virtualAPI.leave).toHaveBeenCalledTimes(1);
    expect(virtualAPI.leave).toHaveBeenCalledWith("9");
    expect(useAuthStore.getState().accessToken).toBe("a");
    expect(useAuthStore.getState().refreshToken).toBe("r");
    expect(screen.getByText("Retour à FEBA").getAttribute("href")).toBe("/teacher/dashboard");
    expect(screen.getByText("Rejoindre à nouveau").getAttribute("href")).toBe("/virtual-room/9/join");
  });
});
