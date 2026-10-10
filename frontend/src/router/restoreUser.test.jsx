/**
 * Jeton présent, utilisateur absent (connexion interrompue entre l'obtention
 * du jeton et /auth/me) : l'écran restait indéfiniment sur « Chargement… ».
 * L'utilisateur est désormais rechargé ; en cas d'échec, retour à la
 * connexion.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, waitFor } from "@testing-library/react";

vi.mock("../api", () => ({ authAPI: { me: vi.fn() } }));

import { authAPI } from "../api";
import { useAuthStore } from "../store/authStore";
import { useRestoreUser } from "./index";

function Probe() {
  useRestoreUser();
  const user = useAuthStore((s) => s.user);
  const token = useAuthStore((s) => s.accessToken);
  return <span data-testid="state">{user?.role || "none"}|{token ? "token" : "no-token"}</span>;
}

beforeEach(() => {
  vi.clearAllMocks();
  useAuthStore.setState({ user: null, accessToken: "jwt", refreshToken: "r", _hasHydrated: true });
});

describe("Reprise d'une connexion interrompue", () => {
  it("recharge l'utilisateur quand seul le jeton est présent", async () => {
    authAPI.me.mockResolvedValue({ data: { role: "admin", first_name: "A" } });
    const { getByTestId } = render(<Probe />);
    await waitFor(() => expect(getByTestId("state").textContent).toBe("admin|token"));
    expect(authAPI.me).toHaveBeenCalledTimes(1);
  });

  it("efface une session inutilisable plutôt que de rester bloqué", async () => {
    authAPI.me.mockRejectedValue(new Error("401"));
    const { getByTestId } = render(<Probe />);
    await waitFor(() => expect(getByTestId("state").textContent).toBe("none|no-token"));
  });
});
