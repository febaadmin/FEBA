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

/**
 * Champs À / Cc / Cci : listes d'entrées { type: "email" | "user", value, label }.
 * Une adresse saisie part telle quelle (validée par le serveur) ; un compte choisi
 * est désigné par son identifiant (le serveur vérifie qu'il est dans l'académie).
 */
export const champsVides = () => ({ a: [], cc: [], cci: [] });
export const MODES = { individuel: "individuel", commun: "commun" };

// Validation de confort (le serveur revalide) : forme local@domaine.tld.
export const adresseValide = (texte) => /^[^\s@<>(),;:"[\]]+@[^\s@<>(),;:"[\]]+\.[^\s@<>(),;:"[\]]{2,}$/.test(texte);

/** Découpe une saisie (virgules, points-virgules, espaces) en adresses valides et invalides. */
export function decouperAdresses(texte) {
  const morceaux = (texte || "").split(/[\s,;]+/).map((x) => x.trim()).filter(Boolean);
  return {
    valides: morceaux.filter(adresseValide).map((x) => x.toLowerCase()),
    invalides: morceaux.filter((x) => !adresseValide(x)),
  };
}

export function ajouterEntree(liste, entree) {
  const cle = (e) => `${e.type}:${String(e.value).toLowerCase()}`;
  return liste.some((e) => cle(e) === cle(entree)) ? liste : [...liste, entree];
}

/** Corps de requête attendu par l'API. */
export function audiencePayload(audience, champs = champsVides(), mode = MODES.individuel) {
  const valeurs = (liste) => liste.map((e) => (e.type === "user" ? e.value : String(e.value)));
  return {
    roles: audience.roles,
    all_profiles: audience.allProfiles,
    include_ids: audience.include,
    exclude_ids: audience.exclude,
    adresses: { a: valeurs(champs.a), cc: valeurs(champs.cc), cci: valeurs(champs.cci) },
    mode,
  };
}

/** Audience d'un brouillon (format API) → état de l'écran. `comptes` : comptes connus, pour les libellés. */
export function depuisAudience(api, comptes = []) {
  const parId = new Map(comptes.map((u) => [u.id, u]));
  const champ = (liste) => (liste || []).map((v) => (typeof v === "number"
    ? { type: "user", value: v, label: parId.get(v) ? `${parId.get(v).full_name} <${parId.get(v).email}>` : `#${v}` }
    : { type: "email", value: v, label: v }));
  return {
    audience: { roles: api?.roles || [], allProfiles: Boolean(api?.all_profiles), include: api?.include_ids || [], exclude: api?.exclude_ids || [] },
    champs: { a: champ(api?.adresses?.a), cc: champ(api?.adresses?.cc), cci: champ(api?.adresses?.cci) },
    mode: api?.mode === MODES.commun ? MODES.commun : MODES.individuel,
  };
}

export function hasAnyRule(audience, champs = champsVides()) {
  return audience.allProfiles || audience.roles.length > 0 || audience.include.length > 0
    || champs.a.length > 0 || champs.cc.length > 0 || champs.cci.length > 0;
}

export function newClientToken() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID().replace(/-/g, "");
  return `${Date.now().toString(16)}${Math.random().toString(16).slice(2)}`.slice(0, 64);
}
