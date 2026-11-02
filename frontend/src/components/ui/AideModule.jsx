/** Présentation d'une page : à quoi elle sert et comment s'en servir, repliable et mémorisée. */
import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { ChevronDown, ChevronUp, CircleHelp } from "lucide-react";
import { t } from "../../i18n";

function lire(cle) {
  try { return localStorage.getItem(cle); } catch { return null; }
}
function ecrire(cle, valeur) {
  try { localStorage.setItem(cle, valeur); } catch { /* préférence seulement */ }
}

export default function AideModule({ cle, description, etapes = [], conditions }) {
  const stockage = `feba-aide-${cle}`;
  const [ouvert, setOuvert] = useState(lire(stockage) !== "ferme");
  const role = useLocation().pathname.split("/")[1];
  const basculer = () => { ecrire(stockage, ouvert ? "ferme" : "ouvert"); setOuvert(!ouvert); };
  return (
    <section className="rounded-xl border border-blue-100 bg-primary-50 p-4 text-sm text-slate-700" aria-label={t("Aide de la page")}>
      <div className="flex items-start gap-2">
        <CircleHelp className="w-4 h-4 mt-0.5 text-primary-700 shrink-0" aria-hidden="true" />
        <p className="flex-1">{description}</p>
        <button type="button" onClick={basculer} aria-expanded={ouvert} className="text-xs text-primary-800 underline flex items-center gap-1 whitespace-nowrap">
          {ouvert ? t("Masquer l'aide") : t("Comment faire ?")}
          {ouvert ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        </button>
      </div>
      {ouvert && (
        <div className="mt-3 pl-6 space-y-2">
          {etapes.length > 0 && <ol className="list-decimal pl-4 space-y-1">{etapes.map((e) => <li key={e}>{e}</li>)}</ol>}
          {conditions && <p className="text-xs text-slate-600">{conditions}</p>}
          <Link to={`/${role}/aide`} className="text-xs text-primary-800 underline">{t("Guides et glossaire")}</Link>
        </div>
      )}
    </section>
  );
}
