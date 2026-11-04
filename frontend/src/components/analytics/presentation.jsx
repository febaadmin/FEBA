/**
 * Mode de présentation du centre d'analyse : français, anglais ou bilingue.
 *
 * Il ne change QUE les libellés affichés : les données, les filtres et les
 * calculs sont identiques dans les trois modes. Par défaut, la langue de
 * l'interface ; le choix est mémorisé pour la session du navigateur.
 */
import { createContext, useContext, useState } from "react";
import { getLang, tBoth, translate } from "../../i18n";

const Ctx = createContext({ mode: "fr", setMode: () => {} });
const CLE = "feba.analyses.presentation";

function lire() {
  try {
    const v = sessionStorage.getItem(CLE);
    return ["fr", "en", "bi"].includes(v) ? v : null;
  } catch {
    return null;
  }
}

export function PresentationProvider({ children }) {
  const [mode, setModeEtat] = useState(() => lire() || getLang());
  const setMode = (m) => {
    setModeEtat(m);
    try { sessionStorage.setItem(CLE, m); } catch { /* stockage indisponible : choix non mémorisé */ }
  };
  return <Ctx.Provider value={{ mode, setMode }}>{children}</Ctx.Provider>;
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

export function ChoixPresentation() {
  const { mode, setMode } = usePresentation();
  const t = useT();
  return (
    <div className="flex gap-1" role="group" aria-label={t("Langue de présentation")} data-testid="presentation">
      {[["fr", "Français"], ["en", "English"], ["bi", "FR / EN"]].map(([v, nom]) => (
        <button key={v} type="button" onClick={() => setMode(v)} aria-pressed={mode === v} data-testid={`presentation-${v}`}
          className={`px-2.5 py-1 rounded-lg text-xs font-medium ${mode === v ? "bg-feba-navy text-white" : "bg-white border border-slate-200 text-slate-600"}`}>
          {nom}
        </button>
      ))}
    </div>
  );
}
