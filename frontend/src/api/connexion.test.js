import { describe, it, expect, afterEach } from "vitest";
import api from "./index";
import { abortInflightRequests, resetAcademyScope, setAcademyScope } from "./academyScope";

const adaptateur = (entete) => (config) => new Promise((ok, ko) => {
  config.signal?.addEventListener?.("abort", () => { const e = new Error("annulée"); e.code = "ERR_CANCELED"; e.config = config; ko(e); });
  setTimeout(() => ok({ status: 200, data: { id: 1 }, headers: { "x-academy-scope": entete }, config }), 20);
});

describe("lecture du profil à la connexion", () => {
  afterEach(() => resetAcademyScope());

  it("n'est pas annulée par une bascule de portée", async () => {
    const p = api.get("/auth/me/", { horsPortee: true, adapter: adaptateur("FEBA") });
    setAcademyScope("FEBA_FHA");
    abortInflightRequests();
    expect((await p).data.id).toBe(1);
  });

  it("n'est pas rejetée comme périmée", async () => {
    setAcademyScope("FEBA_FHA");
    const r = await api.get("/auth/me/", { horsPortee: true, adapter: adaptateur("FEBA") });
    expect(r.status).toBe(200);
  });

  it("garde le jeton fourni, pas celui d'une session expirée", async () => {
    const r = await api.get("/auth/me/", { horsPortee: true, headers: { Authorization: "Bearer neuf" }, adapter: adaptateur("x") });
    expect(r.config.headers.Authorization).toBe("Bearer neuf");
  });

  it("une écriture n'est ni annulée ni rejetée après une bascule", async () => {
    setAcademyScope("FEBA");
    const p = api.post("/payments/", {}, { adapter: adaptateur("FEBA") });
    setAcademyScope("FEBA_FHA");
    abortInflightRequests();
    expect((await p).status).toBe(200);
  });

  it("témoin : une requête métier reste annulée à la bascule", async () => {
    const p = api.get("/grades/", { adapter: adaptateur("FEBA") });
    setAcademyScope("FEBA_FHA");
    await expect(p).rejects.toBeTruthy();
  });
});
