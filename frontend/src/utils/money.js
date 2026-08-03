/**
 * money — formatage des montants. Source unique côté navigateur.
 *
 * PROBLÈME RÉSOLU (P0)
 * --------------------
 * Onze écrans écrivaient `${montant.toLocaleString()} FCFA`. FEBA French
 * Heritage Academy facture en dollars : chacun de ses montants s'affichait
 * donc dans la mauvaise monnaie. Le nombre était juste, l'unité fausse —
 * et rien à l'écran ne permettait de s'en apercevoir.
 *
 * RÈGLE
 * -----
 * Le frontend ne DÉCIDE jamais d'une devise. Il affiche celle que le
 * serveur a attachée à la donnée (`currency` sur chaque objet financier,
 * `currency` sur l'académie active). En l'absence d'information, il
 * affiche le montant SANS symbole plutôt que d'en inventer un : un nombre
 * nu est ambigu, un nombre avec la mauvaise devise est faux.
 *
 * Les règles ci-dessous reproduisent celles de `apps/core/currency.py`.
 * Deux implémentations sont un risque de divergence assumé : le serveur
 * envoie déjà `amount_display` pour les cas critiques (reçus, exports), et
 * ce module sert les totaux calculés à l'écran.
 */

/** Règles de rendu par devise — miroir du registre backend. */
const CURRENCIES = {
  XOF: {
    symbol: "FCFA",
    decimals: 0,
    symbolBefore: false,
    // Espace fine insécable : empêche « 50 » et « 000 » d'être séparés
    // en fin de ligne dans un tableau étroit.
    group: " ",
    decimal: ",",
  },
  USD: {
    symbol: "$",
    decimals: 2,
    symbolBefore: true,
    group: ",",
    decimal: ".",
  },
};

export const SUPPORTED_CURRENCIES = Object.keys(CURRENCIES);

export function currencyRules(code) {
  return CURRENCIES[String(code || "").toUpperCase()] || null;
}

/**
 * Formate un montant en UNITÉ MAJEURE (dollars, francs) avec sa devise.
 *
 * @param {number|string} amount  montant lisible (12.50, "50000")
 * @param {string} code           code ISO de la devise (USD, XOF)
 */
export function formatMoney(amount, code) {
  const rules = currencyRules(code);
  const value = Number(amount ?? 0);
  if (!Number.isFinite(value)) return "";

  if (!rules) {
    // Devise inconnue : on montre le nombre sans inventer de symbole.
    return value.toLocaleString();
  }

  const negative = value < 0;
  // On sépare la partie entière de la partie décimale AVANT de grouper :
  // appliquer le séparateur de milliers à la chaîne complète grouperait
  // aussi les décimales (« 1250.00 » deviendrait « 1,250.0,0 »).
  const fixed = Math.abs(value).toFixed(rules.decimals);
  const [whole, fraction] = fixed.split(".");
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, rules.group);
  const digits = fraction ? `${grouped}${rules.decimal}${fraction}` : grouped;

  const rendered = rules.symbolBefore
    ? `${rules.symbol}${digits}`
    : `${digits} ${rules.symbol}`;
  return negative ? `-${rendered}` : rendered;
}

/**
 * Formate un montant exprimé en UNITÉ MINEURE (cents pour USD).
 * C'est la forme dans laquelle le serveur stocke les montants.
 */
export function formatMinor(amountMinor, code) {
  const rules = currencyRules(code);
  const minor = Number(amountMinor ?? 0);
  if (!rules) return String(minor);
  return formatMoney(minor / 10 ** rules.decimals, code);
}

/**
 * Montant d'une ligne renvoyée par l'API.
 *
 * Le serveur fournit déjà `amount_display` : on le préfère toujours, car
 * il est produit par le même code que les reçus PDF. Les deux autres
 * chemins ne servent qu'aux réponses plus anciennes.
 */
export function rowAmount(row, fallbackCurrency) {
  if (!row) return "";
  if (row.amount_display) return row.amount_display;
  if (row.amount_minor != null && row.currency) {
    return formatMinor(row.amount_minor, row.currency);
  }
  return formatMoney(row.amount, row.currency || fallbackCurrency);
}

/**
 * Totaux VENTILÉS PAR DEVISE.
 *
 * Renvoie un tableau `[{ currency, amountMinor, formatted }]` et non un
 * nombre unique : en mode « Toutes les Académies », additionner des francs
 * CFA et des dollars produirait un total convaincant et dépourvu de sens.
 */
export function totalsByCurrency(rows = [], fallbackCurrency) {
  const totals = new Map();
  for (const row of rows) {
    const code = String(row?.currency || fallbackCurrency || "").toUpperCase();
    if (!code) continue;
    const rules = currencyRules(code);
    const minor =
      row?.amount_minor != null
        ? Number(row.amount_minor)
        : Math.round(Number(row?.amount ?? 0) * 10 ** (rules?.decimals ?? 2));
    totals.set(code, (totals.get(code) || 0) + minor);
  }
  return [...totals.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([currency, amountMinor]) => ({
      currency,
      amountMinor,
      formatted: formatMinor(amountMinor, currency),
    }));
}

/** Rendu compact de plusieurs totaux : « $1,250.00 · 500 000 FCFA ». */
export function formatTotals(totals) {
  return totals.map((t) => t.formatted).join(" · ");
}
