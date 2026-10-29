/**
 * Aperçu d'appréciation CÔTÉ CLIENT — usage AFFICHAGE UNIQUEMENT.
 *
 * La source de vérité reste le backend (apps.grades.appreciations) : la
 * valeur renvoyée par l'API fait toujours foi. Cette fonction sert à
 * l'aperçu en direct pendant la saisie groupée, AVEC LE BARÈME DE
 * L'ACADÉMIE (chargé par useAppreciationScale). Le barème intégré
 * ci-dessous n'est qu'un repli tant que celui de l'académie n'est pas
 * chargé ; il reprend le barème par défaut du serveur.
 *
 * Seuils en POURCENTAGE de la note maximale (95 % = 19/20 = 9,5/10).
 */
export const DEFAULT_SCALE = [
  { min_percent: "95", label_fr: "EXCELLENT" },
  { min_percent: "85", label_fr: "TRÈS SATISFAISANT" },
  { min_percent: "75", label_fr: "SATISFAISANT" },
  { min_percent: "65", label_fr: "ACCEPTABLE" },
  { min_percent: "55", label_fr: "PEUT MIEUX FAIRE" },
  { min_percent: "45", label_fr: "INSUFFISANT" },
  { min_percent: "35", label_fr: "TRÈS INSUFFISANT" },
  { min_percent: "20", label_fr: "FAIBLE" },
  { min_percent: "0", label_fr: "TRÈS FAIBLE" },
];

/** Appréciation d'une note sur `max` (20 par défaut) ; null si invalide. */
export function appreciationPreview(value, scale = DEFAULT_SCALE, max = 20) {
  if (value === "" || value == null) return null;
  const v = Number(value);
  const m = Number(max);
  if (Number.isNaN(v) || v < 0 || v > m || !(m > 0)) return null;
  const sorted = [...(scale?.length ? scale : DEFAULT_SCALE)]
    .sort((a, b) => Number(b.min_percent) - Number(a.min_percent));
  // Même comparaison que le serveur, sans division : v × 100 ≥ seuil × m.
  for (const row of sorted) if (v * 100 >= Number(row.min_percent) * m) return row.label_fr;
  return sorted[sorted.length - 1]?.label_fr || null;
}
