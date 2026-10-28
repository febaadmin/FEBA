/**
 * Géométrie des gabarits de documents — en MILLIMÈTRES, repère haut-gauche.
 *
 * L'écran ne stocke jamais de pixels : une zone placée sur un écran de
 * 1 280 px et relue sur un écran de 390 px doit désigner le même endroit
 * de la page imprimée. Les pixels n'existent qu'au moment de l'affichage,
 * par proportion avec la largeur réelle de l'aperçu.
 */

export const MIN_WIDTH_MM = 5;
export const MIN_HEIGHT_MM = 3;

const round = (n) => Math.round(n * 100) / 100;

/** Position CSS (en %) d'une zone sur l'aperçu. */
export function boxStyle(field, page) {
  return {
    left: `${(field.x_mm / page.width_mm) * 100}%`,
    top: `${(field.y_mm / page.height_mm) * 100}%`,
    width: `${(field.width_mm / page.width_mm) * 100}%`,
    height: `${(field.height_mm / page.height_mm) * 100}%`,
  };
}

/** Déplacement en pixels d'écran → millimètres de page. */
export function pxToMm(deltaPx, renderedPx, pageMm) {
  if (!renderedPx) return 0;
  return (deltaPx / renderedPx) * pageMm;
}

/** Zone ramenée dans la page, dimensions minimales respectées. */
export function clampBox(field, page) {
  const width = Math.min(Math.max(field.width_mm, MIN_WIDTH_MM), page.width_mm);
  const height = Math.min(Math.max(field.height_mm, MIN_HEIGHT_MM), page.height_mm);
  return {
    ...field,
    width_mm: round(width),
    height_mm: round(height),
    x_mm: round(Math.min(Math.max(field.x_mm, 0), page.width_mm - width)),
    y_mm: round(Math.min(Math.max(field.y_mm, 0), page.height_mm - height)),
  };
}

export function overlaps(a, b) {
  return a.x_mm < b.x_mm + b.width_mm - 0.01 && b.x_mm < a.x_mm + a.width_mm - 0.01
    && a.y_mm < b.y_mm + b.height_mm - 0.01 && b.y_mm < a.y_mm + a.height_mm - 0.01;
}

/**
 * Problèmes visibles avant tout envoi — miroir du serveur, qui reste seul
 * juge (`apps/documents/academy_templates.normalize_fields`).
 */
export function layoutProblems(fields, page, labelOf = (name) => name) {
  const problems = [];
  fields.forEach((f) => {
    if (f.x_mm < 0 || f.y_mm < 0 || f.x_mm + f.width_mm > page.width_mm + 0.01
        || f.y_mm + f.height_mm > page.height_mm + 0.01) {
      problems.push({ type: "outside", names: [f.name], label: labelOf(f.name) });
    }
  });
  for (let i = 0; i < fields.length; i += 1) {
    for (let j = i + 1; j < fields.length; j += 1) {
      if (overlaps(fields[i], fields[j])) {
        problems.push({ type: "overlap", names: [fields[i].name, fields[j].name],
          label: `${labelOf(fields[i].name)} / ${labelOf(fields[j].name)}` });
      }
    }
  }
  if (!fields.some((f) => f.name === "student_name")) {
    problems.push({ type: "missing_name", names: [], label: labelOf("student_name") });
  }
  return problems;
}

/** Nouvelle zone posée au centre de la page, sous les zones existantes. */
export function newField(name, page, existing = []) {
  const width = Math.min(120, page.width_mm * 0.6);
  const height = name === "student_name" ? 18 : 10;
  let y = page.height_mm * 0.15;
  const x = (page.width_mm - width) / 2;
  const sorted = [...existing].sort((a, b) => a.y_mm - b.y_mm);
  sorted.forEach((f) => {
    if (overlaps({ x_mm: x, y_mm: y, width_mm: width, height_mm: height }, f)) {
      y = f.y_mm + f.height_mm + 2;
    }
  });
  return clampBox({
    name, x_mm: x, y_mm: y, width_mm: width, height_mm: height,
    font: "serif", font_size_pt: name === "student_name" ? 26 : 12,
    min_font_size_pt: name === "student_name" ? 12 : 8, align: "center",
    color: "#000000", max_lines: name === "student_name" ? 2 : 1,
    required: name === "student_name",
  }, page);
}

/** Lit le message d'une erreur dont la réponse a été demandée en binaire. */
export async function blobErrorDetail(error) {
  const data = error?.response?.data;
  if (data && typeof Blob !== "undefined" && data instanceof Blob) {
    try {
      const parsed = JSON.parse(await data.text());
      return parsed.detail || null;
    } catch {
      return null;
    }
  }
  return null;
}
