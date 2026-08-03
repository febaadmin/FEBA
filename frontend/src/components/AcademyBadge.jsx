/**
 * AcademyBadge — étiquette d'appartenance à une académie.
 *
 * P3 — En mode « Toutes les Académies », les listes renvoyaient bien
 * l'union des deux académies, mais rien n'indiquait à laquelle chaque
 * ligne appartenait : classes, années scolaires, matières et
 * utilisateurs apparaissaient mélangés, sans moyen de les distinguer.
 *
 * Le badge affiche TOUJOURS un texte — jamais une simple couleur — pour
 * rester lisible en niveaux de gris, à l'impression et pour les
 * utilisateurs daltoniens.
 *
 * `academy_code` est un code interne STABLE : le badge ne change pas si
 * l'administration renomme l'académie.
 */

const LABELS = {
  FEBA: { short: "FEBA", tone: "bg-blue-50 text-blue-700 border-blue-200" },
  FEBA_FHA: { short: "FEBA FHA", tone: "bg-emerald-50 text-emerald-700 border-emerald-200" },
};

const UNKNOWN = {
  short: "Sans académie",
  tone: "bg-amber-50 text-amber-700 border-amber-200",
};

/**
 * @param {string} code  academy_code renvoyé par l'API
 * @param {string} name  academy_name (utilisé en info-bulle et en repli)
 * @param {boolean} full affiche le nom complet plutôt que l'abréviation
 */
export default function AcademyBadge({ code, name, full = false, className = "" }) {
  const known = LABELS[code];
  const style = known || UNKNOWN;
  // Une académie inconnue du frontend (ajoutée par l'administration) doit
  // rester lisible : on affiche alors son nom ou son code brut.
  const text = full
    ? name || code || UNKNOWN.short
    : known
      ? known.short
      : name || code || UNKNOWN.short;

  return (
    <span
      title={name || code || undefined}
      className={`inline-flex items-center px-2 py-0.5 rounded-md border text-[11px] font-semibold whitespace-nowrap ${style.tone} ${className}`}
    >
      {text}
    </span>
  );
}

/**
 * Variante pour préfixer un libellé : « [FEBA] Mathématiques ».
 * Utilisée dans les écrans de paramètres, où les objets sont présentés
 * en cartes plutôt qu'en tableau.
 */
export function AcademyPrefixedLabel({ code, name, children }) {
  return (
    <span className="inline-flex items-center gap-2 min-w-0">
      <AcademyBadge code={code} name={name} />
      <span className="truncate">{children}</span>
    </span>
  );
}
