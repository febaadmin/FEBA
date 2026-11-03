import { describe, it, expect, vi } from "vitest";
import { sansDoublon } from "./sansDoublon";

const attente = () => new Promise((fin) => { setTimeout(() => fin({ status: 201 }), 10); });

describe("sansDoublon", () => {
  it("n'envoie qu'une fois une écriture identique en cours", async () => {
    const envoi = vi.fn(attente);
    const a = sansDoublon(envoi);
    const c = { method: "post", url: "/payments/", data: '{"montant":1}' };
    const [x, y] = await Promise.all([a(c), a({ ...c })]);
    expect(envoi).toHaveBeenCalledTimes(1);
    expect(x).toBe(y);
  });
  it("laisse passer une écriture différente", async () => {
    const envoi = vi.fn(attente);
    const a = sansDoublon(envoi);
    await Promise.all([a({ method: "post", url: "/p/", data: "1" }), a({ method: "post", url: "/p/", data: "2" })]);
    expect(envoi).toHaveBeenCalledTimes(2);
  });
  it("renvoie la même écriture une fois la première terminée, même en échec", async () => {
    const envoi = vi.fn().mockRejectedValueOnce(new Error("x")).mockResolvedValueOnce({ status: 201 });
    const a = sansDoublon(envoi);
    const c = { method: "post", url: "/p/", data: "1" };
    await expect(a(c)).rejects.toThrow();
    await expect(a(c)).resolves.toEqual({ status: 201 });
  });
  it("ne touche pas aux lectures", async () => {
    const envoi = vi.fn(attente);
    const a = sansDoublon(envoi);
    await Promise.all([a({ method: "get", url: "/p/" }), a({ method: "get", url: "/p/" })]);
    expect(envoi).toHaveBeenCalledTimes(2);
  });
  it("distingue deux fichiers différents", async () => {
    const envoi = vi.fn(attente);
    const a = sansDoublon(envoi);
    const f = (n) => { const d = new FormData(); d.append("f", new File(["x"], n)); return d; };
    await Promise.all([a({ method: "post", url: "/p/", data: f("a") }), a({ method: "post", url: "/p/", data: f("b") })]);
    expect(envoi).toHaveBeenCalledTimes(2);
  });
});
