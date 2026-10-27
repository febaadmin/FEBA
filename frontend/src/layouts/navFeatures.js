/**
 * Visibilité d'une entrée de menu liée à une fonctionnalité.
 *
 * CONFORT D'AFFICHAGE seulement : le serveur refuse lui-même l'endpoint
 * (HasEntityFeature). Une académie active : sa matrice de fonctionnalités.
 * « Toutes les Académies » (super administrateur) : l'entrée apparaît si
 * AU MOINS UNE académie accessible possède la fonctionnalité — les vues
 * consolidées portent alors l'académie sur chaque ligne.
 */
export function isNavItemVisible(item, { hasFeature, isAllAcademies = false, allowedAcademies = [] }) {
  if (!item.feature) return true;
  if (isAllAcademies) return allowedAcademies.some((a) => Boolean(a?.features?.[item.feature]));
  return Boolean(hasFeature?.(item.feature));
}
