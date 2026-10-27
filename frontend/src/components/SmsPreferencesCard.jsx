/**
 * SmsPreferencesCard — consentement aux SMS, dans « Mon profil ».
 *
 * FEBA peut copier par SMS les e-mails et relances adressés à la personne.
 * Le choix est PERSONNEL et horodaté par le serveur. L'état du numéro est
 * affiché tel que les SMS l'utiliseront (format international) — ou la
 * raison pour laquelle il ne peut pas servir, à corriger ici même.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { MessageSquare } from "lucide-react";
import { authAPI } from "../api";
import { extractApiError } from "../utils/errors";
import { t } from "../i18n";

const PROBLEM = {
  no_phone: "Aucun numéro de téléphone n'est enregistré.",
  invalid_phone: "Le numéro enregistré n'est pas valide : saisissez-le avec l'indicatif du pays (ex. +229 01 …).",
  not_mobile: "Le numéro enregistré est une ligne fixe : il ne peut pas recevoir de SMS.",
};

export default function SmsPreferencesCard() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["me"], queryFn: authAPI.me });
  const user = data?.data;
  const mutation = useMutation({
    mutationFn: (value) => authAPI.updateMe({ sms_consent: value }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["me"] });
      toast.success(t("Préférence SMS enregistrée."));
    },
    onError: (e) => toast.error(extractApiError(e)),
  });
  if (!user) return null;
  const problem = user.sms_phone?.problem;
  return (
    <div className="card" data-testid="sms-preferences">
      <h3 className="font-semibold text-slate-800 flex items-center gap-2 mb-2">
        <MessageSquare className="w-4 h-4" />{t("Notifications par SMS")}
      </h3>
      <p className="text-sm text-slate-500 mb-3">
        {t("Recevoir aussi par SMS le texte des e-mails et des rappels de paiement que votre académie vous adresse.")}
      </p>
      <div className="flex flex-wrap gap-4 text-sm" role="radiogroup" aria-label={t("Notifications par SMS")}>
        {[["granted", t("J'accepte les SMS")], ["refused", t("Je refuse les SMS")]].map(([value, label]) => (
          <label key={value} className="flex items-center gap-2 text-slate-700">
            <input type="radio" name="sms_consent" value={value} checked={user.sms_consent === value}
                   disabled={mutation.isPending} onChange={() => mutation.mutate(value)} />
            {label}
          </label>
        ))}
      </div>
      {user.sms_consent === "unknown" && (
        <p className="text-xs text-amber-700 mt-2">{t("Aucun choix enregistré : aucun SMS ne vous est envoyé.")}</p>
      )}
      <p className="text-xs mt-2 text-slate-500">
        {problem
          ? <span className="text-red-600">{t(PROBLEM[problem] || problem)}</span>
          : <>{t("Numéro utilisé")} : <span className="font-mono">{user.sms_phone?.e164}</span></>}
      </p>
    </div>
  );
}
