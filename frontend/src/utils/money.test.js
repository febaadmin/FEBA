/**
 * Formatage des montants — miroir des tests backend.
 *
 * Le défaut corrigé : onze écrans écrivaient « FCFA » en dur, y compris
 * pour FEBA French Heritage Academy, qui facture en dollars. Le nombre
 * était juste, la monnaie fausse, et rien ne le signalait.
 */
import { describe, expect, it } from "vitest";
import {
  currencyRules, formatMinor, formatMoney, formatTotals, rowAmount, totalsByCurrency,
} from "./money";

describe("formatage par devise", () => {
  it("place le symbole avant en dollars", () => {
    expect(formatMoney(1250, "USD")).toBe("$1,250.00");
    expect(formatMoney(125.5, "USD")).toBe("$125.50");
  });

  it("place le symbole après en francs CFA, sans décimale", () => {
    expect(formatMoney(50000, "XOF")).toBe("50 000 FCFA");
    expect(formatMoney(1250, "XOF")).toBe("1 250 FCFA");
  });

  it("ne groupe pas les décimales avec le séparateur de milliers", () => {
    // Régression : appliquer le groupage à la chaîne entière produisait
    // « 1,250.0,0 ».
    expect(formatMoney(1250.55, "USD")).toBe("$1,250.55");
  });

  it("garde les montants négatifs lisibles", () => {
    expect(formatMoney(-125.5, "USD")).toBe("-$125.50");
  });

  it("n'invente aucun symbole pour une devise inconnue", () => {
    // Afficher un nombre nu est ambigu ; afficher la mauvaise devise est faux.
    expect(formatMoney(100, "EUR")).not.toContain("$");
    expect(formatMoney(100, "EUR")).not.toContain("FCFA");
    expect(currencyRules("EUR")).toBeNull();
  });
});

describe("unité mineure", () => {
  it("convertit les cents en dollars", () => {
    expect(formatMinor(125000, "USD")).toBe("$1,250.00");
  });

  it("traite le franc CFA comme sa propre unité mineure", () => {
    // 50 000 unités mineures = 50 000 FCFA, pas 500.
    expect(formatMinor(50000, "XOF")).toBe("50 000 FCFA");
  });
});

describe("montant d'une ligne d'API", () => {
  it("préfère toujours le rendu calculé par le serveur", () => {
    const row = { amount_display: "$99.00", amount: 1, currency: "USD" };
    expect(rowAmount(row)).toBe("$99.00");
  });

  it("retombe sur l'unité mineure et la devise de la ligne", () => {
    expect(rowAmount({ amount_minor: 12550, currency: "USD" })).toBe("$125.50");
  });
});

describe("totaux consolidés", () => {
  const rows = [
    { amount_minor: 125000, currency: "USD" },
    { amount_minor: 500000, currency: "XOF" },
    { amount_minor: 25000, currency: "USD" },
  ];

  it("ventile par devise au lieu d'additionner", () => {
    const totals = totalsByCurrency(rows);
    expect(totals).toHaveLength(2);
    expect(totals.find((t) => t.currency === "USD").amountMinor).toBe(150000);
    expect(totals.find((t) => t.currency === "XOF").amountMinor).toBe(500000);
  });

  it("rend deux lignes distinctes, jamais une somme", () => {
    // 1 500 $ + 500 000 FCFA n'a pas de résultat : le montrer comme un
    // seul nombre serait plus commode et complètement faux.
    expect(formatTotals(totalsByCurrency(rows))).toBe("$1,500.00 · 500 000 FCFA");
  });
});
