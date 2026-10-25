/**
 * Session FEBA pendant une longue visioconférence : aucun renouvellement
 * concurrent, aucun onglet qui révoque l'autre, aucune déconnexion sur
 * coupure réseau — mais une vraie fin de session quand le serveur refuse.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useAuthStore } from "../store/authStore";
import {
  STORAGE_KEY, SessionExpiredError, __resetRefreshState, readStoredTokens, refreshAccessToken, tokenExpiry,
} from "./tokenRefresh";
import { needsRefresh } from "../hooks/useSessionKeepAlive";

function jwt(expSecondsFromNow, tag = "x") {
  const b64 = (o) => btoa(JSON.stringify(o)).replace(/=+$/, "");
  return `${b64({ alg: "HS256" })}.${b64({ exp: Math.floor(Date.now() / 1000) + expSecondsFromNow, tag })}.sig`;
}

/** Ce qu'un AUTRE onglet écrirait dans le stockage partagé. */
function otherTabWrites(accessToken, refreshToken) {
  const raw = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || '{"state":{},"version":0}');
  raw.state = { ...raw.state, accessToken, refreshToken };
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(raw));
}

const USER = { role: "teacher", first_name: "Awa" };

beforeEach(() => {
  __resetRefreshState();
  window.localStorage.clear();
  useAuthStore.setState({ _hasHydrated: true });
  useAuthStore.getState().setAuth(USER, jwt(-10, "expired"), "refresh-1");
});

describe("renouvellement du jeton d'accès", () => {
  it("dix 401 simultanés → UN SEUL appel /auth/refresh/ (rotation + liste noire)", async () => {
    const failed = useAuthStore.getState().accessToken;
    const fresh = jwt(3600, "fresh");
    const post = vi.fn(() => new Promise((r) => setTimeout(() => r({ access: fresh, refresh: "refresh-2" }), 10)));
    const results = await Promise.all(Array.from({ length: 10 }, () => refreshAccessToken(failed, post)));
    expect(post).toHaveBeenCalledTimes(1);
    expect(new Set(results)).toEqual(new Set([fresh]));
    expect(useAuthStore.getState().refreshToken).toBe("refresh-2");
    expect(useAuthStore.getState().user).toEqual(USER);
  });

  it("un autre onglet a déjà renouvelé : on adopte ses jetons sans rappeler le serveur", async () => {
    const failed = useAuthStore.getState().accessToken;
    const fromOtherTab = jwt(3600, "other-tab");
    otherTabWrites(fromOtherTab, "refresh-2");
    const post = vi.fn();
    await expect(refreshAccessToken(failed, post)).resolves.toBe(fromOtherTab);
    expect(post).not.toHaveBeenCalled();
    expect(useAuthStore.getState().refreshToken).toBe("refresh-2");
  });

  it("course entre onglets sans verrou : refus du serveur MAIS jeton tourné ailleurs → pas de déconnexion", async () => {
    const failed = useAuthStore.getState().accessToken;
    const winner = jwt(3600, "winner");
    const post = vi.fn(async () => {
      otherTabWrites(winner, "refresh-from-other-tab"); // l'autre onglet gagne pendant notre requête
      throw Object.assign(new Error("blacklisted"), { response: { status: 401 } });
    });
    await expect(refreshAccessToken(failed, post)).resolves.toBe(winner);
    expect(useAuthStore.getState().accessToken).toBe(winner);
  });

  it("coupure réseau pendant le renouvellement : la session est CONSERVÉE", async () => {
    const before = useAuthStore.getState();
    const post = vi.fn(async () => { throw Object.assign(new Error("Network Error"), { code: "ERR_NETWORK" }); });
    await expect(refreshAccessToken(before.accessToken, post)).rejects.toThrow("Network Error");
    expect(useAuthStore.getState().refreshToken).toBe("refresh-1");
    expect(useAuthStore.getState().user).toEqual(USER);
  });

  it("refus réel (jeton expiré/révoqué, aucun autre onglet) : fin de session explicite", async () => {
    const post = vi.fn(async () => { throw Object.assign(new Error("token_not_valid"), { response: { status: 401 } }); });
    await expect(refreshAccessToken(useAuthStore.getState().accessToken, post)).rejects.toBeInstanceOf(SessionExpiredError);
    expect(useAuthStore.getState().accessToken).toBeNull();
    expect(readStoredTokens().refreshToken).toBeNull();
  });

  it("renouvellement préventif déjà fait par un autre onglet : rien n'est demandé", async () => {
    const fresh = jwt(3600, "fresh");
    otherTabWrites(fresh, "refresh-2");
    const post = vi.fn();
    await expect(refreshAccessToken(null, post)).resolves.toBe(fresh);
    expect(post).not.toHaveBeenCalled();
  });
});

describe("planification préventive", () => {
  it("renouvelle dans les 5 dernières minutes, pas avant", () => {
    expect(needsRefresh(jwt(3600))).toBe(false);
    expect(needsRefresh(jwt(240))).toBe(true);
    expect(needsRefresh(jwt(-1))).toBe(true);
    expect(needsRefresh(null)).toBe(false);
    expect(tokenExpiry("pas-un-jwt")).toBeNull();
  });

  it("session longue simulée (75 min, jeton de 60 min) : jamais déconnecté", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    try {
      const start = Date.now();
      let counter = 0;
      const post = vi.fn(async (rt) => {
        counter += 1;
        return { access: jwt(3600, `t${counter}`), refresh: `${rt}-r${counter}` };
      });
      useAuthStore.getState().setAuth(USER, jwt(3600, "t0"), "refresh-1");
      for (let minute = 0; minute <= 75; minute += 1) {
        vi.setSystemTime(start + minute * 60 * 1000);
        if (needsRefresh(useAuthStore.getState().accessToken)) {
          await refreshAccessToken(null, post);
        }
        expect(useAuthStore.getState().accessToken).not.toBeNull();
      }
      expect(post).toHaveBeenCalledTimes(1);   // une rotation, vers la 55e minute
      expect(useAuthStore.getState().user).toEqual(USER);
    } finally {
      vi.useRealTimers();
    }
  });
});
