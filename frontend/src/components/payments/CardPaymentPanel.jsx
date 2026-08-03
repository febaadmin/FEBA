/**
 * Paiement par carte — panneau du payeur.
 *
 * TROIS PARTIS PRIS
 * -----------------
 * 1. **Aucun montant saisi.** Le parent choisit un enfant et une ligne de
 *    la grille tarifaire publiée par l'académie. Le serveur relit ce tarif
 *    et ignore tout ce que le navigateur pourrait envoyer : un champ
 *    « montant » ici donnerait l'illusion d'un choix, et ouvrirait la
 *    porte à un paiement de 1 $ pour une facture de 1 250 $.
 *
 * 2. **Rien ne s'affiche si rien ne fonctionne.** Tant que le prestataire
 *    n'est pas configuré, le panneau explique la situation au lieu de
 *    montrer un bouton qui échouerait au clic.
 *
 * 3. **La redirection n'est pas une confirmation.** Au retour, le message
 *    dit que le paiement est en cours de vérification — pas qu'il est
 *    encaissé. Seul le webhook signé le déterminera, et la ligne
 *    apparaîtra alors dans l'historique.
 */
import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { AlertCircle, CreditCard, Loader2, ShieldCheck } from "lucide-react";
import { cardPaymentsAPI } from "../../api";
import { useAcademy } from "../../context/AcademyContext";
import { t } from "../../i18n";

export default function CardPaymentPanel({ students = [] }) {
  const { academyKey } = useAcademy();
  const [studentId, setStudentId] = useState(students[0]?.id ?? null);
  const [error, setError] = useState("");

  const selected = studentId ?? students[0]?.id ?? null;

  // La clé porte l'académie : basculer d'entité ne doit jamais laisser
  // apparaître la configuration ou les tarifs de la précédente.
  const { data: configData } = useQuery({
    queryKey: ["card-payment-config", academyKey],
    queryFn: cardPaymentsAPI.config,
  });
  const config = configData?.data;

  const { data: feesData, isLoading: feesLoading } = useQuery({
    queryKey: ["card-payment-fees", academyKey, selected],
    queryFn: () => cardPaymentsAPI.fees(selected),
    enabled: Boolean(config?.enabled && selected),
  });
  const fees = feesData?.data?.items || [];

  const checkout = useMutation({
    mutationFn: (paymentType) =>
      cardPaymentsAPI.checkout({ student: selected, payment_type: paymentType }),
    onSuccess: (response) => {
      const url = response?.data?.checkout_url;
      if (!url) {
        setError(t("Le prestataire n'a pas renvoyé de page de paiement."));
        return;
      }
      // Redirection vers le formulaire HÉBERGÉ : les données de carte ne
      // touchent ni ce navigateur-ci en tant qu'application, ni nos serveurs.
      window.location.assign(url);
    },
    onError: (err) => {
      setError(
        err?.response?.data?.detail ||
        t("Le paiement n'a pas pu être lancé. Réessayez dans un instant."),
      );
    },
  });

  if (!config) return null;

  if (!config.enabled) {
    return (
      <div className="card border border-amber-200 bg-amber-50/60">
        <div className="flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
          <div>
            <p className="font-medium text-slate-800">
              {t("Paiement par carte indisponible")}
            </p>
            <p className="text-sm text-slate-600 mt-1">
              {config.reason
                ? t(config.reason)
                : t("Cette académie n'a pas encore activé le paiement en ligne.")}
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="card space-y-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <CreditCard className="w-5 h-5 text-primary" />
          <h3 className="font-semibold text-slate-800">{t("Payer par carte")}</h3>
        </div>
        {config.mode === "test" && (
          // Ne jamais laisser croire qu'un paiement de test est réel.
          <span className="text-xs font-medium px-2 py-1 rounded-lg bg-slate-100 text-slate-600">
            {t("Mode test — aucune carte ne sera débitée")}
          </span>
        )}
      </div>

      {students.length > 1 && (
        <div>
          <label className="block text-xs text-slate-500 mb-1" htmlFor="card-payment-student">
            {t("Élève")}
          </label>
          <select
            id="card-payment-student"
            className="input"
            value={selected ?? ""}
            onChange={(e) => { setStudentId(Number(e.target.value)); setError(""); }}
          >
            {students.map((student) => (
              <option key={student.id} value={student.id}>
                {student.full_name || `${student.first_name} ${student.last_name}`}
              </option>
            ))}
          </select>
        </div>
      )}

      {feesLoading && (
        <p className="text-sm text-slate-500 flex items-center gap-2">
          <Loader2 className="w-4 h-4 animate-spin" />{t("Chargement des tarifs…")}
        </p>
      )}

      {!feesLoading && fees.length === 0 && (
        <p className="text-sm text-slate-600">
          {t("Aucun tarif n'est publié pour cet élève. Contactez le secrétariat.")}
        </p>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        {fees.map((fee) => (
          <button
            key={fee.payment_type}
            type="button"
            disabled={checkout.isPending}
            onClick={() => { setError(""); checkout.mutate(fee.payment_type); }}
            className="flex items-center justify-between gap-3 p-4 rounded-xl border border-slate-200
                       hover:border-primary hover:bg-primary/5 transition-colors text-left
                       disabled:opacity-60 disabled:cursor-not-allowed"
          >
            <span className="text-sm font-medium text-slate-700">{t(fee.label)}</span>
            {/* Le montant vient du serveur, déjà rendu dans sa devise :
                aucun symbole n'est reconstitué ici. */}
            <span className="font-bold text-primary whitespace-nowrap">
              {fee.amount_display}
            </span>
          </button>
        ))}
      </div>

      {checkout.isPending && (
        <p className="text-sm text-slate-500 flex items-center gap-2">
          <Loader2 className="w-4 h-4 animate-spin" />
          {t("Ouverture du formulaire sécurisé…")}
        </p>
      )}

      {error && (
        <p className="text-sm text-red-600 flex items-start gap-2">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />{error}
        </p>
      )}

      <p className="text-xs text-slate-500 flex items-start gap-2 pt-2 border-t border-slate-100">
        <ShieldCheck className="w-4 h-4 shrink-0 mt-0.5 text-slate-400" />
        {/* Chaîne d'un seul tenant : le dictionnaire indexe des littéraux,
            une concaténation ne serait jamais traduite. */}
        {t("Le paiement se déroule sur la page sécurisée du prestataire. Aucune donnée de votre carte n'est transmise à l'école ni conservée par elle.")}
      </p>
    </div>
  );
}
