/**
 * Parcours linguistique d'une classe — côté navigateur.
 *
 * POURQUOI CE FICHIER EXISTE
 * --------------------------
 * L'écran « Matières » d'une classe francophone affichait :
 *
 *     Configuration complète ✓ — 4 matière(s) FR
 *
 * et refusait l'enregistrement dans le même souffle :
 *
 *     Sélectionnez au moins une matière anglaise.
 *
 * Les deux phrases venaient du MÊME composant. Le bandeau de résumé
 * lisait le parcours déclaré de la classe ; la garde de soumission, elle,
 * appliquait encore « une matière française ET une anglaise », écrite en
 * dur juste au-dessus. Deux calculs, deux verdicts.
 *
 * Ce module est le seul endroit où la question se décide côté frontend.
 * L'affichage et la soumission l'appellent tous les deux : ils ne peuvent
 * plus diverger sans que ce fichier change.
 *
 * CE N'EST PAS LA PROTECTION
 * --------------------------
 * L'autorité reste `backend/apps/classes/subject_rules.py`, qui refuse en
 * 400. Ce module sert à ne pas laisser l'utilisateur composer une
 * configuration que le serveur rejettera — pas à décider à sa place.
 * D'où la préférence donnée aux champs renvoyés par l'API : le navigateur
 * REFLÈTE la décision du backend plutôt que de la recalculer.
 */
import { t } from "../i18n";

export const TRACK_BILINGUAL = "BILINGUAL";
export const TRACK_FRANCOPHONE = "FRANCOPHONE";
export const TRACK_ANGLOPHONE = "ANGLOPHONE";

/** Doit rester identique à `Class.TRACK_LANGUAGES` côté backend. */
const TRACK_LANGUAGES = {
  [TRACK_BILINGUAL]: ["fr", "en"],
  [TRACK_FRANCOPHONE]: ["fr"],
  [TRACK_ANGLOPHONE]: ["en"],
};

/**
 * Parcours réellement appliqué à cette classe.
 *
 * `effective_language_track` vient du backend et tient compte de
 * l'académie : une classe d'un établissement bilingue par construction
 * reste bilingue même si le champ stocké dit autre chose. On ne retombe
 * sur le champ déclaré que si l'API ne l'a pas encore fourni.
 */
export function effectiveTrack(classe) {
  const effectif = classe?.effective_language_track;
  if (effectif && TRACK_LANGUAGES[effectif]) return effectif;
  const declare = classe?.language_track;
  return TRACK_LANGUAGES[declare] ? declare : TRACK_BILINGUAL;
}

/**
 * Langues que cette classe a le droit de porter.
 *
 * Un parcours monolingue est STRICT : une classe francophone n'accepte
 * pas de matière anglaise. Une matière glissée par erreur ressortirait
 * ensuite dans le bulletin et dans les moyennes.
 */
export function allowedLanguages(classe) {
  const fournies = classe?.allowed_languages;
  if (Array.isArray(fournies) && fournies.length > 0) return fournies;
  return TRACK_LANGUAGES[effectiveTrack(classe)];
}

/** Langues dont au moins une matière est obligatoire. */
export function requiredLanguages(classe) {
  return allowedLanguages(classe);
}

/** Vrai si cette classe peut porter des matières de cette langue. */
export function acceptsLanguage(classe, langue) {
  return allowedLanguages(classe).includes(langue);
}

/**
 * Motifs de refus d'une sélection, dans l'ordre où on les lit.
 * Tableau vide = configuration valide.
 *
 * Reproduit `subject_rules.validate_subject_configuration` : mêmes
 * familles de refus, même ordre, pour que le message affiché avant
 * l'envoi soit celui que le serveur renverrait.
 */
export function validateSelection(classe, matieresSelectionnees) {
  const erreurs = [];
  const selection = matieresSelectionnees || [];
  const autorisees = allowedLanguages(classe);

  const horsParcours = selection.filter((m) => !autorisees.includes(m.language));
  const parLangue = {};
  for (const m of horsParcours) {
    (parLangue[m.language] ||= []).push(m.name);
  }
  for (const langue of Object.keys(parLangue).sort()) {
    const noms = parLangue[langue].slice().sort().join(", ");
    // Une phrase entière par langue et par nombre : recomposer un message
    // à partir de fragments traduits séparément donne un anglais bancal,
    // l'ordre des mots n'étant pas le même.
    erreurs.push(
      langue === "fr"
        ? (parLangue[langue].length > 1
            ? t("Cette classe n'enseigne pas les matières françaises : {noms}.", { noms })
            : t("Cette classe n'enseigne pas la matière française {noms}.", { noms }))
        : (parLangue[langue].length > 1
            ? t("Cette classe n'enseigne pas les matières anglaises : {noms}.", { noms })
            : t("Cette classe n'enseigne pas la matière anglaise {noms}.", { noms })),
    );
  }

  const presentes = new Set(selection.map((m) => m.language));
  for (const langue of requiredLanguages(classe)) {
    if (!presentes.has(langue)) {
      erreurs.push(
        langue === "fr"
          ? t("Sélectionnez au moins une matière française.")
          : t("Sélectionnez au moins une matière anglaise."),
      );
    }
  }
  return erreurs;
}

/**
 * Résumé affiché quand la configuration est complète.
 *
 * §6 demande un résumé qui NOMME ce qui est configuré — « Configuration
 * complète » tout court ne disait rien, et c'est ce vide qui rendait la
 * contradiction avec le message d'erreur si déroutante.
 */
export function summarize(classe, comptes) {
  const langues = requiredLanguages(classe);
  if (langues.length > 1) {
    return t("Configuration bilingue complète — {fr} FR / {en} EN", {
      fr: comptes.fr || 0,
      en: comptes.en || 0,
    });
  }
  const langue = langues[0];
  const n = comptes[langue] || 0;
  return langue === "fr"
    ? t("Configuration complète — {n} matière(s) française(s)", { n })
    : t("Configuration complète — {n} matière(s) anglaise(s)", { n });
}
