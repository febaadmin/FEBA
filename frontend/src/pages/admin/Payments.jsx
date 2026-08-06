import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Receipt, DollarSign, TrendingUp, Eye, RotateCcw, FileSpreadsheet } from "lucide-react";
import { useForm, Controller } from "react-hook-form";
import toast from "react-hot-toast";
import { paymentsAPI, studentsAPI, schoolsAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import DataTable from "../../components/ui/DataTable";
import Modal from "../../components/ui/Modal";
import ConfirmDialog from "../../components/ui/ConfirmDialog";
import StatCard from "../../components/ui/StatCard";
import SearchableSelect from "../../components/ui/SearchableSelect";
import { extractApiError } from "../../utils/errors";
import { t, dateLocale } from "../../i18n";
import { useSchoolYearScope } from "../../hooks/useSchoolYearScope";
import { useMoney } from "../../hooks/useMoney";

function exportCSV(rows, filename) {
  if (!rows.length) { toast.error(t("Aucune donnée à exporter.")); return; }
  const headers = Object.keys(rows[0]);
  const lines = [headers.join(";"), ...rows.map(r => headers.map(h => `"${String(r[h] ?? "").replace(/"/g, '""')}"`).join(";"))];
  const blob = new Blob(["\uFEFF" + lines.join("\n")], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a"); a.href = url; a.download = filename;
  document.body.appendChild(a); a.click();
  document.body.removeChild(a); URL.revokeObjectURL(url);
}

export default function AdminPayments() {
  // P0 : la devise vient de l'académie, jamais d'un symbole codé en dur.
  const money = useMoney();
  const qc = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [deleteItem, setDeleteItem] = useState(null);
  const [showDeleted, setShowDeleted] = useState(false);
  const [viewItem, setViewItem] = useState(null);
  const { register, handleSubmit, reset, control } = useForm({
    defaultValues: { payment_date: new Date().toISOString().slice(0, 10), payment_method: "cash" }
  });

  const { data: yearsData } = useQuery({ queryKey: ["years"], queryFn: schoolsAPI.years });
  const years = yearsData?.data?.results || yearsData?.data || [];
  // P2 : en mode « Toutes les Académies », aucune année ne peut
  // représenter les deux académies — voir useSchoolYearScope.
  const { currentYear: currentYear, yearLabel } = useSchoolYearScope(years);
  const [filterYear, setFilterYear] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["payments", filterYear || currentYear?.id],
    queryFn: () => paymentsAPI.list({ school_year: filterYear || currentYear?.id }),
  });
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

  const payments        = data?.data?.results || data?.data || [];
  const deletedPayments = (deletedData?.data?.results || deletedData?.data || []).filter(p => p.is_deleted);
  const summary         = summaryData?.data || {};
  const students        = studData?.data?.results || studData?.data || [];
  const paymentHistory  = historyData?.data || [];
  const studentOptions  = students.map(s => ({ value: s.id, label: `${s.full_name} — ${s.matricule} (${s.class_name || "?"})` }));

  const cancelMut = useMutation({
    mutationFn: ({ id, justification }) => paymentsAPI.cancel(id, justification),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["payments"] }); toast.success(t("Paiement annulé.")); setViewItem(null); },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const createMut = useMutation({
    mutationFn: paymentsAPI.create,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["payments"] }); qc.invalidateQueries({ queryKey: ["payments-summary"] }); toast.success(t("Paiement enregistré!")); closeModal(); },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const deleteMut = useMutation({
    mutationFn: paymentsAPI.delete,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["payments"] }); qc.invalidateQueries({ queryKey: ["payments-summary"] }); qc.invalidateQueries({ queryKey: ["payments-deleted"] });
      toast.success(t("Supprimé.")); setDeleteItem(null); setViewItem(null);
    },
  });
  const receiptMut = useMutation({
    mutationFn: (id) => paymentsAPI.generateReceipt(id),
    onSuccess: (data) => {
      const url = data?.data?.receipt_url || data?.data?.receipt_file;
      if (url) { toast.success(t("Reçu généré !")); window.open(url, "_blank", "noopener,noreferrer"); }
      else toast.success(t("Reçu généré !"));
      qc.invalidateQueries({ queryKey: ["payments"] });
    },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const restoreMut = useMutation({
    mutationFn: paymentsAPI.restore,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["payments"] }); qc.invalidateQueries({ queryKey: ["payments-summary"] }); qc.invalidateQueries({ queryKey: ["payments-deleted"] }); toast.success(t("Restauré !")); },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const bulkDeleteMut = useMutation({
    mutationFn: (ids) => paymentsAPI.bulkDelete(ids),
    onSuccess: (d) => { qc.invalidateQueries({ queryKey: ["payments"] }); qc.invalidateQueries({ queryKey: ["payments-summary"] }); toast.success(t("{n} élément(s) supprimé(s).", { n: d?.data?.deleted || "" })); },
    onError: (e) => toast.error(extractApiError(e)),
  });

  const closeModal = () => { setModalOpen(false); reset({ payment_date: new Date().toISOString().slice(0, 10), payment_method: "cash" }); };

  /* ── Excel Export ──────────────────────────────────────────────────────── */
  const exportPayments = () => {
    const rows = payments.map(p => ({
      // P2 : sans cette colonne, un export consolidé mélange les recettes
      // des deux académies sans moyen de les séparer.
      "Académie":      p.academy_short_name || p.academy_name || "Sans académie",
      "Référence":     p.reference_number || "",
      "Élève":         p.student_name || "",
      "Matricule":     p.student_matricule || "",
      "Classe":        p.student_class || "",
      "Type":          p.payment_type_label || p.payment_type || "",
      "Montant": Number(p.amount || 0).toFixed(2),
      "Devise": p.currency || "",
      "Mode":          p.payment_method_label || p.payment_method || "",
      "Date":          p.payment_date || "",
      "Reçu par":      p.received_by_name || "",
      "Statut":        p.is_confirmed ? t("Confirmé") : t("Annulé"),
      "Année":         p.school_year_name || "",
      "Notes":         p.notes || "",
    }));
    const yearName = years.find(y => y.id === (filterYear || currentYear?.id))?.name || "toutes";
    exportCSV(rows, `paiements_${yearName}_${new Date().toISOString().slice(0, 10)}.csv`);
  };

  const cols = [
    { key: "ref",    label: t("Référence"),  accessor: "reference_number" },
    { key: "student",label: t("Élève"),      accessor: "student_name" },
    { key: "class",  label: t("Classe"),     accessor: "student_class" },
    { key: "type",   label: t("Type"),       render: r => t(r.payment_type_label || r.payment_type || "—") },
    { key: "amount", label: t("Montant"),    render: r => <span className="font-bold text-success">{money.amountOf(r)}</span> },
    { key: "method", label: t("Mode"),       render: r => t(r.payment_method_label || r.payment_method || "—") },
    { key: "date",   label: t("Date"),       accessor: "payment_date" },
    { key: "status", label: t("Statut"),     render: r => r.is_confirmed
      ? <span className="text-xs text-success font-medium bg-success/10 px-2 py-0.5 rounded-full">{t("Confirmé")}</span>
      : <span className="text-xs text-danger font-medium bg-danger/10 px-2 py-0.5 rounded-full">{t("Annulé")}</span> },
  ];

  return (
    <div className="space-y-6">
      <PageHeader title={t("Paiements")} subtitle={t("Gestion des frais scolaires")}
        action={
          <div className="flex gap-2 flex-wrap justify-end">
            <button onClick={exportPayments} className="btn-secondary flex items-center gap-2 text-sm">
              <FileSpreadsheet className="w-4 h-4" />{t("Export Excel")}</button>
            <button onClick={() => setShowDeleted(true)}
              className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium bg-danger/10 text-danger hover:bg-danger/20 transition-all">
              <Eye className="w-4 h-4" />{t("Voir supprimés")}</button>
            <button onClick={() => setModalOpen(true)} className="btn-primary flex items-center gap-2">
              <Plus className="w-4 h-4" />{t("Nouveau paiement")}</button>
          </div>
        } />

      <div className="flex items-center gap-3">
        <label className="text-sm font-semibold text-slate-600">{t("Année :")}</label>
        <select value={filterYear} onChange={e => setFilterYear(e.target.value)} className="input w-auto text-sm">
          <option value="">— {t("Actuelle")} ({currentYear?.name || "—"}) —</option>
          {years.map(y => <option key={y.id} value={y.id}>{yearLabel(y)}{y.is_current ? " ✓" : ""}</option>)}
        </select>
      </div>

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
          avec FEBA en FCFA et FEBA FHA en dollars, par exemple). */}
      {summary.is_consolidated && (summary.totals_by_currency?.length > 0 || summary.conversion_errors?.length > 0) && (
        <div className="card p-4 text-sm space-y-2 bg-slate-50/60 border border-slate-100">
          <div className="font-semibold text-slate-600">{t("Détail par devise")}</div>
          <div className="flex flex-wrap gap-x-6 gap-y-1 text-slate-700">
            {summary.totals_by_currency.map(row => (
              <span key={row.currency}>
                {row.currency === "USD"
                  ? t("Équivalent FEBA FHA :")
                  : t("FEBA :")} <span className="font-semibold">{row.formatted}</span>
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

      <div className="card overflow-x-auto">
        <DataTable
          columns={cols}
          data={payments}
          loading={isLoading}
          onRowClick={row => setViewItem(row)}
          selectable
          onBulkDelete={ids => bulkDeleteMut.mutate(ids)}
          bulkDeletePending={bulkDeleteMut.isPending}
          actions={row => (
            <div className="flex items-center gap-1 justify-end">
              <button onClick={(e) => { e.stopPropagation(); receiptMut.mutate(row.id); }} title={t("Générer reçu")}
                className="p-1.5 rounded-lg hover:bg-green-50 text-slate-400 hover:text-success">
                <Receipt className="w-4 h-4" />
              </button>
              <button onClick={(e) => { e.stopPropagation(); setDeleteItem(row); }}
                className="p-1.5 rounded-lg hover:bg-danger-50 text-slate-400 hover:text-danger">
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          )}
        />
      </div>

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
                ["Date",      viewItem.payment_date],
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
                  {paymentHistory.slice(0, 5).map((h, i) => (
                    <div key={i} className="text-xs bg-slate-50 rounded-lg px-3 py-1.5 flex justify-between">
                      <span className="text-slate-600">{h.action || h.changed_by_name}</span>
                      <span className="text-slate-400">{h.changed_at ? new Date(h.changed_at).toLocaleDateString(dateLocale()) : ""}</span>
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
                      {["Référence", "Élève", "Type", "Montant", "Date", ""].map(h => (
                        <th key={h} className="px-3 py-2 text-left font-semibold text-slate-600">{h}</th>
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
                        <td className="px-3 py-2 text-slate-500">{p.payment_date}</td>
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
                <option value="">— Choisir —</option>
                <option value="inscription">{t("Inscription")}</option>
                <option value="mensualite">{t("Mensualité")}</option>
                <option value="cantine">{t("Cantine")}</option>
                <option value="transport">{t("Transport")}</option>
                <option value="autre">{t("Autre")}</option>
              </select>
            </div>
            <div>
              <label className="label">{t("Mode *")}</label>
              <select {...register("payment_method")} className="input">
                <option value="cash">{t("Espèces")}</option>
                <option value="mobile_money">{t("Mobile Money")}</option>
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
          <div>
            <label className="label">{t("Mois concerné")}</label>
            <input {...register("month_concerned")} type="month" className="input" />
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
