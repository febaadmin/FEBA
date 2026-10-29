/**
 * La règle des parcours linguistiques, côté navigateur.
 *
 * CE QUE CES TESTS EMPÊCHENT DE REVENIR
 * -------------------------------------
 * L'écran « Matières » annonçait « Configuration complète ✓ — 4
 * matière(s) FR » puis refusait l'enregistrement avec « Sélectionnez au
 * moins une matière anglaise. » Les deux phrases venaient du même
 * composant : le bandeau lisait le parcours de la classe, la garde de
 * soumission appliquait la règle bilingue écrite en dur.
 *
 * Ces tests portent sur la fonction que les DEUX appellent désormais.
 */
import { describe, it, expect, beforeEach } from "vitest";
import { setLang } from "../i18n";
import {
  acceptsLanguage,
  allowedLanguages,
  effectiveTrack,
  requiredLanguages,
  subjectLanguageOptions,
  summarize,
  trackOptions,
  validateSelection,
  TRACK_ANGLOPHONE,
  TRACK_BILINGUAL,
  TRACK_FRANCOPHONE,
} from "./classLanguage";

beforeEach(() => setLang("fr"));

const FR = (n) => ({ id: n, name: `Français ${n}`, language: "fr" });
const EN = (n) => ({ id: 100 + n, name: `English ${n}`, language: "en" });

/** Une classe telle que l'API la renvoie. */
const classe = (track, extra = {}) => ({
  id: 1,
  language_track: track,
  effective_language_track: track,
  ...extra,
});

describe("parcours effectif", () => {
  it("suit le parcours renvoyé par le backend", () => {
    expect(effectiveTrack(classe(TRACK_FRANCOPHONE))).toBe(TRACK_FRANCOPHONE);
    expect(effectiveTrack(classe(TRACK_ANGLOPHONE))).toBe(TRACK_ANGLOPHONE);
  });

  it("préfère le parcours EFFECTIF au parcours déclaré", () => {
    // Une académie bilingue par construction impose BILINGUAL même si le
    // champ stocké dit autre chose. Le navigateur reflète cette décision,
    // il ne la rejoue pas.
    const c = { language_track: TRACK_FRANCOPHONE, effective_language_track: TRACK_BILINGUAL };
    expect(effectiveTrack(c)).toBe(TRACK_BILINGUAL);
    expect(requiredLanguages(c)).toEqual(["fr", "en"]);
  });

  it("retombe sur bilingue devant une valeur inconnue ou absente", () => {
    // En cas de doute, la règle LA PLUS STRICTE — jamais la plus permissive.
    expect(effectiveTrack({})).toBe(TRACK_BILINGUAL);
    expect(effectiveTrack({ language_track: "N_IMPORTE_QUOI" })).toBe(TRACK_BILINGUAL);
    expect(effectiveTrack(null)).toBe(TRACK_BILINGUAL);
  });
});

describe("langues admises", () => {
  it("un parcours monolingue est strict", () => {
    expect(allowedLanguages(classe(TRACK_FRANCOPHONE))).toEqual(["fr"]);
    expect(allowedLanguages(classe(TRACK_ANGLOPHONE))).toEqual(["en"]);
    expect(acceptsLanguage(classe(TRACK_FRANCOPHONE), "en")).toBe(false);
    expect(acceptsLanguage(classe(TRACK_ANGLOPHONE), "fr")).toBe(false);
  });

  it("un parcours bilingue admet les deux", () => {
    expect(allowedLanguages(classe(TRACK_BILINGUAL))).toEqual(["fr", "en"]);
  });

  it("utilise les langues fournies par l'API quand elles existent", () => {
    const c = { effective_language_track: TRACK_BILINGUAL, allowed_languages: ["en"] };
    expect(allowedLanguages(c)).toEqual(["en"]);
  });
});

describe("validation — les huit cas du cahier des charges", () => {
  it("CAS A : francophone, 4 FR, 0 EN → valide", () => {
    // Exactement la capture d'écran du rapport.
    const erreurs = validateSelection(classe(TRACK_FRANCOPHONE), [FR(1), FR(2), FR(3), FR(4)]);
    expect(erreurs).toEqual([]);
  });

  it("CAS B : francophone, 0 FR, 0 EN → invalide, matière française requise", () => {
    const erreurs = validateSelection(classe(TRACK_FRANCOPHONE), []);
    expect(erreurs).toHaveLength(1);
    expect(erreurs[0]).toMatch(/matière française/i);
  });

  it("CAS C : anglophone, 0 FR, 3 EN → valide", () => {
    expect(validateSelection(classe(TRACK_ANGLOPHONE), [EN(1), EN(2), EN(3)])).toEqual([]);
  });

  it("CAS D : anglophone, 0 FR, 0 EN → invalide, matière anglaise requise", () => {
    const erreurs = validateSelection(classe(TRACK_ANGLOPHONE), []);
    expect(erreurs).toHaveLength(1);
    expect(erreurs[0]).toMatch(/matière anglaise/i);
  });

  it("CAS E : bilingue, FR ≥ 1 et EN ≥ 1 → valide", () => {
    expect(validateSelection(classe(TRACK_BILINGUAL), [FR(1), EN(1)])).toEqual([]);
  });

  it("CAS F : bilingue sans anglais → invalide", () => {
    const erreurs = validateSelection(classe(TRACK_BILINGUAL), [FR(1), FR(2)]);
    expect(erreurs.join(" ")).toMatch(/matière anglaise/i);
  });

  it("CAS G : bilingue sans français → invalide", () => {
    const erreurs = validateSelection(classe(TRACK_BILINGUAL), [EN(1)]);
    expect(erreurs.join(" ")).toMatch(/matière française/i);
  });

  it("CAS H : une classe FEBA garde la règle bilingue", () => {
    // FEBA est bilingue par construction : le backend renvoie BILINGUAL
    // comme parcours effectif, quoi qu'il arrive.
    const feba = { language_track: TRACK_BILINGUAL, effective_language_track: TRACK_BILINGUAL };
    expect(validateSelection(feba, [FR(1)]).join(" ")).toMatch(/matière anglaise/i);
    expect(validateSelection(feba, [EN(1)]).join(" ")).toMatch(/matière française/i);
    expect(validateSelection(feba, [FR(1), EN(1)])).toEqual([]);
  });
});

