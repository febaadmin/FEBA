/**
 * Aperçu d'appréciation CÔTÉ CLIENT — usage AFFICHAGE UNIQUEMENT.
 *
 * La source de vérité de l'appréciation reste le backend
 * (apps.grades.models.get_appreciation) : la valeur stockée et renvoyée par
 * l'API fait toujours foi. Cette fonction ne sert qu'à afficher un aperçu
 * en direct pendant la saisie groupée, avant l'enregistrement — elle reprend
 * exactement le même barème officiel V4.
 */
const SCALE = [
  [19, "EXCELLENT"],
  [17, "TRÈS SATISFAISANT"],
  [15, "SATISFAISANT"],
  [13, "ACCEPTABLE"],
  [11, "PEUT MIEUX FAIRE"],
  [9, "INSUFFISANT"],
  [7, "TRÈS INSUFFISANT"],
  [4, "FAIBLE"],
  [0, "TRÈS FAIBLE"],
];

/** Aperçu d'appréciation pour une note /20 (null si valeur hors [0,20]). */
export function appreciationPreview(value) {
  if (value === "" || value == null) return null;
  const v = Number(value);
  if (Number.isNaN(v) || v < 0 || v > 20) return null;
  for (const [threshold, label] of SCALE) if (v >= threshold) return label;
  return "TRÈS FAIBLE";
}
