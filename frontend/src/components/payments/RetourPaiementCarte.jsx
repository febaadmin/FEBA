/**
 * Retour depuis la page de paiement du prestataire.
 *
 * L'adresse de retour est devinable : elle ne prouve rien. L'écran demande au
 * serveur de VÉRIFIER (le serveur interroge le prestataire) et affiche l'état
 * obtenu ; il relance la vérification quelques fois tant que le paiement est en
 * cours de traitement, puis invite à revenir plus tard (le rapprochement
 * automatique et le webhook signé prennent le relais).
 */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Clock, Info, XCircle } from "lucide-react";
import { cardPaymentsAPI } from "../../api";
import { t } from "../../i18n";

const OUVERTS = ["created", "pending", "action_required", "processing"];
const ESSAIS = 8;

export default function RetourPaiementCarte({ transactionId }) {
  const qc = useQueryClient();
  const { data, isError, dataUpdateCount } = useQuery({
    queryKey: ["paiement-carte-verification", transactionId],
    queryFn: async () => {
      const rep = await cardPaymentsAPI.verifier(transactionId);
      if (!OUVERTS.includes(rep.data.status)) {
        qc.invalidateQueries({ queryKey: ["parent-payments"] });
      }
      return rep.data;
    },
    enabled: Boolean(transactionId),
    staleTime: 0,
    retry: false,
    refetchInterval: (q) => (OUVERTS.includes(q.state.data?.status) && q.state.dataUpdateCount < ESSAIS ? 4000 : false),
  });
  if (!transactionId) return null;
  const statut = data?.status;
  const [Icone, ton, titre, texte] = isError
    ? [Info, "border-slate-200", t("Vérification impossible pour le moment"), t("Le paiement sera vérifié automatiquement auprès du prestataire. Revenez sur cette page dans quelques minutes.")]
    : !data || OUVERTS.includes(statut)
      ? [Clock, "border-primary-200 bg-blue-50/60", t("Paiement en cours de vérification"),
        dataUpdateCount >= ESSAIS
          ? t("Le prestataire n'a pas encore confirmé. La vérification continue automatiquement : le paiement apparaîtra ci-dessous dès sa confirmation.")
          : t("FEBA interroge le prestataire de paiement…")]
      : statut === "succeeded"
        ? [CheckCircle2, "border-emerald-200 bg-emerald-50/60", t("Paiement confirmé"), t("Le paiement de {m} est enregistré ; le reçu est disponible dans la liste ci-dessous.", { m: data.amount_display })]
        : [XCircle, "border-red-200 bg-red-50/60", statut === "cancelled" ? t("Paiement abandonné") : statut === "expired" ? t("Paiement expiré") : t("Paiement non abouti"),
          `${data.reason ? `${t(data.reason)} ` : ""}${t("Rien n'a été encaissé ; vous pouvez recommencer.")}`];
  return (
    <div className={`card border flex items-start gap-3 ${ton}`} role="status" data-testid="retour-paiement" data-statut={statut || "verification"}>
      <Icone className="w-5 h-5 shrink-0 mt-0.5 text-slate-600" aria-hidden="true" />
      <div>
        <p className="font-medium text-slate-800">{titre}</p>
        <p className="text-sm text-slate-600 mt-1">{texte}</p>
      </div>
    </div>
  );
}
