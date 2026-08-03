/**
 * academyScope — portée d'académie courante du client HTTP.
 *
 * PROBLÈME RÉSOLU (P0)
 * --------------------
 * Au changement d'académie, le sélecteur changeait de libellé instantanément
 * mais les tableaux restaient plusieurs secondes sur les données de
 * l'académie quittée. La cause n'était pas seulement le cache : les requêtes
 * DÉJÀ EN VOL se terminaient après la bascule et réécrivaient le cache avec
 * la réponse de l'ancienne académie. Vider le cache ne servait à rien
 * puisqu'il était immédiatement re-rempli par ces réponses tardives.
 *
 * Ce module apporte deux garanties :
 *
 *   1. ANNULATION — chaque requête sortante reçoit un AbortController
 *      enregistré ici. `setAcademyScope()` avorte tout ce qui est en vol :
 *      une requête émise pour FEBA ne peut plus aboutir après un passage
 *      sur FEBA FHA.
 *
 *   2. VÉRIFICATION — chaque requête annonce sa portée (`X-Academy-Scope`)
 *      et le serveur répond avec la portée réellement utilisée. Si les deux
 *      diffèrent, la réponse est rejetée : elle décrit une académie qui
 *      n'est plus affichée. C'est le filet de sécurité pour les cas que
 *      l'annulation ne couvre pas (réponse déjà arrivée dans le tampon
 *      réseau, requête émise hors de notre intercepteur…).
 *
 * Le module est volontairement sans dépendance React : il est utilisé par
 * les intercepteurs axios, qui s'exécutent hors du cycle de rendu.
 */

export const SCOPE_ALL = "ALL";
export const SCOPE_UNKNOWN = "UNKNOWN";
export const HEADER = "X-Academy-Scope";

/** Portée annoncée sur les requêtes sortantes. */
let currentScope = SCOPE_UNKNOWN;

/** Contrôleurs des requêtes en vol, avortés à chaque bascule. */
const inflight = new Set();

/** Erreur marquant une réponse écartée parce qu'elle n'est plus d'actualité. */
export class StaleAcademyResponse extends Error {
  constructor(expected, received, url) {
    super(
      `Réponse ignorée : calculée pour l'académie « ${received} », ` +
        `l'interface est sur « ${expected} » (${url || "requête inconnue"}).`,
    );
    this.name = "StaleAcademyResponse";
    this.expected = expected;
    this.received = received;
    /* React Query ne doit ni réessayer ni afficher cette erreur : le
       composant concerné est de toute façon en cours de remontage. */
    this.isStaleAcademy = true;
  }
}

export function getAcademyScope() {
  return currentScope;
}

/**
 * Endpoints exemptés du contrôle de portée.
 *
 * La requête de BASCULE est celle qui CHANGE la portée : le serveur la
 * traite, puis annonce dans sa réponse la nouvelle académie — forcément
 * différente de celle que le client avait au moment de l'envoi. La traiter
 * comme une réponse périmée revenait à rejeter la bascule elle-même : le
 * serveur enregistrait bien le changement, mais le frontend n'en était
 * jamais informé et le sélecteur restait figé sur l'académie précédente.
 *
 * La lecture du contexte est exemptée pour la même raison : c'est elle qui
 * ÉTABLIT la portée, elle ne peut pas être vérifiée contre elle-même.
 */
const SCOPE_EXEMPT = ["/auth/entity-context/"];

export function isScopeExempt(url) {
  if (!url) return false;
  return SCOPE_EXEMPT.some((path) => url.includes(path));
}

/**
 * Déclare la portée active et invalide tout ce qui appartenait à la
 * précédente. Appelée par AcademyProvider dès que le SERVEUR a confirmé
 * la bascule — jamais sur une simple intention de l'utilisateur.
 *
 * @returns {boolean} true si la portée a réellement changé.
 */
export function setAcademyScope(next) {
  const value = next || SCOPE_UNKNOWN;
  if (value === currentScope) return false;
  currentScope = value;
  abortInflightRequests();
  return true;
}

/** Avorte toutes les requêtes en vol (bascule d'académie, déconnexion…). */
export function abortInflightRequests() {
  for (const controller of inflight) {
    try {
      controller.abort();
    } catch {
      /* Un contrôleur déjà consommé lève sur certains navigateurs :
         sans importance, la requête est terminée. */
    }
  }
  inflight.clear();
}

export function trackRequest() {
  const controller = new AbortController();
  inflight.add(controller);
  return controller;
}

export function releaseRequest(controller) {
  if (controller) inflight.delete(controller);
}

/** Nombre de requêtes en vol — utilisé par les tests. */
export function inflightCount() {
  return inflight.size;
}

/**
 * True si la réponse doit être écartée.
 *
 * `UNKNOWN` des deux côtés est toléré : au tout premier rendu, le client
 * n'a pas encore reçu son contexte d'académie. Rejeter ces réponses
 * bloquerait l'application au démarrage.
 */
export function isStaleResponse(responseScope, url) {
  if (!responseScope) return false;
  if (isScopeExempt(url)) return false;
  if (currentScope === SCOPE_UNKNOWN) return false;
  return responseScope !== currentScope;
}

/** Remise à zéro — tests unitaires uniquement. */
export function resetAcademyScope() {
  currentScope = SCOPE_UNKNOWN;
  inflight.clear();
}
