import { describe, it, expect, vi } from "vitest";
import toast from "react-hot-toast";
import { signalerErreurLecture } from "./erreursRequetes";

vi.mock("react-hot-toast", () => ({ default: { error: vi.fn() } }));

describe("signalerErreurLecture", () => {
  it("prévient sur une panne ou une coupure", () => {
    expect(signalerErreurLecture({ response: { status: 500 } })).toBe(true);
    expect(signalerErreurLecture(new Error("Network Error"))).toBe(true);
    expect(toast.error).toHaveBeenCalledTimes(2);
  });
  it("se tait sur une annulation, un refus ou un 404", () => {
    toast.error.mockClear();
    expect(signalerErreurLecture({ code: "ERR_CANCELED" })).toBe(false);
    expect(signalerErreurLecture({ isStaleAcademy: true })).toBe(false);
    expect(signalerErreurLecture({ response: { status: 403 } })).toBe(false);
    expect(signalerErreurLecture({ response: { status: 404 } })).toBe(false);
    expect(signalerErreurLecture({ response: { status: 503 } })).toBe(false);
    expect(toast.error).not.toHaveBeenCalled();
  });
});

describe("signalerErreurEcriture", () => {
  it("affiche le motif du serveur quand l'écran ne gère pas l'erreur", async () => {
    const { signalerErreurEcriture } = await import("./erreursRequetes");
    toast.error.mockClear();
    const refus = { response: { status: 400, data: { detail: "Suppression impossible : compte lié à des notes." } } };
    expect(signalerErreurEcriture(refus, {}, {}, { options: {} })).toBe(true);
    expect(toast.error).toHaveBeenCalledWith("Suppression impossible : compte lié à des notes.");
  });
  it("laisse l'écran parler quand il gère l'erreur, et ignore les annulations", async () => {
    const { signalerErreurEcriture } = await import("./erreursRequetes");
    toast.error.mockClear();
    expect(signalerErreurEcriture({ response: { status: 400 } }, {}, {}, { options: { onError: () => {} } })).toBe(false);
    expect(signalerErreurEcriture({ response: { status: 400 } }, {}, {}, { options: {}, meta: { erreurGeree: true } })).toBe(false);
    expect(signalerErreurEcriture({ code: "ERR_CANCELED" }, {}, {}, { options: {} })).toBe(false);
    expect(toast.error).not.toHaveBeenCalled();
  });
  it("branché sur le client : une mutation sans onError affiche l'erreur une seule fois", async () => {
    const { signalerErreurEcriture } = await import("./erreursRequetes");
    const { MutationCache, QueryClient } = await import("@tanstack/react-query");
    toast.error.mockClear();
    const client = new QueryClient({ mutationCache: new MutationCache({ onError: signalerErreurEcriture }) });
    const refus = { response: { status: 409, data: { detail: "Déjà supprimé." } } };
    await client.getMutationCache().build(client, { mutationFn: () => Promise.reject(refus) }).execute().catch(() => {});
    await client.getMutationCache().build(client, { mutationFn: () => Promise.reject(refus), onError: () => {} }).execute().catch(() => {});
    expect(toast.error).toHaveBeenCalledTimes(1);
  });
});
