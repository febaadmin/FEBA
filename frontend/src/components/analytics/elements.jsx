/**
 * Éléments communs du centre d'analyse : carte de graphique, tuile KPI, choix
 * multiple, tableau de détail, état vide expliqué.
 *
 * Chaque graphique dit ce qu'il montre : titre, période, population analysée,
 * unité, légende et infobulles ; sans donnée, la raison est affichée.
 */
import { useEffect, useRef, useState } from "react";
import { ChevronDown, Info, X } from "lucide-react";
import { useT } from "./presentation";

import { BLEU, ETAT, OR as OR_FEBA, VERT as VERT_FEBA } from "../../theme/graphiques";
import { AideKpi } from "../payments/AideKpi";

// Couleurs issues du système graphique FEBA (theme/graphiques.js) : une seule source.
export const NAVY = BLEU;
export const OR = OR_FEBA;
export const VERT = VERT_FEBA;
export const GRIS = ETAT.neutre;

export function Tuile({ titre, valeur, detail, aide, testid, accent }) {
  return (
    <div className={`rounded-xl border p-3 ${accent ? "border-feba-navy/20 bg-feba-navy/5" : "border-slate-100 bg-slate-50/60"}`} data-testid={testid} title={aide || undefined}>
      <p className="text-xs text-slate-500 flex items-center gap-1">{titre}{aide && <Info className="w-3 h-3" aria-hidden="true" />}</p>
      <p className="mt-0.5 text-xl font-bold text-slate-900 tabular-nums">{valeur}</p>
      {detail && <p className="text-xs text-slate-500 mt-0.5">{detail}</p>}
    </div>
  );
}

export function Vide({ raison, testid }) {
  const t = useT();
  return (
    <div className="flex items-start gap-2 rounded-lg bg-slate-50 px-3 py-6 text-sm text-slate-600 justify-center text-center" data-testid={testid || "analyse-vide"}>
      <Info className="w-4 h-4 mt-0.5 shrink-0 text-slate-400" aria-hidden="true" />
      <span>{raison || t("Aucune donnée pour cette sélection.")}</span>
    </div>
  );
}

/**
 * Carte d'un graphique. `population` : qui est compté (ex. « 30 élèves notés, 600 notes ») ;
 * `contexte` : année et période ; `unite` : unité des valeurs ; `detail` : tableau à la demande.
 */
export function CarteGraphique({ titre, description, contexte, population, unite, vide, raisonVide, detail, children, testid, className = "" }) {
  const t = useT();
  const [ouvert, setOuvert] = useState(false);
  return (
    <figure className={`rounded-xl border border-slate-100 bg-white p-3 min-w-0 ${className}`} data-testid={testid}>
      <figcaption className="mb-2">
        <p className="text-sm font-semibold text-slate-800 flex items-center gap-1.5">{titre}{description && <AideKpi texte={description} />}</p>
        <p className="text-xs text-slate-500">
          {[contexte, population, unite && `${t("Unité")} : ${unite}`].filter(Boolean).join(" · ")}
        </p>
      </figcaption>
      {vide ? <Vide raison={raisonVide} /> : children}
      {detail && !vide && (
        <div className="mt-2">
          <button type="button" className="text-xs font-medium text-feba-navy hover:underline inline-flex items-center gap-1"
            aria-expanded={ouvert} onClick={() => setOuvert((x) => !x)} data-testid={testid ? `${testid}-detail` : undefined}>
            <ChevronDown className={`w-3 h-3 transition-transform ${ouvert ? "rotate-180" : ""}`} aria-hidden="true" />
            {ouvert ? t("Masquer le détail") : t("Voir le détail")}
          </button>
          {/* Toujours présent (masqué tant qu'il n'est pas ouvert) : l'export CSV et l'impression du
              rapport reprennent ainsi chaque tableau de détail, et le contenu reste lisible sans le graphique. */}
          <div className="mt-2" hidden={!ouvert} data-detail>{detail}</div>
        </div>
      )}
    </figure>
  );
}

export function Tableau({ colonnes, lignes, testid, vide }) {
  const t = useT();
  if (!lignes.length) return <Vide raison={vide || t("Aucune donnée pour cette sélection.")} />;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm" data-testid={testid}>
        <thead><tr className="text-left text-xs text-slate-500">
          {colonnes.map(([cle, nom, droite]) => <th key={cle} className={`py-1.5 pr-3 font-medium ${droite ? "text-right" : ""}`}>{nom}</th>)}
        </tr></thead>
        <tbody>
          {lignes.map((l, i) => (
            <tr key={l.id ?? i} className="border-t border-slate-100">
              {colonnes.map(([cle, , droite, rendu]) => (
                <td key={cle} className={`py-1.5 pr-3 ${droite ? "text-right tabular-nums whitespace-nowrap" : ""}`}>{rendu ? rendu(l) : l[cle] ?? "-"}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Liste de choix multiples (cases à cocher dans un menu déroulant), accessible au clavier. */
export function ChoixMultiple({ libelle, options, valeurs, onChange, testid, desactive, aide }) {
  const t = useT();
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
