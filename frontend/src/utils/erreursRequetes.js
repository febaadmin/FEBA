import toast from "react-hot-toast";
import { isCanceledError } from "../api/academyScope";
import { t } from "../i18n";

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
