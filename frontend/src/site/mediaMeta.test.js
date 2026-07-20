/**
 * Tests V5 — cohérence du système de point focal du site vitrine.
 *
 * Garantit qu'aucun réglage de cadrage ne pointe vers un média inexistant,
 * que chaque visuel utilisé par les pages statiques possède un point focal
 * délibéré (pas de recentrage aveugle), et que les valeurs sont des
 * object-position CSS valides. Sert de test de non-régression visuelle
 * structurel (les captures de référence complètent ce filet).
 */
import { describe, it, expect } from "vitest";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { MEDIA_META, OVERLAYS, slugFromSrc, metaFor } from "./mediaMeta";
import { LEVELS, ACTIVITIES } from "./content";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const IMG_DIR = path.resolve(HERE, "../../public/site/img");
const POS_RE = /^(\d{1,3})% (\d{1,3})%$/;

function assertValidPosition(pos, label) {
  const m = pos.match(POS_RE);
  expect(m, `${label} : position invalide « ${pos} »`).toBeTruthy();
  expect(Number(m[1])).toBeLessThanOrEqual(100);
  expect(Number(m[2])).toBeLessThanOrEqual(100);
}

describe("mediaMeta — registre des points focaux", () => {
  it("chaque slug du registre correspond à des fichiers packagés réels (800 et 1600)", () => {
    for (const slug of Object.keys(MEDIA_META)) {
      for (const size of [800, 1600]) {
        const file = path.join(IMG_DIR, `${slug}-${size}.webp`);
        expect(fs.existsSync(file), `fichier manquant : ${slug}-${size}.webp`).toBe(true);
      }
    }
  });

  it("chaque fichier packagé possède une entrée dans le registre (aucun cadrage aveugle)", () => {
    const slugs = new Set(
      fs.readdirSync(IMG_DIR)
        .filter((f) => f.endsWith("-1600.webp"))
        .map((f) => f.replace(/-1600\.webp$/, "")),
    );
    for (const slug of slugs) {
      expect(MEDIA_META[slug], `slug sans point focal défini : ${slug}`).toBeTruthy();
    }
  });

  it("toutes les positions (desktop et mobile) sont des object-position valides", () => {
    for (const [slug, meta] of Object.entries(MEDIA_META)) {
      assertValidPosition(meta.position, slug);
      if (meta.mobile) assertValidPosition(meta.mobile, `${slug} (mobile)`);
    }
  });

  it("slugFromSrc/metaFor résolvent les URLs packagées", () => {
    expect(slugFromSrc("/site/img/hero-campus-1600.webp")).toBe("hero-campus");
    expect(slugFromSrc("/site/img/hero-campus-800.webp")).toBe("hero-campus");
    expect(slugFromSrc("/media/website/upload.jpg")).toBeNull();
    expect(metaFor("/site/img/apropos-encadrement-1600.webp").position).toBe("50% 16%");
    expect(metaFor("https://exemple.org/x.jpg").position).toBe("50% 50%");
  });

  it("les compositions des pages (niveaux, activités) référencent des médias et overlays existants", () => {
    for (const lvl of LEVELS) {
      expect(slugFromSrc(lvl.img), `LEVELS ${lvl.name}`).toBeTruthy();
      expect(MEDIA_META[slugFromSrc(lvl.img)], `focal manquant pour ${lvl.img}`).toBeTruthy();
      expect(Object.keys(OVERLAYS)).toContain(lvl.overlay);
    }
    for (const act of ACTIVITIES) {
      expect(MEDIA_META[slugFromSrc(act.img)], `focal manquant pour ${act.img}`).toBeTruthy();
    }
  });

  it("les dégradés du design system n'utilisent que les couleurs de marque FEBA", () => {
    for (const [name, cls] of Object.entries(OVERLAYS)) {
      if (!cls) continue;
      expect(cls, `overlay ${name}`).toMatch(/feba-(navy|green|gold|cream)/);
    }
  });
});
