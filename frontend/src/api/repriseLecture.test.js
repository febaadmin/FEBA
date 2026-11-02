import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import api from "./index";

describe("reprise pendant un redémarrage", () => {
  let appels;
  const adaptateur = (statuts) => async (config) => {
    const statut = statuts[Math.min(appels, statuts.length - 1)];
    appels += 1;
    if (statut >= 400) {
      const e = new Error(String(statut));
      e.config = config;
      e.response = { status: statut, headers: {}, config };
      throw e;
    }
    return { status: statut, data: {}, headers: {}, config };
  };
  beforeEach(() => { appels = 0; vi.useFakeTimers(); });
  afterEach(() => { vi.useRealTimers(); });

  it("rejoue une lecture après un 502", async () => {
    const p = api.get("/x/", { adapter: adaptateur([502, 502, 200]) });
    await vi.runAllTimersAsync();
    expect((await p).status).toBe(200);
    expect(appels).toBe(3);
  });

  it("ne rejoue pas un 503 de l'application", async () => {
    const p = api.get("/x/", { adapter: adaptateur([503, 200]) }).catch((e) => e.response.status);
    await vi.runAllTimersAsync();
    expect(await p).toBe(503);
    expect(appels).toBe(1);
  });

  it("ne rejoue jamais une écriture", async () => {
    const p = api.post("/x/", {}, { adapter: adaptateur([502, 200]) }).catch((e) => e.response.status);
    await vi.runAllTimersAsync();
    expect(await p).toBe(502);
    expect(appels).toBe(1);
  });

  it("abandonne après plusieurs échecs", async () => {
    const p = api.get("/x/", { adapter: adaptateur([502]) }).catch((e) => e.response.status);
    await vi.runAllTimersAsync();
    expect(await p).toBe(502);
    expect(appels).toBe(5);
  });
});
