import { clsx } from "clsx";
import { t } from "../../i18n";

// Labels en français « source » ; la traduction est appliquée AU RENDU
// (t() au niveau module serait figé à la langue du chargement initial).
const configs = {
  present: { label: "Présent", class: "bg-success-50 text-success-500" },
  absent: { label: "Absent", class: "bg-danger-50 text-danger" },
  late: { label: "En retard", class: "bg-accent/10 text-accent" },
  excused: { label: "Excusé", class: "bg-blue-50 text-blue-500" },
  active: { label: "Actif", class: "bg-success-50 text-success-500" },
  inactive: { label: "Inactif", class: "bg-slate-100 text-slate-500" },
  paid: { label: "Payé", class: "bg-success-50 text-success-500" },
  unpaid: { label: "Impayé", class: "bg-danger-50 text-danger" },
  admin: { label: "Admin", class: "bg-primary-50 text-primary" },
  teacher: { label: "Enseignant", class: "bg-violet-50 text-violet-600" },
  parent: { label: "Parent", class: "bg-amber-50 text-amber-600" },
  student: { label: "Élève", class: "bg-sky-50 text-sky-600" },
};

export default function StatusBadge({ status, label }) {
  const cfg = configs[status] || { label: label || status, class: "bg-slate-100 text-slate-600" };
  return <span className={clsx("badge", cfg.class)}>{t(label || cfg.label)}</span>;
}
