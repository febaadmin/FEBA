import { t } from "../i18n";

export const CIBLES = [
  { value: "all", label: "Tous les profils" },
  { value: "parent", label: "Parents" },
  { value: "teacher", label: "Enseignants" },
  { value: "student", label: "Élèves" },
  { value: "admin", label: "Administrateurs" },
];

/** Libellé d'un rôle destinataire, jamais sa valeur technique. */
export const libelleCible = (valeur) => {
  const cible = CIBLES.find((c) => c.value === valeur);
  return cible ? t(cible.label) : valeur;
};
