import "./utils/zodSansEval";
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { signalerErreurEcriture, signalerErreurLecture } from "./utils/erreursRequetes";
import { Toaster } from "react-hot-toast";
import App from "./App";
import { AcademyProvider } from "./context/AcademyContext";
import "./index.css";
import { rechargerUneFois, signalerErreurInterface } from "./utils/versionPerimee";

// Vite signale ici un module de l'ancienne version introuvable (onglet ouvert
// pendant un déploiement) : on charge la nouvelle version au lieu d'échouer.
// L'erreur n'est PAS étouffée (pas de preventDefault) : sinon l'import se résout
// avec « undefined » et React échoue plus loin sur une erreur trompeuse. Si le
// rechargement a déjà été tenté, l'écran d'erreur explique la nouvelle version.
window.addEventListener("vite:preloadError", (event) => {
  signalerErreurInterface("chunk", event.payload);
  rechargerUneFois();
});

// FIX v40 : ne JAMAIS réessayer les erreurs client 4xx (401/403/404) —
// c'est ce qui produisait la salve de « /api/classes/8/ 404 » dans la
// console (React Query relançait 3× chaque requête échouée). On ne réessaie
// qu'une fois sur les erreurs réseau/5xx transitoires.
const noRetryOn4xx = (failureCount, error) => {
  // P0 : une réponse écartée parce qu'elle concernait l'académie quittée
  // ne doit JAMAIS être réessayée — le composant qui l'attendait est en
  // cours de remontage et relancera lui-même la requête, avec la bonne
  // portée. Réessayer produirait une requête inutile de plus par écran.
  if (error?.isStaleAcademy || error?.code === "ERR_CANCELED") return false;
  const status = error?.response?.status;
  if (status && status >= 400 && status < 500) return false;
  return failureCount < 1;
};
const queryClient = new QueryClient({
  queryCache: new QueryCache({ onError: signalerErreurLecture }),
  mutationCache: new MutationCache({ onError: signalerErreurEcriture }),
  defaultOptions: {
    queries: { retry: noRetryOn4xx, staleTime: 30000 },
    // Jamais de nouvel essai automatique d'une écriture : après une 500 ou une
    // coupure, le serveur a pu l'appliquer (doublon de paiement, de message…).
    mutations: { retry: false },
  },
});

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        {/* AcademyProvider est monté au-dessus de <App/> — donc au-dessus du
            `key={lang}` qui remonte l'arbre au changement de langue. Changer
            de langue ne doit pas recharger le contexte d'académie ni
            réinitialiser la portée envoyée au serveur. */}
        <AcademyProvider>
          <App />
        </AcademyProvider>
        <Toaster position="top-right" toastOptions={{
          duration: 4000,
          style: { background: "#071D49", color: "#F8FAFC", borderRadius: "12px", fontSize: "14px", boxShadow: "0 10px 24px -6px rgba(7,29,73,.4)" },
          success: { iconTheme: { primary: "#10B981", secondary: "#fff" } },
          error: { iconTheme: { primary: "#EF4444", secondary: "#fff" } },
        }} />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
);