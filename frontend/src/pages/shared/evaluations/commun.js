import { t } from "../../../i18n";

export const TYPES_QUESTION = [
  ["qcm_unique", "QCM à réponse unique"], ["qcm_multiple", "QCM à réponses multiples"], ["vrai_faux", "Vrai ou faux"],
  ["ouverte", "Question ouverte"], ["courte", "Réponse courte"], ["numerique", "Réponse numérique"],
  ["trous", "Texte à trous"], ["association", "Associations"], ["classement", "Classement"], ["fichier", "Fichier à déposer"],
];
export const TYPES_EPREUVE = [
  ["quiz", "Quiz d'entraînement"], ["interrogation", "Interrogation"], ["evaluation", "Évaluation"], ["examen", "Examen officiel"],
  ["blanc", "Examen blanc"], ["positionnement", "Évaluation de positionnement"], ["diagnostique", "Évaluation diagnostique"],
  ["competences", "Évaluation de compétences"], ["fin_formation", "Évaluation de fin de formation"],
  ["surveille", "Devoir surveillé"], ["formative", "Évaluation formative"], ["certificative", "Évaluation certificative"],
];
export const STATUTS_EPREUVE = { brouillon: "Brouillon", publiee: "Publiée", close: "Close", archivee: "Archivée" };
export const STATUTS_COPIE = { en_cours: "En cours", remise: "Remise, à corriger", corrigee: "Corrigée", validee: "Validée" };
export const libelle = (liste, cle) => t(liste.find(([k]) => k === cle)?.[1] || cle);

export function telecharger(blob, nom) {
  const url = URL.createObjectURL(blob);
  const lien = document.createElement("a");
  lien.href = url;
  lien.download = nom;
  lien.click();
  URL.revokeObjectURL(url);
}

export const lignes = (texte) => (texte || "").split("\n").map((l) => l.trim()).filter(Boolean);

/** Traduit le formulaire simple de l'enseignant en contenu et corrigé. */
export function construireQuestion(type, f) {
  const items = lignes(f.lignes);
  if (type === "qcm_unique" || type === "qcm_multiple") {
    const remplis = (f.choix || []).filter((c) => c.texte?.trim());
    const choix = remplis.map((c, i) => ({ id: `c${i}`, texte: c.texte.trim() }));
    const bonnes = remplis.map((c, i) => (c.bon ? `c${i}` : null)).filter(Boolean);
    return { contenu: { choix }, corrige: type === "qcm_unique" ? { bonne: bonnes[0] } : { bonnes } };
  }
  if (type === "vrai_faux") return { contenu: {}, corrige: { valeur: f.vrai === "vrai" } };
  if (type === "courte") return { contenu: {}, corrige: { acceptees: items } };
  if (type === "numerique") return { contenu: {}, corrige: { valeur: f.valeur, tolerance: f.tolerance || 0 } };
  if (type === "trous") return { contenu: { nombre_trous: items.length }, corrige: { reponses: items.map((l) => l.split("|").map((x) => x.trim())) } };
  if (type === "association") {
    const paires = items.map((l) => l.split("=").map((x) => x.trim()));
    return {
      contenu: { gauche: paires.map(([g], i) => ({ id: `g${i}`, texte: g })), droite: paires.map(([, d], i) => ({ id: `d${i}`, texte: d })) },
      corrige: { paires: Object.fromEntries(paires.map((_, i) => [`g${i}`, `d${i}`])) },
    };
  }
  if (type === "classement") return { contenu: { elements: items.map((l, i) => ({ id: `e${i}`, texte: l })) }, corrige: { ordre: items.map((_, i) => `e${i}`) } };
  return { contenu: {}, corrige: {} };
}

/** Erreurs à afficher sous le champ concerné, avant tout envoi. La saisie reste en place. */
export function erreursQuestion(type, f) {
  const e = {};
  if (!f.enonce?.trim()) e.enonce = "Saisissez l'énoncé de la question.";
  const items = lignes(f.lignes);
  const uniques = (l) => new Set(l.map((x) => x.toLowerCase())).size === l.length;
  if (type === "qcm_unique" || type === "qcm_multiple") {
    const remplis = (f.choix || []).filter((c) => c.texte?.trim());
    if (remplis.length < 2) e.reponses = "Saisissez au moins deux réponses.";
    else if (!uniques(remplis.map((c) => c.texte.trim()))) e.reponses = "Deux réponses sont identiques.";
    else if (!remplis.some((c) => c.bon)) e.reponses = type === "qcm_unique" ? "Cochez la bonne réponse." : "Cochez au moins une bonne réponse.";
  }
  if (type === "courte" && items.length < 1) e.reponses = "Indiquez au moins une réponse acceptée.";
  if (type === "trous" && items.length < 1) e.reponses = "Indiquez les réponses de chaque trou.";
  if (type === "classement") {
    if (items.length < 2) e.reponses = "Indiquez au moins deux éléments à classer.";
    else if (!uniques(items)) e.reponses = "Deux éléments sont identiques.";
  }
  if (type === "association") {
    if (items.length < 2) e.reponses = "Indiquez au moins deux paires.";
    else if (items.some((l) => l.split("=").length !== 2 || l.split("=").some((x) => !x.trim()))) e.reponses = "Chaque ligne doit suivre le format : gauche = droite.";
  }
  if (type === "numerique" && (f.valeur === undefined || f.valeur === "" || Number.isNaN(Number(String(f.valeur).replace(",", "."))))) e.valeur = "Indiquez un nombre.";
  if (f.points === "" || Number(f.points) < 0) e.points = "Indiquez un nombre de points positif.";
  return e;
}

/** Reconstitue le formulaire depuis une question enregistrée, pour la modifier. */
export function formulaireDepuis(q) {
  const v = q.version || {};
  const c = v.contenu || {};
  const r = v.corrige || {};
  const f = { id: q.id, type: q.type, enonce: v.enonce, points: v.points, difficulte: q.difficulte, subject: q.subject || "", prive: q.prive,
    competence: q.competences?.[0] || "", criteres: v.criteres, explication: v.explication, vrai: "vrai", choix: [{ texte: "" }, { texte: "" }] };
  if (q.type === "qcm_unique" || q.type === "qcm_multiple") {
    const bonnes = q.type === "qcm_unique" ? [r.bonne] : r.bonnes || [];
    f.choix = (c.choix || []).map((x) => ({ texte: x.texte, bon: bonnes.includes(x.id) }));
  }
  if (q.type === "vrai_faux") f.vrai = r.valeur ? "vrai" : "faux";
  if (q.type === "courte") f.lignes = (r.acceptees || []).join("\n");
  if (q.type === "numerique") { f.valeur = r.valeur; f.tolerance = r.tolerance; }
  if (q.type === "trous") f.lignes = (r.reponses || []).map((x) => x.join(" | ")).join("\n");
  if (q.type === "association") f.lignes = (c.gauche || []).map((g, i) => `${g.texte} = ${c.droite?.[i]?.texte ?? ""}`).join("\n");
  if (q.type === "classement") f.lignes = (c.elements || []).map((x) => x.texte).join("\n");
  return f;
}
