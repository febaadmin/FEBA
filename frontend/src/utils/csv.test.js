import { describe, it, expect } from "vitest";
import { celluleCsv } from "./csv";

describe("celluleCsv", () => {
  it("neutralise une formule", () => {
    expect(celluleCsv('=HYPERLINK("http://x")')).toBe('"\'=HYPERLINK(""http://x"")"');
    expect(celluleCsv("@SUM(A1)")).toBe('"\'@SUM(A1)"');
  });
  it("garde les nombres, téléphones et textes", () => {
    expect(celluleCsv("-5")).toBe('"-5"');
    expect(celluleCsv("+229 97 00 00 00")).toBe('"+229 97 00 00 00"');
    expect(celluleCsv("Awa")).toBe('"Awa"');
    expect(celluleCsv(null)).toBe('""');
  });
});
