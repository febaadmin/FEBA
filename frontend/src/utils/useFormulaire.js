import { useRef } from "react";
import { useForm as useFormBase } from "react-hook-form";
import toast from "react-hot-toast";
import { t } from "../i18n";

/**
 * useForm de react-hook-form, avec un message quand la validation bloque l'envoi.
 * Sans lui, « Enregistrer » ne faisait rien de visible si un champ obligatoire restait vide.
 */
const DOUBLE_CLIC_MS = 600;

export function useForm(options) {
  const methodes = useFormBase(options);
  const dernierEnvoi = useRef(0);
  const handleSubmit = (valide, invalide) => {
    const envoyer = methodes.handleSubmit(valide, (erreurs, evenement) => {
      const message = Object.values(erreurs).map((e) => e?.message).find((m) => typeof m === "string" && m);
      toast.error(message ? t(message) : t("Renseignez les champs obligatoires avant d'enregistrer."));
      return invalide?.(erreurs, evenement);
    });
    return (evenement) => {
      // Double clic : le second envoi est ignoré, sans aucun effet visible.
      const maintenant = Date.now();
      if (maintenant - dernierEnvoi.current < DOUBLE_CLIC_MS) {
        evenement?.preventDefault?.();
        return undefined;
      }
      dernierEnvoi.current = maintenant;
      return envoyer(evenement);
    };
  };
  return { ...methodes, handleSubmit };
}
