/**
 * AcademyScopedOutlet — sous-arbre routé rattaché à une académie.
 *
 * PROBLÈME RÉSOLU (P0)
 * --------------------
 * Pendant une bascule d'académie, l'écran restait figé sur les données de
 * l'académie quittée : rien n'indiquait qu'un changement était en cours, et
 * les chiffres affichés étaient donc faux sans que l'utilisateur puisse le
 * savoir. Il devait attendre plusieurs secondes en regardant des données
 * qu'il croyait à jour.
 *
 * Deux garanties ici :
 *
 *   - `key={academyKey}` démonte et remonte tout le sous-arbre à chaque
 *     changement d'académie : aucun composant ne peut conserver un état
 *     local (filtres, sélections, lignes cochées) appartenant à l'autre
 *     académie.
 *
 *   - pendant la bascule, le contenu périmé est MASQUÉ et remplacé par un
 *     état d'attente explicite. Mieux vaut un écran qui dit « chargement »
 *     qu'un écran qui affiche silencieusement les mauvais chiffres.
 */
import { Outlet } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { useAcademy } from "../context/AcademyContext";
import { getLang } from "../i18n";

export default function AcademyScopedOutlet() {
  const { academyKey, isSwitchingAcademy } = useAcademy();
  const en = getLang() === "en";

  if (isSwitchingAcademy) {
    return (
      <div
        role="status"
        aria-live="polite"
        className="flex flex-col items-center justify-center gap-3 py-24 text-slate-500"
      >
        <Loader2 className="w-7 h-7 animate-spin text-primary" aria-hidden="true" />
        <p className="text-sm font-medium">
          {en ? "Switching academy…" : "Changement d'académie…"}
        </p>
        <p className="text-xs text-slate-400">
          {en
            ? "The previous academy's data has been cleared."
            : "Les données de l'académie précédente ont été effacées."}
        </p>
      </div>
    );
  }

  return <Outlet key={academyKey} />;
}
