/**
 * Sélection des destinataires d'un envoi groupé — logique pure.
 *
 * L'audience est un ensemble de RÈGLES, pas une liste d'adresses :
 *   roles        types de profil entiers (« tous les parents »)
 *   allProfiles  tous les profils de l'académie
 *   include      comptes ajoutés un par un
 *   exclude      comptes retirés d'un type sélectionné
 *
 * Le serveur recalcule les destinataires à partir de ces règles ; cette
 * fonction ne sert qu'à refléter fidèlement, case par case, ce qu'il
 * calculera.
 */
export const emptyAudience = () => ({ roles: [], allProfiles: false, include: [], exclude: [] });

export function coveredByRule(user, audience) {
  return audience.allProfiles || audience.roles.includes(user.role);
}

export function isSelected(user, audience) {
  if (!user.sendable) return false;
  if (audience.exclude.includes(user.id)) return false;
  return coveredByRule(user, audience) || audience.include.includes(user.id);
}

const without = (list, id) => list.filter((x) => x !== id);
const withId = (list, id) => (list.includes(id) ? list : [...list, id]);

/** Coche / décoche UN compte, en ajustant inclusions ou exclusions. */
export function toggleUser(audience, user) {
  if (!user.sendable) return audience;
  const selected = isSelected(user, audience);
  if (coveredByRule(user, audience)) {
    return {
      ...audience,
      exclude: selected ? withId(audience.exclude, user.id) : without(audience.exclude, user.id),
      include: without(audience.include, user.id),
    };
  }
  return {
    ...audience,
    include: selected ? without(audience.include, user.id) : withId(audience.include, user.id),
  };
}

/** Coche ou décoche TOUS les comptes affichés (et seulement eux). */
export function setUsers(audience, users, checked) {
  return users.reduce((acc, user) => (
    user.sendable && isSelected(user, acc) !== checked ? toggleUser(acc, user) : acc
  ), audience);
}

export function toggleRole(audience, role) {
  const roles = audience.roles.includes(role)
    ? audience.roles.filter((r) => r !== role)
    : [...audience.roles, role];
  return { ...audience, roles };
}

/** Corps de requête attendu par l'API. */
export function audiencePayload(audience) {
  return {
    roles: audience.roles,
    all_profiles: audience.allProfiles,
    include_ids: audience.include,
    exclude_ids: audience.exclude,
  };
}

export function hasAnyRule(audience) {
  return audience.allProfiles || audience.roles.length > 0 || audience.include.length > 0;
}

export function newClientToken() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID().replace(/-/g, "");
  return `${Date.now().toString(16)}${Math.random().toString(16).slice(2)}`.slice(0, 64);
}
