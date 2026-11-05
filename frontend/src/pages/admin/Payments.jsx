import { useState } from "react";
import { NATURES_FRAIS } from "../../utils/naturesFrais";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Receipt, DollarSign, TrendingUp, Eye, RotateCcw } from "lucide-react";
import { Controller } from "react-hook-form";
import { useForm } from "../../utils/useFormulaire";
import toast from "react-hot-toast";
import { paymentsAPI, studentsAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import RecherchePaiements from "../../components/payments/RecherchePaiements";
import Modal from "../../components/ui/Modal";
import ConfirmDialog from "../../components/ui/ConfirmDialog";
import StatCard from "../../components/ui/StatCard";
import SearchableSelect from "../../components/ui/SearchableSelect";
import { extractApiError } from "../../utils/errors";
import { t } from "../../i18n";
import { useMoney } from "../../hooks/useMoney";
import { useAcademy } from "../../context/AcademyContext";
import {
  academyNowParts, formatDateTime, paymentDateTimeText,
} from "../../utils/datetime";
import { studentOptionLabel } from "../../utils/age";

export default function AdminPayments() {
  // P0 : la devise vient de l'académie, jamais d'un symbole codé en dur.
  const money = useMoney();
  const qc = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [deleteItem, setDeleteItem] = useState(null);
  const [showDeleted, setShowDeleted] = useState(false);
  const [viewItem, setViewItem] = useState(null);
  // Date et heure proposées par défaut : celles de l'ACADÉMIE active.
  // `new Date().toISOString().slice(0, 10)` donnait la date UTC — le
  // lendemain pour un encaissement saisi le soir à New York.
  const { activeAcademy } = useAcademy();
  const formDefaults = () => {
    const now = academyNowParts(activeAcademy?.timezone);
    return { payment_date: now.date, payment_time: now.time, payment_method: "cash" };
  };
  const { register, handleSubmit, reset, control } = useForm({ defaultValues: formDefaults() });

  // Recherche, filtres, tri et pagination : components/payments/RecherchePaiements
  // (calculés par le serveur). Incrémenté après chaque modification pour relire la liste.
  const [rafraichir, setRafraichir] = useState(0);
  const relire = () => setRafraichir((n) => n + 1);
  const { data: deletedData, isLoading: deletedLoading } = useQuery({
    queryKey: ["payments-deleted"],
    queryFn: () => paymentsAPI.listDeleted ? paymentsAPI.listDeleted() : paymentsAPI.list({ show_deleted: 1 }),
    enabled: showDeleted,
  });
  const { data: summaryData } = useQuery({ queryKey: ["payments-summary"], queryFn: paymentsAPI.summary });
  const { data: studData }    = useQuery({ queryKey: ["students-all"],     queryFn: () => studentsAPI.list() });
  const { data: historyData } = useQuery({
    queryKey: ["payment-history", viewItem?.id],
    queryFn: () => paymentsAPI.history(viewItem.id),
    enabled: !!viewItem?.id,
  });

  const deletedPayments = (deletedData?.data?.results || deletedData?.data || []).filter(p => p.is_deleted);
  const summary         = summaryData?.data || {};
  const students        = studData?.data?.results || studData?.data || [];
  const paymentHistory  = historyData?.data || [];
  const studentOptions  = students.map(s => ({ value: s.id, label: studentOptionLabel(s, { withMatricule: true }) }));

  const cancelMut = useMutation({
    mutationFn: ({ id, justification }) => paymentsAPI.cancel(id, justification),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["payments"] }); relire(); toast.success(t("Paiement annulé.")); setViewItem(null); },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const createMut = useMutation({
    mutationFn: paymentsAPI.create,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["payments"] }); relire(); qc.invalidateQueries({ queryKey: ["payments-summary"] }); toast.success(t("Paiement enregistré!")); closeModal(); },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const deleteMut = useMutation({
    mutationFn: paymentsAPI.delete,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["payments"] }); relire(); qc.invalidateQueries({ queryKey: ["payments-summary"] }); qc.invalidateQueries({ queryKey: ["payments-deleted"] });
      toast.success(t("Supprimé.")); setDeleteItem(null); setViewItem(null);
    },
  });
  const receiptMut = useMutation({
    mutationFn: (id) => paymentsAPI.generateReceipt(id),
    onSuccess: (data) => {
      const url = data?.data?.receipt_url || data?.data?.receipt_file;
      if (url) { toast.success(t("Reçu généré !")); window.open(url, "_blank", "noopener,noreferrer"); }
      else toast.success(t("Reçu généré !"));
      qc.invalidateQueries({ queryKey: ["payments"] }); relire();
    },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const restoreMut = useMutation({
    mutationFn: paymentsAPI.restore,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["payments"] }); relire(); qc.invalidateQueries({ queryKey: ["payments-summary"] }); qc.invalidateQueries({ queryKey: ["payments-deleted"] }); toast.success(t("Restauré !")); },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const bulkDeleteMut = useMutation({
    mutationFn: (ids) => paymentsAPI.bulkDelete(ids),
    onSuccess: (d) => { qc.invalidateQueries({ queryKey: ["payments"] }); relire(); qc.invalidateQueries({ queryKey: ["payments-summary"] }); toast.success(t("{n} élément(s) supprimé(s).", { n: d?.data?.deleted || "" })); },
    onError: (e) => toast.error(extractApiError(e)),
  });

  const closeModal = () => { setModalOpen(false); reset(formDefaults()); };
  const openModal = () => { reset(formDefaults()); setModalOpen(true); };

  return (
    <div className="space-y-6">
      <PageHeader title={t("Paiements")} subtitle={t("Gestion des frais scolaires")}
        action={
          <div className="flex gap-2 flex-wrap justify-end">
            <button onClick={() => setShowDeleted(true)}
              className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium bg-danger/10 text-danger hover:bg-danger/20 transition-all">
              <Eye className="w-4 h-4" />{t("Voir supprimés")}</button>
            <button onClick={openModal} className="btn-primary flex items-center gap-2">
              <Plus className="w-4 h-4" />{t("Nouveau paiement")}</button>
          </div>
        } />


      {/*
        P1 (juillet 2026) : ces montants viennent tels quels de
        `summary.consolidated_total.formatted` / `summary.by_type.*.formatted`
        — déjà convertis et formatés côté serveur. Le frontend n'additionne
        et ne convertit plus jamais de devises lui-même : c'était exactement
        la cause du bug (2 850 000 FCFA + 601,50 $ affiché « 2 850 601,5 »).
      */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard title={t("Total encaissé")}  value={summary.consolidated_total?.formatted ?? money.format(0)}  icon={DollarSign} color="success" />
        <StatCard title={t("Inscriptions")}    value={summary.by_type?.inscription?.formatted ?? money.format(0)} icon={TrendingUp} color="primary" />
        <StatCard title={t("Mensualités")}     value={summary.by_type?.mensualite?.formatted  ?? money.format(0)} icon={TrendingUp} color="secondary" />
      </div>

      {/* Détail par devise + taux utilisé — affiché uniquement quand le total
          ci-dessus consolide plusieurs devises (« Toutes les Académies »
          avec des académies en FCFA et d'autres en dollars, par exemple).
          Libellé par DEVISE : nommer une académie (« Équivalent FEBA FHA »)
          attribuait à une seule académie les dollars de toutes. */}
      {summary.is_consolidated && (summary.totals_by_currency?.length > 0 || summary.conversion_errors?.length > 0) && (
        <div className="card p-4 text-sm space-y-2 bg-slate-50/60 border border-slate-100">
          <div className="font-semibold text-slate-600">{t("Détail par devise")}</div>
          <div className="flex flex-wrap gap-x-6 gap-y-1 text-slate-700">
            {summary.totals_by_currency.map(row => (
              <span key={row.currency}>
                {t("Montants en {devise} :", { devise: row.currency })} <span className="font-semibold">{row.formatted}</span>
              </span>
            ))}
          </div>
          {summary.conversions?.length > 0 && (
            <div className="text-slate-500 text-xs">
              {summary.conversions.map((c, i) => (
                <div key={i}>
                  {t("Taux utilisé :")} {c.conversion.label}
                  {c.conversion.is_fallback && (
                    <span className="ml-1 text-warning">({t("taux par défaut, à confirmer")})</span>
                  )}
                </div>
              ))}
            </div>
          )}
          {summary.conversion_errors?.length > 0 && (
            <div className="text-danger text-xs">
              {t("Certains montants n'ont pas pu être convertis et sont exclus du total : ")}
              {summary.conversion_errors.join(" ")}
            </div>
          )}
        </div>
      )}

      <RecherchePaiements rafraichir={rafraichir} onOuvrir={setViewItem}
        onRecu={(p) => receiptMut.mutate(p.id)} onSupprimer={setDeleteItem}
        onSupprimerSelection={(ids, fini) => bulkDeleteMut.mutate(ids, { onSuccess: fini })} />

      {/* Payment detail modal */}
      {viewItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setViewItem(null)} />
          <div className="relative bg-white rounded-2xl shadow-2xl max-w-md w-full p-6 space-y-4 z-10 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between">
              <h2 className="font-bold text-slate-800 text-lg">{t("Détail du paiement")}</h2>
              <button onClick={() => setViewItem(null)} className="text-slate-400 hover:text-slate-600 text-2xl leading-none">×</button>
            </div>
            <div className="space-y-0 text-sm divide-y divide-slate-100">
              {[
                ["Référence", <span key="ref" className="font-bold text-slate-800">{viewItem.reference_number}</span>],
                ["Élève",     viewItem.student_name],
                ["Classe",    viewItem.student_class],
                ["Type",      t(viewItem.payment_type_label || "")],
                ["Montant",   <span key="amount" className="font-bold text-success">{money.amountOf(viewItem)}</span>],
                ["Mode",      t(viewItem.payment_method_label || "")],
                ["Date et heure", viewItem.has_time
                  ? paymentDateTimeText(viewItem)
                  : `${paymentDateTimeText(viewItem)} (${t("heure non enregistrée")})`],
                ["Reçu par",  viewItem.received_by_name],
                ["Statut",    <span key="status" className={viewItem.is_confirmed ? "text-success font-medium" : "text-danger font-medium"}>{viewItem.is_confirmed ? t("Confirmé") : t("Annulé")}</span>],
              ].map(([label, val]) => (
                <div key={label} className="flex justify-between py-2">
                  <span className="text-slate-500">{label}</span><span>{val}</span>
                </div>
              ))}
              {viewItem.notes && <div className="bg-slate-50 rounded-xl p-3 text-slate-600 text-xs py-2 text-longform">{viewItem.notes}</div>}
            </div>
            {/* Historique */}
            {paymentHistory.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-slate-500 mb-2">{t("Historique")}</p>
                <div className="space-y-1">
                  {/* L'API renvoie `performed_at` / `action_label` /
                      `performed_by_name` : l'écran lisait `changed_at`, qui
                      n'existe pas — la date de chaque action restait vide. */}
                  {paymentHistory.slice(0, 5).map((h) => (
                    <div key={h.id} className="text-xs bg-slate-50 rounded-lg px-3 py-1.5 flex justify-between gap-2">
                      <span className="text-slate-600">
                        {t(h.action_label || h.action || "")}
                        {h.performed_by_name ? ` - ${h.performed_by_name}` : ""}
                      </span>
                      <span className="text-slate-400 whitespace-nowrap">{formatDateTime(h.performed_at, viewItem.academy_timezone)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            <div className="flex gap-2 pt-2">
              {viewItem.receipt_file && (
                <a href={viewItem.receipt_file} target="_blank" rel="noreferrer"
                  className="btn-secondary flex items-center gap-1 text-sm flex-1 justify-center">
                  <Receipt className="w-4 h-4" />{t("Voir le reçu")}</a>
              )}
              {viewItem.is_confirmed && (
                <button onClick={() => {
                  const justification = prompt("Raison de l'annulation (obligatoire):");
                  if (justification) cancelMut.mutate({ id: viewItem.id, justification });
                }} className="btn-secondary text-danger border-danger text-sm flex-1">{t("Annuler")}</button>
              )}
              <button onClick={() => setDeleteItem(viewItem)}
                className="p-2 rounded-xl hover:bg-danger-50 text-slate-400 hover:text-danger">
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Deleted payments panel */}
      {showDeleted && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setShowDeleted(false)} />
          <div className="relative bg-white rounded-2xl shadow-2xl max-w-3xl w-full p-6 z-10 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-bold text-slate-800 text-lg">{t("Paiements supprimés")}</h2>
              <button onClick={() => setShowDeleted(false)} className="text-slate-400 text-2xl leading-none">×</button>
            </div>
            {deletedLoading ? (
              <div className="text-center py-8 text-slate-400">{t("Chargement…")}</div>
            ) : deletedPayments.length === 0 ? (
              <div className="text-center py-8 text-slate-400">{t("Aucun paiement supprimé.")}</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 border-b border-slate-100">
                    <tr>
                      {["Référence", "Élève", "Type", "Montant", "Date et heure", ""].map(h => (
                        <th key={h} className="px-3 py-2 text-left font-semibold text-slate-600">{h ? t(h) : ""}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-50">
                    {deletedPayments.map(p => (
                      <tr key={p.id} className="hover:bg-slate-50">
                        <td className="px-3 py-2 font-mono text-xs">{p.reference_number}</td>
                        <td className="px-3 py-2">{p.student_name}</td>
                        <td className="px-3 py-2">{t(p.payment_type_label)}</td>
                        <td className="px-3 py-2 font-bold text-slate-600">{money.amountOf(p)}</td>
                        <td className="px-3 py-2 text-slate-500 whitespace-nowrap">{paymentDateTimeText(p)}</td>
                        <td className="px-3 py-2">
                          <button onClick={() => restoreMut.mutate(p.id)}
                            className="flex items-center gap-1 text-xs text-success hover:underline">
                            <RotateCcw className="w-3 h-3" />{t("Restaurer")}</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Create modal */}
      <Modal open={modalOpen} onClose={closeModal} title={t("Nouveau paiement")} size="md">
        <form onSubmit={handleSubmit(d => createMut.mutate(d))} className="space-y-4">
          <div>
            <label className="label">{t("Élève *")}</label>
            <Controller name="student" control={control} rules={{ required: true }}
              render={({ field }) => (
                <SearchableSelect options={studentOptions} value={field.value} onChange={field.onChange}
                  placeholder={t("Rechercher un élève…")} />
              )} />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">{t("Type *")}</label>
              <select {...register("payment_type", { required: true })} className="input">
                <option value="">{t("Choisir")}</option>
                {NATURES_FRAIS.map(([valeur, libelle]) => <option key={valeur} value={valeur}>{t(libelle)}</option>)}
              </select>
            </div>
            <div>
              <label className="label">{t("Mode *")}</label>
              <select {...register("payment_method")} className="input">
                {/* Valeurs EXACTES du serveur : « mobile_money » n'existait
                    pas côté API et l'enregistrement échouait (erreur 400). */}
                <option value="cash">{t("Espèces")}</option>
                <option value="mtn_momo">MTN MoMo</option>
                <option value="moov_money">Moov Money</option>
                <option value="bank_transfer">{t("Virement")}</option>
                <option value="check">{t("Chèque")}</option>
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">{t("Montant")} {money.symbol ? `(${money.symbol})` : ""} *</label>
              <input {...register("amount", { required: true, min: 1 })} type="number" className="input" placeholder="0" />
            </div>
            <div>
              <label className="label">{t("Date *")}</label>
              <input {...register("payment_date", { required: true })} type="date" className="input" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">{t("Heure")}</label>
              <input {...register("payment_time")} type="time" className="input" />
              <p className="text-xs text-slate-400 mt-1">{t("Heure locale de l'académie. Laissez vide si elle n'est pas connue.")}</p>
            </div>
            <div>
              {/* Le champ s'appelait « month_concerned », inconnu du
                  serveur : la valeur saisie était perdue sans erreur. */}
              <label className="label">{t("Mois concerné")}</label>
              <input {...register("period_month")} type="month" className="input" />
            </div>
          </div>
          <div>
            <label className="label">{t("Notes")}</label>
            <textarea {...register("notes")} className="input" rows={2} />
          </div>
          <div className="flex gap-3 justify-end pt-2">
            <button type="button" onClick={closeModal} className="btn-secondary">{t("Annuler")}</button>
            <button type="submit" disabled={createMut.isPending} className="btn-primary">
              {createMut.isPending ? t("Enregistrement…") : t("Enregistrer")}
            </button>
          </div>
        </form>
      </Modal>

      <ConfirmDialog open={!!deleteItem} onClose={() => setDeleteItem(null)}
        onConfirm={() => deleteMut.mutate(deleteItem?.id)} loading={deleteMut.isPending}
        message={`Supprimer le paiement ${deleteItem?.reference_number} ?`} />
    </div>
  );
}
