import { describe, expect, it } from "vitest";

import {
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
    expect(audiencePayload(a)).toEqual({ roles: ["parent"], all_profiles: false, include_ids: [], exclude_ids: [1] });
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
});
