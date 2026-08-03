/**
 * Transactions par carte — journal et remboursements.
 *
 * POURQUOI UN ÉCRAN SÉPARÉ DES PAIEMENTS
 * --------------------------------------
 * La page « Paiements » liste des ENCAISSEMENTS : de l'argent arrivé, sur
 * lequel la comptabilité s'appuie. Une tentative par carte, elle, peut
 * échouer, expirer ou rester en attente d'une authentification bancaire.
 * Les mélanger donnerait soit des recettes fantômes, soit un historique
 * où les échecs disparaissent — or c'est précisément l'échec qu'un parent
 * vient signaler quand il téléphone.
 *
 * Chaque ligne porte son académie et son montant dans SA devise : aucun
 * total agrégé ne mélange dollars et francs CFA.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CreditCard, RotateCcw } from "lucide-react";
import toast from "react-hot-toast";
import { cardPaymentsAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import DataTable from "../../components/ui/DataTable";
import Modal from "../../components/ui/Modal";
import { useAcademy } from "../../context/AcademyContext";
import { extractApiError } from "../../utils/errors";
import { t } from "../../i18n";

/** Couleur du statut. Un échec doit se voir sans lire le libellé. */
const STATUS_STYLES = {
  succeeded: "bg-green-50 text-green-700",
  partially_refunded: "bg-amber-50 text-amber-700",
  refunded: "bg-slate-100 text-slate-600",
  disputed: "bg-red-50 text-red-700",
  failed: "bg-red-50 text-red-700",
  cancelled: "bg-slate-100 text-slate-500",
  expired: "bg-slate-100 text-slate-500",
  action_required: "bg-amber-50 text-amber-700",
};

export default function AdminCardTransactions() {
  const qc = useQueryClient();
  const { academyKey, isAllAcademies } = useAcademy();
  const [refundItem, setRefundItem] = useState(null);
  const [refundAmount, setRefundAmount] = useState("");

  const { data, isLoading } = useQuery({
    // Clé portée par l'académie : basculer d'entité ne doit jamais laisser
    // les transactions de la précédente à l'écran.
    queryKey: ["card-transactions", academyKey],
    queryFn: () => cardPaymentsAPI.transactions(),
  });
  const rows = data?.data || [];

  const refund = useMutation({
    mutationFn: ({ id, amount }) => cardPaymentsAPI.refund(id, amount || null),
    onSuccess: (response) => {
      toast.success(t("Remboursement enregistré : {n}", {
        n: response?.data?.refunded_total || "",
      }));
      setRefundItem(null);
      setRefundAmount("");
      qc.invalidateQueries({ queryKey: ["card-transactions", academyKey] });
      qc.invalidateQueries({ queryKey: ["payments"] });
    },
    onError: (err) => toast.error(extractApiError(err)),
  });

  const cols = [
    {
      key: "academy", label: t("Académie"), sortable: false,
      render: r => (
        <span className="text-xs font-medium px-2 py-1 rounded-lg bg-slate-100 text-slate-700">
          {r.academy_code}
        </span>
      ),
    },
    { key: "student", label: t("Élève"), accessor: "student" },
    { key: "type", label: t("Type"), render: r => t(r.payment_type) },
    {
      key: "amount", label: t("Montant"),
      // Rendu par le serveur, dans la devise de l'académie : aucun symbole
      // n'est reconstitué côté navigateur.
      render: r => <span className="font-bold">{r.amount_display}</span>,
    },
    {
      key: "refunded", label: t("Remboursé"),
      render: r => r.refunded_display && !/^[^\d]*0([.,]0+)?/.test(r.refunded_display)
        ? <span className="text-amber-700">{r.refunded_display}</span>
        : <span className="text-slate-400">—</span>,
    },
    {
      key: "status", label: t("Statut"),
      render: r => (
        <span className={`text-xs font-medium px-2 py-1 rounded-lg ${
          STATUS_STYLES[r.status] || "bg-slate-100 text-slate-600"}`}>
          {t(r.status_display)}
        </span>
      ),
    },
    {
      key: "reference", label: t("Référence prestataire"), sortable: false,
      render: r => <code className="text-xs text-slate-500">{r.provider_reference}</code>,
    },
    {
      key: "actions", label: "", sortable: false,
      render: r => (
        ["succeeded", "partially_refunded"].includes(r.status)
          ? (
            <button
              type="button"
              onClick={() => { setRefundItem(r); setRefundAmount(""); }}
              className="flex items-center gap-1 text-xs text-primary hover:underline font-medium"
            >
              <RotateCcw className="w-3 h-3" />{t("Rembourser")}
            </button>
          )
          : <span className="text-xs text-slate-400">—</span>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("Transactions par carte")}
        subtitle={t("{n} tentative(s) — échecs et expirations compris", { n: rows.length })}
      />

      {isAllAcademies && (
        <div className="card border border-slate-200 flex items-start gap-3">
          <CreditCard className="w-5 h-5 text-slate-400 shrink-0 mt-0.5" />
          <p className="text-sm text-slate-600">
            {t("Vue consolidée : chaque ligne porte son académie et sa devise. Aucun total n'est agrégé, deux devises ne s'additionnant pas.")}
          </p>
        </div>
      )}

      <div className="card">
        <DataTable columns={cols} data={rows} loading={isLoading} />
      </div>

      <Modal
        open={Boolean(refundItem)}
        onClose={() => setRefundItem(null)}
        title={t("Rembourser une transaction")}
        size="sm"
      >
        {refundItem && (
          <div className="space-y-4">
            <div className="flex items-start gap-3 p-3 rounded-xl bg-amber-50 border border-amber-200">
              <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
              <p className="text-sm text-slate-700">
                {t("Le remboursement est transmis au prestataire et ne peut pas être annulé. Il apparaîtra sur le relevé du payeur sous quelques jours.")}
              </p>
            </div>

            <div className="text-sm text-slate-600 space-y-1">
              <p>{t("Élève")} : <strong>{refundItem.student}</strong></p>
              <p>{t("Encaissé")} : <strong>{refundItem.amount_display}</strong></p>
              <p>{t("Déjà remboursé")} : <strong>{refundItem.refunded_display}</strong></p>
            </div>

            <div>
              <label className="block text-xs text-slate-500 mb-1" htmlFor="refund-amount">
                {t("Montant à rembourser (vide = solde restant)")}
              </label>
              <input
                id="refund-amount"
                className="input"
                inputMode="decimal"
                value={refundAmount}
                onChange={(e) => setRefundAmount(e.target.value)}
                placeholder={refundItem.amount_display}
              />
              <p className="text-xs text-slate-500 mt-1">
                {t("Exprimé dans la devise de l'académie ({c}).",
                   { c: refundItem.currency })}
              </p>
            </div>

            <div className="flex justify-end gap-2">
              <button type="button" className="btn-secondary"
                      onClick={() => setRefundItem(null)}>
                {t("Annuler")}
              </button>
              <button
                type="button"
                className="btn-primary"
                disabled={refund.isPending}
                onClick={() => refund.mutate({ id: refundItem.id, amount: refundAmount.trim() })}
              >
                {refund.isPending ? t("Envoi…") : t("Confirmer le remboursement")}
              </button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
