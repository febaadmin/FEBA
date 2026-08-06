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
  const { academyKey, isSwitchingAcademy, scopeReady, hasAcademyError } = useAcademy();
  const en = getLang() === "en";

  /**
   * GARDE DE DÉMARRAGE (P1) — cause racine du « tableau de bord à zéro ».
   *
   * Tant que la portée d'académie n'est pas établie, AUCUN écran métier
   * n'est monté : ils ne peuvent donc pas émettre de requête sous la portée
   * UNKNOWN, requête qui aurait été avortée dès l'arrivée du contexte et
   * n'aurait jamais été réessayée (`retry: false` sur ERR_CANCELED),
   * laissant les compteurs à zéro jusqu'à une bascule manuelle.
   *
   * On affiche un état d'attente, jamais des zéros : un chiffre faux est
   * pire qu'un chargement visible.
   */
  if (hasAcademyError) {
    return (
      <div role="alert" className="flex flex-col items-center justify-center gap-3 py-24 text-slate-500">
        <p className="text-sm font-medium text-red-600">
          {en
            ? "Unable to determine your academy scope."
            : "Impossible de déterminer votre portée d'académie."}
        </p>
        <p className="text-xs text-slate-400">
          {en
            ? "Data is not displayed rather than shown incorrectly. Please reload the page."
            : "Les données ne sont pas affichées plutôt que de l'être faussement. Rechargez la page."}
        </p>
      </div>
    );
  }

  if (!scopeReady) {
    return (
      <div
        role="status"
        aria-live="polite"
        className="flex flex-col items-center justify-center gap-3 py-24 text-slate-500"
      >
        <Loader2 className="w-7 h-7 animate-spin text-primary" aria-hidden="true" />
        <p className="text-sm font-medium">
          {en ? "Loading your academy scope…" : "Chargement de votre portée d'académie…"}
        </p>
      </div>
    );
  }

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
