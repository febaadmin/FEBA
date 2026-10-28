/**
 * Renouvellement du jeton d'accès — UN SEUL à la fois, tous onglets confondus.
 *
 * LE DÉFAUT CORRIGÉ (déconnexions pendant les visioconférences)
 * ------------------------------------------------------------
 * Le serveur fait tourner les jetons de renouvellement : chaque appel à
 * /auth/refresh/ en émet un NOUVEAU et met l'ancien sur liste noire
 * (ROTATE_REFRESH_TOKENS + BLACKLIST_AFTER_ROTATION). Le jeton d'accès vit
 * 60 minutes. Au bout d'une heure de cours :
 *
 *   1. plusieurs requêtes reçoivent 401 en même temps (notifications,
 *      messages, liste des salles…) ; chacune lançait SON renouvellement
 *      avec le MÊME jeton : le premier réussissait, les suivants étaient
 *      refusés (jeton déjà sur liste noire) → `clearAuth()` → /login ;
 *   2. l'onglet de la salle et l'onglet FEBA gardaient chacun leur copie
 *      des jetons en mémoire : quand l'un renouvelait, l'autre présentait
 *      ensuite un jeton révoqué → déconnexion ;
 *   3. une coupure réseau pendant le renouvellement était traitée comme
 *      un refus → déconnexion.
 *
 * CE QUI EST GARANTI ICI
 * ----------------------
 *   - un seul renouvellement en vol par onglet (promesse partagée) ;
 *   - un seul entre onglets (verrou `navigator.locks`) ; dans le verrou, on
 *     relit le stockage : si un autre onglet a déjà renouvelé, on prend
 *     ses jetons sans rien demander au serveur ;
 *   - la session n'est effacée QUE si le serveur refuse explicitement le
 *     jeton de renouvellement ET qu'aucun autre onglet ne l'a remplacé
 *     entre-temps. Une erreur réseau ne déconnecte jamais.
 *
 * Ce qui n'est PAS fait : prolonger les jetons au-delà de ce que le
 * serveur accorde. Le jeton de renouvellement expire toujours (7 jours
 * par défaut) et une déconnexion explicite le révoque.
 */
import { useAuthStore } from "../store/authStore";

export const STORAGE_KEY = "feba-auth";
const LOCK_NAME = "feba-token-refresh";

/** Jetons tels qu'ils sont dans le stockage PARTAGÉ entre onglets. */
export function readStoredTokens() {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    const state = raw ? JSON.parse(raw)?.state : null;
    return { accessToken: state?.accessToken || null, refreshToken: state?.refreshToken || null };
  } catch {
    return { accessToken: null, refreshToken: null };
  }
}

/** Expiration (ms epoch) lue dans le jeton, sans vérification (affichage/planification). */
export function tokenExpiry(token) {
  try {
    const payload = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    return typeof payload.exp === "number" ? payload.exp * 1000 : null;
  } catch {
    return null;
  }
}

export class SessionExpiredError extends Error {
  constructor() {
    super("Session expirée");
    this.name = "SessionExpiredError";
  }
}

function withCrossTabLock(fn) {
  const locks = typeof navigator !== "undefined" ? navigator.locks : undefined;
  if (locks?.request) return locks.request(LOCK_NAME, fn);
  return fn();
}

function isExplicitRejection(error) {
  const status = error?.response?.status;
  return status === 401 || status === 400;
}

let inflight = null;

/**
 * Renvoie un jeton d'accès valide, en renouvelant si nécessaire.
 *
 * @param failedAccessToken jeton qui vient d'être refusé (ou null pour un
 *        renouvellement préventif) : si le stockage contient déjà un autre
 *        jeton, c'est qu'un onglet a renouvelé — on l'adopte.
 * @param postRefresh (refreshToken) => Promise<{access, refresh?}>
 * @throws SessionExpiredError si le serveur refuse le renouvellement
 *         (la session est alors effacée) ; toute autre erreur (réseau)
 *         est relancée SANS effacer la session.
 */
export function refreshAccessToken(failedAccessToken, postRefresh) {
  if (inflight) return inflight;
  inflight = withCrossTabLock(async () => {
    const store = useAuthStore.getState();
    const stored = readStoredTokens();
    const adopt = () => {
      if (stored.accessToken !== store.accessToken || stored.refreshToken !== store.refreshToken) {
        store.setAuth(store.user, stored.accessToken, stored.refreshToken);
      }
      return stored.accessToken;
    };
    // 1. Un autre onglet (ou une requête précédente) a déjà renouvelé :
    //    le jeton refusé n'est plus celui du stockage.
    if (failedAccessToken !== null && stored.accessToken && stored.accessToken !== failedAccessToken) {
      return adopt();
    }
    // 2. Renouvellement préventif déjà fait ailleurs : rien à demander.
    if (failedAccessToken === null && stored.accessToken) {
      const exp = tokenExpiry(stored.accessToken);
      if (exp && exp - Date.now() > 5 * 60 * 1000) return adopt();
    }
    const refreshToken = stored.refreshToken || store.refreshToken;
    if (!refreshToken) throw new SessionExpiredError();
    try {
      const data = await postRefresh(refreshToken);
      useAuthStore.getState().setAuth(useAuthStore.getState().user, data.access, data.refresh || refreshToken);
      return data.access;
    } catch (error) {
      if (!isExplicitRejection(error)) throw error; // réseau : on garde la session
      // Refusé… mais peut-être parce qu'un autre onglet l'a fait tourner
      // pendant notre requête (navigateur sans `navigator.locks`).
      const after = readStoredTokens();
      if (after.refreshToken && after.refreshToken !== refreshToken && after.accessToken) {
        useAuthStore.getState().setAuth(useAuthStore.getState().user, after.accessToken, after.refreshToken);
        return after.accessToken;
      }
      useAuthStore.getState().clearAuth();
      throw new SessionExpiredError();
    }
  }).finally(() => {
    inflight = null;
  });
  return inflight;
}

/** Remet à zéro l'état du module (tests). */
export function __resetRefreshState() {
  inflight = null;
}

/**
 * Garde les onglets alignés : quand un onglet renouvelle (ou se
 * déconnecte), les autres relisent le stockage au lieu de garder en
 * mémoire un jeton révoqué.
 */
export function installCrossTabSync() {
  if (typeof window === "undefined") return () => {};
  const onStorage = (event) => {
    if (event.key !== STORAGE_KEY) return;
    useAuthStore.persist?.rehydrate?.();
  };
  window.addEventListener("storage", onStorage);
  return () => window.removeEventListener("storage", onStorage);
}
