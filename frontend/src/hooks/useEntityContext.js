/**
 * useEntityContext — compatibilité avec l'ancien nommage « entité ».
 *
 * L'état d'académie vit désormais dans un contexte React unique
 * (`src/context/AcademyContext.jsx`) : un seul endroit décide de
 * l'académie active, de la portée envoyée au serveur, de l'annulation des
 * requêtes en vol et de la purge du cache. Le fournisseur enveloppe toute
 * l'application, donc tous les écrans lisent forcément la même valeur —
 * ce que trois hooks indépendants ne garantissaient pas.
 *
 * Ce module reste comme façade : les écrans déjà écrits continuent
 * d'utiliser `useEntityContext()`, `useAcademyKey()` et
 * `useEntitySwitch()` sans modification. Les nouveaux écrans utilisent
 * directement `useAcademy()`.
 *
 * PRINCIPE DE SÉCURITÉ — inchangé : l'académie active est résolue PAR LE
 * SERVEUR (`GET /api/auth/entity-context/`). Rien n'est lu depuis
 * localStorage, et `features` ne sert qu'à masquer des menus : le backend
 * refuse de lui-même les endpoints d'une fonctionnalité désactivée
 * (permission HasEntityFeature).
 */
import { useAcademy, ENTITY_CONTEXT_KEY } from "../context/AcademyContext";

export { ENTITY_CONTEXT_KEY };

/**
 * Clé de remontage du sous-arbre routé : changer cette clé démonte tous
 * les écrans et les remonte vides, ce qui garantit qu'aucune donnée de
 * l'académie précédente ne reste affichée.
 */
export function useAcademyKey() {
  return useAcademy().academyKey;
}

export function useEntityContext() {
  const academy = useAcademy();
  return {
    isLoading: academy.isLoadingAcademy,
    activeEntity: academy.activeAcademy,
    entities: academy.allowedAcademies,
    canSwitch: academy.canSwitchAcademy,
    allEntitiesMode: academy.isAllAcademies,
    features: academy.features,
    hasFeature: academy.hasFeature,
  };
}

/**
 * Façade « mutation » de la bascule d'académie, pour les composants
 * écrits avant l'introduction du contexte (ils appellent `.mutate()`
 * avec des callbacks `onSuccess` / `onError`).
 */
export function useEntitySwitch() {
  const { switchAcademy, isSwitchingAcademy, switchError } = useAcademy();

  const mutate = (entityId, options = {}) =>
    switchAcademy(entityId ?? null)
      .then((data) => {
        options.onSuccess?.(data);
        return data;
      })
      .catch((error) => {
        options.onError?.(error);
      });

  return {
    mutate,
    mutateAsync: switchAcademy,
    isPending: isSwitchingAcademy,
    error: switchError,
  };
}
