/**
 * P6 — Un message long ne doit JAMAIS être coupé.
 *
 * Les neuf cas demandés sont couverts : 10, 500 et 5 000 caractères, un mot
 * continu de 300 caractères, une URL très longue, des retours à la ligne,
 * des accents, des caractères spéciaux, et un contenu qui ressemble à du
 * HTML ou du JavaScript.
 *
 * Le test le plus important est le dernier de la première série : il
 * interdit `text-overflow: ellipsis` et `line-clamp`. Trois petits points à
 * la place de la fin d'un message ne signalent pas un défaut d'affichage —
 * ils font croire que le visiteur s'est arrêté là.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import LongText from "./LongText";

const block = () => screen.getByTestId("long-text");

describe("LongText — le texte intégral est conservé", () => {
  it("affiche un texte court tel quel", () => {
    render(<LongText value="Bonjour !!" />);
    expect(block().textContent).toBe("Bonjour !!");
  });

  it("affiche 500 caractères sans en perdre un seul", () => {
    const value = "a".repeat(500);
    render(<LongText value={value} />);
    expect(block().textContent).toHaveLength(500);
  });

  it("affiche 5 000 caractères sans troncature", () => {
    const value = "Message très long. ".repeat(280).slice(0, 5000);
    render(<LongText value={value} />);
    expect(block().textContent).toBe(value);
    expect(block().textContent).toHaveLength(5000);
  });

  it("conserve un mot continu de 300 caractères", () => {
    const value = "M".repeat(300);
    render(<LongText value={value} />);
    expect(block().textContent).toBe(value);
  });

  it("conserve une URL très longue", () => {
    const value =
      "https://exemple.test/" + "chemin-tres-long/".repeat(20) + "?q=" + "x".repeat(120);
    render(<LongText value={value} />);
    expect(block().textContent).toBe(value);
  });

  it("préserve les retours à la ligne et les lignes vides", () => {
    const value = "Ligne 1\n\nLigne 3\nLigne 4";
    render(<LongText value={value} />);
    expect(block().textContent).toBe(value);
  });

  it("préserve les accents et les caractères spéciaux", () => {
    const value = "Élisabeth Ahouéfa Gbêdjissi — « N’Guessan » · 100 % ✓ €$£";
    render(<LongText value={value} />);
    expect(block().textContent).toBe(value);
  });

  it("affiche un contenu ressemblant à du HTML comme du texte", () => {
    const value = "<script>alert('xss')</script><img src=x onerror=alert(1)>";
    render(<LongText value={value} />);
    // Le texte est présent LITTÉRALEMENT…
    expect(block().textContent).toBe(value);
    // …et aucune balise n'a été créée dans le DOM.
    expect(block().querySelector("script")).toBeNull();
    expect(block().querySelector("img")).toBeNull();
  });

  it("affiche un repère lisible quand le message est vide", () => {
    render(<LongText value="" emptyLabel="—" />);
    expect(screen.getByText("—")).toBeTruthy();
  });
});

describe("LongText — mise en forme", () => {
  it("se replie au lieu de déborder", () => {
    render(<LongText value={"x".repeat(300)} />);
    const style = block().style;
    expect(style.whiteSpace).toBe("pre-wrap");
    expect(style.overflowWrap).toBe("anywhere");
    expect(style.wordBreak).toBe("break-word");
  });

  it("défile verticalement au lieu de repousser les boutons", () => {
    render(<LongText value={"ligne\n".repeat(400)} />);
    expect(block().style.maxHeight).toBeTruthy();
    expect(block().className).toContain("overflow-y-auto");
  });

  it("ne peut pas déborder horizontalement", () => {
    render(<LongText value={"y".repeat(1000)} />);
    expect(block().className).toContain("overflow-x-hidden");
  });

  it("n'utilise ni ellipsis ni line-clamp", () => {
    render(<LongText value={"z".repeat(2000)} />);
    const element = block();
    expect(element.style.textOverflow).not.toBe("ellipsis");
    expect(element.className).not.toContain("truncate");
    expect(element.className).not.toContain("line-clamp");
    expect(element.className).not.toContain("text-ellipsis");
  });

  it("propose une action de copie du texte intégral", () => {
    render(<LongText value="Texte à copier" />);
    expect(screen.getByRole("button", { name: /copier/i })).toBeTruthy();
  });
});
