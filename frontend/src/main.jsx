import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "react-hot-toast";
import App from "./App";
import { AcademyProvider } from "./context/AcademyContext";
import "./index.css";

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
  defaultOptions: {
    queries: { retry: noRetryOn4xx, staleTime: 30000 },
    mutations: { retry: noRetryOn4xx },
  },
});

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        {/* AcademyProvider est monté au-dessus de <App/> — donc au-dessus du
            `key={lang}` qui remonte l'arbre au changement de langue. Changer
            de langue ne doit pas recharger le contexte d'académie ni
            réinitialiser la portée envoyée au serveur. */}
        <AcademyProvider>
          <App />
        </AcademyProvider>
        <Toaster position="top-right" toastOptions={{
          duration: 4000,
          style: { background: "#1E293B", color: "#F8FAFC", borderRadius: "12px" },
          success: { iconTheme: { primary: "#10B981", secondary: "#fff" } },
          error: { iconTheme: { primary: "#EF4444", secondary: "#fff" } },
        }} />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
);