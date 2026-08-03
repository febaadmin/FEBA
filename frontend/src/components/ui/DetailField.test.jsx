import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import DetailField, { isLongValue, longestToken } from "./DetailField";

/**
 * P0 — La vue de détail n'a le droit ni de tronquer, ni de laisser sortir.
 *
 * Le panneau latéral d'une candidature FEBA FHA affichait chaque champ en
 * `flex justify-between` + `text-right`, sans aucune règle de repli. Une
 * adresse complète, un objectif parental de dix lignes ou une liste de
 * certifications restaient sur une seule ligne, écrasaient le libellé,
 * puis débordaient du panneau — six annotations « Les textes longs ne sont
 * pas bien cadrés » sur une seule capture d'écran.
 */

const MOT_300 = "M" + "o".repeat(298) + "T";
const URL_LONGUE =
  "https://feba-academy.example.org/dossiers/" +
  "segment-tres-long-".repeat(12) +
  "?token=" + "a".repeat(120);
const MESSAGE_5000 =
  "Bonjour,\n\nNotre fille a besoin d'un accompagnement <renforcé> " +
  "en lecture & en écriture.\n" +
  "Détail pédagogique. ".repeat(260) +
  "\n\nCordialement,\nFamille Adjovi-Bokô";

describe("longestToken", () => {
  it("mesure le plus long mot sans espace", () => {
    expect(longestToken("abc def")).toBe(3);
    expect(longestToken(MOT_300)).toBe(300);
    expect(longestToken("")).toBe(0);
  });

  it("compte les retours à la ligne comme des séparateurs", () => {
    expect(longestToken("court\ntresLongMotIci")).toBe("tresLongMotIci".length);
  });
});

describe("isLongValue", () => {
  it("garde en deux colonnes une valeur courte", () => {
    expect(isLongValue("Cotonou")).toBe(false);
    expect(isLongValue("+229 01 02 03 04")).toBe(false);
  });

  it("passe en pleine largeur dès qu'il y a un retour à la ligne", () => {
    // Une valeur de dix caractères sur deux lignes doit conserver ses
    // deux lignes : les aplatir change le sens de la réponse.
    expect(isLongValue("Un.\nDeux.")).toBe(true);
  });

  it("passe en pleine largeur pour un texte long", () => {
    expect(isLongValue("a".repeat(57).split("").join(" ").slice(0, 200))).toBe(true);
    expect(isLongValue(MESSAGE_5000)).toBe(true);
  });

  it("passe en pleine largeur pour un mot indivisible trop large", () => {
    expect(isLongValue(MOT_300)).toBe(true);
    expect(isLongValue(URL_LONGUE)).toBe(true);
  });

  it("ne considère pas une valeur vide comme longue", () => {
    expect(isLongValue("")).toBe(false);
    expect(isLongValue("   ")).toBe(false);
    expect(isLongValue(null)).toBe(false);
    expect(isLongValue(undefined)).toBe(false);
  });
});

describe("DetailField", () => {
  it("n'affiche rien pour un champ vide, par défaut", () => {
    const { container } = render(<DetailField label="Ville" value="" />);
    expect(container.firstChild).toBeNull();
  });

  it("peut marquer explicitement une absence de réponse", () => {
    render(<DetailField label="Ville" value={null} emptyLabel="Non renseigné" />);
    expect(screen.getByText("Non renseigné")).toBeTruthy();
  });

  it("affiche une valeur courte sur deux colonnes", () => {
    render(<DetailField label="Ville" value="Cotonou" />);
    expect(screen.getByTestId("detail-field-short")).toBeTruthy();
    expect(screen.getByText("Cotonou")).toBeTruthy();
  });

  it("passe un texte long en pleine largeur", () => {
    render(<DetailField label="Objectifs" value={MESSAGE_5000} />);
    expect(screen.getByTestId("detail-field-long")).toBeTruthy();
  });

  it("rend le texte long INTÉGRALEMENT, sans coupure", () => {
    render(<DetailField label="Objectifs" value={MESSAGE_5000} />);
    const bloc = screen.getByTestId("long-text");
    expect(bloc.textContent).toBe(MESSAGE_5000);
    expect(bloc.textContent).toContain("Famille Adjovi-Bokô");
    expect(bloc.textContent.endsWith("…")).toBe(false);
    expect(bloc.textContent.endsWith("...")).toBe(false);
  });

  it("applique les trois règles de repli, jamais une seule", () => {
    render(<DetailField label="Lien" value={URL_LONGUE} />);
    const bloc = screen.getByTestId("long-text");
    // Les trois propriétés viennent de la classe partagée `.text-longform`
    // (jsdom n'applique pas les feuilles Tailwind : on vérifie le contrat
    // de classe, la mesure réelle est faite dans le parcours navigateur).
    expect(bloc.className).toContain("text-longform");
  });

  it("ne pose aucune hauteur fixe dans une vue de détail", () => {
    render(<DetailField label="Objectifs" value={MESSAGE_5000} />);
    const bloc = screen.getByTestId("long-text");
    expect(bloc.style.maxHeight).toBe("");
    expect(bloc.className).not.toContain("overflow-y-auto");
    // Et les trois règles de repli sont bien posées, pas seulement
    // promises par une classe Tailwind susceptible d'être purgée.
    expect(bloc.style.whiteSpace).toBe("pre-wrap");
    expect(bloc.style.overflowWrap).toBe("anywhere");
    expect(bloc.style.wordBreak).toBe("break-word");
  });

  it("n'utilise jamais line-clamp ni ellipsis", () => {
    render(<DetailField label="Objectifs" value={MESSAGE_5000} />);
    const bloc = screen.getByTestId("long-text");
    expect(bloc.className).not.toContain("line-clamp");
    expect(bloc.className).not.toContain("truncate");
    expect(bloc.className).not.toContain("text-ellipsis");
  });

  it("préserve un mot de 300 caractères en entier", () => {
    render(<DetailField label="Référence" value={MOT_300} />);
    expect(screen.getByTestId("long-text").textContent).toHaveLength(300);
  });

  it("affiche un texte ressemblant à du HTML littéralement", () => {
    const brut = "<script>alert('x')</script><b>gras</b>";
    render(<DetailField label="Message" value={brut} />);
    const bloc = screen.getByTestId("long-text");
    expect(bloc.textContent).toBe(brut);
    expect(bloc.querySelector("script")).toBeNull();
    expect(bloc.querySelector("b")).toBeNull();
  });

  it("joint une liste sans perdre d'élément", () => {
    render(<DetailField label="Jours" value={["Lundi", "Mardi", "Mercredi"]} />);
    expect(screen.getByText("Lundi, Mardi, Mercredi")).toBeTruthy();
  });

  it("conserve les accents et les guillemets français", () => {
    const valeur = "Élève à Cotonou — coût « 25 000 F CFA »";
    render(<DetailField label="Note" value={valeur} />);
    expect(screen.getByText(valeur)).toBeTruthy();
  });
});
