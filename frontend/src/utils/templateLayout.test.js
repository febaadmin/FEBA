/**
 * Géométrie des gabarits : millimètres stables, conversion écran → page,
 * zones ramenées dans la page, superpositions détectées.
 */
import { describe, it, expect } from "vitest";
import { boxStyle, clampBox, layoutProblems, newField, overlaps, pxToMm } from "./templateLayout";

const A4L = { width_mm: 297, height_mm: 210 };
const A4P = { width_mm: 210, height_mm: 297 };

describe("templateLayout", () => {
  it("exprime une zone en pourcentage de la page, quelle que soit la taille de l'écran", () => {
    const style = boxStyle({ x_mm: 29.7, y_mm: 21, width_mm: 148.5, height_mm: 10.5 }, A4L);
    expect(style).toEqual({ left: "10%", top: "10%", width: "50%", height: "5%" });
  });

  it("convertit un déplacement en pixels en millimètres selon la largeur rendue", () => {
    expect(pxToMm(100, 1000, 297)).toBeCloseTo(29.7);
    expect(pxToMm(100, 500, 297)).toBeCloseTo(59.4); // même geste, écran deux fois plus petit
    expect(pxToMm(10, 0, 297)).toBe(0);
  });

  it("ramène une zone dans la page et impose une taille minimale", () => {
    const box = clampBox({ x_mm: 290, y_mm: -5, width_mm: 50, height_mm: 1 }, A4L);
    expect(box).toMatchObject({ x_mm: 247, y_mm: 0, width_mm: 50, height_mm: 3 });
    const portrait = clampBox({ x_mm: 0, y_mm: 280, width_mm: 400, height_mm: 30 }, A4P);
    expect(portrait).toMatchObject({ width_mm: 210, y_mm: 267 });
  });

  it("détecte superpositions, zones hors page et nom manquant", () => {
    const a = { name: "student_name", x_mm: 10, y_mm: 10, width_mm: 100, height_mm: 20 };
    const b = { name: "issue_date", x_mm: 50, y_mm: 25, width_mm: 40, height_mm: 10 };
    const c = { name: "class_name", x_mm: 200, y_mm: 200, width_mm: 120, height_mm: 30 };
    expect(overlaps(a, b)).toBe(true);
    const problems = layoutProblems([a, b, c], A4L);
    expect(problems.map((p) => p.type).sort()).toEqual(["outside", "overlap"]);
    expect(layoutProblems([b], A4L).map((p) => p.type)).toContain("missing_name");
    // Deux zones bord à bord ne se chevauchent pas.
    expect(overlaps(a, { ...b, y_mm: 30 })).toBe(false);
  });

  it("pose un nouveau champ sans recouvrir les zones existantes", () => {
    const first = newField("student_name", A4L);
    const second = newField("issue_date", A4L, [first]);
    expect(overlaps(first, second)).toBe(false);
    expect(first.required).toBe(true);
    expect(second.required).toBe(false);
    expect(second.x_mm + second.width_mm).toBeLessThanOrEqual(297);
  });
});
