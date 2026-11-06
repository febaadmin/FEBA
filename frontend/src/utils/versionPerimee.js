/**
 * Onglet resté ouvert pendant un déploiement : les modules JavaScript de l'ancienne
 * version n'existent plus sur le serveur (404) et l'ouverture d'une page affichait
 * l'écran « Une erreur est survenue » — « Réessayer » ne pouvait rien y faire.
 *
 * Remède : recharger UNE fois la page (la nouvelle version est alors chargée).
 * Le garde en sessionStorage empêche toute boucle si le module manque vraiment.
 */
const CLE = "feba-rechargement-version";
const MOTIFS = /Failed to fetch dynamically imported module|Importing a module script failed|error loading dynamically imported module|Unable to preload CSS|ChunkLoadError|Loading chunk [\w-]+ failed/i;

export function estErreurChargementModule(erreur) {
  const texte = typeof erreur === "string" ? erreur : `${erreur?.name || ""} ${erreur?.message || ""}`;
  return MOTIFS.test(texte);
}

function lire() {
  try { return Number(sessionStorage.getItem(CLE) || 0); } catch { return 0; }
}

/** Recharge si ce n'a pas déjà été tenté dans les 30 dernières secondes. Renvoie true si rechargé. */
export function rechargerUneFois(maintenant = Date.now(), recharger = () => window.location.reload()) {
  if (maintenant - lire() < 30000) return false;
  try { sessionStorage.setItem(CLE, String(maintenant)); } catch { return false; }
  recharger();
  return true;
}

/** Signalement côté serveur (best effort, jamais bloquant, sans donnée personnelle). */
export function signalerErreurInterface(type, erreur) {
  import("../api").then(({ incidentsAPI }) => incidentsAPI.signalerInterface({
    type, message: String(erreur?.message || erreur || "").slice(0, 500), route: window.location.pathname,
  })).catch(() => {});
}
