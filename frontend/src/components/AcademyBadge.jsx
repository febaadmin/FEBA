/**
 * AcademyBadge — étiquette d'appartenance à une académie.
 *
 * P3 — En mode « Toutes les Académies », les listes renvoyaient bien
 * l'union des académies, mais rien n'indiquait à laquelle chaque ligne
 * appartenait : classes, années scolaires, matières et utilisateurs
 * apparaissaient mélangés, sans moyen de les distinguer.
 *
 * Le badge affiche TOUJOURS un texte — jamais une simple couleur — pour
 * rester lisible en niveaux de gris, à l'impression et pour les
 * utilisateurs daltoniens.
 *
 * AUCUNE ACADÉMIE CONNUE EN DUR
 * -----------------------------
 * Le badge connaissait FEBA et FEBA FHA par leur code ; toute autre
 * académie s'affichait en ORANGE, la couleur d'un avertissement, comme si
 * elle était en défaut. Désormais le texte vient des données servies
 * (`academy_short_name`, sinon `academy_name`, sinon le code) et la teinte
 * est dérivée du code interne STABLE : identique d'un écran à l'autre et
 * après un renommage, sans liste à tenir à jour. L'orange est réservé à
 * l'objet SANS académie.
 */

const TONES = [
  "bg-blue-50 text-blue-700 border-blue-200",
  "bg-emerald-50 text-emerald-700 border-emerald-200",
  "bg-indigo-50 text-indigo-700 border-indigo-200",
  "bg-sky-50 text-sky-700 border-sky-200",
  "bg-violet-50 text-violet-700 border-violet-200",
  "bg-teal-50 text-teal-700 border-teal-200",
  "bg-rose-50 text-rose-700 border-rose-200",
  "bg-slate-100 text-slate-700 border-slate-300",
];

const UNKNOWN = {
  short: "Sans académie",
  tone: "bg-amber-50 text-amber-700 border-amber-200",
};

/** Teinte stable d'une académie, dérivée de son code interne. */
export function academyTone(code) {
  if (!code) return UNKNOWN.tone;
  let hash = 0;
  for (const ch of String(code)) hash = (hash * 31 + ch.codePointAt(0)) >>> 0;
  return TONES[hash % TONES.length];
}

/**
 * @param {string} code       academy_code renvoyé par l'API
 * @param {string} name       academy_name (info-bulle, et texte à défaut d'abréviation)
 * @param {string} shortName  academy_short_name (texte du badge)
 * @param {boolean} full      affiche le nom complet plutôt que l'abréviation
 */
export default function AcademyBadge({ code, name, shortName, full = false, className = "" }) {
  const text = (full ? name || shortName : shortName || name) || code || UNKNOWN.short;
  const tone = code || name ? academyTone(code || name) : UNKNOWN.tone;
  return (
    <span
      title={name || shortName || code || undefined}
      data-academy-code={code || undefined}
      className={`inline-flex items-center px-2 py-0.5 rounded-md border text-[11px] font-semibold whitespace-nowrap max-w-[16rem] ${tone} ${className}`}
    >
      <span className="truncate">{text}</span>
    </span>
  );
}

/**
 * Variante pour préfixer un libellé : « [Académie] Mathématiques ».
 * Utilisée dans les écrans de paramètres, où les objets sont présentés
 * en cartes plutôt qu'en tableau.
 */
export function AcademyPrefixedLabel({ code, name, shortName, children }) {
  return (
    <span className="inline-flex items-center gap-2 min-w-0">
      <AcademyBadge code={code} name={name} shortName={shortName} />
      <span className="truncate">{children}</span>
    </span>
  );
}
