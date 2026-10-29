/**
 * P2 — « Voir le détail des formules » doit DONNER le flyer, pas naviguer.
 *
 * SYMPTÔME
 * --------
 * Sur le formulaire d'inscription FEBA FHA, ce lien était un
 * `<Link to="/feba-fha">`. Un parent au milieu du formulaire qui voulait
 * revérifier un tarif quittait la page — et perdait toute sa saisie, le
 * formulaire n'étant pas remonté au retour. Le « détail des formules »
 * qu'il cherchait ne lui était même pas montré : il atterrissait en haut
 * d'une page de présentation, à charge pour lui de le retrouver.
 *
 * GARANTIES VERROUILLÉES ICI
 * --------------------------
 *   - le lien pointe le FICHIER du flyer, pas une route de l'application ;
 *   - il porte `download`, avec un nom de fichier propre ;
 *   - il ne navigue pas (pas de `<Link>` du routeur, donc pas de perte de
 *     saisie) et n'ouvre pas d'onglet ;
 *   - le libellé existe dans les deux langues ;
 *   - AUCUNE occurrence du libellé, où qu'elle soit, ne renvoie vers
 *     /feba-fha : c'était la forme exacte du défaut.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { readFileSync, existsSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

import FhaFlyerDownload from "./components/FhaFlyerDownload";
import { FHA_FLYER_PDF_PATH, FHA_FLYER_DOWNLOAD_NAME } from "./fhaPlans";

const ICI = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(ICI, "..", "..");

describe("Lien « Voir le détail des formules »", () => {
  it("télécharge un fichier au lieu de naviguer", () => {
    render(<FhaFlyerDownload lang="fr" />);
    const lien = screen.getByTestId("fha-flyer-download");

    expect(lien.tagName).toBe("A");
    expect(lien.getAttribute("href")).toBe(FHA_FLYER_PDF_PATH);
    expect(lien.getAttribute("download")).toBe(FHA_FLYER_DOWNLOAD_NAME);
    // Le défaut d'origine, verrouillé nommément.
    expect(lien.getAttribute("href")).not.toBe("/feba-fha");
  });

  it("reste dans l'onglet courant, pour ne pas perdre la saisie", () => {
    render(<FhaFlyerDownload lang="fr" />);
    expect(
      screen.getByTestId("fha-flyer-download").getAttribute("target"),
    ).toBeNull();
  });

  it("porte le libellé attendu dans les deux langues", () => {
    const { unmount } = render(<FhaFlyerDownload lang="fr" />);
    expect(screen.getByText("Voir le détail des formules")).toBeTruthy();
    unmount();
    render(<FhaFlyerDownload lang="en" />);
    expect(screen.getByText("See full plan details")).toBeTruthy();
  });

  it("cible un fichier réellement livré, et un PDF", () => {
    // Sans ce contrôle, le lien resterait « correct » tout en servant un
    // 404 — ou, pire, la page d'accueil du SPA avec un code 200.
    const chemin = resolve(FRONTEND, "public", FHA_FLYER_PDF_PATH.replace(/^\//, ""));
    expect(existsSync(chemin)).toBe(true);
    const entete = readFileSync(chemin).subarray(0, 5).toString("latin1");
    expect(entete).toBe("%PDF-");
  });
});

describe("Aucune occurrence du libellé ne navigue vers /feba-fha", () => {
  const PAGES = [
    "src/site/pages/FhaEnrollPage.jsx",
    "src/site/pages/FhaPage.jsx",
  ];

  it.each(PAGES)("%s utilise le composant de téléchargement", (relatif) => {
    const source = readFileSync(resolve(FRONTEND, relatif), "utf8");
    if (!source.includes("Voir le détail des formules")) return;

    expect(source).toContain("FhaFlyerDownload");

    // Le libellé ne doit plus apparaître à l'intérieur d'un <Link>, ni
    // d'une ancre vers /feba-fha : on cherche le motif exact du défaut.
    const fautif =
      /<Link[^>]*to=["']\/feba-fha["'][^>]*>[\s\S]{0,200}?Voir le détail des formules/;
    expect(source).not.toMatch(fautif);
  });
});
