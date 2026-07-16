import { Component } from "react";
import { AlertTriangle, RotateCcw, Home } from "lucide-react";
import { tBoth } from "../i18n";

/**
 * Error Boundary global — filet de sécurité contre les pages blanches.
 *
 * Toute erreur de rendu non prévue affiche un écran d'erreur bilingue avec
 * réessai et retour à l'accueil, au lieu d'une page vide. L'erreur d'origine
 * reste visible dans la console (console.error) : ce composant N'EST PAS un
 * moyen de masquer un bug — il évite seulement que l'utilisateur soit
 * bloqué devant un écran vide pendant qu'on le corrige.
 *
 * Affichage bilingue simultané (tBoth) : au moment du crash on ne peut pas
 * garantir la langue de l'utilisateur.
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    // Toujours tracer la cause racine — jamais silencieux.
    console.error("[ErrorBoundary] Erreur de rendu interceptée :", error, info?.componentStack);
  }

  handleRetry = () => {
    this.setState({ error: null });
  };

  handleHome = () => {
    this.setState({ error: null });
    window.location.assign("/");
  };

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 p-6">
        <div className="max-w-lg w-full bg-white rounded-2xl shadow-xl border border-slate-100 p-8 text-center">
          <div className="w-14 h-14 rounded-2xl bg-red-50 flex items-center justify-center mx-auto mb-4">
            <AlertTriangle className="w-7 h-7 text-red-500" />
          </div>
          <h1 className="text-lg font-bold text-slate-800 mb-2">
            {tBoth("Une erreur est survenue.")}
          </h1>
          <p className="text-sm text-slate-500 mb-6">
            {tBoth("La page n'a pas pu s'afficher. Vous pouvez réessayer ou revenir à l'accueil.")}
          </p>
          {import.meta.env.DEV && (
            <pre className="text-left text-xs bg-slate-50 border border-slate-200 rounded-xl p-3 mb-6 overflow-x-auto text-red-600 max-h-40">
              {String(this.state.error?.stack || this.state.error)}
            </pre>
          )}
          <div className="flex gap-3 justify-center">
            <button onClick={this.handleRetry}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-blue-800 text-white text-sm font-semibold hover:bg-blue-900 transition">
              <RotateCcw className="w-4 h-4" />{tBoth("Réessayer")}
            </button>
            <button onClick={this.handleHome}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-100 text-slate-700 text-sm font-semibold hover:bg-slate-200 transition">
              <Home className="w-4 h-4" />{tBoth("Retour au tableau de bord")}
            </button>
          </div>
        </div>
      </div>
    );
  }
}
