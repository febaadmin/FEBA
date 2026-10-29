/**
 * Nom de l'académie active, tel que servi par l'API (contexte d'entité).
 *
 * Les en-têtes de menu affichaient « FEBA » ou « FEBA Academy » écrits en
 * dur : un utilisateur d'une autre académie lisait le nom d'un autre
 * établissement en haut de chaque page. Pendant le chargement, rien n'est
 * affiché plutôt qu'un nom provisoire qui serait celui d'une autre académie.
 */
import { useAcademy } from "../context/AcademyContext";
import { t } from "../i18n";

export function academyDisplayName(academy) {
  return academy?.short_name || academy?.name || "";
}

export default function AcademyName({ className = "" }) {
  const { activeAcademy, isAllAcademies } = useAcademy();
  const text = isAllAcademies ? t("Toutes les Académies") : academyDisplayName(activeAcademy);
  return (
    <p className={`truncate ${className}`} title={activeAcademy?.name || text || undefined}
       data-testid="layout-academy-name">
      {text}
    </p>
  );
}
