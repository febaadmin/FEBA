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
    const bonnes = items.map((l, i) => (l.startsWith("*") ? `c${i}` : null)).filter(Boolean);
    const choix = items.map((l, i) => ({ id: `c${i}`, texte: l.replace(/^\*\s*/, "") }));
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
