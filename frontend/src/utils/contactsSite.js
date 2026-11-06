/**
 * Coordonnées laissées sur le site vitrine : normalisation SANS invention.
 *
 * WhatsApp (wa.me) exige un numéro international, chiffres seulement.
 * - « +229 0197… », « 00229… » : indicatif explicite → accepté (8 à 15 chiffres, E.164).
 * - « 01XXXXXXXX » (10 chiffres) : format national béninois depuis 2024 → +229.
 * - tout autre numéro sans indicatif (ex. 0705… nigérian ?) : ambigu → refusé, expliqué.
 * Le numéro de TÉLÉPHONE n'est jamais utilisé à la place du numéro WhatsApp.
 */
export function numeroWhatsApp(brut) {
  const texte = String(brut || "").trim();
  if (!texte) return { valide: false, raison: "Aucun numéro WhatsApp renseigné par le contact." };
  let chiffres = texte.replace(/[^\d+]/g, "");
  if (chiffres.startsWith("00")) chiffres = `+${chiffres.slice(2)}`;
  if (chiffres.startsWith("+")) {
    const n = chiffres.slice(1).replace(/\D/g, "");
    if (n.length >= 8 && n.length <= 15) return { valide: true, numero: n };
    return { valide: false, raison: "Numéro WhatsApp invalide (indicatif pays et longueur à vérifier)." };
  }
  if (/^01\d{8}$/.test(chiffres)) return { valide: true, numero: `229${chiffres}` };
  return { valide: false, raison: "Numéro WhatsApp sans indicatif pays : impossible de savoir à quel pays il appartient." };
}

export const emailValide = (e) => /^[^\s@<>(),;:"]+@[^\s@<>(),;:"]+\.[^\s@<>(),;:"]{2,}$/.test(String(e || "").trim());

export function lienWhatsApp(numero, texte) {
  return `https://wa.me/${numero}${texte ? `?text=${encodeURIComponent(texte)}` : ""}`;
}
