/**
 * Badge d'académie : texte issu des données, teinte stable dérivée du code,
 * orange réservé à l'objet sans académie.
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const ctx = vi.hoisted(() => ({ value: {} }));
vi.mock("../context/AcademyContext", () => ({ useAcademy: () => ctx.value }));

import AcademyBadge, { academyTone } from "./AcademyBadge";
import FeatureGate from "./FeatureGate";

describe("AcademyBadge", () => {
  it("une académie inconnue du code (testete) n'est pas présentée comme en défaut", () => {
    render(<AcademyBadge code="TESTETE" name="Académie Évangélique Saint-Éloi de Natitingou" shortName="Saint-Éloi" />);
    const badge = screen.getByText("Saint-Éloi").closest("[title]");
    expect(badge.getAttribute("title")).toBe("Académie Évangélique Saint-Éloi de Natitingou");
    expect(badge.className).not.toMatch(/amber/);
  });

  it("sans abréviation : le nom ; nom long tronqué, complet en info-bulle", () => {
    const long = "Académie Évangélique Saint-Éloi de Natitingou - Programme Francophone";
    render(<AcademyBadge code="TESTETE" name={long} />);
    const text = screen.getByText(long);
    expect(text.className).toMatch(/truncate/);
    expect(text.parentElement.getAttribute("title")).toBe(long);
  });

  it("teinte stable par code, identique entre deux rendus", () => {
    expect(academyTone("TESTETE")).toBe(academyTone("TESTETE"));
    const tones = new Set(Array.from({ length: 19 }, (_, i) => academyTone(`ACAD_${i}`)));
    expect(tones.size).toBeGreaterThan(3);
  });

  it("objet sans académie : « Sans académie », en orange", () => {
    render(<AcademyBadge />);
    expect(screen.getByText("Sans académie").parentElement.className).toMatch(/amber/);
  });
});

describe("FeatureGate", () => {
  it("URL saisie à la main sur une académie sans la fonctionnalité : message, pas l'écran", () => {
    ctx.value = { scopeReady: true, isAllAcademies: false, allowedAcademies: [],
      activeAcademy: { name: "Académie testete", short_name: "testete" }, hasFeature: () => false };
    render(<FeatureGate feature="online_admissions"><div data-testid="ecran" /></FeatureGate>);
    expect(screen.getByTestId("feature-unavailable").textContent).toMatch("n'est pas activée pour testete");
    expect(screen.queryByTestId("ecran")).toBeNull();
  });

  it("académie qui possède la fonctionnalité : l'écran s'affiche", () => {
    ctx.value = { scopeReady: true, isAllAcademies: false, allowedAcademies: [],
      activeAcademy: { name: "X" }, hasFeature: (f) => f === "online_admissions" };
    render(<FeatureGate feature="online_admissions"><div data-testid="ecran" /></FeatureGate>);
    expect(screen.getByTestId("ecran")).toBeTruthy();
  });

  it("contexte pas encore chargé : rien (pas de message trompeur)", () => {
    ctx.value = { scopeReady: false, hasFeature: () => false };
    const { container } = render(<FeatureGate feature="online_admissions"><div /></FeatureGate>);
    expect(container.textContent).toBe("");
  });
});
