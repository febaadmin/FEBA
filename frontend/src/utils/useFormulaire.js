import { useForm as useFormBase } from "react-hook-form";
import toast from "react-hot-toast";
import { t } from "../i18n";

/**
 * useForm de react-hook-form, avec un message quand la validation bloque l'envoi.
 * Sans lui, « Enregistrer » ne faisait rien de visible si un champ obligatoire restait vide.
 */
export function useForm(options) {
  const methodes = useFormBase(options);
  const handleSubmit = (valide, invalide) => methodes.handleSubmit(valide, (erreurs, evenement) => {
    const message = Object.values(erreurs).map((e) => e?.message).find((m) => typeof m === "string" && m);
    toast.error(message ? t(message) : t("Renseignez les champs obligatoires avant d'enregistrer."));
    return invalide?.(erreurs, evenement);
  });
  return { ...methodes, handleSubmit };
}
