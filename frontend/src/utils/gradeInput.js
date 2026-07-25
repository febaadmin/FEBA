/**
 * Saisie de note — utilitaires (V7).
 *
 * Cause racine du bug « 10 devient 9,5 / 9,75 » : les champs de note étaient
 * des <input type="number" step="0.25">. Un tel champ, une fois focalisé,
 * modifie SILENCIEUSEMENT sa valeur au moindre coup de molette, flèche
 * haut/bas ou clic sur les compteurs (± step). Taper « 10 » puis faire
 * défiler la page suffisait à enregistrer 9,75 puis 9,5. Le backend stockait
 * fidèlement cette valeur altérée.
 *
 * Correctif : les champs de note deviennent des <input type="text"
 * inputMode="decimal"> (aucun compteur, aucun pas, insensibles à la molette
 * et aux flèches) et la valeur saisie est NORMALISÉE puis VALIDÉE ici. La
 * valeur tapée n'est jamais transformée arbitrairement : « 10 » reste « 10 ».
 */

/**
 * Normalise une note telle que tapée : accepte la virgule française,
 * supprime les caractères non numériques, ne garde qu'un seul séparateur.
 * Ne change JAMAIS la valeur numérique (« 10 » → « 10 », « 10,5 » → « 10.5 »).
 */
export function normalizeGradeInput(raw) {
  if (raw == null) return "";
  let s = String(raw).trim().replace(",", ".").replace(/[^\d.]/g, "");
  const i = s.indexOf(".");
  if (i !== -1) s = s.slice(0, i + 1) + s.slice(i + 1).replace(/\./g, "");
  return s;
}

/** Vrai si la saisie représente une note valide dans [0, 20]. */
export function isValidGrade(raw) {
  const s = normalizeGradeInput(raw);
  if (s === "" || s === ".") return false;
  const n = Number(s);
  return Number.isFinite(n) && n >= 0 && n <= 20;
}

/**
 * Valeur numérique normalisée à envoyer au backend (chaîne « 10 », « 10.5 »),
 * ou null si invalide. On renvoie une chaîne : le backend (DecimalField)
 * la stocke telle quelle, sans imprécision flottante.
 */
export function gradePayloadValue(raw) {
  return isValidGrade(raw) ? normalizeGradeInput(raw) : null;
}
