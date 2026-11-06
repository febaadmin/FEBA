import { useQuery } from "@tanstack/react-query";
import { conversationsAPI } from "../api";
import { useAcademy } from "../context/AcademyContext";

/**
 * Compteur « Messages » du menu — UNE seule règle pour les cinq profils :
 * conversations non lues hors archives, corbeille et conversations masquées
 * (même chiffre que le badge « Réception » de la messagerie).
 *
 * La clé commence par « messagerie » : toute action de la messagerie (lecture,
 * envoi, déplacement) invalide ce préfixe, le badge se met donc à jour sans attendre.
 *
 * Attend `businessDataEnabled` : partie avant que la portée d'académie soit établie,
 * la requête était annulée par la bascule de portée qui suit la connexion, et le
 * badge restait vide jusqu'au rafraîchissement suivant (30 s).
 */
export function useNonLusMessagerie(userId) {
  const { businessDataEnabled } = useAcademy();
  const { data } = useQuery({
    queryKey: ["messagerie", "menu", userId],
    queryFn: conversationsAPI.unreadCount,
    refetchInterval: 30000,
    refetchOnWindowFocus: true,
    staleTime: 0,
    enabled: Boolean(userId) && businessDataEnabled !== false,
  });
  return data?.data?.count || 0;
}

/** Vrai quand les requêtes métier peuvent partir (portée d'académie établie). */
export function usePretPourDonnees() {
  return useAcademy().businessDataEnabled !== false;
}
