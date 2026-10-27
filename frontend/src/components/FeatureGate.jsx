/**
 * Écran lié à une fonctionnalité d'académie (admissions en ligne, rapports
 * mensuels). Une URL saisie à la main n'affiche plus l'écran d'une autre
 * académie, vide et refusé par l'API : elle explique que la fonctionnalité
 * n'est pas activée pour l'académie active. La protection reste le serveur
 * (HasEntityFeature, 403).
 */
import { useAcademy } from "../context/AcademyContext";
import { isNavItemVisible } from "../layouts/navFeatures";
import { academyDisplayName } from "./AcademyName";
import { t } from "../i18n";

export default function FeatureGate({ feature, children }) {
  const academy = useAcademy();
  if (!academy.scopeReady) return null;
  if (isNavItemVisible({ feature }, academy)) return children;
  return (
    <div className="card text-sm text-slate-600" data-testid="feature-unavailable">
      <p className="font-semibold text-slate-800">{t("Fonctionnalité non activée")}</p>
      <p className="mt-1">
        {t("Cette fonctionnalité n'est pas activée pour {nom}.", {
          nom: academyDisplayName(academy.activeAcademy) || t("cette académie"),
        })}
      </p>
    </div>
  );
}
