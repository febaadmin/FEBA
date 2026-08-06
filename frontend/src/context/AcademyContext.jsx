/**
 * AcademyContext — académie active de l'application privée.
 *
 * PROBLÈME RÉSOLU (P0)
 * --------------------
 * Le sélecteur d'académie changeait de libellé instantanément, mais les
 * écrans mettaient quatre à cinq secondes à se mettre à jour — et pouvaient
 * entre-temps afficher les données de l'académie que l'on venait de
 * quitter. Trois causes cumulées, corrigées ici :
 *
 *  1. DOUBLE VAGUE DE REQUÊTES. L'ancienne bascule enchaînait
 *     `clear()` → `invalidateQueries()` → `refetchQueries({type:"active"})`.
 *     Les deux derniers appels relançaient les requêtes des écrans ENCORE
 *     MONTÉS, juste avant que le changement de clé ne les démonte et que
 *     les nouveaux écrans ne relancent les mêmes requêtes. Chaque bascule
 *     coûtait donc deux fois le trafic nécessaire. Le remontage suffit :
 *     on ne relance plus rien manuellement.
 *
 *  2. RÉPONSES TARDIVES. Les requêtes émises avant la bascule
 *     aboutissaient après, et réécrivaient le cache avec les données de
 *     l'ancienne académie. Elles sont désormais avortées (AbortController)
 *     et, en dernier recours, rejetées d'après l'en-tête `X-Academy-Scope`
 *     renvoyé par le serveur.
 *
 *  3. CACHE SURVIVANT. Les écrans remontés lisaient les entrées encore
 *     fraîches (`staleTime` de 30 s) de l'académie précédente et les
 *     affichaient avant même la première requête. Le cache est maintenant
 *     purgé AVANT le remontage.
 *
 * PRINCIPE DE SÉCURITÉ — inchangé : l'académie active est décidée par le
 * SERVEUR. Rien n'est lu depuis localStorage, et la matrice `features` ne
 * sert qu'à masquer des menus : l'API refuse d'elle-même les endpoints
 * d'une fonctionnalité désactivée.
 */
