/**
 * Langue des analyses : celle de l'interface (sélecteur FR / EN en haut de page).
 *
 * Avant novembre 2026, un second sélecteur (Français, English, FR / EN) changeait
 * la langue des seules analyses : il faisait doublon avec le sélecteur général et a
 * été remplacé par des actions utiles (impression, export, lien, vues enregistrées).
 */
import { createContext, useContext } from "react";
import { getLang, tBoth, translate } from "../../i18n";

const Ctx = createContext({ mode: "fr", setMode: () => {} });
export function PresentationProvider({ children }) {
  // L'application est remontée à chaque changement de langue : la langue lue ici est toujours à jour.
  return <Ctx.Provider value={{ mode: getLang(), setMode: () => {} }}>{children}</Ctx.Provider>;
}

export function traducteur(mode) {
  if (mode === "bi") return (texte, params) => tBoth(texte, params);
  return (texte, params) => translate(texte, params, mode === "en" ? "en" : "fr");
}

/** Traduction selon le mode de présentation (et non la langue de l'interface). */
export function useT() {
  const { mode } = useContext(Ctx);
  return traducteur(mode);
}

export function usePresentation() {
  return useContext(Ctx);
}

/** Libellé d'une donnée qui porte ses deux langues (appréciations de l'académie). */
export function libelleDouble(mode, fr, en) {
  if (mode === "en") return en || fr;
  if (mode === "bi") return en && en !== fr ? `${fr} / ${en}` : fr;
  return fr;
}
