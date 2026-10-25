/**
 * Jeton présent, utilisateur absent (connexion interrompue entre l'obtention
 * du jeton et /auth/me) : l'écran restait indéfiniment sur « Chargement… ».
 * L'utilisateur est désormais rechargé ; si le SERVEUR refuse (401),
 * retour à la connexion ; une coupure réseau, elle, ne déconnecte pas.
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

  it("efface une session refusée par le serveur (401) plutôt que de rester bloqué", async () => {
    authAPI.me.mockRejectedValue(Object.assign(new Error("401"), { response: { status: 401 } }));
    const { getByTestId } = render(<Probe />);
    await waitFor(() => expect(getByTestId("state").textContent).toBe("none|no-token"));
  });

  it("une coupure réseau ne déconnecte pas : la session est conservée", async () => {
    authAPI.me.mockRejectedValue(Object.assign(new Error("Network Error"), { code: "ERR_NETWORK" }));
    const { getByTestId } = render(<Probe />);
    await waitFor(() => expect(authAPI.me).toHaveBeenCalledTimes(1));
    await new Promise((r) => setTimeout(r, 20));
    expect(getByTestId("state").textContent).toBe("none|token");
  });
});
