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

function exportCSV(rows, filename) {
  if (!rows.length) { toast.error("Aucune donnée à exporter."); return; }
  const headers = Object.keys(rows[0]);
  const lines = [headers.join(";"), ...rows.map(r => headers.map(h => `"${String(r[h] ?? "").replace(/"/g, '""')}"`).join(";"))];
  const blob = new Blob(["\uFEFF" + lines.join("\n")], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a"); a.href = url; a.download = filename;
  document.body.appendChild(a); a.click();
  document.body.removeChild(a); URL.revokeObjectURL(url);
}

export default function AdminPayments() {
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
  const currentYear = years.find(y => y.is_current);
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
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["payments"] }); toast.success("Paiement annulé."); setViewItem(null); },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const createMut = useMutation({
    mutationFn: paymentsAPI.create,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["payments"] }); qc.invalidateQueries({ queryKey: ["payments-summary"] }); toast.success("Paiement enregistré!"); closeModal(); },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const deleteMut = useMutation({
    mutationFn: paymentsAPI.delete,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["payments"] }); qc.invalidateQueries({ queryKey: ["payments-summary"] }); qc.invalidateQueries({ queryKey: ["payments-deleted"] });
      toast.success("Supprimé."); setDeleteItem(null); setViewItem(null);
    },
  });
  const receiptMut = useMutation({
    mutationFn: (id) => paymentsAPI.generateReceipt(id),
    onSuccess: (data) => {
      const url = data?.data?.receipt_url || data?.data?.receipt_file;
      if (url) { toast.success("Reçu généré !"); window.open(url, "_blank", "noopener,noreferrer"); }
      else toast.success("Reçu généré !");
      qc.invalidateQueries({ queryKey: ["payments"] });
    },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const restoreMut = useMutation({
    mutationFn: paymentsAPI.restore,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["payments"] }); qc.invalidateQueries({ queryKey: ["payments-summary"] }); qc.invalidateQueries({ queryKey: ["payments-deleted"] }); toast.success("Restauré !"); },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const bulkDeleteMut = useMutation({
    mutationFn: (ids) => paymentsAPI.bulkDelete(ids),
    onSuccess: (d) => { qc.invalidateQueries({ queryKey: ["payments"] }); qc.invalidateQueries({ queryKey: ["payments-summary"] }); toast.success(`${d?.data?.deleted || ""} élément(s) supprimé(s).`); },
    onError: (e) => toast.error(extractApiError(e)),
  });

  const closeModal = () => { setModalOpen(false); reset({ payment_date: new Date().toISOString().slice(0, 10), payment_method: "cash" }); };

  /* ── Excel Export ──────────────────────────────────────────────────────── */
  const exportPayments = () => {
    const rows = payments.map(p => ({
      "Référence":     p.reference_number || "",
      "Élève":         p.student_name || "",
      "Matricule":     p.student_matricule || "",
      "Classe":        p.student_class || "",
      "Type":          p.payment_type_label || p.payment_type || "",
      "Montant (FCFA)": Number(p.amount || 0).toFixed(0),
      "Mode":          p.payment_method_label || p.payment_method || "",
      "Date":          p.payment_date || "",
      "Reçu par":      p.received_by_name || "",
      "Statut":        p.is_confirmed ? "Confirmé" : "Annulé",
      "Année":         p.school_year_name || "",
      "Notes":         p.notes || "",
    }));
    const yearName = years.find(y => y.id === (filterYear || currentYear?.id))?.name || "toutes";
    exportCSV(rows, `paiements_${yearName}_${new Date().toISOString().slice(0, 10)}.csv`);
  };

  const cols = [
    { key: "ref",    label: "Référence",  accessor: "reference_number" },
    { key: "student",label: "Élève",      accessor: "student_name" },
    { key: "class",  label: "Classe",     accessor: "student_class" },
    { key: "type",   label: "Type",       accessor: "payment_type_label" },
    { key: "amount", label: "Montant",    render: r => <span className="font-bold text-success">{Number(r.amount).toLocaleString()} FCFA</span> },
    { key: "method", label: "Mode",       accessor: "payment_method_label" },
    { key: "date",   label: "Date",       accessor: "payment_date" },
    { key: "status", label: "Statut",     render: r => r.is_confirmed
      ? <span className="text-xs text-success font-medium bg-success/10 px-2 py-0.5 rounded-full">Confirmé</span>
      : <span className="text-xs text-danger font-medium bg-danger/10 px-2 py-0.5 rounded-full">Annulé</span> },
  ];

  return (
    <div className="space-y-6">
      <PageHeader title="Paiements" subtitle="Gestion des frais scolaires"
        action={
          <div className="flex gap-2 flex-wrap justify-end">
            <button onClick={exportPayments} className="btn-secondary flex items-center gap-2 text-sm">
              <FileSpreadsheet className="w-4 h-4" />Export Excel
            </button>
            <button onClick={() => setShowDeleted(true)}
              className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium bg-danger/10 text-danger hover:bg-danger/20 transition-all">
              <Eye className="w-4 h-4" />Voir supprimés
            </button>
            <button onClick={() => setModalOpen(true)} className="btn-primary flex items-center gap-2">
              <Plus className="w-4 h-4" />Nouveau paiement
            </button>
          </div>
        } />

      <div className="flex items-center gap-3">
        <label className="text-sm font-semibold text-slate-600">Année :</label>
        <select value={filterYear} onChange={e => setFilterYear(e.target.value)} className="input w-auto text-sm">
          <option value="">— Actuelle ({currentYear?.name || "—"}) —</option>
          {years.map(y => <option key={y.id} value={y.id}>{y.name}{y.is_current ? " ✓" : ""}</option>)}
        </select>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard title="Total encaissé"  value={`${Number(summary.total || 0).toLocaleString()} FCFA`}  icon={DollarSign} color="success" />
        <StatCard title="Inscriptions"    value={`${Number(summary.by_type?.inscription || 0).toLocaleString()} FCFA`} icon={TrendingUp} color="primary" />
        <StatCard title="Mensualités"     value={`${Number(summary.by_type?.mensualite  || 0).toLocaleString()} FCFA`} icon={TrendingUp} color="secondary" />
      </div>

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
              <button onClick={(e) => { e.stopPropagation(); receiptMut.mutate(row.id); }} title="Générer reçu"
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
              <h2 className="font-bold text-slate-800 text-lg">Détail du paiement</h2>
              <button onClick={() => setViewItem(null)} className="text-slate-400 hover:text-slate-600 text-2xl leading-none">×</button>
            </div>
            <div className="space-y-0 text-sm divide-y divide-slate-100">
              {[
                ["Référence", <span key="ref" className="font-bold text-slate-800">{viewItem.reference_number}</span>],
                ["Élève",     viewItem.student_name],
                ["Classe",    viewItem.student_class],
                ["Type",      viewItem.payment_type_label],
                ["Montant",   <span key="amount" className="font-bold text-success">{Number(viewItem.amount).toLocaleString()} FCFA</span>],
                ["Mode",      viewItem.payment_method_label],
                ["Date",      viewItem.payment_date],
                ["Reçu par",  viewItem.received_by_name],
                ["Statut",    <span key="status" className={viewItem.is_confirmed ? "text-success font-medium" : "text-danger font-medium"}>{viewItem.is_confirmed ? "Confirmé" : "Annulé"}</span>],
              ].map(([label, val]) => (
                <div key={label} className="flex justify-between py-2">
                  <span className="text-slate-500">{label}</span><span>{val}</span>
                </div>
              ))}
              {viewItem.notes && <div className="bg-slate-50 rounded-xl p-3 text-slate-600 text-xs py-2">{viewItem.notes}</div>}
            </div>
            {/* Historique */}
            {paymentHistory.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-slate-500 mb-2">Historique</p>
                <div className="space-y-1">
                  {paymentHistory.slice(0, 5).map((h, i) => (
                    <div key={i} className="text-xs bg-slate-50 rounded-lg px-3 py-1.5 flex justify-between">
                      <span className="text-slate-600">{h.action || h.changed_by_name}</span>
                      <span className="text-slate-400">{h.changed_at ? new Date(h.changed_at).toLocaleDateString("fr-FR") : ""}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            <div className="flex gap-2 pt-2">
              {viewItem.receipt_file && (
                <a href={viewItem.receipt_file} target="_blank" rel="noreferrer"
                  className="btn-secondary flex items-center gap-1 text-sm flex-1 justify-center">
                  <Receipt className="w-4 h-4" />Voir le reçu
                </a>
              )}
              {viewItem.is_confirmed && (
                <button onClick={() => {
                  const justification = prompt("Raison de l'annulation (obligatoire):");
                  if (justification) cancelMut.mutate({ id: viewItem.id, justification });
                }} className="btn-secondary text-danger border-danger text-sm flex-1">
                  Annuler
                </button>
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
              <h2 className="font-bold text-slate-800 text-lg">Paiements supprimés</h2>
              <button onClick={() => setShowDeleted(false)} className="text-slate-400 text-2xl leading-none">×</button>
            </div>
            {deletedLoading ? (
              <div className="text-center py-8 text-slate-400">Chargement…</div>
            ) : deletedPayments.length === 0 ? (
              <div className="text-center py-8 text-slate-400">Aucun paiement supprimé.</div>
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
                        <td className="px-3 py-2">{p.payment_type_label}</td>
                        <td className="px-3 py-2 font-bold text-slate-600">{Number(p.amount).toLocaleString()} FCFA</td>
                        <td className="px-3 py-2 text-slate-500">{p.payment_date}</td>
                        <td className="px-3 py-2">
                          <button onClick={() => restoreMut.mutate(p.id)}
                            className="flex items-center gap-1 text-xs text-success hover:underline">
                            <RotateCcw className="w-3 h-3" />Restaurer
                          </button>
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
      <Modal open={modalOpen} onClose={closeModal} title="Nouveau paiement" size="md">
        <form onSubmit={handleSubmit(d => createMut.mutate(d))} className="space-y-4">
          <div>
            <label className="label">Élève *</label>
            <Controller name="student" control={control} rules={{ required: true }}
              render={({ field }) => (
                <SearchableSelect options={studentOptions} value={field.value} onChange={field.onChange}
                  placeholder="Rechercher un élève…" />
              )} />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">Type *</label>
              <select {...register("payment_type", { required: true })} className="input">
                <option value="">— Choisir —</option>
                <option value="inscription">Inscription</option>
                <option value="mensualite">Mensualité</option>
                <option value="cantine">Cantine</option>
                <option value="transport">Transport</option>
                <option value="autre">Autre</option>
              </select>
            </div>
            <div>
              <label className="label">Mode *</label>
              <select {...register("payment_method")} className="input">
                <option value="cash">Espèces</option>
                <option value="mobile_money">Mobile Money</option>
                <option value="bank_transfer">Virement</option>
                <option value="check">Chèque</option>
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">Montant (FCFA) *</label>
              <input {...register("amount", { required: true, min: 1 })} type="number" className="input" placeholder="0" />
            </div>
            <div>
              <label className="label">Date *</label>
              <input {...register("payment_date", { required: true })} type="date" className="input" />
            </div>
          </div>
          <div>
            <label className="label">Mois concerné</label>
            <input {...register("month_concerned")} type="month" className="input" />
          </div>
          <div>
            <label className="label">Notes</label>
            <textarea {...register("notes")} className="input" rows={2} />
          </div>
          <div className="flex gap-3 justify-end pt-2">
            <button type="button" onClick={closeModal} className="btn-secondary">Annuler</button>
            <button type="submit" disabled={createMut.isPending} className="btn-primary">
              {createMut.isPending ? "Enregistrement…" : "Enregistrer"}
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
