import toast from "react-hot-toast";
import { isCanceledError } from "../api/academyScope";
import { t } from "../i18n";
import { extractApiError } from "./errors";

/**
 * Une lecture en panne ne doit pas passer pour une liste vide. Les droits et les 404 sont gérés par
 * les écrans ; les annulations ne sont pas des échecs. Un seul message, même si plusieurs tombent.
 */
export function signalerErreurLecture(erreur) {
  if (isCanceledError(erreur)) return false;
  const statut = erreur?.response?.status;
  // 503 : service volontairement indisponible (visioconférence, limite), expliqué par son écran.
  if ((statut && statut < 500) || statut === 503) return false;
  toast.error(t("Certaines données n'ont pas pu être chargées. Rechargez la page."), { id: "erreur-lecture" });
  return true;
}

/**
 * Une écriture refusée ne doit jamais rester silencieuse. Les écrans qui gèrent
 * eux-mêmes l'erreur (onError) gardent leur message ; pour les autres (63
 * mutations à l'audit du 04/11 : modifier, supprimer, activer…), le motif
 * renvoyé par le serveur est affiché. Les annulations ne sont pas des échecs.
 */
export function signalerErreurEcriture(erreur, _variables, _contexte, mutation) {
  // Erreur affichée par l'écran : onError de la mutation, ou appelant qui le déclare (meta.erreurGeree).
  if (mutation?.options?.onError || mutation?.meta?.erreurGeree) return false;
  if (isCanceledError(erreur)) return false;
  toast.error(extractApiError(erreur));
  return true;
}
