/**
 * Reproduction, au niveau de l'intercepteur réel, de la déconnexion
 * observée après une heure de visioconférence.
 *
 * Le « serveur » ci-dessous applique les règles de SimpleJWT telles que
 * configurées dans FEBA : rotation du jeton de renouvellement à chaque
 * appel, et liste noire de l'ancien. Plusieurs requêtes expirent en même
 * temps (notifications, messagerie, salles…).
 *
 * Ancien intercepteur : chaque 401 lançait son propre /auth/refresh/ avec
 * le même jeton ; le second était refusé (liste noire) → clearAuth() →
 * /login. Ce test échoue sur l'ancien code et passe sur le nouveau.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import axios from "axios";
import api from "./index";
import { useAuthStore } from "../store/authStore";
import { __resetRefreshState } from "./tokenRefresh";

let valid;          // jeton d'accès accepté par le « serveur »
let liveRefresh;    // seul jeton de renouvellement encore valide
let refreshCalls;
let originalLocation;

function serverAdapter(config) {
  const auth = config.headers?.Authorization || config.headers?.get?.("Authorization");
  const ok = auth === `Bearer ${valid}`;
  return Promise.resolve({
    data: ok ? { ok: true, url: config.url } : { detail: "token_not_valid" },
    status: ok ? 200 : 401, statusText: "", headers: {}, config, request: {},
  }).then((r) => (r.status === 200 ? r : Promise.reject(Object.assign(new Error("401"), { response: r, config }))));
}

beforeEach(() => {
  __resetRefreshState();
  window.localStorage.clear();
  originalLocation = window.location;
  Object.defineProperty(window, "location", { configurable: true, value: { ...originalLocation, href: "/teacher/dashboard" } });
  valid = "access-2";
  liveRefresh = "refresh-1";
  refreshCalls = 0;
  api.defaults.adapter = serverAdapter;
  vi.spyOn(axios, "post").mockImplementation(async (url, body) => {
    refreshCalls += 1;
    await new Promise((r) => setTimeout(r, 5));
    if (body.refresh !== liveRefresh) {
      throw Object.assign(new Error("blacklisted"), { response: { status: 401, data: { detail: "Token is blacklisted" } } });
    }
    liveRefresh = `refresh-${refreshCalls + 1}`;   // rotation + liste noire de l'ancien
    return { data: { access: valid, refresh: liveRefresh } };
  });
  useAuthStore.setState({ _hasHydrated: true });
  useAuthStore.getState().setAuth({ role: "teacher" }, "access-1-expired", "refresh-1");
});

afterEach(() => {
  vi.restoreAllMocks();
  Object.defineProperty(window, "location", { configurable: true, value: originalLocation });
});

describe("intercepteur 401 — jeton expiré pendant un cours", () => {
  it("6 requêtes expirées simultanément : toutes rejouées, un seul renouvellement, aucune déconnexion", async () => {
    const urls = ["/notifications/unread-count/", "/messages/inbox", "/virtual-rooms/", "/classes/", "/auth/me/", "/students/"];
    const responses = await Promise.all(urls.map((u) => api.get(u)));
    expect(responses.every((r) => r.status === 200)).toBe(true);
    expect(refreshCalls).toBe(1);
    expect(useAuthStore.getState().accessToken).toBe("access-2");
    expect(useAuthStore.getState().refreshToken).toBe("refresh-2");
    expect(window.location.href).toBe("/teacher/dashboard");
  });

  it("panne réseau sur /auth/refresh/ : la requête échoue mais la session reste ouverte", async () => {
    axios.post.mockImplementation(async () => { throw Object.assign(new Error("Network Error"), { code: "ERR_NETWORK" }); });
    await expect(api.get("/classes/")).rejects.toBeTruthy();
    expect(useAuthStore.getState().refreshToken).toBe("refresh-1");
    expect(window.location.href).toBe("/teacher/dashboard");
  });

  it("jeton de renouvellement réellement révoqué : retour à la connexion", async () => {
    liveRefresh = "autre-chose";
    await expect(api.get("/classes/")).rejects.toBeTruthy();
    expect(useAuthStore.getState().accessToken).toBeNull();
    expect(window.location.href).toBe("/login");
  });
});
