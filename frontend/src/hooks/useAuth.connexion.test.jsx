import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useAuth } from "./useAuth";
import { useAuthStore } from "../store/authStore";
import { authAPI } from "../api";

vi.mock("react-router-dom", () => ({ useNavigate: () => vi.fn() }));
vi.mock("@tanstack/react-query", () => ({ useQueryClient: () => ({ clear: vi.fn() }) }));
vi.mock("react-hot-toast", () => ({ default: Object.assign(vi.fn(), { success: vi.fn() }) }));
vi.mock("../api", () => ({ authAPI: { login: vi.fn(), me: vi.fn() } }));

describe("connexion", () => {
  let etats;
  beforeEach(() => {
    useAuthStore.setState({ user: null, accessToken: null, refreshToken: null });
    etats = [];
    useAuthStore.subscribe((s) => etats.push({ user: s.user, jeton: s.accessToken }));
    authAPI.login.mockResolvedValue({ data: { access: "a.e30.c", refresh: "r" } });
    authAPI.me.mockResolvedValue({ data: { id: 1, role: "admin", first_name: "A" } });
  });

  it("n'enregistre jamais de session sans utilisateur : cet état intermédiaire annulait la lecture du profil", async () => {
    const { result } = renderHook(() => useAuth());
    await act(() => result.current.login("a@b.c", "x"));
    expect(etats.filter((e) => e.jeton && !e.user)).toEqual([]);
    expect(useAuthStore.getState().user.id).toBe(1);
  });

  it("lit le profil hors portée, avec le nouveau jeton", async () => {
    const { result } = renderHook(() => useAuth());
    await act(() => result.current.login("a@b.c", "x"));
    expect(authAPI.me).toHaveBeenCalledWith({ horsPortee: true, headers: { Authorization: "Bearer a.e30.c" } });
  });

  it("n'enregistre aucune session si le profil ne se charge pas", async () => {
    authAPI.me.mockRejectedValue(new Error("coupure"));
    const { result } = renderHook(() => useAuth());
    await act(async () => { await expect(result.current.login("a@b.c", "x")).rejects.toThrow(); });
    expect(useAuthStore.getState().accessToken).toBeNull();
  });
});
