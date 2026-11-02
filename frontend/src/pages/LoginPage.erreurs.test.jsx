import { describe, it, expect, vi } from "vitest";
import { messageErreurConnexion } from "./LoginPage";

vi.mock("../hooks/useAuth", () => ({ useAuth: () => ({}) }));
vi.mock("../hooks/useBranding", () => ({ useBranding: () => ({}) }));

const INCORRECT = /incorrects/i;

describe("message d'erreur de connexion", () => {
  it("annonce des identifiants incorrects seulement si le serveur les refuse", () => {
    expect(messageErreurConnexion({ response: { status: 400, data: {} } })).toMatch(INCORRECT);
  });
  it.each([
    ["annulation", { code: "ERR_CANCELED" }],
    ["réseau", new Error("Network Error")],
    ["panne", { response: { status: 502 } }],
    ["serveur", { response: { status: 500 } }],
    ["limite", { response: { status: 429 } }],
  ])("%s : jamais d'identifiants incorrects", (_, erreur) => {
    expect(messageErreurConnexion(erreur)).not.toMatch(INCORRECT);
  });
  it("transmet le refus du serveur", () => {
    const m = messageErreurConnexion({ response: { status: 400, data: { non_field_errors: ["Ce compte est désactivé."] } } });
    expect(m).toMatch(/désactivé/);
  });
});
