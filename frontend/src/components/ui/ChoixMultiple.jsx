/**
 * Liste de choix multiples (cases à cocher dans un menu déroulant), accessible
 * au clavier ; libellés dans la langue de l'interface. Le centre d'analyse a la
 * sienne (components/analytics/elements.jsx), traduite selon son mode de présentation.
 */
import { useEffect, useRef, useState } from "react";
import { ChevronDown, X } from "lucide-react";
import { t } from "../../i18n";

/** Liste de choix multiples (cases à cocher dans un menu déroulant), accessible au clavier. */
export default function ChoixMultiple({ libelle, options, valeurs, onChange, testid, desactive, aide }) {
  const [ouvert, setOuvert] = useState(false);
  const zone = useRef(null);
  useEffect(() => {
    if (!ouvert) return undefined;
    const fermer = (e) => { if (!zone.current?.contains(e.target)) setOuvert(false); };
    const echap = (e) => { if (e.key === "Escape") setOuvert(false); };
    document.addEventListener("mousedown", fermer);
    document.addEventListener("keydown", echap);
    return () => { document.removeEventListener("mousedown", fermer); document.removeEventListener("keydown", echap); };
  }, [ouvert]);
  const choisis = options.filter(([v]) => valeurs.includes(v));
  const resume = choisis.length === 0 ? t("Tous") : choisis.length === 1 ? choisis[0][1] : t("{n} sélectionnés", { n: choisis.length });
  const basculer = (v) => onChange(valeurs.includes(v) ? valeurs.filter((x) => x !== v) : [...valeurs, v]);
  return (
    <div className="relative flex flex-col gap-1 text-xs text-slate-600 min-w-0" ref={zone}>
      <span className="font-medium">{libelle}</span>
      <button type="button" className="input !py-1 text-sm text-left flex items-center justify-between gap-1 disabled:opacity-60"
        aria-haspopup="listbox" aria-expanded={ouvert} disabled={desactive} title={aide || undefined}
        onClick={() => setOuvert((x) => !x)} data-testid={testid}>
        <span className="truncate">{resume}</span>
        <ChevronDown className="w-3.5 h-3.5 shrink-0" aria-hidden="true" />
      </button>
      {ouvert && (
        <div role="listbox" aria-multiselectable="true" aria-label={libelle}
          className="absolute top-full left-0 z-20 mt-1 max-h-64 w-full min-w-[12rem] overflow-y-auto rounded-lg border border-slate-200 bg-white p-1 shadow-lg">
          {options.length === 0 && <p className="px-2 py-1.5 text-slate-500">{t("Aucun choix disponible")}</p>}
          {options.map(([v, nom]) => (
            <label key={v} className="flex items-center gap-2 rounded px-2 py-1.5 text-sm text-slate-700 hover:bg-slate-50 cursor-pointer"
              role="option" aria-selected={valeurs.includes(v)}>
              <input type="checkbox" checked={valeurs.includes(v)} onChange={() => basculer(v)} data-testid={testid ? `${testid}-${v}` : undefined} />
              <span className="truncate">{nom}</span>
            </label>
          ))}
          {valeurs.length > 0 && (
            <button type="button" className="mt-1 w-full rounded px-2 py-1 text-xs text-red-700 hover:bg-red-50 inline-flex items-center gap-1"
              onClick={() => onChange([])}>
              <X className="w-3 h-3" aria-hidden="true" />{t("Tout désélectionner")}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
