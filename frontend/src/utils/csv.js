const NOMBRE = /^[+-]?[\d\s.,]+$/;

/** Cellule de CSV : un tableur exécuterait un texte commençant par un signe de formule. */
export function celluleCsv(valeur) {
  const texte = String(valeur ?? "");
  const sur = /^[=+\-@\t\r]/.test(texte) && !NOMBRE.test(texte) ? `'${texte}` : texte;
  return `"${sur.replace(/"/g, '""')}"`;
}
