import { describe, it, expect } from "vitest";
import { lierLibelles } from "./useLabelLinker";

describe("lierLibelles", () => {
  it("relie le libellé au champ unique de son bloc", () => {
    document.body.innerHTML = '<div><label>Nom</label><input /></div>';
    lierLibelles(document.body);
    expect(document.querySelector("input").labels).toHaveLength(1);
  });

  it("garde l'identifiant existant du champ", () => {
    document.body.innerHTML = '<div><label>Nom</label><select id="x"></select></div>';
    lierLibelles(document.body);
    expect(document.querySelector("label").htmlFor).toBe("x");
  });

  it("ne devine pas quand le bloc contient plusieurs champs", () => {
    document.body.innerHTML = '<div><label>Période</label><input /><input /></div>';
    lierLibelles(document.body);
    expect(document.querySelector("label").htmlFor).toBe("");
  });

  it("ne touche pas un libellé déjà relié ou englobant", () => {
    document.body.innerHTML = '<div><label for="y">A</label><input id="y" /></div><div><label>B<input /></label></div>';
    lierLibelles(document.body);
    expect(document.querySelectorAll("label")[1].htmlFor).toBe("");
  });
});
