/**
 * Régression P0 — une réponse ne doit jamais survivre à la bascule
 * d'académie qui l'a rendue obsolète.
 *
 * Le symptôme rapporté était : « le sélecteur change, mais les données
 * restent celles de l'ancienne académie pendant plusieurs secondes ».
 * Ces tests verrouillent les deux mécanismes qui l'empêchent — l'annulation
 * des requêtes en vol et le rejet des réponses de portée incorrecte.
 */
import { beforeEach, describe, expect, it } from "vitest";
import {
  SCOPE_ALL,
  SCOPE_UNKNOWN,
  abortInflightRequests,
  getAcademyScope,
  inflightCount,
  isStaleResponse,
  releaseRequest,
  resetAcademyScope,
  setAcademyScope,
  trackRequest,
} from "./academyScope";

beforeEach(() => resetAcademyScope());

describe("portée d'académie", () => {
  it("part d'une portée inconnue tant que le serveur n'a rien dit", () => {
    expect(getAcademyScope()).toBe(SCOPE_UNKNOWN);
  });

  it("signale un changement réel et ignore une réaffectation identique", () => {
    expect(setAcademyScope("FEBA")).toBe(true);
    expect(setAcademyScope("FEBA")).toBe(false);
    expect(setAcademyScope("FEBA_FHA")).toBe(true);
  });
});

describe("annulation des requêtes en vol", () => {
  it("avorte toutes les requêtes ouvertes lors d'une bascule", () => {
    const a = trackRequest();
    const b = trackRequest();
    expect(inflightCount()).toBe(2);

    setAcademyScope("FEBA_FHA");

    expect(a.signal.aborted).toBe(true);
    expect(b.signal.aborted).toBe(true);
    expect(inflightCount()).toBe(0);
  });

  it("n'avorte pas les requêtes émises APRÈS la bascule", () => {
    setAcademyScope("FEBA");
    const before = trackRequest();
    setAcademyScope("FEBA_FHA");
    const after = trackRequest();

    expect(before.signal.aborted).toBe(true);
    expect(after.signal.aborted).toBe(false);
  });

  it("libère les requêtes terminées pour ne pas les avorter inutilement", () => {
    const done = trackRequest();
    releaseRequest(done);
    abortInflightRequests();
    expect(done.signal.aborted).toBe(false);
  });
});

describe("rejet des réponses périmées", () => {
  it("écarte une réponse calculée pour l'académie quittée", () => {
    setAcademyScope("FEBA_FHA");
    expect(isStaleResponse("FEBA")).toBe(true);
  });

  it("accepte une réponse de l'académie affichée", () => {
    setAcademyScope("FEBA_FHA");
    expect(isStaleResponse("FEBA_FHA")).toBe(false);
  });

  it("distingue le mode consolidé d'une académie précise", () => {
    setAcademyScope(SCOPE_ALL);
    expect(isStaleResponse("FEBA")).toBe(true);
    expect(isStaleResponse(SCOPE_ALL)).toBe(false);
  });

  it("laisse passer les réponses du tout premier chargement", () => {
    // Portée encore inconnue : rejeter bloquerait le démarrage de l'application.
    expect(isStaleResponse("FEBA")).toBe(false);
  });

  it("laisse passer une réponse sans en-tête (serveur plus ancien)", () => {
    setAcademyScope("FEBA");
    expect(isStaleResponse(undefined)).toBe(false);
    expect(isStaleResponse("")).toBe(false);
  });

  /**
   * Régression : le contrôle de portée rejetait la BASCULE elle-même.
   *
   * Le serveur enregistrait bien le changement d'académie et répondait 200,
   * mais sa réponse annonçait la NOUVELLE portée — forcément différente de
   * celle que le client avait au moment de l'envoi. Elle était donc traitée
   * comme périmée et rejetée : `onSuccess` ne s'exécutait jamais, et le
   * sélecteur restait figé sur l'académie précédente alors que le serveur
   * avait basculé. Symptôme visible : cliquer sur « FEBA FHA » ne changeait
   * rien à l'écran.
   */
  describe("exemption des endpoints de contexte", () => {
    it("n'écarte jamais la réponse de la bascule d'académie", () => {
      setAcademyScope("FEBA");
      expect(isStaleResponse("FEBA_FHA", "/auth/entity-context/switch/")).toBe(false);
    });

    it("n'écarte jamais la lecture du contexte d'académie", () => {
      setAcademyScope("FEBA");
      expect(isStaleResponse("FEBA_FHA", "/auth/entity-context/")).toBe(false);
    });

    it("continue d'écarter les données métier périmées", () => {
      setAcademyScope("FEBA");
      expect(isStaleResponse("FEBA_FHA", "/students/")).toBe(true);
    });
  });
});
