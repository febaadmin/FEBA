import { describe, expect, it } from "vitest";

import {
  academyNowParts, formatCalendarDate, formatDateTime, paymentDateTimeText, paymentSortValue,
} from "./datetime";

/**
 * P1 — La colonne « Date » des paiements affiche la date ET l'heure
 * (JJ/MM/AAAA HH:mm), dans le fuseau de l'académie, et n'invente jamais
 * une heure qui n'a pas été enregistrée.
 */
describe("formatDateTime", () => {
  it("formate en JJ/MM/AAAA HH:mm dans le fuseau de Cotonou", () => {
    expect(formatDateTime("2026-10-09T13:37:00Z", "Africa/Porto-Novo")).toBe("09/10/2026 14:37");
  });

  it("formate dans le fuseau de New York (FHA)", () => {
    expect(formatDateTime("2026-10-09T18:37:00Z", "America/New_York")).toBe("09/10/2026 14:37");
  });

  it("gère le changement de jour et de mois", () => {
    // 1er novembre 03:30 UTC = 31 octobre 23:30 à New York.
    expect(formatDateTime("2026-11-01T03:30:00Z", "America/New_York")).toBe("31/10/2026 23:30");
  });

  it("distingue les minutes", () => {
    const a = formatDateTime("2026-10-09T09:05:00Z", "UTC");
    const b = formatDateTime("2026-10-09T09:06:00Z", "UTC");
    expect(a).toBe("09/10/2026 09:05");
    expect(b).toBe("09/10/2026 09:06");
  });

  it("ne plante pas sur une valeur vide ou un fuseau inconnu", () => {
    expect(formatDateTime(null, "UTC")).toBe("");
    expect(formatDateTime("2026-10-09T09:05:00Z", "Pas/UnFuseau")).toMatch(/09\/10\/2026|10\/09\/2026/);
  });
});

describe("paymentDateTimeText", () => {
  it("affiche l'heure quand elle est connue", () => {
    expect(paymentDateTimeText({
      paid_at: "2026-10-09T13:37:00Z", academy_timezone: "Africa/Porto-Novo", payment_date: "2026-10-09",
    })).toBe("09/10/2026 14:37");
  });

  it("affiche la date seule quand l'heure n'a jamais été enregistrée", () => {
    expect(paymentDateTimeText({ paid_at: null, payment_date: "2026-10-01" })).toBe("01/10/2026");
  });

  it("une date calendaire n'est jamais décalée par le fuseau", () => {
    expect(formatCalendarDate("2026-10-01")).toBe("01/10/2026");
  });
});

describe("paymentSortValue", () => {
  it("ordonne chronologiquement à la minute près", () => {
    const rows = [
      { paid_at: "2026-10-09T10:06:00Z" },
      { paid_at: "2026-10-09T10:05:00Z" },
      { paid_at: null, payment_date: "2026-10-08" },
    ];
    const sorted = [...rows].sort((a, b) => paymentSortValue(a) - paymentSortValue(b));
    expect(sorted.map((r) => r.paid_at)).toEqual([null, "2026-10-09T10:05:00Z", "2026-10-09T10:06:00Z"]);
  });
});

describe("academyNowParts", () => {
  it("donne la date et l'heure de l'académie, pas la date UTC", () => {
    // 9 oct. 02:30 UTC : déjà le 9 à Cotonou, encore le 8 à New York.
    const now = new Date("2026-10-09T02:30:00Z");
    expect(academyNowParts("Africa/Porto-Novo", now)).toEqual({ date: "2026-10-09", time: "03:30" });
    expect(academyNowParts("America/New_York", now)).toEqual({ date: "2026-10-08", time: "22:30" });
  });
});
