/** Filtrage du centre d'aide : profil, catégorie et recherche plein texte. */
import { ARTICLES, CATEGORIES, DEPANNAGE, FAQ, GLOSSAIRE, RACINES } from "./articles";

const IDX = { fr: 0, en: 1 };

/** Texte d'une paire [fr, en] dans la langue demandée. */
export const L = (paire, lang) => (Array.isArray(paire) ? paire[IDX[lang] ?? 0] ?? paire[0] : paire ?? "");

/** Minuscules sans accents, pour une recherche tolérante. */
export const normaliser = (s) => String(s || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();

function texteArticle(a, lang) {
  const morceaux = [a.titre, a.module, a.objet, a.resultat, a.consequences, a.permissions,
    ...a.prerequis, ...a.etapes, ...a.champs, ...a.erreurs.flat()];
  return normaliser(`${a.motsCles || ""} ${morceaux.map((m) => L(m, lang)).join(" ")}`);
}

/** Tous les mots saisis doivent apparaître (ordre libre). */
export function correspond(texte, requete) {
  const mots = normaliser(requete).split(/\s+/).filter(Boolean);
  return mots.every((m) => texte.includes(m));
}

export function articlesPour(role, { lang = "fr", requete = "", categorie = null } = {}) {
  return ARTICLES.filter((a) => a.roles.includes(role))
    .filter((a) => !categorie || a.categorie === categorie)
    .filter((a) => !requete.trim() || correspond(texteArticle(a, lang), requete));
}

export function categoriesPour(role) {
  const presentes = new Set(ARTICLES.filter((a) => a.roles.includes(role)).map((a) => a.categorie));
  return CATEGORIES.filter((c) => presentes.has(c.id));
}

const questions = (liste, role, lang, requete) => liste
  .filter((x) => x.roles.includes(role))
  .filter((x) => !requete.trim() || correspond(normaliser(`${L(x.q, lang)} ${L(x.r, lang)}`), requete));

export const faqPour = (role, lang = "fr", requete = "") => questions(FAQ, role, lang, requete);
export const depannagePour = (role, lang = "fr", requete = "") => questions(DEPANNAGE, role, lang, requete);
export const glossairePour = (lang = "fr", requete = "") => GLOSSAIRE
  .filter(([mot, def]) => !requete.trim() || correspond(normaliser(`${L(mot, lang)} ${L(def, lang)}`), requete));

/** Lien vers l'écran de la fonctionnalité pour ce profil, ou null. */
export function lienPour(article, role) {
  const chemin = article.liens?.[role];
  return chemin && RACINES[role] ? `${RACINES[role]}/${chemin}` : null;
}
