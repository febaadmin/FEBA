import { clsx } from "clsx";
import { t } from "../../i18n";

// Labels en français « source » ; la traduction est appliquée AU RENDU
// (t() au niveau module serait figé à la langue du chargement initial).
const configs = {
  present: { label: "Présent", class: "bg-success-50 text-green-800" },
  absent: { label: "Absent", class: "bg-red-50 text-red-800" },
  late: { label: "En retard", class: "bg-amber-50 text-amber-800" },
  excused: { label: "Excusé", class: "bg-blue-50 text-blue-800" },
  active: { label: "Actif", class: "bg-success-50 text-green-800" },
  inactive: { label: "Inactif", class: "bg-slate-100 text-slate-700" },
  paid: { label: "Payé", class: "bg-success-50 text-green-800" },
  unpaid: { label: "Impayé", class: "bg-red-50 text-red-800" },
  admin: { label: "Admin", class: "bg-primary-50 text-primary-800" },
  teacher: { label: "Enseignant", class: "bg-violet-50 text-violet-800" },
  parent: { label: "Parent", class: "bg-amber-50 text-amber-800" },
  student: { label: "Élève", class: "bg-sky-50 text-sky-800" },
};

export default function StatusBadge({ status, label }) {
  const cfg = configs[status] || { label: label || status, class: "bg-slate-100 text-slate-600" };
  return <span className={clsx("badge", cfg.class)}>{t(label || cfg.label)}</span>;
}
