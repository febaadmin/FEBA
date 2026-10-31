// `mutationFn: xAPI.y` : React Query appelle y(variables, contexte). Si y a un
// 2e paramètre, le contexte y entre et part au serveur (ERR-72B72D et suivants).
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const SRC = join(__dirname, "..");
const fichiers = (d) => readdirSync(d).flatMap((n) => {
  const p = join(d, n);
  return statSync(p).isDirectory() ? fichiers(p) : /\.jsx?$/.test(n) ? [p] : [];
});

describe("mutationFn et méthodes d'API", () => {
  it("aucune méthode à plusieurs paramètres n'est passée directement", () => {
    const api = readFileSync(join(SRC, "api/index.js"), "utf8");
    const multiples = new Set();
    for (const bloc of api.matchAll(/export const (\w+) *= *\{([\s\S]*?)\n\};/g)) {
      for (const m of bloc[2].matchAll(/^\s*(\w+):\s*\(([^)]*)\)\s*=>/gm)) {
        if (m[2].includes(",")) multiples.add(`${bloc[1]}.${m[1]}`);
      }
    }
    expect(multiples.has("gradesAPI.delete")).toBe(true);
    const fautes = [];
    for (const f of fichiers(SRC)) {
      for (const m of readFileSync(f, "utf8").matchAll(/mutationFn:\s*(\w+\.\w+)\s*[,}\n]/g)) {
        if (multiples.has(m[1])) fautes.push(`${f}: ${m[1]}`);
      }
    }
    expect(fautes).toEqual([]);
  });
});
