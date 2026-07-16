/**
 * Système d'internationalisation centralisé FEBA — FR (source) / EN.
 *
 * Architecture « gettext » : la chaîne française EST la clé de traduction.
 *  - t("Tableau de bord")  → "Tableau de bord" (fr) | "Dashboard" (en)
 *  - Repli automatique sur le français si une traduction manque : aucune
 *    clé technique n'est jamais visible à l'écran.
 *  - Interpolation : t("Bienvenue, {name}!", { name: "Awa" })
 *
 * Persistance :
 *  1. localStorage("feba-lang") — survit au rafraîchissement et à la
 *     fermeture du navigateur.
 *  2. Profil utilisateur (user.preferred_language, PATCH /auth/me/) —
 *     prioritaire à la reconnexion (appliqué par useAuth.login()).
 *
 * Utilisable dans les composants via useI18n() (réactif) et hors
 * composants via translate()/getLang() (toasts, utilitaires, zod).
 */
import { useCallback, useSyncExternalStore } from "react";
import { EN } from "./translations";

const STORAGE_KEY = "feba-lang";
const SUPPORTED = ["fr", "en"];

let currentLang = (() => {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    return SUPPORTED.includes(saved) ? saved : "fr";
  } catch {
    return "fr";
  }
})();

if (typeof document !== "undefined") {
  document.documentElement.lang = currentLang;
}

const listeners = new Set();

function subscribe(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getLang() {
  return currentLang;
}

export function setLang(lang) {
  if (!SUPPORTED.includes(lang) || lang === currentLang) return;
  currentLang = lang;
  try {
    localStorage.setItem(STORAGE_KEY, lang);
  } catch { /* stockage local indisponible (navigation privée) : non bloquant */ }
  if (typeof document !== "undefined") document.documentElement.lang = lang;
  listeners.forEach((fn) => fn());
}

function interpolate(text, params) {
  if (!params) return text;
  let out = text;
  for (const [k, v] of Object.entries(params)) {
    out = out.split(`{${k}}`).join(String(v));
  }
  return out;
}

/** Traduit une chaîne source française vers la langue donnée (défaut : langue courante). */
export function translate(text, params, lang = currentLang) {
  const base = lang === "en" ? (EN[text] ?? text) : text;
  return interpolate(base, params);
}

/**
 * Affichage bilingue simultané « FR / EN » (page de connexion,
 * messages avant authentification).
 */
export function tBoth(text, params) {
  const fr = interpolate(text, params);
  const en = EN[text] ? interpolate(EN[text], params) : null;
  return en && en !== fr ? `${fr} / ${en}` : fr;
}

/**
 * t() global, lié à la langue courante. Utilisable partout (composants,
 * handlers, toasts, définitions de colonnes créées au rendu).
 *
 * Réactivité : App.jsx remonte l'arbre React à chaque changement de langue
 * (<AppRouter key={lang} />), donc chaque t() est réévalué immédiatement —
 * aucun composant n'a besoin de s'abonner individuellement.
 */
export function t(text, params) {
  return translate(text, params, currentLang);
}

/** Locale BCP-47 pour le formatage des dates selon la langue courante. */
export function dateLocale() {
  return currentLang === "en" ? "en-GB" : "fr-FR";
}

/** Hook réactif : re-rend le composant à chaque changement de langue. */
export function useI18n() {
  const lang = useSyncExternalStore(subscribe, getLang);
  const t = useCallback((text, params) => translate(text, params, lang), [lang]);
  return { lang, setLang, t };
}
