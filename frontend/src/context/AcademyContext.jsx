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
import { SCOPE_ALL, SCOPE_UNKNOWN, setAcademyScope } from "../api/academyScope";
import { useAuthStore } from "../store/authStore";

export const ENTITY_CONTEXT_KEY = ["entity-context"];

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

  const { data, isLoading, isError } = useQuery({
    queryKey: ENTITY_CONTEXT_KEY,
    queryFn: () => api.get("/auth/entity-context/").then((r) => r.data),
    enabled: isAuthenticated,
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });

  const context = data || {};
  const activeAcademy = context.active_entity || null;
  const isAllAcademies = Boolean(context.all_entities_mode);
  const academyScope = scopeOf(activeAcademy, { allMode: isAllAcademies });

  /* Le client HTTP doit connaître la portée avant toute requête. On la
     synchronise dès que le serveur la communique — y compris au premier
     chargement, où elle vaut encore UNKNOWN. */
  useEffect(() => {
    if (isLoading) return;
    setAcademyScope(academyScope);
  }, [academyScope, isLoading]);

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
};

export { SCOPE_ALL };
