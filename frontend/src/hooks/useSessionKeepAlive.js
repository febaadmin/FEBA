/**
 * Garde la session FEBA valide tant que l'utilisateur est connecté,
 * y compris pendant une longue visioconférence ouverte dans un autre onglet.
 *
 * - Renouvelle le jeton d'accès AVANT son expiration (marge de 5 min),
 *   au lieu d'attendre une salve de 401 simultanés.
 * - Le fait au retour sur l'onglet (visibilitychange) et au retour du
 *   réseau (online) : un ordinateur sorti de veille après le cours ne
 *   présente pas un jeton périmé.
 * - Aligne les onglets : quand l'un renouvelle, les autres relisent le
 *   stockage (installCrossTabSync).
 *
 * Aucune prolongation artificielle : le jeton de renouvellement garde sa
 * durée de vie serveur ; s'il est refusé, la session se termine.
 */
import { useEffect } from "react";
import { useAuthStore } from "../store/authStore";
import { refreshSession } from "../api";
import { installCrossTabSync, tokenExpiry } from "../api/tokenRefresh";

export const REFRESH_MARGIN_MS = 5 * 60 * 1000;
const CHECK_EVERY_MS = 60 * 1000;

export function needsRefresh(accessToken, now = Date.now()) {
  if (!accessToken) return false;
  const exp = tokenExpiry(accessToken);
  return exp !== null && exp - now <= REFRESH_MARGIN_MS;
}

export function useSessionKeepAlive() {
  const accessToken = useAuthStore((s) => s.accessToken);
  const refreshToken = useAuthStore((s) => s.refreshToken);

  useEffect(() => installCrossTabSync(), []);

  useEffect(() => {
    if (!accessToken || !refreshToken) return undefined;
    let stopped = false;
    const check = () => {
      if (stopped || (typeof navigator !== "undefined" && navigator.onLine === false)) return;
      if (needsRefresh(useAuthStore.getState().accessToken)) {
        // Une erreur réseau n'efface rien ; un refus explicite termine la
        // session (géré dans refreshAccessToken).
        refreshSession().catch(() => {});
      }
    };
    check();
    const timer = setInterval(check, CHECK_EVERY_MS);
    const onVisible = () => { if (document.visibilityState === "visible") check(); };
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("online", check);
    return () => {
      stopped = true;
      clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("online", check);
    };
  }, [accessToken, refreshToken]);
}