describe("parcours monolingue strict", () => {
  it("refuse une matière anglaise sur une classe francophone", () => {
    const erreurs = validateSelection(classe(TRACK_FRANCOPHONE), [FR(1), EN(1)]);
    expect(erreurs.join(" ")).toMatch(/n'enseigne pas la matière anglaise/i);
  });

  it("refuse une matière française sur une classe anglophone", () => {
    const erreurs = validateSelection(classe(TRACK_ANGLOPHONE), [EN(1), FR(1)]);
    expect(erreurs.join(" ")).toMatch(/n'enseigne pas la matière française/i);
  });

  it("nomme les matières fautives, pas seulement la langue", () => {
    // Un message qui ne dit pas QUOI décocher oblige à chercher.
    const erreurs = validateSelection(classe(TRACK_FRANCOPHONE), [FR(1), EN(1), EN(2)]);
    expect(erreurs[0]).toContain("English 1");
    expect(erreurs[0]).toContain("English 2");
  });
});

describe("résumé affiché", () => {
  it("nomme ce qui est configuré pour un parcours monolingue", () => {
    // « Configuration complète » tout court ne disait rien — et c'est ce
    // vide qui rendait la contradiction si déroutante.
    expect(summarize(classe(TRACK_FRANCOPHONE), { fr: 4, en: 0 }))
      .toBe("Configuration complète — 4 matière(s) française(s)");
    expect(summarize(classe(TRACK_ANGLOPHONE), { fr: 0, en: 3 }))
      .toBe("Configuration complète — 3 matière(s) anglaise(s)");
  });

  it("détaille les deux langues pour un parcours bilingue", () => {
    expect(summarize(classe(TRACK_BILINGUAL), { fr: 4, en: 3 }))
      .toBe("Configuration bilingue complète — 4 FR / 3 EN");
  });
});

describe("l'affichage et la soumission ne peuvent plus diverger", () => {
  it("une sélection déclarée valide ne produit aucune erreur", () => {
    // Le défaut d'origine tenait en une phrase : le bandeau annonçait
    // « complète » là où la garde refusait. Les deux appellent maintenant
    // la même fonction, donc l'un ne peut plus contredire l'autre.
    const cas = [
      [classe(TRACK_FRANCOPHONE), [FR(1), FR(2), FR(3), FR(4)]],
      [classe(TRACK_ANGLOPHONE), [EN(1), EN(2)]],
      [classe(TRACK_BILINGUAL), [FR(1), EN(1)]],
    ];
    for (const [c, selection] of cas) {
      const erreurs = validateSelection(c, selection);
      expect(erreurs).toEqual([]);
      const comptes = {
        fr: selection.filter((m) => m.language === "fr").length,
        en: selection.filter((m) => m.language === "en").length,
      };
      expect(summarize(c, comptes)).toMatch(/complète/i);
    }
  });
});

describe("programme linguistique de l'académie", () => {
  const COMMUNE = { id: 900, name: "Éducation physique", language: "bilingual" };

  it("matière commune admise dans une classe bilingue d'académie bilingue, jamais exigée", () => {
    const c = classe(TRACK_BILINGUAL, { allowed_languages: ["fr", "en", "bilingual"],
      expected_languages: ["fr", "en"] });
    expect(requiredLanguages(c)).toEqual(["fr", "en"]);
    expect(validateSelection(c, [FR(1), EN(1), COMMUNE])).toEqual([]);
    expect(validateSelection(c, [COMMUNE])).toEqual([
      "Sélectionnez au moins une matière française.",
      "Sélectionnez au moins une matière anglaise.",
    ]);
  });

  it("matière commune refusée dans une classe qui ne l'admet pas, avec un message dédié", () => {
    const c = classe(TRACK_FRANCOPHONE, { allowed_languages: ["fr"], expected_languages: ["fr"] });
    expect(validateSelection(c, [FR(1), COMMUNE])).toEqual([
      "Cette classe n'admet pas de matière commune (bilingue) : Éducation physique.",
    ]);
  });

  it("parcours proposés = ceux servis par l'API pour l'académie", () => {
    expect(trackOptions({ class_tracks: ["FRANCOPHONE"] })).toEqual([TRACK_FRANCOPHONE]);
    expect(trackOptions({ class_tracks: ["BILINGUAL"] })).toEqual([TRACK_BILINGUAL]);
    expect(trackOptions(null)).toEqual([TRACK_BILINGUAL, TRACK_FRANCOPHONE, TRACK_ANGLOPHONE]);
  });

  it("catégories de matière = langues admises ; une valeur enregistrée reste visible", () => {
    const fr = { subject_languages: ["fr"] };
    expect(subjectLanguageOptions(fr).map((o) => o.value)).toEqual(["fr"]);
    expect(subjectLanguageOptions(fr, "en").map((o) => o.value)).toEqual(["fr", "en"]);
    expect(subjectLanguageOptions({ subject_languages: ["en"] }).map((o) => o.value)).toEqual(["en"]);
    expect(subjectLanguageOptions({ subject_languages: ["fr", "en", "bilingual"] }).map((o) => o.value))
      .toEqual(["fr", "en", "bilingual"]);
  });
});
