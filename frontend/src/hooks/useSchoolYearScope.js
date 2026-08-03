/**
 * useSchoolYearScope — année scolaire par défaut, compatible mode consolidé.
 *
 * PROBLÈME RÉSOLU (P2)
 * --------------------
 * Une dizaine d'écrans choisissaient leur filtre par défaut ainsi :
 *
 *     const currentYear = years.find((y) => y.is_current);
 *
 * En mode « Toutes les Académies », la liste des années contient l'année
 * courante de CHAQUE académie. `find()` en retenait donc UNE — la première
 * renvoyée par l'API — et l'écran filtrait silencieusement sur elle. La vue
 * consolidée n'affichait alors qu'une seule académie : 30 élèves au lieu de
 * 33, sans que rien à l'écran ne signale le filtre appliqué.
 *
 * C'est exactement l'interdit « ne jamais ne renvoyer qu'une académie en
 * mode consolidé », et il était d'autant plus trompeur que les données
 * étaient correctes côté serveur.
 *
 * En mode consolidé, ce hook ne choisit donc AUCUNE année : le serveur
 * applique de lui-même l'année courante de chaque académie
 * (`current_school_years`), ce qui donne bien l'union des deux.
 */
import { useAcademy } from "../context/AcademyContext";

export function useSchoolYearScope(years = []) {
  const { isAllAcademies } = useAcademy();

  // En mode consolidé, aucune année ne peut représenter les deux académies.
  const currentYear = isAllAcademies ? undefined : years.find((y) => y.is_current);

  /**
   * Libellé d'une année scolaire.
   *
   * En mode consolidé, deux académies ont chacune une « 2025-2026 » : sans
   * préfixe d'académie, les deux boutons sont indiscernables.
   */
  const yearLabel = (year) => {
    if (!year) return "";
    const academy = year.academy_short_name || year.academy_code;
    return isAllAcademies && academy ? `${academy} · ${year.name}` : year.name;
  };

  return { currentYear, yearLabel, isAllAcademies };
}

export default useSchoolYearScope;
