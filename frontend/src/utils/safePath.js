/**
 * Chemin INTERNE sûr pour `navigate()`, ou null.
 *
 * React Router 6 (avis GHSA, CVE-2025-68470 et contournement) : un chemin
 * commençant par « // » ou « /\ » est interprété comme une adresse d'un
 * autre site — redirection ouverte. Les liens des notifications viennent
 * du serveur (chemins internes, API en lecture seule) ; cette garde
 * empêche qu'une valeur inattendue fasse quitter l'application.
 */
export function safeInternalPath(value) {
  if (typeof value !== "string") return null;
  // Pas de trim() : un caractère de contrôle en tête (« \n/x ») serait
  // effacé au lieu d'être refusé.
  const path = value;
  if (!path.startsWith("/") || path.startsWith("//") || path.startsWith("/\\")) return null;
  // Caractère de contrôle (code < 32) ou barre oblique inverse : refusé.
  if ([...path].some((c) => c.charCodeAt(0) < 32 || c === "\\")) return null;
  return path;
}
