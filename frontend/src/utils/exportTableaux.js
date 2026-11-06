/**
 * Export CSV des tableaux d'un rapport affiché (centre d'analyse) : chaque tableau
 * est précédé du titre de son graphique et du contexte. Les données exportées
 * sont exactement celles affichées (mêmes filtres, mêmes droits).
 * Cellules protégées contre l'injection de formules (=, +, -, @).
 */
const proteger = (v) => {
  const s = String(v ?? "").replace(/\s+/g, " ").trim();
  const sur = /^[=+\-@]/.test(s) && !/^[+-]?[\d\s.,]+(\s?%|\s?\/\s?\d+)?$/.test(s) ? `'${s}` : s;
  return /[";\n]/.test(sur) ? `"${sur.replace(/"/g, '""')}"` : sur;
};

export function tableauxEnCsv(racine, entete = []) {
  const lignes = entete.map((l) => proteger(l));
  let n = 0;
  for (const table of racine?.querySelectorAll("table") || []) {
    const figure = table.closest("figure");
    const titre = figure?.querySelector("figcaption p")?.textContent || "";
    if (lignes.length) lignes.push("");
    if (titre) lignes.push(proteger(titre));
    for (const tr of table.querySelectorAll("tr")) {
      lignes.push([...tr.querySelectorAll("th,td")].map((c) => proteger(c.textContent)).join(";"));
    }
    n += 1;
  }
  return { csv: `\ufeff${lignes.join("\n")}`, tableaux: n };
}

export function telechargerTexte(nom, texte, type = "text/csv;charset=utf-8") {
  const url = URL.createObjectURL(new Blob([texte], { type }));
  const a = document.createElement("a");
  a.href = url; a.download = nom; a.click();
  URL.revokeObjectURL(url);
}
