/**
 * Âge des élèves — AFFICHAGE uniquement.
 *
 * Le calcul (années révolues, 29 février, fuseau de l'académie) est fait
 * par le serveur (backend/apps/core/age.py) et livré dans `age` /
 * `age_status` (fiche élève) ou `student_age` / `student_age_status`
 * (paiement, absence, note…). Recalculer ici depuis la date de naissance
 * créerait une seconde règle, et deux règles finissent par diverger : le
 * navigateur d'un parent à New York n'a pas la même « date du jour » que
 * le serveur.
 *
 * Statuts : "ok" | "missing" (pas de date) | "invalid" (date future ou
 * invraisemblable — anomalie de données, jamais un âge négatif).
 */
import { t } from "../i18n";

export function ageText(age, status) {
  if (status === "invalid") return t("Date invalide");
  if (age === null || age === undefined || status === "missing") return t("Non renseigné");
  return age <= 1 ? t("{n} an", { n: age }) : t("{n} ans", { n: age });
}

/** Valeur de tri : les âges inconnus vont en fin de liste, quel que soit le sens. */
export function ageSortValue(age, status) {
  if (status !== "ok" || age === null || age === undefined) return null;
  return Number(age);
}

/**
 * Colonne « Âge » prête pour <DataTable>.
 *   ageColumn()                 → lit row.age / row.age_status
 *   ageColumn("student_age")    → lit row.student_age / row.student_age_status
 */
export function ageColumn(field = "age") {
  const statusField = `${field}_status`;
  return {
    key: field,
    label: t("Âge"),
    sortValue: (row) => ageSortValue(row[field], row[statusField]),
    render: (row) => {
      const status = row[statusField];
      const text = ageText(row[field], status);
      if (status === "invalid") {
        return (
          <span className="text-xs font-medium text-danger" title={t("Date de naissance dans le futur ou invraisemblable : à corriger dans la fiche élève.")}>
            {text}
          </span>
        );
      }
      if (status !== "ok") return <span className="text-xs text-slate-400">{text}</span>;
      return <span className="whitespace-nowrap">{text}</span>;
    },
  };
}

/** Libellé d'option d'un sélecteur d'élève : « Nom — Classe · 9 ans ». */
export function studentOptionLabel(s, { withMatricule = false } = {}) {
  const name = s.full_name || `${s.first_name || ""} ${s.last_name || ""}`.trim();
  const klass = s.class_name || "?";
  const ident = withMatricule ? `${name} - ${s.matricule || ""} (${klass})` : `${name} - ${klass}`;
  return `${ident} · ${ageText(s.age, s.age_status)}`;
}
