import AppRouter from "./router";
import { useI18n } from "./i18n";
import ErrorBoundary from "./components/ErrorBoundary";

export default function App() {
  // key={lang} : remonte tout l'arbre au changement de langue, garantissant
  // que chaque texte traduit via t() est réévalué immédiatement, sans
  // déconnexion ni rechargement de page (la route courante est préservée).
  const { lang } = useI18n();
  return (
    <ErrorBoundary>
      <AppRouter key={lang} />
    </ErrorBoundary>
  );
}
