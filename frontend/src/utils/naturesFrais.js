/**
 * Natures de frais : la liste unique côté interface, alignée sur
 * Payment.PAYMENT_TYPES (backend). Utilisée par les paiements, les tarifs,
 * les relances et les analyses.
 */
export const NATURES_FRAIS = [
  ["inscription", "Inscription"], ["reinscription", "Réinscription"], ["mensualite", "Mensualité"],
  ["dossier", "Frais de dossier"], ["examen", "Frais d'examen"], ["fournitures", "Fournitures"],
  ["activites", "Activités"], ["cantine", "Cantine"], ["transport", "Transport"],
  ["garderie", "Garderie"], ["other", "Autre"],
];
export const libelleNature = (code) => (NATURES_FRAIS.find(([c]) => c === code) || [code, code])[1];
