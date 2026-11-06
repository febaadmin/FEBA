/**
 * Système graphique FEBA : une palette, une animation, des axes et des légendes
 * communs à TOUS les graphiques (recharts).
 *
 * Palette catégorielle validée (scripts/validate_palette.js, surface claire) :
 * luminosité et saturation dans la bande, séparation daltonisme ΔE ≥ 15,1,
 * séparation en vision normale ΔE ≥ 19,2. L'or et le bleu ciel ont un contraste
 * < 3:1 sur blanc : jamais de texte à leur couleur, et chaque graphique garde
 * sa légende, ses infobulles et un tableau de détail.
 *
 * Règles : couleurs attribuées dans l'ordre, jamais recyclées ; une même
 * catégorie (nature de frais, statut…) garde la même couleur dans tous les modules ;
 * les couleurs d'état (succès, attention, alerte) sont réservées aux états.
 */
import { useReducedMotion } from "framer-motion";

export const PALETTE = ["#1E4FA8", "#D89B16", "#3A9BD9", "#2E8B57", "#8E5BB5", "#C8553D"];
export const [BLEU, OR, CIEL, VERT, VIOLET, TERRE] = PALETTE;

/** États : jamais utilisés comme simple « série n° 4 ». */
export const ETAT = {
  succes: "#15803D", attention: "#B45309", alerte: "#B91C1C", info: "#1D4ED8", neutre: "#94A3B8", fond: "#E2E8F0",
};

/** Même couleur pour une nature de frais, partout (tableau de bord, situation, paiements). */
export const COULEUR_NATURE = {
  mensualite: BLEU, scolarite: BLEU, inscription: OR, reinscription: OR, cantine: VERT, transport: CIEL,
  garderie: VIOLET, examen: TERRE, dossier: TERRE, fournitures: TERRE, activites: TERRE, other: ETAT.neutre,
};
export const couleurNature = (code) => COULEUR_NATURE[code] || ETAT.neutre;

/** Même couleur pour un mode de paiement, partout. */
export const COULEUR_MODE = { cash: BLEU, mtn_momo: OR, moov_money: CIEL, card: VIOLET, bank_transfer: VERT, check: TERRE };
export const couleurMode = (code) => COULEUR_MODE[code] || ETAT.neutre;

/** Une seule animation : apparition et transitions, 700 ms, décélération douce. */
export const MOUVEMENT = { duree: 700, courbe: "ease-out" };
export function useAnimation() {
  const reduit = useReducedMotion();
  return { isAnimationActive: !reduit, animationDuration: MOUVEMENT.duree, animationEasing: MOUVEMENT.courbe };
}

/** Axes, grille : discrets, texte à l'encre secondaire. */
export const AXE = { fontSize: 11, fill: "#64748B" };
export const GRILLE = { strokeDasharray: "3 3", stroke: "#E2E8F0" };
export const LEGENDE = { wrapperStyle: { fontSize: 12 }, iconType: "circle", iconSize: 8 };
export const CURSEUR = { fill: "rgba(14,42,99,0.06)" };
