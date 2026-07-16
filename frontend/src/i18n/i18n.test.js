/**
 * Tests unitaires du système i18n central.
 */
import { describe, it, expect, beforeEach } from "vitest";
import { t, translate, tBoth, getLang, setLang } from "./index";
import { EN } from "./translations";

beforeEach(() => setLang("fr"));

describe("t / translate", () => {
  it("retourne la chaîne française telle quelle en fr", () => {
    expect(t("Tableau de bord")).toBe("Tableau de bord");
  });

  it("traduit vers l'anglais quand la langue est en", () => {
    setLang("en");
    expect(t("Tableau de bord")).toBe("Dashboard");
    expect(t("Moy.")).toBe("Avg.");
  });

  it("repli sûr : une chaîne absente du dictionnaire reste affichée (jamais de clé technique)", () => {
    setLang("en");
    expect(t("Chaîne totalement inconnue du dictionnaire"))
      .toBe("Chaîne totalement inconnue du dictionnaire");
  });

  it("interpole les paramètres {x} dans les deux langues", () => {
    expect(t("{n} élève(s)", { n: 4 })).toBe("4 élève(s)");
    setLang("en");
    expect(t("{n} élève(s)", { n: 4 })).toBe("4 student(s)");
  });

  it("translate() permet de forcer une langue", () => {
    expect(translate("Déconnexion", null, "en")).toBe("Logout");
    expect(translate("Déconnexion", null, "fr")).toBe("Déconnexion");
  });
});

describe("tBoth (affichage bilingue simultané — page de connexion)", () => {
  it("affiche « FR / EN »", () => {
    expect(tBoth("Connexion")).toBe("Connexion / Login");
    expect(tBoth("Mot de passe")).toBe("Mot de passe / Password");
  });

  it("n'affiche qu'une fois quand FR et EN sont identiques ou absents", () => {
    expect(tBoth("FEBA totalement inconnu")).toBe("FEBA totalement inconnu");
  });
});

describe("setLang / getLang", () => {
  it("bascule et persiste dans localStorage", () => {
    setLang("en");
    expect(getLang()).toBe("en");
    expect(localStorage.getItem("feba-lang")).toBe("en");
    setLang("fr");
    expect(getLang()).toBe("fr");
  });

  it("ignore une langue non supportée", () => {
    setLang("de");
    expect(getLang()).toBe("fr");
  });
});

describe("dictionnaire", () => {
  it("t est bien une FONCTION importable (garde anti-régression « t2 is not a function »)", () => {
    expect(typeof t).toBe("function");
  });

  it("contient les entrées critiques de la page de connexion", () => {
    for (const key of ["Connexion", "Se connecter", "Adresse e-mail", "Mot de passe",
                       "Afficher le mot de passe", "Masquer le mot de passe",
                       "Identifiants incorrects."]) {
      expect(EN[key], `clé manquante : ${key}`).toBeTruthy();
    }
  });
});
