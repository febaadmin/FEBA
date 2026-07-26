import AppRouter from "./router";
import { useI18n } from "./i18n";
import ErrorBoundary from "./components/ErrorBoundary";
import { useNumberInputGuard } from "./utils/useNumberInputGuard";

export default function App() {
  // key={lang} : remonte tout l'arbre au changement de langue, garantissant
  // que chaque texte traduit via t() est réévalué immédiatement, sans
  // déconnexion ni rechargement de page (la route courante est préservée).
  const { lang } = useI18n();
  // V7 : neutralise la modification accidentelle des champs numériques à la molette.
  useNumberInputGuard();
  return (
    <ErrorBoundary>
      <AppRouter key={lang} />
    </ErrorBoundary>
  );
}
