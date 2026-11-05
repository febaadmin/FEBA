import { describe, expect, it } from "vitest";

import {
  ajouterEntree, champsVides, decouperAdresses, depuisAudience, MODES,
  audiencePayload, emptyAudience, hasAnyRule, isSelected, setUsers, toggleRole, toggleUser,
} from "./massEmailSelection";

const parentA = { id: 1, role: "parent", sendable: true };
const parentB = { id: 2, role: "parent", sendable: true };
const teacher = { id: 3, role: "teacher", sendable: true };
const inactive = { id: 4, role: "parent", sendable: false };

describe("sélection des destinataires", () => {
  it("un type de profil sélectionne tous ses membres joignables", () => {
    const a = toggleRole(emptyAudience(), "parent");
    expect(isSelected(parentA, a)).toBe(true);
    expect(isSelected(parentB, a)).toBe(true);
    expect(isSelected(teacher, a)).toBe(false);
    expect(isSelected(inactive, a)).toBe(false);
  });

  it("décocher un membre d'un profil sélectionné l'exclut", () => {
    let a = toggleRole(emptyAudience(), "parent");
    a = toggleUser(a, parentA);
    expect(isSelected(parentA, a)).toBe(false);
    expect(audiencePayload(a)).toEqual({ roles: ["parent"], all_profiles: false, include_ids: [], exclude_ids: [1],
      adresses: { a: [], cc: [], cci: [] }, mode: "individuel" });
    a = toggleUser(a, parentA);
    expect(isSelected(parentA, a)).toBe(true);
    expect(a.exclude).toEqual([]);
  });

  it("cocher une personne hors profil l'inclut individuellement", () => {
    const a = toggleUser(emptyAudience(), teacher);
    expect(a.include).toEqual([3]);
    expect(hasAnyRule(a)).toBe(true);
    expect(toggleUser(a, teacher).include).toEqual([]);
  });

  it("un compte non joignable ne peut pas être coché", () => {
    expect(toggleUser(emptyAudience(), inactive)).toEqual(emptyAudience());
  });

  it("« Tous les profils » couvre chaque rôle", () => {
    const a = { ...emptyAudience(), allProfiles: true };
    expect([parentA, parentB, teacher].every((u) => isSelected(u, a))).toBe(true);
  });

  it("cocher / décocher la liste affichée ne touche que les lignes visibles", () => {
    let a = setUsers(emptyAudience(), [parentA, teacher, inactive], true);
    expect(a.include.sort()).toEqual([1, 3]);
    expect(isSelected(parentB, a)).toBe(false);
    a = setUsers(a, [teacher], false);
    expect(a.include).toEqual([1]);
  });

  it("champs À / Cc / Cci : découpage, validation, doublons, charge utile et reprise d'un brouillon", () => {
    expect(decouperAdresses("A@x.org; b@y.fr,  pas-valide c@z")).toEqual({ valides: ["a@x.org", "b@y.fr"], invalides: ["pas-valide", "c@z"] });
    let liste = ajouterEntree([], { type: "email", value: "a@x.org", label: "a@x.org" });
    liste = ajouterEntree(liste, { type: "email", value: "A@X.org", label: "A@X.org" });
    expect(liste).toHaveLength(1);
    const champs = { a: liste, cc: [{ type: "user", value: 7, label: "Prof <p@x.org>" }], cci: [] };
    expect(audiencePayload(emptyAudience(), champs, MODES.commun).adresses).toEqual({ a: ["a@x.org"], cc: [7], cci: [] });
    expect(hasAnyRule(emptyAudience(), champs)).toBe(true);
    expect(hasAnyRule(emptyAudience(), champsVides())).toBe(false);
    const repris = depuisAudience({ roles: ["parent"], adresses: { a: ["a@x.org"], cc: [7] }, mode: "commun" },
      [{ id: 7, full_name: "Prof", email: "p@x.org" }]);
    expect(repris.champs.cc[0].label).toBe("Prof <p@x.org>");
    expect(repris.mode).toBe("commun");
    expect(repris.audience.roles).toEqual(["parent"]);
  });
});