import { createContext, useContext, useEffect, useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../api";
import { SCOPE_ALL, SCOPE_UNKNOWN, getAcademyScope, setAcademyScope } from "../api/academyScope";
import { useAuthStore } from "../store/authStore";

export const ENTITY_CONTEXT_KEY = ["entity-context"];

/**
 * CYCLE DE DÉMARRAGE EXPLICITE (P1)
 * ---------------------------------
 * Le bug « tableau de bord à zéro après actualisation » venait d'une course :
 * au rechargement, les écrans métier se montaient AVANT que la portée
 * d'académie soit connue. Ils émettaient donc leurs requêtes avec
 * `X-Academy-Scope: UNKNOWN` ; quand le contexte arrivait enfin, la bascule
 * UNKNOWN → ALL avortait ces requêtes en vol. React Query ne réessaie pas une
 * requête annulée (`retry: false` sur ERR_CANCELED), la donnée restait donc
 * `undefined` — et les écrans, qui repliaient `undefined` sur `[]`,
 * affichaient des zéros définitifs jusqu'à une bascule manuelle.
 *
 * La correction n'est pas un délai : c'est un ORDRE GARANTI. Aucune requête
 * métier ne part tant que la portée n'est pas établie, ce qui rend
 * l'annulation de démarrage structurellement impossible.
 */
export const BOOT = {
  APP_BOOTING: "APP_BOOTING",
  AUTH_HYDRATING: "AUTH_HYDRATING",
  TOKEN_READY: "TOKEN_READY",
  AUTH_LOADING: "AUTH_LOADING",
  AUTH_READY: "AUTH_READY",
  SCOPE_LOADING: "SCOPE_LOADING",
  SCOPE_READY: "SCOPE_READY",
  BUSINESS_DATA_ENABLED: "BUSINESS_DATA_ENABLED",
};

/**
 * DÉDUPLICATION DES APPELS CONCURRENTS à `/auth/entity-context/`.
 *
 * React Query déduplique déjà les requêtes partageant une clé, mais le
 * contexte est aussi lu hors React Query (rechargement de portée après un
 * refresh de jeton). Cette promesse partagée garantit qu'un seul appel réseau
 * est en vol à un instant donné, quel que soit le nombre d'appelants.
 */
let entityContextInflight = null;

export function fetchEntityContext() {
  if (entityContextInflight) return entityContextInflight;
  entityContextInflight = api
    .get("/auth/entity-context/")
    .then((r) => r.data)
    .finally(() => {
      entityContextInflight = null;
    });
  return entityContextInflight;
}

/** Tests uniquement — remet à zéro la déduplication. */
export function resetEntityContextDedup() {
  entityContextInflight = null;
}

/**
 * Portée comparable à celle renvoyée par le serveur dans
 * `X-Academy-Scope`. Doit rester alignée sur
 * `apps/core/academy_scope.resolve_scope_value`.
 */
export function scopeOf(entity, { allMode = false } = {}) {
  if (entity) return entity.code || `id:${entity.id}`;
  return allMode ? SCOPE_ALL : SCOPE_UNKNOWN;
}

const AcademyContext = createContext(null);

export function AcademyProvider({ children }) {
  const queryClient = useQueryClient();
  // Le fournisseur enveloppe TOUTE l'application, site vitrine compris.
  // Interroger le contexte d'académie sans être connecté déclencherait un
  // 401 sur chaque page publique — et donc une redirection vers /login.
  const isAuthenticated = useAuthStore((s) => Boolean(s.accessToken));
  /* L'hydratation de zustand-persist est asynchrone : pendant le premier
     tick, `accessToken` est null alors qu'un jeton existe en localStorage.
     Interroger le contexte à ce moment produirait un 401 puis une portée
     UNKNOWN durablement fausse. On attend donc l'hydratation. */
  const hasHydrated = useAuthStore((s) => s._hasHydrated);

  const { data, isLoading, isError, isSuccess } = useQuery({
    queryKey: ENTITY_CONTEXT_KEY,
    queryFn: fetchEntityContext,
    enabled: hasHydrated && isAuthenticated,
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });

  const context = data || {};
  const activeAcademy = context.active_entity || null;
  const isAllAcademies = Boolean(context.all_entities_mode);
  const academyScope = scopeOf(activeAcademy, { allMode: isAllAcademies });

  /**
   * Portée RÉELLEMENT appliquée au client HTTP.
   *
   * `scopeReady` ne passe à `true` qu'APRÈS `setAcademyScope()`. Comme les
   * écrans métier sont montés sous un garde qui exige `scopeReady`, l'ordre
   * « portée appliquée → écrans montés → requêtes émises » est garanti par
   * la construction, sans aucun délai arbitraire.
   */
  /* La synchronisation se fait PENDANT LE RENDU, pas dans un effet.
     Un effet s'exécute après le commit : il y aurait donc un rendu
     intermédiaire où le contexte est connu mais la portée pas encore
     appliquée — exactement la fenêtre dans laquelle les écrans partaient
     avec UNKNOWN. Ici, le corps du composant parent s'exécute forcément
     avant celui de ses enfants : quand un écran métier se rend pour la
     première fois, la portée est déjà posée. `setAcademyScope` est
     idempotent (il renvoie false si la valeur ne change pas), ce qui rend
     l'opération sûre malgré le double rendu de StrictMode. */
  const scopeResolved = hasHydrated && isAuthenticated && isSuccess;
  if (scopeResolved) {
    setAcademyScope(academyScope);
  }
  const scopeReady = scopeResolved && getAcademyScope() === academyScope;

  /* Déconnexion : la portée redevient indéterminée. Traité en effet car
     c'est une remise à zéro, pas une préparation au rendu des enfants. */
  useEffect(() => {
    if (hasHydrated && !isAuthenticated) {
      setAcademyScope(SCOPE_UNKNOWN);
    }
  }, [hasHydrated, isAuthenticated]);

  /** Phase de démarrage courante — exposée pour le diagnostic et les tests. */
  const bootPhase = !hasHydrated
    ? BOOT.AUTH_HYDRATING
    : !isAuthenticated
      ? BOOT.APP_BOOTING
      : isLoading
        ? BOOT.SCOPE_LOADING
        : scopeReady
          ? BOOT.BUSINESS_DATA_ENABLED
          : BOOT.AUTH_READY;

  const mutation = useMutation({
    mutationFn: (entityId) =>
      api
        .post("/auth/entity-context/switch/", { entity_id: entityId ?? null })
        .then((r) => r.data),

    onMutate: () => {
      // Les requêtes en cours appartiennent à l'académie que l'on quitte :
      // on demande à React Query d'arrêter de les suivre tout de suite,
      // pour qu'aucune ne vienne repeupler le cache pendant la bascule.
      queryClient.cancelQueries();
    },

    onSuccess: (result) => {
      const nextScope = scopeOf(result.active_entity, {
        allMode: result.active_entity === null,
      });

      // 1. Nouvelle portée : avorte tout ce qui est encore en vol et fait
      //    rejeter les réponses de l'ancienne académie déjà parties.
      setAcademyScope(nextScope);

      // 2. Purge du cache métier — AVANT tout rendu, sinon les écrans
      //    remontés afficheraient l'ancienne académie le temps d'un
      //    aller-retour. Le contexte lui-même est préservé : le réécrire
      //    plutôt que le recharger économise une requête complète.
      queryClient.removeQueries({
        predicate: (query) => query.queryKey?.[0] !== ENTITY_CONTEXT_KEY[0],
      });

      // 3. Contexte réécrit sans aller-retour réseau : le sélecteur et la
      //    clé de remontage reflètent la bascule immédiatement.
      queryClient.setQueryData(ENTITY_CONTEXT_KEY, (previous) => ({
        ...(previous || {}),
        active_entity: result.active_entity,
        features: result.features,
        all_entities_mode: result.active_entity === null,
      }));

      // Volontairement PAS d'invalidateQueries ni de refetchQueries ici :
      // le changement de clé démonte les écrans et les remonte, ce qui
      // relance exactement les requêtes nécessaires, une seule fois.
    },
  });

  const value = useMemo(
    () => ({
      /** Académie active, ou null en mode « Toutes les Académies ». */
      activeAcademy,
      /** Portée normalisée, identique à l'en-tête X-Academy-Scope. */
      academyScope,
      /** Académies auxquelles l'utilisateur a réellement accès (source : API). */
      allowedAcademies: context.entities || [],
      /** Vue consolidée des deux académies. */
      isAllAcademies,
      /** Une bascule est en cours : les écrans doivent afficher un état d'attente. */
      isSwitchingAcademy: mutation.isPending,
      /** Demande une bascule au serveur. `null` = toutes les académies. */
      switchAcademy: mutation.mutateAsync,
      /** Dernière erreur de bascule, à afficher près du sélecteur. */
      switchError: mutation.error || null,

      /* ── Compléments utiles à l'interface ─────────────────────────── */
      isLoadingAcademy: isLoading,
      hasAcademyError: isError,

      /* ── Cycle de démarrage (P1) ──────────────────────────────────────
         `businessDataEnabled` est la seule condition qu'un écran métier doit
         tester avant de déclencher une requête. */
      bootPhase,
      authReady: hasHydrated && isAuthenticated,
      scopeReady,
      businessDataEnabled: hasHydrated && isAuthenticated && scopeReady,
      canSwitchAcademy: Boolean(context.can_switch),
      features: context.features || {},
      hasFeature: (flag) => Boolean((context.features || {})[flag]),
      /**
       * Clé de remontage du sous-arbre routé. Changer cette clé démonte
       * tous les écrans et les remonte vides : c'est ce qui garantit
       * qu'aucune donnée de l'académie précédente ne subsiste à l'écran,
       * sans avoir à annoter des centaines de `queryKey` une par une.
       */
      academyKey: `academy:${academyScope}`,
    }),
    [
      activeAcademy,
      academyScope,
      context.entities,
      context.can_switch,
      context.features,
      isAllAcademies,
      isLoading,
      isError,
      mutation.isPending,
      mutation.mutateAsync,
      mutation.error,
      bootPhase,
      hasHydrated,
      isAuthenticated,
      scopeReady,
    ],
  );

  return <AcademyContext.Provider value={value}>{children}</AcademyContext.Provider>;
}

/**
 * Accès à l'académie active.
 *
 * Utilisable hors du fournisseur (site public, écran de connexion) : on
 * renvoie alors un contexte neutre plutôt que de lever, pour qu'un
 * composant partagé entre le site vitrine et l'application privée n'ait
 * pas à savoir dans lequel des deux il est rendu.
 */
export function useAcademy() {
  return useContext(AcademyContext) || FALLBACK;
}

const FALLBACK = {
  activeAcademy: null,
  academyScope: SCOPE_UNKNOWN,
  allowedAcademies: [],
  isAllAcademies: false,
  isSwitchingAcademy: false,
  switchAcademy: async () => {
    throw new Error("Aucun contexte d'académie : AcademyProvider est absent.");
  },
  switchError: null,
  isLoadingAcademy: false,
  hasAcademyError: false,
  canSwitchAcademy: false,
  features: {},
  hasFeature: () => false,
  academyKey: `academy:${SCOPE_UNKNOWN}`,
  bootPhase: BOOT.APP_BOOTING,
  authReady: false,
  scopeReady: false,
  businessDataEnabled: false,
};

export { SCOPE_ALL };
