/**
 * Champ de destinataires (À, Cc, Cci) : adresses saisies librement et comptes
 * FEBA choisis dans les suggestions, présentés en pastilles supprimables.
 *
 * Entrée, virgule, point-virgule ou sortie du champ valident la saisie ;
 * Retour arrière dans un champ vide retire la dernière pastille. Une saisie
 * invalide reste dans le champ, signalée, et n'est jamais envoyée.
 */
import { useId, useMemo, useState } from "react";
import { UserRound, X } from "lucide-react";
import { t } from "../../i18n";
import { ajouterEntree, decouperAdresses } from "../../utils/massEmailSelection";

export default function ChampAdresses({ libelle, entrees, onChange, comptes = [], testid, aide }) {
  const id = useId();
  const [saisie, setSaisie] = useState("");
  const [erreur, setErreur] = useState("");
  const [ouvert, setOuvert] = useState(false);

  const suggestions = useMemo(() => {
    const n = saisie.trim().toLowerCase();
    if (n.length < 2) return [];
    const pris = new Set(entrees.filter((e) => e.type === "user").map((e) => e.value));
    return comptes.filter((u) => u.sendable && !pris.has(u.id)
      && `${u.full_name} ${u.email}`.toLowerCase().includes(n)).slice(0, 8);
  }, [saisie, comptes, entrees]);

  const valider = () => {
    if (!saisie.trim()) return;
    const { valides, invalides } = decouperAdresses(saisie);
    let suivant = entrees;
    for (const v of valides) suivant = ajouterEntree(suivant, { type: "email", value: v, label: v });
    onChange(suivant);
    setSaisie(invalides.join(" "));
    setErreur(invalides.length ? t("Adresse(s) invalide(s) : {liste}", { liste: invalides.join(", ") }) : "");
  };
  const choisir = (u) => {
    onChange(ajouterEntree(entrees, { type: "user", value: u.id, label: `${u.full_name} <${u.email}>` }));
    setSaisie("");
    setErreur("");
    setOuvert(false);
  };
  const touche = (e) => {
    if (["Enter", ",", ";"].includes(e.key)) {
      e.preventDefault();
      if (suggestions.length && e.key === "Enter" && !decouperAdresses(saisie).valides.length) choisir(suggestions[0]);
      else valider();
    } else if (e.key === "Backspace" && !saisie && entrees.length) {
      onChange(entrees.slice(0, -1));
    } else if (e.key === "Escape") {
      setOuvert(false);
    }
  };

  return (
    <div className="relative" data-testid={testid}>
      <div className="flex items-start gap-2 border-b border-slate-100 py-1.5">
        <label htmlFor={id} className="w-10 shrink-0 pt-1.5 text-sm font-medium text-slate-500">{libelle}</label>
        <div className="flex flex-1 flex-wrap items-center gap-1.5 min-w-0">
          {entrees.map((e) => (
            <span key={`${e.type}:${e.value}`} data-testid={`${testid}-pastille`}
              className={`inline-flex max-w-full items-center gap-1 rounded-full px-2 py-0.5 text-xs ${e.type === "user" ? "bg-primary-50 text-primary-700" : "bg-slate-100 text-slate-700"}`}>
              {e.type === "user" && <UserRound className="w-3 h-3 shrink-0" aria-hidden="true" />}
              <span className="truncate">{e.label}</span>
              <button type="button" onClick={() => onChange(entrees.filter((x) => x !== e))}
                aria-label={t("Retirer {n}", { n: e.label })} className="rounded-full hover:bg-black/10">
                <X className="w-3 h-3" aria-hidden="true" />
              </button>
            </span>
          ))}
          <input id={id} value={saisie} onChange={(e) => { setSaisie(e.target.value); setOuvert(true); }}
            onKeyDown={touche} onBlur={() => { setTimeout(() => setOuvert(false), 150); valider(); }}
            className="flex-1 min-w-[10rem] bg-transparent py-1 text-sm outline-none" autoComplete="off"
            placeholder={entrees.length ? "" : (aide || t("Adresse e-mail ou nom d'un membre de l'académie"))}
            aria-describedby={erreur ? `${id}-err` : undefined} data-testid={`${testid}-saisie`} />
        </div>
      </div>
      {erreur && <p id={`${id}-err`} className="ml-12 mt-1 text-xs text-red-600" role="alert">{erreur}</p>}
      {ouvert && suggestions.length > 0 && (
        <ul className="absolute left-12 right-0 z-20 mt-1 max-h-60 overflow-y-auto rounded-xl border border-slate-200 bg-white p-1 shadow-lg" role="listbox">
          {suggestions.map((u) => (
            <li key={u.id}>
              <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => choisir(u)} role="option" aria-selected="false"
                className="w-full rounded-lg px-2 py-1.5 text-left text-sm hover:bg-slate-50" data-testid={`${testid}-suggestion-${u.id}`}>
                <span className="font-medium text-slate-800">{u.full_name}</span>
                <span className="ml-2 text-xs text-slate-500">{u.email} · {t(u.role_label || u.role)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
