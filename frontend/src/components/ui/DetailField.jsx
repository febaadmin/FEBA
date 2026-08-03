import LongText from "./LongText";

/**
 * P0 — Une ligne « libellé / valeur » d'une vue de détail officielle.
 *
 * LE DÉFAUT CORRIGÉ
 * -----------------
 * Le panneau latéral d'une candidature FEBA FHA affichait chaque champ
 * ainsi :
 *
 *     <div className="flex justify-between gap-4">
 *       <span>{label}</span>
 *       <span className="text-right font-medium">{String(value)}</span>
 *     </div>
 *
 * Trois défauts s'additionnaient dans ces quatre lignes :
 *
 *  1. aucune règle de repli. Une adresse complète, un objectif parental de
 *     dix lignes ou une liste de certifications restaient sur UNE ligne ;
 *  2. la largeur minimale d'un enfant flex est celle de son contenu. La
 *     valeur poussait donc le libellé jusqu'à l'écraser sur deux ou trois
 *     caractères, puis débordait du panneau — texte hors cadre, sans barre
 *     de défilement, sans le moindre signe qu'il manquait quelque chose ;
 *  3. `String(value)` sur un texte multiligne : les retours à la ligne
 *     étaient conservés dans la chaîne mais aplatis par le HTML. Un texte
 *     structuré en paragraphes s'affichait en un seul bloc illisible.
 *
 * CE QUE FAIT CE COMPOSANT
 * ------------------------
 * Il choisit la mise en forme d'après le contenu réel, pas d'après le nom
 * du champ — parce qu'un champ « ville » peut recevoir trois mots et un
 * champ « commentaire » peut recevoir « ok ».
 *
 *  - valeur courte, sur une seule ligne : deux colonnes, libellé à gauche,
 *    valeur alignée à droite. La valeur garde `overflow-wrap: anywhere`,
 *    donc même ici rien ne peut sortir du cadre ;
 *  - valeur longue, multiligne, ou contenant un mot indivisible trop
 *    large : le libellé passe au-dessus et la valeur occupe toute la
 *    largeur, en `pre-wrap`, avec les retours à la ligne de l'auteur.
 *
 * Aucune troncature, dans aucun des deux cas.
 */

/** Le plus long mot (suite sans espace) de la chaîne. */
export function longestToken(text) {
  let best = 0;
  let current = 0;
  for (const char of text) {
    if (/\s/.test(char)) {
      current = 0;
    } else {
      current += 1;
      if (current > best) best = current;
    }
  }
  return best;
}

/**
 * Une valeur mérite-t-elle la présentation « pleine largeur » ?
 *
 * Les trois seuils correspondent aux trois façons dont une valeur sort du
 * cadre dans un panneau étroit : trop de caractères, un retour à la ligne
 * à respecter, ou un seul mot (une URL, une référence) plus large que la
 * colonne.
 */
export function isLongValue(value) {
  const text = value == null ? "" : String(value);
  if (!text.trim()) return false;
  if (/[\r\n]/.test(text)) return true;
  if (text.length > 56) return true;
  return longestToken(text) > 22;
}

export default function DetailField({
  label,
  value,
  emptyLabel = null,
  copyable = false,
  // Hauteur naturelle par défaut : le panneau de détail défile déjà, et une
  // seconde zone de défilement imbriquée cache la fin du texte sans le dire.
  maxHeight = "none",
  className = "",
}) {
  const text =
    value === null || value === undefined
      ? ""
      : Array.isArray(value)
        ? value.filter(Boolean).join(", ")
        : String(value);

  // Champ vide : on ne montre rien, sauf si l'appelant demande explicitement
  // un marqueur d'absence (utile sur une fiche officielle où l'on doit
  // pouvoir distinguer « non renseigné » de « champ oublié à l'écran »).
  if (!text.trim()) {
    if (emptyLabel === null) return null;
    return (
      <div className={`border-b border-slate-50 pb-1 ${className}`}>
        <span className="text-slate-500">{label}</span>{" "}
        <span className="text-slate-400 italic">{emptyLabel}</span>
      </div>
    );
  }

  if (isLongValue(text)) {
    return (
      <div
        data-testid="detail-field-long"
        className={`border-b border-slate-50 pb-2 pt-1 ${className}`}
      >
        <span className="block text-slate-500 mb-1">{label}</span>
        <LongText
          value={text}
          maxHeight={maxHeight}
          copyable={copyable}
          plain
          className="font-medium text-slate-800"
        />
      </div>
    );
  }

  return (
    <div
      data-testid="detail-field-short"
      // `flex-wrap` : si la traduction du libellé s'allonge, la valeur
      // descend d'une ligne au lieu de comprimer le libellé.
      className={`flex flex-wrap justify-between items-baseline gap-x-4 gap-y-0.5 border-b border-slate-50 pb-1 ${className}`}
    >
      <span className="text-slate-500 shrink-0">{label}</span>
      <span className="font-medium text-slate-800 text-right text-wrapsafe">
        {text}
      </span>
    </div>
  );
}
