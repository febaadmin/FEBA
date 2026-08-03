/**
 * useSiteLang — langue du SITE PUBLIC, partagée par toutes les pages.
 *
 * P1 : le sélecteur FR/EN n'existait que sur la page FEBA FHA, avec un état
 * local. Les autres pages publiques n'avaient aucun moyen de changer de
 * langue, et le choix ne survivait pas à la navigation.
 *
 * Cette source unique corrige les deux problèmes :
 *   - un `localStorage` partagé rend le choix PERSISTANT entre les pages
 *     et entre les visites ;
 *   - un événement `storage` + un événement interne synchronisent TOUS les
 *     composants montés, donc le changement est instantané et sans
 *     rechargement.
 *
 * LANGUE PAR DÉFAUT : le FRANÇAIS.
 *
 * Le site public est d'abord celui de FEBA, école bilingue de Cotonou
 * dont les familles sont francophones. Seul le PROGRAMME FEBA FHA
 * s'adresse à des familles anglophones — et il reste accessible en
 * anglais d'un clic, choix ensuite mémorisé.
 *
 * Faire l'inverse afficherait un site anglais à toutes les familles
 * béninoises dès leur première visite.
 */
import { useCallback, useEffect, useState } from "react";

export const SITE_LANG_KEY = "feba-fha-lang";
const CHANGE_EVENT = "feba-site-lang-change";

/** Langue actuellement stockée, avec repli sûr si le stockage est bloqué. */
export function readSiteLang() {
  try {
    const stored = localStorage.getItem(SITE_LANG_KEY);
    return stored === "fr" || stored === "en" ? stored : "fr";
  } catch {
    return "fr";
  }
}

/**
 * Aligne `<html lang>` sur la langue stockée, dès le chargement du module.
 *
 * `setLang()` mettait bien l'attribut à jour, mais uniquement lors d'un
 * changement. Un visiteur ayant choisi l'anglais puis rechargé la page
 * obtenait donc un document annoncé `lang="fr"` alors que tout son contenu
 * était en anglais : les lecteurs d'écran le prononçaient avec la
 * phonétique française, et les moteurs de recherche l'indexaient comme
 * une page française.
 */
function syncDocumentLang(lang) {
  try {
    if (typeof document !== "undefined") document.documentElement.lang = lang;
  } catch {
    /* environnement sans DOM (tests, rendu serveur) */
  }
}

syncDocumentLang(readSiteLang());

export function useSiteLang() {
  const [lang, setLangState] = useState(readSiteLang);

  // Le site public et l'application privée partagent le même document :
  // revenir sur une page publique doit réafficher l'attribut correct.
  useEffect(() => {
    syncDocumentLang(lang);
  }, [lang]);

  useEffect(() => {
    const sync = () => setLangState(readSiteLang());
    // `storage` couvre les autres onglets ; l'événement interne couvre les
    // composants du même onglet (storage ne s'y déclenche pas).
    window.addEventListener("storage", sync);
    window.addEventListener(CHANGE_EVENT, sync);
    return () => {
      window.removeEventListener("storage", sync);
      window.removeEventListener(CHANGE_EVENT, sync);
    };
  }, []);

  const setLang = useCallback((next) => {
    if (next !== "fr" && next !== "en") return;
    try {
      localStorage.setItem(SITE_LANG_KEY, next);
    } catch {
      /* stockage indisponible : le choix vaut pour la session en cours */
    }
    setLangState(next);
    // Prévient les autres composants montés : aucun rechargement de page.
    window.dispatchEvent(new Event(CHANGE_EVENT));
    // Aide les lecteurs d'écran et le référencement à suivre la langue.
    syncDocumentLang(next);
  }, []);

  /** Sélecteur de traduction : `t("Bonjour", "Hello")`. */
  const t = useCallback((fr, en) => (lang === "fr" ? fr : en), [lang]);

  return { lang, setLang, t };
}
